"""
Order API Views.

Implements:
- GET /orders/ - List orders with optimized queries
- POST /orders/ - Create order with atomic transaction
- GET /orders/{id}/ - Order detail with items
"""
import logging
from django.db import models
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Order
from .serializers import (
    OrderSerializer,
    OrderListSerializer,
    OrderCreateSerializer,
    OrderResponseSerializer,
)
from .services import create_order, OrderValidationError

logger = logging.getLogger(__name__)


class OrderListCreateView(generics.ListCreateAPIView):
    """
    GET: List all orders with optimized queries
    POST: Create a new order with atomic transaction handling
    
    Query Parameters (GET):
        - store_id: Filter by store
        - status: Filter by status (PENDING, CONFIRMED, REJECTED)
    
    Request Body (POST):
    {
        "store_id": 1,
        "items": [
            {"product_id": 1, "quantity": 2},
            {"product_id": 3, "quantity": 1}
        ]
    }
    """
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return OrderCreateSerializer
        return OrderListSerializer

    def get_queryset(self):
        queryset = Order.objects.select_related('store').prefetch_related(
            'items__product'
        )
        
        # Filter by store
        store_id = self.request.query_params.get('store_id')
        if store_id:
            queryset = queryset.filter(store_id=store_id)
        
        # Filter by status
        status_filter = self.request.query_params.get('status', '').upper()
        if status_filter in ['PENDING', 'CONFIRMED', 'REJECTED']:
            queryset = queryset.filter(status=status_filter)
        
        return queryset.order_by('-created_at')

    def create(self, request, *args, **kwargs):
        """
        Create order with atomic transaction handling.
        
        Returns:
            - 201: Order created (CONFIRMED or REJECTED)
            - 400: Validation error
            - 404: Store or products not found
        """
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        store_id = serializer.validated_data['store_id']
        items = serializer.validated_data['items']
        
        try:
            order, error = create_order(store_id, items)
            
            # Fetch fresh order with all relations
            order = Order.objects.select_related('store').prefetch_related(
                'items__product'
            ).get(id=order.id)
            
            response_serializer = OrderResponseSerializer(order)
            
            # Use 201 for confirmed, 200 for rejected (order was created but rejected)
            status_code = status.HTTP_201_CREATED if order.is_confirmed else status.HTTP_200_OK
            
            return Response(response_serializer.data, status=status_code)
            
        except OrderValidationError as e:
            logger.warning(f"Order validation failed: {e}")
            return Response(
                {'error': 'Validation Error', 'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.exception(f"Unexpected error creating order: {e}")
            return Response(
                {'error': 'Server Error', 'detail': 'An unexpected error occurred'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class OrderDetailView(generics.RetrieveAPIView):
    """
    GET: Retrieve order details with all items.
    
    Uses prefetch_related for optimized item loading.
    """
    serializer_class = OrderSerializer

    def get_queryset(self):
        return Order.objects.select_related('store').prefetch_related(
            'items__product__category'
        )


class OrderStatsView(APIView):
    """
    GET: Get order statistics for a store or overall.
    
    Query Parameters:
        - store_id: Filter stats by store (optional)
    """
    
    def get(self, request):
        from django.db.models import Sum, Count, Avg
        
        queryset = Order.objects.all()
        
        store_id = request.query_params.get('store_id')
        if store_id:
            queryset = queryset.filter(store_id=store_id)
        
        stats = queryset.aggregate(
            total_orders=Count('id'),
            confirmed_orders=Count('id', filter=models.Q(status=Order.Status.CONFIRMED)),
            rejected_orders=Count('id', filter=models.Q(status=Order.Status.REJECTED)),
            pending_orders=Count('id', filter=models.Q(status=Order.Status.PENDING)),
            total_revenue=Sum('total_amount', filter=models.Q(status=Order.Status.CONFIRMED)),
            avg_order_value=Avg('total_amount', filter=models.Q(status=Order.Status.CONFIRMED))
        )
        
        # Handle None values
        stats['total_revenue'] = str(stats['total_revenue'] or '0.00')
        stats['avg_order_value'] = str(round(stats['avg_order_value'] or 0, 2))
        
        return Response(stats)
