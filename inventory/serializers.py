"""
Serializers for inventory models.
Provides data validation and JSON conversion for API endpoints.
"""
from rest_framework import serializers
from .models import Category, Product, Store, Inventory


class CategorySerializer(serializers.ModelSerializer):
    """Serializer for Category model."""
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'product_count', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_product_count(self, obj):
        """Get count of products in this category."""
        return obj.products.count()


class CategoryMinimalSerializer(serializers.ModelSerializer):
    """Minimal serializer for nested category representation."""
    class Meta:
        model = Category
        fields = ['id', 'name']


class ProductSerializer(serializers.ModelSerializer):
    """Serializer for Product model with nested category."""
    category = CategoryMinimalSerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        source='category',
        write_only=True
    )

    class Meta:
        model = Product
        fields = [
            'id', 'title', 'description', 'price',
            'category', 'category_id', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProductMinimalSerializer(serializers.ModelSerializer):
    """Minimal serializer for autocomplete and nested representations."""
    class Meta:
        model = Product
        fields = ['id', 'title', 'price']


class ProductSearchSerializer(serializers.ModelSerializer):
    """Serializer for product search results with category info."""
    category = CategoryMinimalSerializer(read_only=True)

    class Meta:
        model = Product
        fields = ['id', 'title', 'description', 'price', 'category', 'is_active']


class StoreSerializer(serializers.ModelSerializer):
    """Serializer for Store model."""
    inventory_count = serializers.SerializerMethodField()

    class Meta:
        model = Store
        fields = ['id', 'name', 'location', 'is_active', 'inventory_count', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_inventory_count(self, obj):
        """Get count of inventory items in this store."""
        return obj.inventories.count()


class StoreMinimalSerializer(serializers.ModelSerializer):
    """Minimal serializer for nested store representation."""
    class Meta:
        model = Store
        fields = ['id', 'name', 'location']


class InventorySerializer(serializers.ModelSerializer):
    """
    Serializer for Inventory model with nested store and product.
    Uses select_related optimization in view.
    """
    store = StoreMinimalSerializer(read_only=True)
    product = ProductMinimalSerializer(read_only=True)
    store_id = serializers.PrimaryKeyRelatedField(
        queryset=Store.objects.all(),
        source='store',
        write_only=True
    )
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source='product',
        write_only=True
    )
    is_low_stock = serializers.BooleanField(read_only=True)
    is_out_of_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Inventory
        fields = [
            'id', 'store', 'store_id', 'product', 'product_id',
            'quantity', 'low_stock_threshold',
            'is_low_stock', 'is_out_of_stock',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        """Validate unique constraint on create."""
        if self.instance is None:  # Creating new inventory
            store = attrs.get('store')
            product = attrs.get('product')
            if Inventory.objects.filter(store=store, product=product).exists():
                raise serializers.ValidationError(
                    "Inventory for this store and product combination already exists."
                )
        return attrs


class InventoryListSerializer(serializers.ModelSerializer):
    """
    Optimized serializer for listing inventory with all related data.
    Uses select_related('store', 'product__category') in view.
    """
    store_name = serializers.CharField(source='store.name', read_only=True)
    store_location = serializers.CharField(source='store.location', read_only=True)
    product_title = serializers.CharField(source='product.title', read_only=True)
    product_price = serializers.DecimalField(
        source='product.price',
        max_digits=10,
        decimal_places=2,
        read_only=True
    )
    category_name = serializers.CharField(source='product.category.name', read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Inventory
        fields = [
            'id', 'store_name', 'store_location',
            'product_title', 'product_price', 'category_name',
            'quantity', 'is_low_stock', 'updated_at'
        ]
