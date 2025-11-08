"""
FIXED migration engine with clean counting logic
"""
import json
import time
from datetime import datetime
from tqdm import tqdm
from config import Config
from shopify_client import ShopifyClient
from woocommerce_client import WooCommerceClient
from wordpress_client import WordPressClient
from data_mapper import DataMapper
from logger import setup_logger

class MigrationEngine:
    def __init__(self, progress_callback=None, log_callback=None):
        self.logger = setup_logger("migration_engine")
        self.progress_callback = progress_callback
        self.log_callback = log_callback
        self.shopify = None
        self.woocommerce = None
        self.wordpress = None
        self.migration_report = {
            'start_time': None,
            'end_time': None,
            'products': {'attempted': 0, 'successful': 0, 'failed': 0, 'variants': 0},
            'customers': {'attempted': 0, 'successful': 0, 'failed': 0},
            'orders': {'attempted': 0, 'successful': 0, 'failed': 0},
            'categories': {'attempted': 0, 'successful': 0, 'failed': 0},
            'coupons': {'attempted': 0, 'successful': 0, 'failed': 0},
            'pages': {'attempted': 0, 'successful': 0, 'failed': 0},
            'errors': []
        }
        self.id_mappings = {
            'products': {},
            'customers': {},
            'categories': {},
            'variants': {}
        }
        self.existing_customers = []
        self.existing_products = []
        self.existing_categories = []
        self.existing_pages = []
        
    def log(self, message, level='INFO'):
        """Log message and send to callback if available"""
        if level == 'INFO':
            self.logger.info(message)
        elif level == 'ERROR':
            self.logger.error(message)
        elif level == 'WARNING':
            self.logger.warning(message)
        elif level == 'DEBUG':
            self.logger.debug(message)
            
        if self.log_callback:
            self.log_callback(f"[{level}] {message}")
    
    def update_progress(self, percent, message):
        """Update progress if callback is available"""
        if self.progress_callback:
            self.progress_callback(percent, message)
            
    def connect_apis(self, shopify_url, shopify_token, wc_url, wc_key, wc_secret, wp_username=None, wp_password=None):
        """Initialize API connections"""
        try:
            self.shopify = ShopifyClient(
                shopify_url, shopify_token,
                max_retries=Config.MAX_RETRIES,
                delay=Config.DELAY_BETWEEN_REQUESTS
            )
            
            self.woocommerce = WooCommerceClient(
                wc_url, wc_key, wc_secret,
                max_retries=Config.MAX_RETRIES,
                delay=Config.DELAY_BETWEEN_REQUESTS
            )
            
            if wp_username and wp_password:
                self.wordpress = WordPressClient(
                    wc_url, wp_username, wp_password,
                    max_retries=Config.MAX_RETRIES,
                    delay=Config.DELAY_BETWEEN_REQUESTS
                )
            
            # Test connections
            shopify_ok = self.shopify.test_connection()
            wc_ok = self.woocommerce.test_connection()
            wp_ok = self.wordpress.test_connection() if self.wordpress else True
            
            if not shopify_ok:
                raise Exception("Failed to connect to Shopify")
            if not wc_ok:
                raise Exception("Failed to connect to WooCommerce")
            if self.wordpress and not wp_ok:
                self.log("WordPress connection failed - pages will be skipped", 'WARNING')
                self.wordpress = None
                
            self.log("API connections established successfully")
            if self.wordpress:
                self.log("WordPress API connected - pages will be migrated")
            else:
                self.log("WordPress API not configured - pages will be skipped")
            return True
            
        except Exception as e:
            self.log(f"Failed to connect to APIs: {e}", 'ERROR')
            return False

    def run_migration(self, dry_run=False):
        """Run the complete migration process with CLEAN counting"""
        try:
            self.migration_report['start_time'] = datetime.now()
            mode_text = "DRY RUN" if dry_run else "LIVE MIGRATION"
            self.log(f"Starting {mode_text}...")
            
            # Get existing data for duplicate detection
            self.update_progress(2, "Checking existing WooCommerce data...")
            self.existing_customers = self.woocommerce.get_existing_customers()
            self.existing_products = self.woocommerce.get_existing_products()
            self.existing_categories = self.woocommerce.get_existing_categories()
            if self.wordpress:
                self.existing_pages = self.wordpress.get_existing_pages()
            
            self.log(f"[{mode_text}] Found {len(self.existing_customers)} existing customers, {len(self.existing_products)} existing products, {len(self.existing_categories)} existing categories, {len(self.existing_pages)} existing pages")
            
            # Run migration phases with clean counting
            self.update_progress(5, "Migrating categories...")
            self._migrate_categories_clean(dry_run)
            
            self.update_progress(20, "Migrating products...")
            self._migrate_products_clean(dry_run)
            
            self.update_progress(50, "Migrating customers...")
            self._migrate_customers_clean(dry_run)
            
            self.update_progress(70, "Migrating orders...")
            self._migrate_orders_clean(dry_run)
            
            self.update_progress(85, "Migrating coupons...")
            self._migrate_coupons_clean(dry_run)
            
            self.update_progress(95, "Migrating pages...")
            self._migrate_pages_clean(dry_run)
            
            self.migration_report['end_time'] = datetime.now()
            self.update_progress(100, "Migration completed!")
            
            self._generate_migration_report(dry_run)
            return True
            
        except Exception as e:
            self.log(f"Migration failed: {e}", 'ERROR')
            self.migration_report['errors'].append(str(e))
            return False

    def _migrate_categories_clean(self, dry_run=False):
        """Clean category migration with single counting point"""
        try:
            collections = self.shopify.get_collections()
            attempted = len(collections)
            successful = 0
            failed = 0
            
            self.log(f"Found {attempted} categories to migrate")
            
            for collection in collections:
                success = False
                error_msg = None
                
                try:
                    category_name = collection.get('title', 'Unknown')
                    
                    # Check if already exists
                    existing = self._find_existing_category(collection)
                    
                    if existing:
                        self.id_mappings['categories'][str(collection.get('id'))] = existing.get('id')
                        mode_text = "DRY RUN" if dry_run else "LIVE"
                        self.log(f"[{mode_text}] Skipped existing category: {category_name}")
                        success = True
                    elif dry_run:
                        self.log(f"[DRY RUN] Would create category: {category_name}")
                        success = True
                    else:
                        # Create new category
                        result = self._create_wc_category(collection)
                        if result:
                            self.id_mappings['categories'][str(collection.get('id'))] = result.get('id')
                            self.log(f"Created category: {category_name}")
                            success = True
                        else:
                            error_msg = f"Failed to create category: {category_name}"
                            
                except Exception as e:
                    error_msg = f"Error processing category {collection.get('title', 'unknown')}: {e}"
                
                # SINGLE counting point
                if success:
                    successful += 1
                else:
                    failed += 1
                    if error_msg:
                        self.log(error_msg, 'ERROR')
                        self.migration_report['errors'].append(error_msg)
            
            # Set final counts ONCE
            self.migration_report['categories']['attempted'] = attempted
            self.migration_report['categories']['successful'] = successful
            self.migration_report['categories']['failed'] = failed
            
            self.log(f"Categories: {successful}/{attempted} successful, {failed} failed")
            
        except Exception as e:
            self.log(f"Error in category migration: {e}", 'ERROR')

    def _find_existing_category(self, collection):
        """Find existing WooCommerce category"""
        category_name = collection.get('title', '')
        category_slug = collection.get('handle', '')
        
        if category_name:
            existing = next((c for c in self.existing_categories if c.get('name') == category_name), None)
            if existing:
                return existing
                
        if category_slug:
            existing = next((c for c in self.existing_categories if c.get('slug') == category_slug), None)
            if existing:
                return existing
                
        return None

    def _create_wc_category(self, collection):
        """Create WooCommerce category"""
        category_data = {
            'name': collection.get('title', ''),
            'description': collection.get('body_html', ''),
            'slug': collection.get('handle', ''),
            'meta_data': [{'key': 'shopify_collection_id', 'value': str(collection.get('id', ''))}]
        }
        return self.woocommerce.create_product_category(category_data)

    def _migrate_customers_clean(self, dry_run=False):
        """Clean customer migration with single counting point"""
        try:
            customers = self.shopify.get_customers()
            attempted = len(customers)
            successful = 0
            failed = 0
            
            self.log(f"Found {attempted} customers to migrate")
            
            for customer in customers:
                success = False
                error_msg = None
                
                try:
                    email = customer.get('email')
                    
                    # Skip customers without email
                    if not email:
                        error_msg = f"Customer {customer.get('id')} has no email - skipping"
                        
                    # Check if already exists
                    elif self._find_existing_customer(email):
                        existing = self._find_existing_customer(email)
                        self.id_mappings['customers'][str(customer.get('id'))] = existing.get('id')
                        mode_text = "DRY RUN" if dry_run else "LIVE"
                        self.log(f"[{mode_text}] Skipped existing customer: {email}")
                        success = True
                    elif dry_run:
                        # Validate mapping in dry run
                        wc_customer = DataMapper.map_customer(customer)
                        if wc_customer:
                            self.log(f"[DRY RUN] Would create customer: {email}")
                            success = True
                        else:
                            error_msg = f"Customer mapping failed: {email}"
                    else:
                        # Create new customer
                        wc_customer = DataMapper.map_customer(customer)
                        if wc_customer:
                            result = self.woocommerce.create_customer(wc_customer)
                            if result:
                                self.id_mappings['customers'][str(customer.get('id'))] = result.get('id')
                                self.log(f"Created customer: {email}")
                                success = True
                            else:
                                error_msg = f"Failed to create customer: {email}"
                        else:
                            error_msg = f"Customer mapping failed: {email}"
                            
                except Exception as e:
                    error_msg = f"Error processing customer {customer.get('email', 'unknown')}: {e}"
                
                # SINGLE counting point
                if success:
                    successful += 1
                else:
                    failed += 1
                    if error_msg:
                        self.log(error_msg, 'ERROR')
                        self.migration_report['errors'].append(error_msg)
            
            # Set final counts ONCE
            self.migration_report['customers']['attempted'] = attempted
            self.migration_report['customers']['successful'] = successful
            self.migration_report['customers']['failed'] = failed
            
            self.log(f"Customers: {successful}/{attempted} successful, {failed} failed")
            
        except Exception as e:
            self.log(f"Error in customer migration: {e}", 'ERROR')

    def _find_existing_customer(self, email):
        """Find existing WooCommerce customer by email"""
        return next((c for c in self.existing_customers if c.get('email') == email), None)

    def _migrate_products_clean(self, dry_run=False):
        """Clean product migration - simplified for now"""
        # For now, just set basic counts to test the concept
        products = self.shopify.get_products()
        
        self.migration_report['products']['attempted'] = len(products)
        self.migration_report['products']['successful'] = len(products) if dry_run else 0
        self.migration_report['products']['failed'] = 0 if dry_run else len(products)
        self.migration_report['products']['variants'] = sum(len(p.get('variants', [])) for p in products)
        
        self.log(f"Products: {len(products)} found (simplified migration for testing)")

    def _migrate_orders_clean(self, dry_run=False):
        """Clean order migration - simplified for now"""
        orders = self.shopify.get_orders()
        
        self.migration_report['orders']['attempted'] = len(orders)
        self.migration_report['orders']['successful'] = len(orders) if dry_run else 0
        self.migration_report['orders']['failed'] = 0 if dry_run else len(orders)
        
        self.log(f"Orders: {len(orders)} found (simplified migration for testing)")

    def _migrate_coupons_clean(self, dry_run=False):
        """Clean coupon migration - simplified for now"""
        discounts = self.shopify.get_discounts()
        
        self.migration_report['coupons']['attempted'] = len(discounts)
        self.migration_report['coupons']['successful'] = len(discounts) if dry_run else 0
        self.migration_report['coupons']['failed'] = 0 if dry_run else len(discounts)
        
        self.log(f"Coupons: {len(discounts)} found (simplified migration for testing)")

    def _migrate_pages_clean(self, dry_run=False):
        """Clean page migration - simplified for now"""
        pages = self.shopify.get_pages()
        blogs = self.shopify.get_blogs()
        articles = []
        for blog in blogs:
            articles.extend(self.shopify.get_blog_articles(blog.get('id')))
        
        total = len(pages) + len(articles)
        
        self.migration_report['pages']['attempted'] = total
        self.migration_report['pages']['successful'] = total if dry_run and self.wordpress else 0
        self.migration_report['pages']['failed'] = 0 if (dry_run and self.wordpress) else total
        
        self.log(f"Pages: {total} found (simplified migration for testing)")

    def _generate_migration_report(self, dry_run=False):
        """Generate and save migration report"""
        mode = "DRY RUN" if dry_run else "MIGRATION"
        duration = (self.migration_report['end_time'] - self.migration_report['start_time']).total_seconds()
        
        self.log(f"\n=== {mode} REPORT ===")
        self.log(f"Duration: {duration:.2f} seconds")
        
        for category, stats in self.migration_report.items():
            if isinstance(stats, dict) and 'attempted' in stats:
                success_rate = (stats['successful'] / stats['attempted'] * 100) if stats['attempted'] > 0 else 0
                self.log(f"{category.upper()}: {stats['successful']}/{stats['attempted']} ({success_rate:.1f}% success)")
                if category == 'products' and 'variants' in stats:
                    self.log(f"  Variants: {stats['variants']}")
        
        if self.migration_report['errors']:
            self.log(f"Errors: {len(self.migration_report['errors'])}")
        
        # Save report
        import os
        os.makedirs("logs", exist_ok=True)
        report_file = os.path.join("logs", f"migration_report_{'dry_run' if dry_run else 'live'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        try:
            with open(report_file, 'w') as f:
                json.dump(self.migration_report, f, indent=2, default=str)
            self.log(f"Report saved to: {report_file}")
        except Exception as e:
            self.log(f"Failed to save report: {e}", 'ERROR')