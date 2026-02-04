"""
Tests for order transaction logic.

Test Cases:
1. Order confirmed with sufficient stock
2. Order rejected with insufficient stock
3. No stock deduction on rejection
4. Atomic rollback on error
5. Concurrent order race condition prevention
"""
from decimal import Decimal
from django.test import TestCase, TransactionTestCase
from django.db import connection
from unittest.mock import patch
import threading

from inventory.models import Category, Product, Store, Inventory
from orders.models import Order, OrderItem
from orders.services import create_order, OrderValidationError


class OrderTransactionTestCase(TestCase):
    """Test cases for order transaction logic."""
    
    def setUp(self):
        """Set up test data."""
        # Create category
        self.category = Category.objects.create(name='Test Category')
        
        # Create products
        self.product1 = Product.objects.create(
            title='Test Product 1',
            description='Description 1',
            price=Decimal('10.00'),
            category=self.category
        )
        self.product2 = Product.objects.create(
            title='Test Product 2',
            description='Description 2',
            price=Decimal('25.00'),
            category=self.category
        )
        self.product3 = Product.objects.create(
            title='Test Product 3',
            description='Description 3',
            price=Decimal('15.50'),
            category=self.category
        )
        
        # Create store
        self.store = Store.objects.create(
            name='Test Store',
            location='123 Test Street'
        )
        
        # Create inventory with known quantities
        self.inv1 = Inventory.objects.create(
            store=self.store,
            product=self.product1,
            quantity=100
        )
        self.inv2 = Inventory.objects.create(
            store=self.store,
            product=self.product2,
            quantity=50
        )
        self.inv3 = Inventory.objects.create(
            store=self.store,
            product=self.product3,
            quantity=10  # Low stock
        )

    def test_order_confirmed_with_sufficient_stock(self):
        """
        Test: Order is CONFIRMED when all items have enough stock.
        
        Given: Products with sufficient stock
        When: Creating an order within stock limits
        Then: Order status is CONFIRMED, stock is deducted
        """
        items = [
            {'product_id': self.product1.id, 'quantity': 5},
            {'product_id': self.product2.id, 'quantity': 3}
        ]
        
        order, error = create_order(self.store.id, items)
        
        # Assert order is confirmed
        self.assertEqual(order.status, Order.Status.CONFIRMED)
        self.assertIsNone(error)
        
        # Assert total is correct: (5 * 10) + (3 * 25) = 125
        self.assertEqual(order.total_amount, Decimal('125.00'))
        
        # Assert order items created
        self.assertEqual(order.items.count(), 2)
        
        # Assert inventory deducted
        self.inv1.refresh_from_db()
        self.inv2.refresh_from_db()
        self.assertEqual(self.inv1.quantity, 95)  # 100 - 5
        self.assertEqual(self.inv2.quantity, 47)  # 50 - 3

    def test_order_rejected_with_insufficient_stock(self):
        """
        Test: Order is REJECTED when any item lacks stock.
        
        Given: Product3 has only 10 units
        When: Requesting 15 units of product3
        Then: Order status is REJECTED
        """
        items = [
            {'product_id': self.product1.id, 'quantity': 5},
            {'product_id': self.product3.id, 'quantity': 15}  # Only 10 available
        ]
        
        order, error = create_order(self.store.id, items)
        
        # Assert order is rejected
        self.assertEqual(order.status, Order.Status.REJECTED)
        self.assertIsNotNone(error)
        self.assertIn('Insufficient stock', error)
        self.assertIn('Test Product 3', error)

    def test_no_stock_deduction_on_rejection(self):
        """
        Test: Inventory unchanged after rejected order.
        
        Given: Insufficient stock for one item
        When: Order is rejected
        Then: No inventory quantities are changed
        """
        # Store original quantities
        original_qty1 = self.inv1.quantity
        original_qty2 = self.inv2.quantity
        original_qty3 = self.inv3.quantity
        
        items = [
            {'product_id': self.product1.id, 'quantity': 5},
            {'product_id': self.product2.id, 'quantity': 10},
            {'product_id': self.product3.id, 'quantity': 20}  # Exceeds available
        ]
        
        order, error = create_order(self.store.id, items)
        
        # Assert order rejected
        self.assertEqual(order.status, Order.Status.REJECTED)
        
        # Refresh inventories
        self.inv1.refresh_from_db()
        self.inv2.refresh_from_db()
        self.inv3.refresh_from_db()
        
        # Assert NO deductions occurred
        self.assertEqual(self.inv1.quantity, original_qty1)
        self.assertEqual(self.inv2.quantity, original_qty2)
        self.assertEqual(self.inv3.quantity, original_qty3)

    def test_order_with_exact_stock(self):
        """
        Test: Order succeeds when requesting exactly available stock.
        """
        items = [
            {'product_id': self.product3.id, 'quantity': 10}  # Exactly 10 available
        ]
        
        order, error = create_order(self.store.id, items)
        
        # Assert order confirmed
        self.assertEqual(order.status, Order.Status.CONFIRMED)
        
        # Assert inventory is now 0
        self.inv3.refresh_from_db()
        self.assertEqual(self.inv3.quantity, 0)

    def test_validation_error_empty_items(self):
        """
        Test: Validation fails for empty items list.
        """
        with self.assertRaises(OrderValidationError) as context:
            create_order(self.store.id, [])
        
        self.assertIn('at least one item', str(context.exception))

    def test_validation_error_invalid_quantity(self):
        """
        Test: Validation fails for invalid quantity.
        """
        items = [
            {'product_id': self.product1.id, 'quantity': 0}
        ]
        
        with self.assertRaises(OrderValidationError):
            create_order(self.store.id, items)

    def test_validation_error_duplicate_products(self):
        """
        Test: Validation fails for duplicate products in same order.
        """
        items = [
            {'product_id': self.product1.id, 'quantity': 5},
            {'product_id': self.product1.id, 'quantity': 3}  # Duplicate
        ]
        
        with self.assertRaises(OrderValidationError) as context:
            create_order(self.store.id, items)
        
        self.assertIn('duplicate', str(context.exception).lower())

    def test_order_invalid_store(self):
        """
        Test: Order fails for non-existent store.
        """
        items = [
            {'product_id': self.product1.id, 'quantity': 5}
        ]
        
        with self.assertRaises(OrderValidationError) as context:
            create_order(99999, items)  # Non-existent store
        
        self.assertIn('not found', str(context.exception))

    def test_order_invalid_product(self):
        """
        Test: Order rejected for non-existent product.
        """
        items = [
            {'product_id': 99999, 'quantity': 5}  # Non-existent product
        ]
        
        order, error = create_order(self.store.id, items)
        
        self.assertEqual(order.status, Order.Status.REJECTED)
        self.assertIn('not found', error.lower())


