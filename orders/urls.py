"""
URL routing for order API endpoints.
"""
from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    path('orders/', views.OrderListCreateView.as_view(), name='order-list'),
    path('orders/<int:pk>/', views.OrderDetailView.as_view(), name='order-detail'),
    path('orders/stats/', views.OrderStatsView.as_view(), name='order-stats'),
]
