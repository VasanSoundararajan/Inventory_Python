"""
Inventory Models - Core data entities for the inventory management system.

Models:
    - Category: Product categorization
    - Product: Items available for sale
    - Store: Physical or virtual store locations
    - Inventory: Stock levels linking stores and products (unique constraint)
"""
from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal


class Category(models.Model):
    """
    Product category for organizing products.
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Unique category name"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    """
    Product entity representing items available for sale.
    """
    title = models.CharField(
        max_length=200,
        db_index=True,
        help_text="Product title for display and search"
    )
    description = models.TextField(
        blank=True,
        default='',
        help_text="Optional product description"
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Product price (must be positive)"
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='products',
        help_text="Product category"
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether product is available for ordering"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Product'
        verbose_name_plural = 'Products'
        ordering = ['title']
        indexes = [
            models.Index(fields=['title', 'is_active']),
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['price']),
        ]

    def __str__(self):
        return f"{self.title} (${self.price})"


class Store(models.Model):
    """
    Store entity representing physical or virtual locations.
    """
    name = models.CharField(
        max_length=200,
        db_index=True,
        help_text="Store name"
    )
    location = models.CharField(
        max_length=300,
        help_text="Store address or location description"
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether store is operational"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Store'
        verbose_name_plural = 'Stores'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} - {self.location}"


class Inventory(models.Model):
    """
    Inventory entity linking stores and products with stock quantities.
    
    Constraint: Exactly one inventory row per product per store.
    This is enforced via unique_together and UniqueConstraint.
    """
    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name='inventories',
        help_text="Store holding this inventory"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='inventories',
        help_text="Product in inventory"
    )
    quantity = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Current stock quantity"
    )
    low_stock_threshold = models.PositiveIntegerField(
        default=10,
        help_text="Threshold for low stock alerts"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Inventory'
        verbose_name_plural = 'Inventories'
        ordering = ['store', 'product']
        # Enforce unique constraint: one row per product per store
        unique_together = ['store', 'product']
        constraints = [
            models.UniqueConstraint(
                fields=['store', 'product'],
                name='unique_store_product_inventory'
            )
        ]
        indexes = [
            models.Index(fields=['store', 'quantity']),
            models.Index(fields=['product', 'quantity']),
        ]

    def __str__(self):
        return f"{self.product.title} @ {self.store.name}: {self.quantity} units"

    @property
    def is_low_stock(self) -> bool:
        """Check if inventory is below low stock threshold."""
        return self.quantity <= self.low_stock_threshold

    @property
    def is_out_of_stock(self) -> bool:
        """Check if inventory is out of stock."""
        return self.quantity == 0
