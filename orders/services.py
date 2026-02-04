"""
Order Service Layer - Atomic order creation logic.

Implements fail-fast pattern:
1. Create order in PENDING status
2. Lock inventory rows with select_for_update()
3. Validate ALL items have sufficient stock
4. If ANY fails: Mark REJECTED, no deductions
5. If ALL pass: Deduct stock, mark CONFIRMED, trigger async task
"""
import logging
from decimal import Decimal
from typing import List, Dict, Tuple, Optional

from django.db import transaction, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

from inventory.models import Store, Product, Inventory
from .models import Order, OrderItem

logger = logging.getLogger(__name__)


class InsufficientStockError(Exception):
    """Raised when there's not enough stock for an order item."""
    def __init__(self, product_id: int, requested: int, available: int):
        self.product_id = product_id
        self.requested = requested
        self.available = available
        super().__init__(
            f"Insufficient stock for product {product_id}: "
            f"requested {requested}, available {available}"
        )


class OrderValidationError(Exception):
    """Raised when order validation fails."""
    pass


def validate_order_items(items: List[Dict]) -> None:
    """
    Validate order items structure.
    
    Args:
        items: List of dicts with 'product_id' and 'quantity'
        
    Raises:
        OrderValidationError: If validation fails
    """
    if not items:
        raise OrderValidationError("Order must contain at least one item")
    
    seen_products = set()
    for idx, item in enumerate(items):
        if 'product_id' not in item:
            raise OrderValidationError(f"Item {idx}: missing 'product_id'")
        if 'quantity' not in item:
            raise OrderValidationError(f"Item {idx}: missing 'quantity'")
        
        product_id = item['product_id']
        quantity = item['quantity']
        
        if not isinstance(quantity, int) or quantity < 1:
            raise OrderValidationError(f"Item {idx}: quantity must be a positive integer")
        
        if product_id in seen_products:
            raise OrderValidationError(f"Item {idx}: duplicate product_id {product_id}")
        seen_products.add(product_id)


def create_order(store_id: int, items: List[Dict]) -> Tuple[Order, Optional[str]]:
    """
    Create an order with atomic transaction handling.
    
    Implements fail-fast pattern:
    - If ANY item has insufficient stock, order is REJECTED immediately
    - No partial deductions occur on failure
    - Stock is locked during validation to prevent race conditions
    
    Args:
        store_id: ID of the store to place order at
        items: List of dicts with 'product_id' and 'quantity'
        
    Returns:
        Tuple of (Order object, error message or None)
        
    Raises:
        OrderValidationError: If items validation fails
        ObjectDoesNotExist: If store or products don't exist
    """
    # Validate items structure
    validate_order_items(items)
    
    # Validate store exists
    try:
        store = Store.objects.get(id=store_id, is_active=True)
    except Store.DoesNotExist:
        raise OrderValidationError(f"Store {store_id} not found or inactive")
    
    with transaction.atomic():
        # Create order in PENDING status
        order = Order.objects.create(
            store=store,
            status=Order.Status.PENDING
        )
        
        logger.info(f"Created order #{order.id} for store {store.name}")
        
        # Collect product IDs for batch lookup
        product_ids = [item['product_id'] for item in items]
        
        # Validate all products exist and are active
        products = {
            p.id: p for p in Product.objects.filter(id__in=product_ids, is_active=True)
        }
        missing_products = set(product_ids) - set(products.keys())
        if missing_products:
            order.status = Order.Status.REJECTED
            order.rejection_reason = f"Products not found or inactive: {missing_products}"
            order.save()
            return order, order.rejection_reason
        
        # Lock inventory rows for update (prevents race conditions)
        # Order by product_id to prevent deadlocks
        inventory_qs = Inventory.objects.select_for_update().filter(
            store=store,
            product_id__in=product_ids
        ).order_by('product_id')
        
        inventory_map = {inv.product_id: inv for inv in inventory_qs}
        
        # Check for products not in this store's inventory
        missing_inventory = set(product_ids) - set(inventory_map.keys())
        if missing_inventory:
            order.status = Order.Status.REJECTED
            order.rejection_reason = f"Products not available in store: {missing_inventory}"
            order.save()
            return order, order.rejection_reason
        
        # FAIL-FAST: Check all stock BEFORE any deductions
        insufficient_stock = []
        for item in items:
            product_id = item['product_id']
            requested_qty = item['quantity']
            inventory = inventory_map[product_id]
            
            if inventory.quantity < requested_qty:
                insufficient_stock.append({
                    'product_id': product_id,
                    'product_title': products[product_id].title,
                    'requested': requested_qty,
                    'available': inventory.quantity
                })
        
        # If ANY item has insufficient stock, REJECT the entire order
        if insufficient_stock:
            rejection_details = "; ".join([
                f"{s['product_title']}: requested {s['requested']}, available {s['available']}"
                for s in insufficient_stock
            ])
            order.status = Order.Status.REJECTED
            order.rejection_reason = f"Insufficient stock: {rejection_details}"
            order.save()
            logger.warning(f"Order #{order.id} rejected: insufficient stock")
            return order, order.rejection_reason
        
        # All checks passed - deduct stock and create order items
        total_amount = Decimal('0.00')
        order_items = []
        
        for item in items:
            product_id = item['product_id']
            quantity = item['quantity']
            product = products[product_id]
            inventory = inventory_map[product_id]
            
            # Deduct inventory
            inventory.quantity -= quantity
            inventory.save(update_fields=['quantity', 'updated_at'])
            
            # Create order item
            order_item = OrderItem(
                order=order,
                product=product,
                quantity=quantity,
                unit_price=product.price
            )
            order_items.append(order_item)
            
            total_amount += product.price * quantity
            
            logger.debug(
                f"Order #{order.id}: deducted {quantity} of {product.title}, "
                f"remaining stock: {inventory.quantity}"
            )
        
        # Bulk create order items
        OrderItem.objects.bulk_create(order_items)
        
        # Update order to CONFIRMED
        order.status = Order.Status.CONFIRMED
        order.total_amount = total_amount
        order.save()
        
        logger.info(
            f"Order #{order.id} confirmed: {len(order_items)} items, "
            f"total ${total_amount}"
        )
        
        # Trigger async confirmation task
        try:
            from .tasks import send_order_confirmation
            send_order_confirmation.delay(order.id)
            logger.info(f"Triggered confirmation task for order #{order.id}")
        except Exception as e:
            # Don't fail the order if task queuing fails
            logger.error(f"Failed to queue confirmation task: {e}")
        
        return order, None


def get_order_summary(order_id: int) -> Dict:
    """
    Get detailed order summary with optimized queries.
    
    Uses select_related and prefetch_related to minimize database hits.
    """
    order = Order.objects.select_related('store').prefetch_related(
        'items__product__category'
    ).get(id=order_id)
    
    return {
        'id': order.id,
        'store': {
            'id': order.store.id,
            'name': order.store.name,
            'location': order.store.location
        },
        'status': order.status,
        'total_amount': str(order.total_amount),
        'item_count': order.items.count(),
        'items': [
            {
                'product_id': item.product.id,
                'product_title': item.product.title,
                'category': item.product.category.name,
                'quantity': item.quantity,
                'unit_price': str(item.unit_price),
                'subtotal': str(item.subtotal)
            }
            for item in order.items.all()
        ],
        'rejection_reason': order.rejection_reason or None,
        'created_at': order.created_at.isoformat(),
        'updated_at': order.updated_at.isoformat()
    }
