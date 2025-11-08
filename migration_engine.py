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
from image_manager import ImageManager
from logger import setup_logger

class MigrationEngine:
    def __init__(self, progress_callback=None, log_callback=None):
        self.logger = setup_logger("migration_engine")
        self.progress_callback = progress_callback
        self.log_callback = log_callback
        self.shopify = None
        self.woocommerce = None
        self.wordpress = None
        self.image_manager = None
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
        self.existing_orders = []
        self.used_placeholder_emails = set()  # Track generated placeholder emails
        
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
            
            # Initialize image manager with WordPress credentials for Media API
            self.image_manager = ImageManager(
                wc_url, wc_key, wc_secret, 
                wp_username=wp_username, 
                wp_app_password=wp_password
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
            self.existing_orders = self.woocommerce.get_existing_orders()
            if self.wordpress:
                self.existing_pages = self.wordpress.get_existing_pages()
            
            self.log(f"[{mode_text}] Found {len(self.existing_customers)} existing customers, {len(self.existing_products)} existing products, {len(self.existing_categories)} existing categories, {len(self.existing_orders)} existing orders, {len(self.existing_pages)} existing pages")
            
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
            
            # Determine completion status based on errors and failures
            has_errors = len(self.migration_report['errors']) > 0
            has_failures = any(
                stats.get('failed', 0) > 0 
                for stats in self.migration_report.values() 
                if isinstance(stats, dict) and 'failed' in stats
            )
            
            if has_errors or has_failures:
                self.update_progress(100, "Migration completed with errors!")
            else:
                self.update_progress(100, "Migration completed successfully!")
            
            self._generate_migration_report(dry_run)
            
            # Return dictionary with status information
            return {
                'success': True,  # Migration didn't crash
                'has_errors': has_errors,
                'has_failures': has_failures,
                'report': self.migration_report
            }
            
        except Exception as e:
            self.log(f"Migration failed: {e}", 'ERROR')
            self.migration_report['errors'].append(str(e))
            return {
                'success': False,
                'has_errors': True,
                'has_failures': True,
                'error': str(e),
                'report': self.migration_report
            }

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
    
    def _find_existing_product(self, product):
        """Find existing WooCommerce product by SKU or name"""
        # Try to find by SKU first (most reliable)
        variants = product.get('variants', [])
        if variants:
            sku = variants[0].get('sku') or ''
            sku = sku.strip() if sku else ''
            if sku:
                existing = next((p for p in self.existing_products if (p.get('sku') or '').strip() == sku), None)
                if existing:
                    return existing
        
        # Try to find by product name
        product_name = product.get('title', '')
        if product_name:
            existing = next((p for p in self.existing_products if p.get('name') == product_name), None)
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
                    # Map customer (generates placeholder email if needed)
                    wc_customer = DataMapper.map_customer(customer, self.used_placeholder_emails)
                    
                    if not wc_customer:
                        error_msg = f"Customer {customer.get('id')} mapping failed"
                        
                    else:
                        email = wc_customer.get('email')
                        
                        # Check if already exists
                        if self._find_existing_customer(email):
                            existing = self._find_existing_customer(email)
                            self.id_mappings['customers'][str(customer.get('id'))] = existing.get('id')
                            mode_text = "DRY RUN" if dry_run else "LIVE"
                            self.log(f"[{mode_text}] Skipped existing customer: {email}")
                            success = True
                        elif dry_run:
                            # Validate mapping in dry run
                            self.log(f"[DRY RUN] Would create customer: {email}")
                            success = True
                        else:
                            # Create new customer
                            result = self.woocommerce.create_customer(wc_customer)
                            if result:
                                self.id_mappings['customers'][str(customer.get('id'))] = result.get('id')
                                self.log(f"Created customer: {email}")
                                success = True
                            else:
                                error_msg = f"Failed to create customer: {email}"
                            
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
        """Clean product migration with two-phase approach (products first, then images)"""
        try:
            products = self.shopify.get_products()
            attempted = len(products)
            successful = 0
            failed = 0
            products_with_images = []  # Track products that need images added
            
            self.log(f"Found {attempted} products to migrate")
            
            # Phase 1: Create products WITHOUT images to avoid timeout
            for product in products:
                success = False
                error_msg = None
                
                try:
                    product_name = product.get('title', 'Unknown')
                    shopify_id = str(product.get('id'))
                    
                    # Check if already exists
                    try:
                        existing = self._find_existing_product(product)
                    except Exception as find_error:
                        self.log(f"Error checking if product exists: {find_error}", 'WARNING')
                        existing = None
                    
                    if existing:
                        self.id_mappings['products'][shopify_id] = existing.get('id')
                        mode_text = "DRY RUN" if dry_run else "LIVE"
                        self.log(f"[{mode_text}] Skipped existing product: {product_name}")
                        success = True
                        
                        # Check if existing product needs images updated
                        if not dry_run:
                            images = product.get('images', [])
                            if images:
                                # Check if existing product has images
                                existing_images = existing.get('images', [])
                                if len(existing_images) == 0:
                                    # Product exists but has no images - add to image processing queue
                                    mapped_product = DataMapper.map_product(product)
                                    if mapped_product:
                                        product_images = mapped_product.get('images', [])
                                        if product_images:
                                            products_with_images.append({
                                                'wc_id': existing.get('id'),
                                                'name': product_name,
                                                'images': product_images
                                            })
                                            self.log(f"Existing product '{product_name}' has no images - will add them")
                    else:
                        # Map product data
                        mapped_product = DataMapper.map_product(product)
                        
                        if not mapped_product:
                            error_msg = "Product mapping failed"
                        elif dry_run:
                            self.log(f"[DRY RUN] Would create product: {product_name}")
                            success = True
                        else:
                            # Extract images before creating product
                            images = mapped_product.get('images', [])
                            
                            # Create product WITHOUT images to avoid timeout
                            result = self.woocommerce.create_product(mapped_product, include_images=False)
                            
                            if result:
                                wc_product_id = result.get('id')
                                self.id_mappings['products'][shopify_id] = wc_product_id
                                self.log(f"Created product: {product_name} (ID: {wc_product_id})")
                                success = True
                                
                                # Track for phase 2 if it has images
                                if images:
                                    products_with_images.append({
                                        'wc_id': wc_product_id,
                                        'name': product_name,
                                        'images': images
                                    })
                            else:
                                error_msg = "WooCommerce API returned None"
                
                except Exception as e:
                    error_msg = str(e)
                
                # SINGLE counting point
                if success:
                    successful += 1
                else:
                    failed += 1
                    if error_msg:
                        self.log(f"Failed to create product {product.get('title', 'Unknown')}: {error_msg}", 'ERROR')
                        self.migration_report['errors'].append(f"Product: {error_msg}")
            
            # Set final counts
            self.migration_report['products']['attempted'] = attempted
            self.migration_report['products']['successful'] = successful
            self.migration_report['products']['failed'] = failed
            self.migration_report['products']['variants'] = sum(len(p.get('variants', [])) for p in products)
            
            self.log(f"Products: {successful}/{attempted} successful, {failed} failed")
            
            # Phase 2: Download and upload images locally (if live migration and we have products with images)
            if not dry_run and products_with_images:
                self.log(f"Phase 2: Processing images for {len(products_with_images)} products...")
                self.log("Downloading images from Shopify and uploading to WordPress Media Library...")
                images_successful = 0
                images_failed = 0
                
                for item in products_with_images:
                    try:
                        product_name = item['name']
                        shopify_images = item['images']
                        
                        # Download images from Shopify and upload to WordPress Media Library
                        wordpress_images = self.image_manager.process_product_images(
                            product_name, 
                            shopify_images
                        )
                        
                        if wordpress_images:
                            # Update product with WordPress Media Library image IDs
                            result = self.woocommerce.update_product_images(item['wc_id'], wordpress_images)
                            if result:
                                images_successful += 1
                                self.log(f"Added {len(wordpress_images)} images to product: {product_name}")
                            else:
                                images_failed += 1
                                self.log(f"Failed to update product with images: {product_name}", 'ERROR')
                        else:
                            images_failed += 1
                            self.log(f"Failed to process images for: {product_name}", 'ERROR')
                            
                    except Exception as e:
                        images_failed += 1
                        self.log(f"Error processing images for {item['name']}: {e}", 'ERROR')
                
                self.log(f"Images: {images_successful}/{len(products_with_images)} products updated successfully")
                
                # Clean up old downloaded images
                try:
                    self.image_manager.cleanup_old_images(days=7)
                except Exception as e:
                    self.log(f"Warning: Could not cleanup old images: {e}", 'ERROR')
        
        except Exception as e:
            self.log(f"Error in product migration: {e}", 'ERROR')
            self.migration_report['errors'].append(f"Product migration: {str(e)}")

    def _find_existing_order(self, shopify_order_id, shopify_order_number):
        """Find existing WooCommerce order by Shopify order ID or number
        
        Args:
            shopify_order_id: Shopify order ID
            shopify_order_number: Shopify order number
            
        Returns:
            WooCommerce order object if found, None otherwise
        """
        for wc_order in self.existing_orders:
            # Check meta_data for shopify_order_id or shopify_order_number
            meta_data = wc_order.get('meta_data', [])
            for meta in meta_data:
                if meta.get('key') == 'shopify_order_id' and str(meta.get('value')) == str(shopify_order_id):
                    return wc_order
                if meta.get('key') == 'shopify_order_number' and str(meta.get('value')) == str(shopify_order_number):
                    return wc_order
        return None
    
    def _order_needs_update(self, existing_order, new_order_data):
        """Check if an order has meaningful differences that require an update
        
        Args:
            existing_order: Current WooCommerce order
            new_order_data: New order data from Shopify mapping
            
        Returns:
            Boolean indicating if update is needed
        """
        # Compare key fields that might change
        fields_to_compare = [
            'status',
            'total',
            'subtotal', 
            'total_tax',
            'shipping_total',
            'discount_total'
        ]
        
        for field in fields_to_compare:
            existing_val = str(existing_order.get(field, ''))
            new_val = str(new_order_data.get(field, ''))
            if existing_val != new_val:
                self.log(f"Order field '{field}' changed: '{existing_val}' → '{new_val}'", 'DEBUG')
                return True
        
        # Compare line items count
        existing_items = len(existing_order.get('line_items', []))
        new_items = len(new_order_data.get('line_items', []))
        if existing_items != new_items:
            self.log(f"Line items count changed: {existing_items} → {new_items}", 'DEBUG')
            return True
        
        # Compare line item quantities and totals
        for i, (existing_item, new_item) in enumerate(zip(
            existing_order.get('line_items', []),
            new_order_data.get('line_items', [])
        )):
            if str(existing_item.get('quantity')) != str(new_item.get('quantity')):
                return True
            if str(existing_item.get('total')) != str(new_item.get('total')):
                return True
        
        # No meaningful differences found
        return False

    def _migrate_orders_clean(self, dry_run=False):
        """Clean order migration with single counting point and duplicate detection"""
        try:
            orders = self.shopify.get_orders()
            attempted = len(orders)
            successful = 0
            failed = 0
            skipped = 0
            updated = 0
            
            self.log(f"Found {attempted} orders to migrate")
            
            for order in orders:
                success = False
                error_msg = None
                is_update = False
                
                try:
                    order_number = order.get('order_number', 'Unknown')
                    shopify_order_id = order.get('id')
                    
                    # Check if order already exists in WooCommerce
                    existing_order = self._find_existing_order(shopify_order_id, order_number)
                    
                    if dry_run:
                        if existing_order:
                            # Map the order data to check if update needed
                            wc_order = DataMapper.map_order(order, self.id_mappings['customers'])
                            if wc_order:
                                self._map_order_line_items(wc_order, order)
                                if self._order_needs_update(existing_order, wc_order):
                                    self.log(f"[DRY RUN] Order {order_number} already exists (WC ID: {existing_order.get('id')}), would update (changes detected)")
                                else:
                                    self.log(f"[DRY RUN] Order {order_number} already exists (WC ID: {existing_order.get('id')}), no changes needed")
                                success = True
                            else:
                                error_msg = f"Order mapping failed: {order_number}"
                        else:
                            # Validate mapping in dry run
                            wc_order = DataMapper.map_order(order, self.id_mappings['customers'])
                            if wc_order:
                                self.log(f"[DRY RUN] Would create order: {order_number}")
                                success = True
                            else:
                                error_msg = f"Order mapping failed: {order_number}"
                    else:
                        if existing_order:
                            # Order exists - check if update needed
                            wc_order_id = existing_order.get('id')
                            
                            # Map the order data
                            wc_order = DataMapper.map_order(order, self.id_mappings['customers'])
                            if wc_order:
                                # Map line items to WooCommerce products
                                self._map_order_line_items(wc_order, order)
                                
                                # Check if update is actually needed
                                if self._order_needs_update(existing_order, wc_order):
                                    self.log(f"Order {order_number} has changes, updating... (WC ID: {wc_order_id})")
                                    
                                    # IMPORTANT: Remove line_items and shipping_lines from update to prevent duplication
                                    # WooCommerce API appends these on update instead of replacing
                                    # Only update order-level fields, not line items or shipping
                                    update_data = wc_order.copy()
                                    update_data.pop('line_items', None)
                                    update_data.pop('shipping_lines', None)
                                    
                                    # Update the order
                                    result = self.woocommerce.update_order(wc_order_id, update_data)
                                    if result:
                                        self.log(f"Updated order: {order_number} (WC ID: {wc_order_id})")
                                        
                                        # Update notes if needed
                                        self._migrate_order_notes(wc_order_id, order, wc_order)
                                        
                                        success = True
                                        is_update = True
                                        updated += 1
                                    else:
                                        error_msg = f"Failed to update order: {order_number}"
                                else:
                                    # Order exists but no changes needed
                                    self.log(f"Order {order_number} unchanged, skipping (WC ID: {wc_order_id})")
                                    success = True
                                    skipped += 1
                            else:
                                error_msg = f"Order mapping failed: {order_number}"
                        else:
                            # Order doesn't exist - create new order
                            wc_order = DataMapper.map_order(order, self.id_mappings['customers'])
                            if wc_order:
                                # Map line items to WooCommerce products
                                self._map_order_line_items(wc_order, order)
                                
                                result = self.woocommerce.create_order(wc_order)
                                if result:
                                    wc_order_id = result.get('id')
                                    self.log(f"Created order: {order_number} (WC ID: {wc_order_id})")
                                    
                                    # Add Shopify order ID as private note
                                    if shopify_order_id:
                                        self.woocommerce.add_order_note(
                                            wc_order_id,
                                            f"Original Shopify order ID: {shopify_order_id}",
                                            customer_note=False
                                        )
                                    
                                    # Migrate Shopify notes as private WooCommerce notes (including job notes from $0 line items)
                                    self._migrate_order_notes(wc_order_id, order, wc_order)
                                    
                                    success = True
                                else:
                                    error_msg = f"Failed to create order: {order_number}"
                            else:
                                error_msg = f"Order mapping failed: {order_number}"
                            
                except Exception as e:
                    error_msg = f"Error processing order {order.get('order_number', 'unknown')}: {e}"
                
                # SINGLE counting point
                if success:
                    successful += 1
                    if not is_update:
                        # Only count as skipped if it already existed
                        pass
                else:
                    failed += 1
                    if error_msg:
                        self.log(error_msg, 'ERROR')
                        self.migration_report['errors'].append(error_msg)
            
            # Set final counts ONCE
            self.migration_report['orders']['attempted'] = attempted
            self.migration_report['orders']['successful'] = successful
            self.migration_report['orders']['failed'] = failed
            
            # Calculate created count (successful minus updated minus skipped)
            created = successful - updated - skipped
            
            if updated > 0 or skipped > 0:
                self.log(f"Orders: {successful}/{attempted} successful ({created} created, {updated} updated, {skipped} unchanged), {failed} failed")
            else:
                self.log(f"Orders: {successful}/{attempted} successful, {failed} failed")
            
        except Exception as e:
            self.log(f"Error in order migration: {e}", 'ERROR')

    def _migrate_order_notes(self, wc_order_id, shopify_order, wc_order=None):
        """Migrate Shopify order notes to WooCommerce as private notes
        
        Handles both:
        1. Standard Shopify order notes (from 'note' field)
        2. Job notes stored as $0 line items (extracted during mapping)
        
        Detects embedded images in notes and adds a placeholder note instead.
        
        Args:
            wc_order_id: WooCommerce order ID
            shopify_order: Shopify order data (original)
            wc_order: Mapped WooCommerce order (may contain _job_notes)
        """
        try:
            import re
            notes_added = 0
            
            # First, handle job notes from $0 line items (if any)
            if wc_order and '_job_notes' in wc_order:
                job_notes = wc_order.get('_job_notes', [])
                for job_note in job_notes:
                    if job_note and job_note.strip():
                        note_text = f"Job Notes (from Shopify line item):\n{job_note}"
                        
                        result = self.woocommerce.add_order_note(
                            wc_order_id,
                            note_text,
                            customer_note=False
                        )
                        
                        if result:
                            notes_added += 1
                            self.log(f"Added job note to WC order {wc_order_id}")
                        else:
                            self.log(f"Failed to add job note to WC order {wc_order_id}", 'ERROR')
            
            # Then, handle standard Shopify order note
            shopify_note = shopify_order.get('note')
            
            if shopify_note and shopify_note.strip():
                # Check for embedded images
                has_img_tag = '<img' in shopify_note.lower()
                has_cdn = 'cdn.shopify' in shopify_note.lower()
                has_image_url = re.search(r'\.(jpg|jpeg|png|gif|webp)', shopify_note.lower())
                
                if has_img_tag or has_cdn or has_image_url:
                    # Note contains images - strip them and add placeholder
                    # Remove HTML img tags
                    clean_note = re.sub(r'<img[^>]*>', '', shopify_note, flags=re.IGNORECASE)
                    # Remove standalone image URLs
                    clean_note = re.sub(r'https?://[^\s]*\.(jpg|jpeg|png|gif|webp)', '[image removed]', clean_note, flags=re.IGNORECASE)
                    
                    # Add note about images being removed
                    note_text = "Shopify Order Note:\n"
                    note_text += "[NOTE: Pictures were attached in the original Shopify order notes]\n\n"
                    if clean_note.strip():
                        note_text += clean_note.strip()
                    else:
                        note_text += "(Note contained only images)"
                    
                    self.log(f"Order note contains images - they will be stripped", 'WARNING')
                else:
                    # Normal note without images
                    note_text = f"Shopify Order Note:\n{shopify_note}"
                
                # Add as private note (not visible to customer)
                result = self.woocommerce.add_order_note(
                    wc_order_id,
                    note_text,
                    customer_note=False
                )
                
                if result:
                    notes_added += 1
                    self.log(f"Added order note to WC order {wc_order_id}")
                else:
                    self.log(f"Failed to add note to WC order {wc_order_id}", 'ERROR')
            
            if notes_added > 0:
                self.log(f"Added {notes_added} note(s) to order {wc_order_id}")
        
        except Exception as e:
            self.log(f"Error migrating notes for order {wc_order_id}: {e}", 'ERROR')
    
    def _map_order_line_items(self, wc_order, shopify_order):
        """Map Shopify line items to WooCommerce products
        
        WooCommerce allows creating orders with unmapped items as custom/unlisted products.
        Items without a product match will use product_id=0 and be treated as custom items.
        """
        shopify_line_items = shopify_order.get('line_items', [])
        
        for i, item in enumerate(wc_order.get('line_items', [])):
            shopify_variant_id = None
            shopify_product_id = None
            sku = item.get('sku')  # Get SKU from mapped item (may be None or '')
            
            # WooCommerce API requires SKU to be a string, not None
            # Convert None to empty string
            if sku is None:
                sku = ''
                item['sku'] = ''
            
            # Extract Shopify IDs from meta_data
            for meta in item.get('meta_data', []):
                if meta.get('key') == 'shopify_variant_id':
                    shopify_variant_id = meta.get('value')
                elif meta.get('key') == 'shopify_product_id':
                    shopify_product_id = meta.get('value')
            
            # Try to map to WooCommerce product/variation ID
            mapped = False
            
            if shopify_variant_id and shopify_variant_id in self.id_mappings['variants']:
                item['variation_id'] = self.id_mappings['variants'][shopify_variant_id]
                mapped = True
            elif shopify_product_id and shopify_product_id in self.id_mappings['products']:
                item['product_id'] = self.id_mappings['products'][shopify_product_id]
                mapped = True
            
            # If we couldn't map by ID, try to use SKU
            if not mapped and sku:
                # Find product in existing products by SKU
                wc_product = next((p for p in self.existing_products if p.get('sku') == sku), None)
                if wc_product:
                    item['product_id'] = wc_product.get('id')
                    mapped = True
            
            # If still not mapped, leave product_id=0 and WooCommerce will treat as custom/unlisted item
            # This allows orders with custom items (labour, custom parts, etc.) to be created
            if not mapped:
                self.log(f"Line item '{item.get('name')}' will be added as custom/unlisted item (no matching product)", 'INFO')

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