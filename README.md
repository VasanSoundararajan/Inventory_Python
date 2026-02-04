# Inventory & Order Management System

A production-ready Django backend module for inventory and order management with atomic transactions, high-performance APIs, Redis rate limiting, and Celery async processing.

## Features

- **Model Architecture**: Category, Product, Store, Inventory, Order, OrderItem
- **Atomic Order Logic**: Fail-fast pattern with `transaction.atomic()` and `select_for_update()`
- **High-Performance APIs**: Optimized queries with `select_related`/`prefetch_related`
- **Product Search**: Keyword search with price and store filters
- **Autocomplete**: Fast prefix-matching with rate limiting (20 req/min)
- **Redis Rate Limiting**: Sliding window counter pattern
- **Celery Tasks**: Async order confirmation processing
- **Docker Ready**: Full orchestration with PostgreSQL, Redis, and Celery

## Tech Stack

| Component | Technology |
|-----------|------------|
| Framework | Django 4.2 + Django REST Framework |
| Database | PostgreSQL 15 |
| Cache/Rate Limiting | Redis 7 |
| Task Queue | Celery 5.3 |
| Containerization | Docker & Docker Compose |

## Quick Start

### Using Docker (Recommended)

```bash
# Clone and navigate to project
cd Afforo

# Start all services
docker-compose up --build

# In another terminal, run migrations and seed data
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py seed_data

# Create superuser (optional)
docker-compose exec web python manage.py createsuperuser
```

### Local Development

```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Set environment variables (or use .env file)
set DATABASE_URL=postgres://user:pass@localhost:5432/inventory_db
set REDIS_URL=redis://localhost:6379/0

# Run migrations
python manage.py migrate

# Seed database
python manage.py seed_data

# Run development server
python manage.py runserver
```

## API Endpoints

### Categories
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/categories/` | List all categories |
| POST | `/api/categories/` | Create category |
| GET | `/api/categories/{id}/` | Category detail |

### Products
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/products/` | List products |
| POST | `/api/products/` | Create product |
| GET | `/api/products/{id}/` | Product detail |
| GET | `/api/products/search/` | Search with filters |
| GET | `/api/products/autocomplete/` | Prefix autocomplete (rate-limited) |

**Search Parameters:**
- `q`: Keyword search (title, description, category)
- `min_price`, `max_price`: Price range filter
- `store_id`: Products available in store
- `category_id`: Filter by category

### Stores
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/stores/` | List stores |
| POST | `/api/stores/` | Create store |
| GET | `/api/stores/{id}/` | Store detail |

### Inventory
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/inventory/` | List inventory |
| POST | `/api/inventory/` | Create inventory |
| GET | `/api/inventory/{id}/` | Inventory detail |

**Filter Parameters:**
- `store_id`: Filter by store
- `product_id`: Filter by product
- `low_stock=true`: Show low stock items

### Orders
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/orders/` | List orders |
| POST | `/api/orders/` | Create order (atomic) |
| GET | `/api/orders/{id}/` | Order detail |
| GET | `/api/orders/stats/` | Order statistics |

**Create Order Example:**
```json
POST /api/orders/
{
    "store_id": 1,
    "items": [
        {"product_id": 1, "quantity": 2},
        {"product_id": 3, "quantity": 1}
    ]
}
```

**Response (Confirmed):**
```json
{
    "id": 1,
    "store": {"id": 1, "name": "Main Store", "location": "123 Main St"},
    "status": "CONFIRMED",
    "total_amount": "125.00",
    "items": [...],
    "created_at": "2024-01-15T10:30:00Z"
}
```

**Response (Rejected - Insufficient Stock):**
```json
{
    "id": 2,
    "status": "REJECTED",
    "rejection_reason": "Insufficient stock: Product X: requested 10, available 5",
    ...
}
```

## Order Transaction Logic

The order creation uses a **fail-fast pattern**:

1. Create order in `PENDING` status
2. Lock inventory rows with `select_for_update()` (prevents race conditions)
3. Validate ALL items have sufficient stock
4. If ANY fails → Mark `REJECTED`, no deductions occur
5. If ALL pass → Deduct stock, mark `CONFIRMED`, trigger Celery task

```python
# Simplified logic
with transaction.atomic():
    order = Order.objects.create(status='PENDING')
    
    # Lock rows
    inventories = Inventory.objects.select_for_update().filter(...)
    
    # Check ALL stock first (fail-fast)
    for item in items:
        if inventory.quantity < item.quantity:
            order.status = 'REJECTED'
            return order  # No deductions!
    
    # All checks passed - deduct and confirm
    for item in items:
        inventory.quantity -= item.quantity
    order.status = 'CONFIRMED'
```

## Rate Limiting

The autocomplete endpoint is rate-limited to **20 requests per minute** per IP address.

```
X-RateLimit-Limit: 20
X-RateLimit-Remaining: 15
X-RateLimit-Reset: 45
```

When limit exceeded:
```json
{
    "error": "Rate limit exceeded",
    "detail": "Maximum 20 requests per 60 seconds allowed.",
    "retry_after": 45
}
```

## Running Tests

```bash
# With Docker
docker-compose exec web python manage.py test orders.tests

# Local
python manage.py test orders.tests -v 2
```

**Test Coverage:**
- Order confirmed with sufficient stock
- Order rejected with insufficient stock
- No stock deduction on rejection
- Validation errors (empty items, duplicates)
- Concurrent order race condition prevention

## Project Structure

```
Afforo/
├── config/                 # Django project configuration
│   ├── settings.py         # Settings with PostgreSQL, Redis, Celery
│   ├── urls.py             # Root URL configuration
│   ├── celery.py           # Celery app configuration
│   └── wsgi.py             # WSGI entry point
├── core/                   # Core utilities
│   └── rate_limiting.py    # Redis rate limiting decorator
├── inventory/              # Inventory app
│   ├── models.py           # Category, Product, Store, Inventory
│   ├── views.py            # API views with optimized queries
│   ├── serializers.py      # DRF serializers
│   └── management/commands/
│       └── seed_data.py    # Database seeding command
├── orders/                 # Orders app
│   ├── models.py           # Order, OrderItem with status
│   ├── services.py         # Atomic order creation logic
│   ├── views.py            # Order API views
│   ├── tasks.py            # Celery async tasks
│   └── tests.py            # Transaction tests
├── Dockerfile              # Production Docker image
├── docker-compose.yml      # Multi-service orchestration
├── requirements.txt        # Python dependencies
└── README.md               # This file
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | (required) | Django secret key |
| `DEBUG` | `True` | Debug mode |
| `DATABASE_URL` | SQLite | PostgreSQL connection URL |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated hosts |
| `RATE_LIMIT_ENABLED` | `True` | Enable/disable rate limiting |

## License

MIT License
