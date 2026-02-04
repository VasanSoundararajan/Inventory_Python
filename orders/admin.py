"""
Django Admin configuration for order models.
"""
from django.contrib import admin
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['product', 'quantity', 'unit_price', 'subtotal']
    can_delete = False
    
    def subtotal(self, obj):
        return f"${obj.subtotal}"
    subtotal.short_description = 'Subtotal'


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'store', 'status', 'total_amount', 'item_count', 'created_at']
    list_filter = ['status', 'store', 'created_at']
    search_fields = ['id', 'store__name']
    ordering = ['-created_at']
    readonly_fields = ['status', 'total_amount', 'rejection_reason', 'created_at', 'updated_at']
    inlines = [OrderItemInline]

    def item_count(self, obj):
        return obj.items.count()
    item_count.short_description = 'Items'


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'product', 'quantity', 'unit_price', 'subtotal']
    list_filter = ['order__status', 'created_at']
    search_fields = ['product__title', 'order__id']
    ordering = ['-created_at']
    raw_id_fields = ['order', 'product']

    def subtotal(self, obj):
        return f"${obj.subtotal}"
    subtotal.short_description = 'Subtotal'
