"""
Management command to seed the database with sample data.

Generates:
- 10+ categories
- 1000+ products
- 20+ stores
- Inventory records linking stores and products

Usage:
    python manage.py seed_data
    python manage.py seed_data --clear  # Clear existing data first
"""
import random
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction

from inventory.models import Category, Product, Store, Inventory


class Command(BaseCommand):
    help = 'Seed the database with sample categories, products, stores, and inventory'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data before seeding',
        )
        parser.add_argument(
            '--categories',
            type=int,
            default=12,
            help='Number of categories to create (default: 12)',
        )
        parser.add_argument(
            '--products',
            type=int,
            default=1000,
            help='Number of products to create (default: 1000)',
        )
        parser.add_argument(
            '--stores',
            type=int,
            default=25,
            help='Number of stores to create (default: 25)',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('Clearing existing data...')
            self._clear_data()

        self.stdout.write('Starting database seeding...')
        
        with transaction.atomic():
            categories = self._create_categories(options['categories'])
            products = self._create_products(options['products'], categories)
            stores = self._create_stores(options['stores'])
            self._create_inventory(products, stores)

        self.stdout.write(self.style.SUCCESS('Database seeding completed successfully!'))

    def _clear_data(self):
        """Clear all existing data."""
        from orders.models import OrderItem, Order
        
        OrderItem.objects.all().delete()
        Order.objects.all().delete()
        Inventory.objects.all().delete()
        Product.objects.all().delete()
        Store.objects.all().delete()
        Category.objects.all().delete()
        
        self.stdout.write(self.style.WARNING('All existing data cleared.'))

    def _create_categories(self, count):
        """Create sample categories."""
        category_names = [
            'Electronics', 'Clothing', 'Home & Garden', 'Sports & Outdoors',
            'Books', 'Toys & Games', 'Health & Beauty', 'Food & Beverages',
            'Automotive', 'Office Supplies', 'Pet Supplies', 'Jewelry',
            'Musical Instruments', 'Arts & Crafts', 'Baby Products'
        ]
        
        categories = []
        for i, name in enumerate(category_names[:count]):
            category, created = Category.objects.get_or_create(name=name)
            categories.append(category)
            if created:
                self.stdout.write(f'  Created category: {name}')
        
        self.stdout.write(self.style.SUCCESS(f'Created {len(categories)} categories'))
        return categories

    def _create_products(self, count, categories):
        """Create sample products with realistic data."""
        # Product name templates by category
        product_templates = {
            'Electronics': [
                'Wireless Headphones', 'Bluetooth Speaker', 'USB-C Cable',
                'Power Bank', 'Smart Watch', 'Laptop Stand', 'Webcam HD',
                'Gaming Mouse', 'Mechanical Keyboard', 'Monitor 27"'
            ],
            'Clothing': [
                'Cotton T-Shirt', 'Denim Jeans', 'Wool Sweater', 'Rain Jacket',
                'Running Shoes', 'Leather Belt', 'Silk Tie', 'Casual Dress',
                'Sports Shorts', 'Winter Coat'
            ],
            'Home & Garden': [
                'Garden Hose', 'Plant Pot Set', 'LED Light Bulbs', 'Throw Pillow',
                'Area Rug', 'Kitchen Knife Set', 'Bed Sheet Set', 'Wall Clock',
                'Picture Frame', 'Storage Bins'
            ],
            'Sports & Outdoors': [
                'Yoga Mat', 'Dumbbells Set', 'Running Belt', 'Water Bottle',
                'Camping Tent', 'Hiking Backpack', 'Bicycle Helmet', 'Golf Clubs',
                'Tennis Racket', 'Swimming Goggles'
            ],
            'Books': [
                'Fiction Bestseller', 'Self-Help Guide', 'Cookbook', 'Biography',
                'Sci-Fi Novel', 'History Book', 'Programming Guide', 'Art Book',
                'Travel Guide', 'Children\'s Story'
            ],
            'Toys & Games': [
                'Board Game Classic', 'Building Blocks', 'Remote Control Car',
                'Puzzle 1000pc', 'Action Figure', 'Plush Toy', 'Card Game',
                'Educational Toy', 'Outdoor Playset', 'Dollhouse'
            ],
        }
        
        adjectives = [
            'Premium', 'Deluxe', 'Professional', 'Classic', 'Modern',
            'Vintage', 'Eco-Friendly', 'Compact', 'Portable', 'Wireless',
            'Organic', 'Handmade', 'Limited Edition', 'Essential', 'Ultimate'
        ]
        
        colors = [
            'Black', 'White', 'Silver', 'Gold', 'Blue', 'Red', 'Green',
            'Navy', 'Gray', 'Brown', 'Pink', 'Purple', 'Orange', 'Teal'
        ]
        
        products = []
        existing_titles = set()
        
        self.stdout.write(f'Creating {count} products...')
        
        for i in range(count):
            category = random.choice(categories)
            templates = product_templates.get(category.name, ['Product'])
            
            # Generate unique title
            for _ in range(10):  # Try up to 10 times to get unique title
                base_name = random.choice(templates)
                adj = random.choice(adjectives)
                color = random.choice(colors)
                variant = random.randint(1, 99)
                
                title = f"{adj} {color} {base_name} v{variant}"
                if title not in existing_titles:
                    existing_titles.add(title)
                    break
            else:
                title = f"Product {i+1} - {category.name}"
                existing_titles.add(title)
            
            # Random price between $5 and $500
            price = Decimal(str(round(random.uniform(5, 500), 2)))
            
            # Random description
            descriptions = [
                f"High-quality {base_name.lower()} for everyday use.",
                f"Premium {category.name.lower()} product with excellent features.",
                f"Best-selling {base_name.lower()} with great reviews.",
                f"Perfect for home or office. {base_name} with modern design.",
                "",  # Some products without description
            ]
            
            product = Product(
                title=title,
                description=random.choice(descriptions),
                price=price,
                category=category,
                is_active=random.random() > 0.05  # 95% active
            )
            products.append(product)
            
            if (i + 1) % 200 == 0:
                self.stdout.write(f'  Created {i + 1} products...')
        
        # Bulk create for efficiency
        Product.objects.bulk_create(products, ignore_conflicts=True)
        
        # Fetch all created products
        products = list(Product.objects.all())
        self.stdout.write(self.style.SUCCESS(f'Created {len(products)} products'))
        return products

    def _create_stores(self, count):
        """Create sample stores."""
        cities = [
            ('New York', 'NY'), ('Los Angeles', 'CA'), ('Chicago', 'IL'),
            ('Houston', 'TX'), ('Phoenix', 'AZ'), ('Philadelphia', 'PA'),
            ('San Antonio', 'TX'), ('San Diego', 'CA'), ('Dallas', 'TX'),
            ('San Jose', 'CA'), ('Austin', 'TX'), ('Jacksonville', 'FL'),
            ('Fort Worth', 'TX'), ('Columbus', 'OH'), ('Charlotte', 'NC'),
            ('Seattle', 'WA'), ('Denver', 'CO'), ('Boston', 'MA'),
            ('Portland', 'OR'), ('Las Vegas', 'NV'), ('Detroit', 'MI'),
            ('Memphis', 'TN'), ('Baltimore', 'MD'), ('Milwaukee', 'WI'),
            ('Albuquerque', 'NM'), ('Tucson', 'AZ'), ('Nashville', 'TN'),
            ('Oklahoma City', 'OK'), ('Kansas City', 'MO'), ('Miami', 'FL')
        ]
        
        store_types = ['Main', 'Downtown', 'Mall', 'Outlet', 'Express', 'Warehouse']
        
        stores = []
        for i in range(count):
            city, state = cities[i % len(cities)]
            store_type = random.choice(store_types)
            
            store = Store(
                name=f"{city} {store_type} Store",
                location=f"{random.randint(100, 9999)} Main Street, {city}, {state}",
                is_active=random.random() > 0.1  # 90% active
            )
            stores.append(store)
        
        Store.objects.bulk_create(stores, ignore_conflicts=True)
        
        stores = list(Store.objects.all())
        self.stdout.write(self.style.SUCCESS(f'Created {len(stores)} stores'))
        return stores

    def _create_inventory(self, products, stores):
        """Create inventory records linking stores and products."""
        inventory_records = []
        
        self.stdout.write(f'Creating inventory for {len(stores)} stores...')
        
        for store in stores:
            # Each store carries 60-90% of products
            products_for_store = random.sample(
                products,
                k=int(len(products) * random.uniform(0.6, 0.9))
            )
            
            for product in products_for_store:
                # Random quantity between 0 and 500
                quantity = random.randint(0, 500)
                
                inventory_records.append(Inventory(
                    store=store,
                    product=product,
                    quantity=quantity,
                    low_stock_threshold=random.randint(5, 20)
                ))
        
        # Bulk create in batches to avoid memory issues
        batch_size = 5000
        total = len(inventory_records)
        
        for i in range(0, total, batch_size):
            batch = inventory_records[i:i + batch_size]
            Inventory.objects.bulk_create(batch, ignore_conflicts=True)
            self.stdout.write(f'  Created {min(i + batch_size, total)} inventory records...')
        
        final_count = Inventory.objects.count()
        self.stdout.write(self.style.SUCCESS(f'Created {final_count} inventory records'))
