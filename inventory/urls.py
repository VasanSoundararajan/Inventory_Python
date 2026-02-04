"""
URL routing for inventory API endpoints.
"""
from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    # Categories
    path('categories/', views.CategoryListCreateView.as_view(), name='category-list'),
    path('categories/<int:pk>/', views.CategoryDetailView.as_view(), name='category-detail'),
    
    # Products
    path('products/', views.ProductListCreateView.as_view(), name='product-list'),
    path('products/<int:pk>/', views.ProductDetailView.as_view(), name='product-detail'),
    path('products/search/', views.ProductSearchView.as_view(), name='product-search'),
    path('products/autocomplete/', views.ProductAutocompleteView.as_view(), name='product-autocomplete'),
    
    # Stores
    path('stores/', views.StoreListCreateView.as_view(), name='store-list'),
    path('stores/<int:pk>/', views.StoreDetailView.as_view(), name='store-detail'),
    
    # Inventory
    path('inventory/', views.InventoryListCreateView.as_view(), name='inventory-list'),
    path('inventory/<int:pk>/', views.InventoryDetailView.as_view(), name='inventory-detail'),
]
