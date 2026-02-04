"""
Serializers for order models.
"""
from rest_framework import serializers
from .models import Order, OrderItem
from inventory.serializers import ProductMinimalSerializer, StoreMinimalSerializer


class OrderItemSerializer(serializers.ModelSerializer):
    """Serializer for OrderItem with product details."""
    product = ProductMinimalSerializer(read_only=True)
    subtotal = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True
    )

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'quantity', 'unit_price', 'subtotal']


class OrderItemCreateSerializer(serializers.Serializer):
    """Serializer for creating order items in order creation request."""
    product_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1)


class OrderSerializer(serializers.ModelSerializer):
    """
    Serializer for Order model with nested items.
    Uses prefetch_related for optimized queries.
    """
    store = StoreMinimalSerializer(read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)
    item_count = serializers.IntegerField(read_only=True)
    is_confirmed = serializers.BooleanField(read_only=True)
    is_rejected = serializers.BooleanField(read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'store', 'status', 'total_amount',
            'rejection_reason', 'items', 'item_count',
            'is_confirmed', 'is_rejected',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'status', 'total_amount', 'rejection_reason', 'created_at', 'updated_at']


class OrderListSerializer(serializers.ModelSerializer):
    """
    Optimized serializer for listing orders.
    Uses select_related for store data.
    """
    store_name = serializers.CharField(source='store.name', read_only=True)
    store_location = serializers.CharField(source='store.location', read_only=True)
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'store_name', 'store_location', 'status',
            'total_amount', 'item_count', 'created_at'
        ]

    def get_item_count(self, obj):
        # Use prefetched items count if available
        if hasattr(obj, '_prefetched_objects_cache') and 'items' in obj._prefetched_objects_cache:
            return len(obj.items.all())
        return obj.items.count()


class OrderCreateSerializer(serializers.Serializer):
    """
    Serializer for creating orders via POST /orders/
    
    Request format:
    {
        "store_id": 1,
        "items": [
            {"product_id": 1, "quantity": 2},
            {"product_id": 3, "quantity": 1}
        ]
    }
    """
    store_id = serializers.IntegerField(min_value=1)
    items = OrderItemCreateSerializer(many=True)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("At least one item is required")
        
        # Check for duplicate products
        product_ids = [item['product_id'] for item in value]
        if len(product_ids) != len(set(product_ids)):
            raise serializers.ValidationError("Duplicate products in order items")
        
        return value


class OrderResponseSerializer(serializers.ModelSerializer):
    """
    Serializer for order creation response.
    Includes complete order details.
    """
    store = StoreMinimalSerializer(read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'store', 'status', 'total_amount',
            'rejection_reason', 'items', 'created_at'
        ]
