"""
URL configuration for Inventory & Order Management System.
"""
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse


def health_check(request):
    """Health check endpoint for container orchestration."""
    return JsonResponse({'status': 'healthy', 'service': 'inventory-api'})


urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', health_check, name='health-check'),
    path('api/', include('inventory.urls')),
    path('api/', include('orders.urls')),
]