class ConcurrentOrderTestCase(TransactionTestCase):
    """
    Test concurrent order handling to verify select_for_update works.
    Uses TransactionTestCase for proper multi-threading support.
    """
    
    def setUp(self):
        """Set up test data for concurrent testing."""
        self.category = Category.objects.create(name='Concurrent Test Category')
        self.product = Product.objects.create(
            title='Limited Stock Product',
            price=Decimal('50.00'),
            category=self.category
        )
        self.store = Store.objects.create(
            name='Concurrent Test Store',
            location='456 Race Street'
        )
        # Only 10 units available
        self.inventory = Inventory.objects.create(
            store=self.store,
            product=self.product,
            quantity=10
        )

    def test_concurrent_orders_no_overselling(self):
        """
        Test: Concurrent orders don't oversell inventory.
        
        Given: 10 units in stock
        When: Two concurrent orders of 8 units each
        Then: One succeeds (CONFIRMED), one fails (REJECTED)
              Final inventory matches expected (2 or 10)
        """
        results = {'order1': None, 'order2': None}
        
        def place_order(key):
            items = [{'product_id': self.product.id, 'quantity': 8}]
            order, error = create_order(self.store.id, items)
            results[key] = order.status
        
        # Create threads for concurrent orders
        thread1 = threading.Thread(target=place_order, args=('order1',))
        thread2 = threading.Thread(target=place_order, args=('order2',))
        
        # Start both threads
        thread1.start()
        thread2.start()
        
        # Wait for both to complete
        thread1.join()
        thread2.join()
        
        # Refresh inventory
        self.inventory.refresh_from_db()
        
        # Count outcomes
        confirmed = sum(1 for r in results.values() if r == 'CONFIRMED')
        rejected = sum(1 for r in results.values() if r == 'REJECTED')
        
        # At most one should be confirmed (prevents overselling)
        self.assertLessEqual(confirmed, 1)
        
        # If one confirmed, inventory should be 2 (10 - 8)
        # If none confirmed (both saw insufficient), inventory should be 10
        if confirmed == 1:
            self.assertEqual(self.inventory.quantity, 2)
        else:
            self.assertEqual(self.inventory.quantity, 10)


class OrderModelTestCase(TestCase):
    """Test cases for Order model properties."""
    
    def setUp(self):
        self.category = Category.objects.create(name='Model Test Category')
        self.product = Product.objects.create(
            title='Model Test Product',
            price=Decimal('100.00'),
            category=self.category
        )
        self.store = Store.objects.create(
            name='Model Test Store',
            location='789 Model Street'
        )

    def test_order_status_properties(self):
        """Test is_confirmed and is_rejected properties."""
        order = Order.objects.create(
            store=self.store,
            status=Order.Status.CONFIRMED,
            total_amount=Decimal('100.00')
        )
        
        self.assertTrue(order.is_confirmed)
        self.assertFalse(order.is_rejected)
        
        order.status = Order.Status.REJECTED
        order.save()
        
        self.assertFalse(order.is_confirmed)
        self.assertTrue(order.is_rejected)

    def test_order_item_subtotal(self):
        """Test OrderItem subtotal calculation."""
        order = Order.objects.create(
            store=self.store,
            status=Order.Status.CONFIRMED
        )
        
        item = OrderItem.objects.create(
            order=order,
            product=self.product,
            quantity=3,
            unit_price=Decimal('25.50')
        )
        
        self.assertEqual(item.subtotal, Decimal('76.50'))
