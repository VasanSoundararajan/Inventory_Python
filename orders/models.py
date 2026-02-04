"""
Order Models - Order and OrderItem entities with status tracking.

Order Status Flow:
    PENDING -> CONFIRMED (successful stock validation)
    PENDING -> REJECTED (insufficient stock)
"""
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator

from inventory.models import Store, Product


class Order(models.Model):
    """
    Order entity representing a customer order at a specific store.
    
    Status:
        - PENDING: Order created, awaiting stock validation
        - CONFIRMED: All items validated, stock deducted
        - REJECTED: Insufficient stock, no deductions made
    """
    
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        CONFIRMED = 'CONFIRMED', 'Confirmed'
        REJECTED = 'REJECTED', 'Rejected'
    
    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name='orders',
        help_text="Store where order is placed"
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        help_text="Current order status"
    )
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Total order amount"
    )
    rejection_reason = models.TextField(
        blank=True,
        default='',
        help_text="Reason for rejection if order was rejected"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Order'
        verbose_name_plural = 'Orders'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['store', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f"Order #{self.id} - {self.store.name} ({self.status})"

    @property
    def is_confirmed(self) -> bool:
        return self.status == self.Status.CONFIRMED

    @property
    def is_rejected(self) -> bool:
        return self.status == self.Status.REJECTED

    @property
    def item_count(self) -> int:
        return self.items.count()


class OrderItem(models.Model):
    """
    OrderItem entity representing a product in an order.
    
    Stores the unit price at time of order to preserve historical pricing.
    """
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items',
        help_text="Parent order"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,  # Prevent deletion of products with orders
        related_name='order_items',
        help_text="Ordered product"
    )
    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Quantity ordered"
    )
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Price per unit at time of order"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Order Item'
        verbose_name_plural = 'Order Items'
        ordering = ['id']

    def __str__(self):
        return f"{self.quantity}x {self.product.title} @ ${self.unit_price}"

    @property
    def subtotal(self) -> Decimal:
        """Calculate item subtotal."""
        return self.quantity * self.unit_price
