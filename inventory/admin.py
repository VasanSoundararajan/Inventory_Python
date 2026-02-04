"""
Django Admin configuration for inventory models.
"""
from django.contrib import admin
from .models import Category, Product, Store, Inventory


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'product_count', 'created_at']
    search_fields = ['name']
    ordering = ['name']

    def product_count(self, obj):
        return obj.products.count()
    product_count.short_description = 'Products'


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'price', 'category', 'is_active', 'created_at']
    list_filter = ['category', 'is_active', 'created_at']
    search_fields = ['title', 'description']
    ordering = ['title']
    raw_id_fields = ['category']


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'location', 'is_active', 'inventory_count', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'location']
    ordering = ['name']

    def inventory_count(self, obj):
        return obj.inventories.count()
    inventory_count.short_description = 'Inventory Items'


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'store', 'product', 'quantity', 'is_low_stock', 'updated_at']
    list_filter = ['store', 'updated_at']
    search_fields = ['product__title', 'store__name']
    ordering = ['store', 'product']
    raw_id_fields = ['store', 'product']

    def is_low_stock(self, obj):
        return obj.is_low_stock
    is_low_stock.boolean = True
    is_low_stock.short_description = 'Low Stock'
