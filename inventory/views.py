"""
Inventory API Views with optimized queries.

Implements:
- CRUD operations for Category, Product, Store, Inventory
- Product search with keyword and filter support
- Autocomplete with rate limiting
"""
from django.db.models import Q
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response

from core.rate_limiting import rate_limit
from .models import Category, Product, Store, Inventory
from .serializers import (
    CategorySerializer,
    ProductSerializer,
    ProductSearchSerializer,
    ProductMinimalSerializer,
    StoreSerializer,
    InventorySerializer,
    InventoryListSerializer,
)


# =============================================================================
# Category Views
# =============================================================================

class CategoryListCreateView(generics.ListCreateAPIView):
    """
    GET: List all categories
    POST: Create a new category
    """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class CategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET: Retrieve a category
    PUT/PATCH: Update a category
    DELETE: Delete a category
    """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


# =============================================================================
# Product Views
# =============================================================================

class ProductListCreateView(generics.ListCreateAPIView):
    """
    GET: List all products with category info
    POST: Create a new product
    
    Uses select_related to eliminate N+1 queries.
    """
    serializer_class = ProductSerializer

    def get_queryset(self):
        return Product.objects.select_related('category').filter(is_active=True)


class ProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET: Retrieve a product
    PUT/PATCH: Update a product
    DELETE: Delete a product
    """
    serializer_class = ProductSerializer

    def get_queryset(self):
        return Product.objects.select_related('category')


class ProductSearchView(generics.ListAPIView):
    """
    GET: Search products with keyword and filters.
    
    Query Parameters:
        - q: Keyword to search in title, description, and category name
        - min_price: Minimum price filter
        - max_price: Maximum price filter
        - store_id: Filter products available in specific store
        - category_id: Filter by category ID
    
    Uses select_related for optimized queries.
    """
    serializer_class = ProductSearchSerializer

    def get_queryset(self):
        queryset = Product.objects.select_related('category').filter(is_active=True)

        # Keyword search across title, description, and category
        keyword = self.request.query_params.get('q', '').strip()
        if keyword:
            queryset = queryset.filter(
                Q(title__icontains=keyword) |
                Q(description__icontains=keyword) |
                Q(category__name__icontains=keyword)
            )

        # Category filter
        category_id = self.request.query_params.get('category_id')
        if category_id:
            queryset = queryset.filter(category_id=category_id)

        # Price range filters
        min_price = self.request.query_params.get('min_price')
        if min_price:
            try:
                queryset = queryset.filter(price__gte=float(min_price))
            except ValueError:
                pass

        max_price = self.request.query_params.get('max_price')
        if max_price:
            try:
                queryset = queryset.filter(price__lte=float(max_price))
            except ValueError:
                pass

        # Store availability filter
        store_id = self.request.query_params.get('store_id')
        if store_id:
            queryset = queryset.filter(
                inventories__store_id=store_id,
                inventories__quantity__gt=0
            ).distinct()

        return queryset.order_by('title')


class ProductAutocompleteView(APIView):
    """
    GET: Fast prefix-matching autocomplete for product titles.
    
    Query Parameters:
        - q: Search query (minimum 3 characters)
    
    Returns top 10 matching products.
    Rate limited to 20 requests per minute.
    """
    
    @rate_limit(max_requests=20, window_seconds=60)
    def get(self, request):
        query = request.query_params.get('q', '').strip()
        
        # Require minimum 3 characters
        if len(query) < 3:
            return Response(
                {'error': 'Query must be at least 3 characters'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Fast prefix matching with limit
        products = Product.objects.filter(
            title__istartswith=query,
            is_active=True
        ).values('id', 'title', 'price')[:10]
        
        return Response(list(products))


# =============================================================================
# Store Views
# =============================================================================

class StoreListCreateView(generics.ListCreateAPIView):
    """
    GET: List all stores
    POST: Create a new store
    """
    queryset = Store.objects.filter(is_active=True)
    serializer_class = StoreSerializer


class StoreDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET: Retrieve a store
    PUT/PATCH: Update a store
    DELETE: Delete a store
    """
    queryset = Store.objects.all()
    serializer_class = StoreSerializer


# =============================================================================
# Inventory Views
# =============================================================================

class InventoryListCreateView(generics.ListCreateAPIView):
    """
    GET: List all inventory records with store and product info
    POST: Create a new inventory record
    
    Query Parameters:
        - store_id: Filter by store
        - product_id: Filter by product
        - low_stock: Show only low stock items (true/false)
    
    Uses select_related to eliminate N+1 queries.
    """
    
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return InventoryListSerializer
        return InventorySerializer

    def get_queryset(self):
        queryset = Inventory.objects.select_related(
            'store', 'product', 'product__category'
        )

        # Store filter
        store_id = self.request.query_params.get('store_id')
        if store_id:
            queryset = queryset.filter(store_id=store_id)

        # Product filter
        product_id = self.request.query_params.get('product_id')
        if product_id:
            queryset = queryset.filter(product_id=product_id)

        # Low stock filter
        low_stock = self.request.query_params.get('low_stock', '').lower()
        if low_stock == 'true':
            from django.db.models import F
            queryset = queryset.filter(quantity__lte=F('low_stock_threshold'))

        return queryset.order_by('store__name', 'product__title')


class InventoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET: Retrieve an inventory record
    PUT/PATCH: Update an inventory record
    DELETE: Delete an inventory record
    """
    serializer_class = InventorySerializer

    def get_queryset(self):
        return Inventory.objects.select_related('store', 'product')
