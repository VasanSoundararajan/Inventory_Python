"""
Celery tasks for order processing.

Tasks:
    - send_order_confirmation: Async notification after order confirmation
"""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True
)
def send_order_confirmation(self, order_id: int):
    """
    Async task triggered after successful order creation.
    
    In production, this would:
    - Send email confirmation to customer
    - Send SMS notification
    - Update external systems (ERP, CRM)
    - Generate invoice
    
    Args:
        order_id: ID of the confirmed order
        
    Returns:
        Dict with confirmation details
    """
    from orders.models import Order
    
    try:
        order = Order.objects.select_related('store').prefetch_related(
            'items__product'
        ).get(id=order_id)
    except Order.DoesNotExist:
        logger.error(f"Order #{order_id} not found for confirmation")
        return {'status': 'error', 'message': f'Order {order_id} not found'}
    
    if order.status != Order.Status.CONFIRMED:
        logger.warning(
            f"Order #{order_id} is not confirmed (status: {order.status}), "
            "skipping confirmation"
        )
        return {
            'status': 'skipped',
            'message': f'Order {order_id} is not confirmed'
        }
    
    # Simulate confirmation processing
    logger.info(f"[CELERY] Processing confirmation for Order #{order.id}")
    logger.info(f"[CELERY] Store: {order.store.name}")
    logger.info(f"[CELERY] Total: ${order.total_amount}")
    logger.info(f"[CELERY] Items: {order.items.count()}")
    
    # In production, you would:
    # 1. send_email(customer_email, order_details)
    # 2. send_sms(customer_phone, f"Order #{order.id} confirmed!")
    # 3. update_erp_system(order)
    # 4. generate_invoice_pdf(order)
    
    items_summary = [
        f"  - {item.quantity}x {item.product.title} @ ${item.unit_price}"
        for item in order.items.all()
    ]
    
    confirmation_message = f"""
    ===============================================
    ORDER CONFIRMATION - #{order.id}
    ===============================================
    Store: {order.store.name}
    Location: {order.store.location}
    Status: {order.status}
    Total: ${order.total_amount}
    
    Items:
    {chr(10).join(items_summary)}
    
    Created: {order.created_at.strftime('%Y-%m-%d %H:%M:%S')}
    ===============================================
    """
    
    logger.info(confirmation_message)
    
    return {
        'status': 'success',
        'order_id': order.id,
        'message': f'Confirmation sent for order {order_id}'
    }


@shared_task
def process_pending_orders():
    """
    Periodic task to process any stuck pending orders.
    
    This is a cleanup task that handles edge cases where orders
    might get stuck in PENDING status.
    """
    from orders.models import Order
    from django.utils import timezone
    from datetime import timedelta
    
    # Find orders stuck in PENDING for more than 5 minutes
    threshold = timezone.now() - timedelta(minutes=5)
    stuck_orders = Order.objects.filter(
        status=Order.Status.PENDING,
        created_at__lt=threshold
    )
    
    count = stuck_orders.count()
    if count > 0:
        logger.warning(f"Found {count} stuck pending orders")
        # Mark them as rejected
        stuck_orders.update(
            status=Order.Status.REJECTED,
            rejection_reason="Order processing timeout"
        )
    
    return {'processed': count}


@shared_task
def generate_daily_order_report():
    """
    Generate daily order statistics report.
    
    Can be scheduled via Celery Beat for daily execution.
    """
    from orders.models import Order
    from django.utils import timezone
    from django.db.models import Sum, Count
    from datetime import timedelta
    
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    
    orders = Order.objects.filter(
        created_at__date=yesterday
    )
    
    stats = orders.aggregate(
        total_orders=Count('id'),
        confirmed_orders=Count('id', filter=models.Q(status=Order.Status.CONFIRMED)),
        rejected_orders=Count('id', filter=models.Q(status=Order.Status.REJECTED)),
        total_revenue=Sum('total_amount', filter=models.Q(status=Order.Status.CONFIRMED))
    )
    
    report = f"""
    ===============================================
    DAILY ORDER REPORT - {yesterday}
    ===============================================
    Total Orders: {stats['total_orders']}
    Confirmed: {stats['confirmed_orders']}
    Rejected: {stats['rejected_orders']}
    Total Revenue: ${stats['total_revenue'] or 0}
    ===============================================
    """
    
    logger.info(report)
    
    return stats
