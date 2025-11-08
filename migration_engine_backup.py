"""
Complete migration engine for transferring data from Shopify to WooCommerce
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
            'products': {},  # shopify_id -> wc_id
            'customers': {},  # shopify_id -> wc_id
            'categories': {},  # shopify_collection_id -> wc_category_id
            'variants': {}  # shopify_variant_id -> wc_variation_id
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
    
    def update_progress(self, percentage, status=""):
        """Update progress and send to callback if available"""
        if self.progress_callback:
            self.progress_callback(percentage, status)
            
    def connect_apis(self, shopify_url, shopify_token, wc_url, wc_key, wc_secret, wp_username=None, wp_password=None):
        """Initialize API connections"""
        try:
            self.shopify = ShopifyClient(
                shopify_url,
                shopify_token,
                max_retries=Config.MAX_RETRIES,
                delay=Config.DELAY_BETWEEN_REQUESTS
            )
            
            self.woocommerce = WooCommerceClient(
                wc_url,
                wc_key,
                wc_secret,
                max_retries=Config.MAX_RETRIES,
                delay=Config.DELAY_BETWEEN_REQUESTS
            )
            
            # Initialize WordPress client if credentials provided
            if wp_username and wp_password:
                self.wordpress = WordPressClient(
                    wc_url,  # Same URL as WooCommerce typically
                    wp_username,
                    wp_password,
                    max_retries=Config.MAX_RETRIES,
                    delay=Config.DELAY_BETWEEN_REQUESTS
                )
            
            # Test connections
            shopify_ok = self.shopify.test_connection()
            wc_ok = self.woocommerce.test_connection()
            wp_ok = self.wordpress.test_connection() if self.wordpress else True  # Optional
            
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
        """Run the complete migration process"""
        try:
            self.migration_report['start_time'] = datetime.now()
            mode = "DRY RUN" if dry_run else "LIVE MIGRATION"
            self.log(f"Starting {mode}...")
            
            # Pre-migration: Get existing WooCommerce data for duplicate detection
            # This should happen for both dry run and live migration to be accurate
            self.update_progress(2, "Checking existing WooCommerce data...")
            self.existing_customers = self.woocommerce.get_existing_customers()
            self.existing_products = self.woocommerce.get_existing_products()
            self.existing_categories = self.woocommerce.get_existing_categories()
            
            # Get existing WordPress pages if WordPress is configured
            if self.wordpress:
                self.existing_pages = self.wordpress.get_existing_pages()
            else:
                self.existing_pages = []
            
            mode_text = "DRY RUN" if dry_run else "LIVE MIGRATION"
            self.log(f"[{mode_text}] Found {len(self.existing_customers)} existing customers, {len(self.existing_products)} existing products, {len(self.existing_categories)} existing categories, {len(self.existing_pages)} existing pages")
            
            # Phase 1: Migrate Categories (Collections)
            self.update_progress(5, "Migrating categories...")
            self.migrate_categories(dry_run)
            
            # Phase 2: Migrate Products and Variants
            self.update_progress(20, "Migrating products...")
            self.migrate_products(dry_run)
            
            # Phase 3: Migrate Customers
            self.update_progress(50, "Migrating customers...")
            self.migrate_customers(dry_run)
            
            # Phase 4: Migrate Orders
            self.update_progress(70, "Migrating orders...")
            self.migrate_orders(dry_run)
            
            # Phase 5: Migrate Coupons
            self.update_progress(85, "Migrating coupons...")
            self.migrate_coupons(dry_run)
            
            # Phase 6: Migrate Pages
            self.update_progress(95, "Migrating pages...")
            self.migrate_pages(dry_run)
            
            self.migration_report['end_time'] = datetime.now()
            self.update_progress(100, "Migration completed!")
            
            self.generate_migration_report(dry_run)
            return True
            
        except Exception as e:
            self.log(f"Migration failed: {e}", 'ERROR')
            self.migration_report['errors'].append(str(e))
            return False
    
    def migrate_categories(self, dry_run=False):
        """Migrate Shopify collections to WooCommerce categories"""
        try:
            collections = self.shopify.get_collections()
            self.migration_report['categories']['attempted'] = len(collections)
            
            for collection in collections:
                try:
                    # Check if category already exists (for both dry run and live migration)
                    category_name = collection.get('title', '')
                    category_slug = collection.get('handle', '')
                    
                    existing_category = None
                    if category_name:
                        existing_category = next((c for c in self.existing_categories if c.get('name') == category_name), None)
                    if not existing_category and category_slug:
                        existing_category = next((c for c in self.existing_categories if c.get('slug') == category_slug), None)
                    
                    if existing_category:
                        self.id_mappings['categories'][str(collection.get('id'))] = existing_category.get('id')
                        mode_text = "DRY RUN" if dry_run else "LIVE"
                        self.log(f"[{mode_text}] Skipped existing category: {category_name}")
                        # Don't increment successful here - it's handled at the end
                    elif dry_run:
                        self.log(f"[DRY RUN] Would create category: {collection.get('title', 'Unknown')}")
                        # Don't increment successful here - it's handled at the end
                    else:
                        category_data = {
                            'name': collection.get('title', ''),
                            'description': collection.get('body_html', ''),
                            'slug': collection.get('handle', ''),
                            'meta_data': [
                                {
                                    'key': 'shopify_collection_id',
                                    'value': str(collection.get('id', ''))
                                }
                            ]
                        }
                        
                        result = self.woocommerce.create_product_category(category_data)
                        if result:
                            self.id_mappings['categories'][str(collection.get('id'))] = result.get('id')
                            self.log(f"Created category: {collection.get('title', 'Unknown')}")
                            # Don't increment successful here - it's handled at the end
                        else:
                            self.migration_report['categories']['failed'] += 1
                            self.log(f"Failed to create category: {collection.get('title', 'Unknown')}", 'ERROR')
                            continue  # Skip the success increment at the end
                    
                    # Count as successful (either skipped existing or created new)
                    self.migration_report['categories']['successful'] += 1
                            
                except Exception as e:
                    self.log(f"Failed to migrate collection {collection.get('id', 'unknown')}: {e}", 'ERROR')
                    self.migration_report['categories']['failed'] += 1
                    self.migration_report['errors'].append(f"Category migration error: {str(e)}")
                    
        except Exception as e:
            self.log(f"Error in category migration: {e}", 'ERROR')
    
    def migrate_products(self, dry_run=False):
        """Migrate Shopify products with variants to WooCommerce"""
        try:
            products = self.shopify.get_products()
            self.migration_report['products']['attempted'] = len(products)
            
            for product in tqdm(products, desc="Migrating products"):
                try:
                    variants = product.get('variants', [])
                    
                    # Check if product already exists (for both dry run and live migration)
                    product_name = product.get('title', '')
                    product_sku = None
                    if variants:
                        product_sku = variants[0].get('sku')
                    
                    existing_product = None
                    if product_sku:
                        existing_product = next((p for p in self.existing_products if p.get('sku') == product_sku), None)
                    if not existing_product and product_name:
                        existing_product = next((p for p in self.existing_products if p.get('name') == product_name), None)
                    
                    if existing_product:
                        self.id_mappings['products'][str(product.get('id'))] = existing_product.get('id')
                        mode_text = "DRY RUN" if dry_run else "LIVE"
                        self.log(f"[{mode_text}] Skipped existing product: {product_name}")
                        # Success and variants counted at end
                    elif dry_run:
                        wc_product = DataMapper.map_product(product)
                        if wc_product:
                            self.log(f"[DRY RUN] Would create product: {product.get('title', 'Unknown')} with {len(variants)} variants")
                            # Success and variants counted at end
                        else:
                            self.log(f"[DRY RUN] Would fail to create product: {product.get('title', 'Unknown')} (mapping failed)")
                            self.migration_report['products']['failed'] += 1
                            continue  # Skip success increment
                    else:
                        # Map product data
                        wc_product = DataMapper.map_product(product)
                        if not wc_product:
                            self.migration_report['products']['failed'] += 1
                            continue
                        
                        # Add categories if they exist
                        self.add_product_categories(wc_product, product)
                        
                        # Handle single variant products
                        if len(variants) == 1:
                            wc_product['type'] = 'simple'
                            result = self.woocommerce.create_product(wc_product)
                            
                        # Handle variable products
                        else:
                            wc_product['type'] = 'variable'
                            wc_product['attributes'] = self.create_product_attributes(product, variants)
                            
                            # Create parent product
                            result = self.woocommerce.create_product(wc_product)
                            
                            if result:
                                parent_id = result.get('id')
                                # Create variations
                                product_options = product.get('options', [])
                                self.create_product_variations(parent_id, variants, product_options, dry_run)
                        
                        if result:
                            self.id_mappings['products'][str(product.get('id'))] = result.get('id')
                            self.log(f"Created product: {product.get('title', 'Unknown')}")
                            # Success and variants counted at end
                        else:
                            self.migration_report['products']['failed'] += 1
                            self.log(f"Failed to create product: {product.get('title', 'Unknown')}", 'ERROR')
                            continue  # Skip success increment
                    
                    # Count as successful (either skipped existing or created new)
                    self.migration_report['products']['successful'] += 1
                    self.migration_report['products']['variants'] += len(variants)
                            
                except Exception as e:
                    self.log(f"Failed to migrate product {product.get('id', 'unknown')}: {e}", 'ERROR')
                    self.migration_report['products']['failed'] += 1
                    self.migration_report['errors'].append(f"Product migration error: {str(e)}")
                    
        except Exception as e:
            self.log(f"Error in product migration: {e}", 'ERROR')
    
    def create_product_attributes(self, product, variants):
        """Create WooCommerce attributes from Shopify product options"""
        attributes = []
        options = product.get('options', [])
        
        # If no options defined, create from variant data
        if not options:
            # Analyze variants to determine attributes
            for i in range(1, 4):  # Shopify supports up to 3 options
                option_values = list(set([
                    v.get(f'option{i}') for v in variants 
                    if v.get(f'option{i}') and v.get(f'option{i}') != 'Default Title'
                ]))
                
                if option_values:
                    attributes.append({
                        'name': f'Attribute {i}',
                        'options': option_values,
                        'visible': True,
                        'variation': True
                    })
        else:
            # Use defined options
            for option in options:
                option_name = option.get('name', '')
                position = option.get('position', 1)
                
                # Get all unique values for this option from variants
                option_values = list(set([
                    v.get(f'option{position}') for v in variants 
                    if v.get(f'option{position}') and v.get(f'option{position}') != 'Default Title'
                ]))
                
                if option_values:
                    attributes.append({
                        'name': option_name,
                        'options': option_values,
                        'visible': True,
                        'variation': True
                    })
        
        return attributes
    
    def create_product_variations(self, parent_id, variants, product_options=None, dry_run=False):
        """Create WooCommerce variations from Shopify variants"""
        for variant in variants:
            try:
                if dry_run:
                    variant_name = variant.get('sku', f"Variant {variant.get('id', 'unknown')}")
                    self.log(f"[DRY RUN] Would create variation: {variant_name}")
                    continue
                
                variation_data = DataMapper.map_product_variant(variant, product_options)
                if not variation_data:
                    continue
                
                # Create variation via WooCommerce API
                result = self.woocommerce._make_request('POST', f'products/{parent_id}/variations', json=variation_data)
                
                if result:
                    self.id_mappings['variants'][str(variant.get('id'))] = result.get('id')
                    variant_name = variant.get('sku', f"Variant {variant.get('id')}")
                    self.log(f"Created variation: {variant_name}")
                else:
                    self.log(f"Failed to create variation {variant.get('id', 'unknown')}: No response", 'ERROR')
                    
            except Exception as e:
                self.log(f"Failed to create variation {variant.get('id', 'unknown')}: {e}", 'ERROR')
    
    def add_product_categories(self, wc_product, shopify_product):
        """Add categories to WooCommerce product based on Shopify collections"""
        # This would require fetching product collections from Shopify
        # and mapping them to the created categories
        pass
    
    def migrate_customers(self, dry_run=False):
        """Migrate Shopify customers to WooCommerce"""
        try:
            customers = self.shopify.get_customers()
            self.migration_report['customers']['attempted'] = len(customers)
            
            for customer in tqdm(customers, desc="Migrating customers"):
                try:
                    # Check if customer already exists (for both dry run and live migration)
                    email = customer.get('email')
                    existing_customer = None
                    if email:
                        existing_customer = next((c for c in self.existing_customers if c.get('email') == email), None)
                    
                    if existing_customer:
                        self.id_mappings['customers'][str(customer.get('id'))] = existing_customer.get('id')
                        mode_text = "DRY RUN" if dry_run else "LIVE"
                        self.log(f"[{mode_text}] Skipped existing customer: {email}")
                        # Success counted at end
                    elif dry_run:
                        wc_customer = DataMapper.map_customer(customer)
                        if wc_customer:
                            self.log(f"[DRY RUN] Would create customer: {customer.get('email', 'Unknown')}")
                            # Success counted at end
                        else:
                            self.log(f"[DRY RUN] Would fail to create customer: {customer.get('email', 'Unknown')} (mapping failed)")
                            self.migration_report['customers']['failed'] += 1
                            continue  # Skip success increment
                    else:
                        wc_customer = DataMapper.map_customer(customer)
                        if not wc_customer:
                            self.migration_report['customers']['failed'] += 1
                            continue
                            
                        result = self.woocommerce.create_customer(wc_customer)
                        if result:
                            self.id_mappings['customers'][str(customer.get('id'))] = result.get('id')
                            self.log(f"Created customer: {customer.get('email', 'Unknown')}")
                            # Success counted at end
                        else:
                            self.migration_report['customers']['failed'] += 1
                            self.log(f"Failed to create customer: {customer.get('email', 'Unknown')}", 'ERROR')
                            continue  # Skip success increment
                    
                    # Count as successful (either skipped existing or created new)
                    self.migration_report['customers']['successful'] += 1
                            
                except Exception as e:
                    self.log(f"Failed to migrate customer {customer.get('id', 'unknown')}: {e}", 'ERROR')
                    self.migration_report['customers']['failed'] += 1
                    self.migration_report['errors'].append(f"Customer migration error: {str(e)}")
                    
        except Exception as e:
            self.log(f"Error in customer migration: {e}", 'ERROR')
    
    def migrate_orders(self, dry_run=False):
        """Migrate Shopify orders to WooCommerce"""
        try:
            orders = self.shopify.get_orders()
            self.migration_report['orders']['attempted'] = len(orders)
            
            for order in tqdm(orders, desc="Migrating orders"):
                try:
                    if dry_run:
                        # Validate order mapping in dry run
                        wc_order = DataMapper.map_order(order, self.id_mappings['customers'])
                        if wc_order:
                            self.log(f"[DRY RUN] Would create order: {order.get('order_number', 'Unknown')}")
                            self.migration_report['orders']['successful'] += 1
                        else:
                            self.log(f"[DRY RUN] Would fail to create order: {order.get('order_number', 'Unknown')} (mapping failed)")
                            self.migration_report['orders']['failed'] += 1
                    else:
                        wc_order = DataMapper.map_order(order, self.id_mappings['customers'])
                        if not wc_order:
                            self.migration_report['orders']['failed'] += 1
                            continue
                        
                        # Map line items to WooCommerce products
                        self.map_order_line_items(wc_order, order)
                        
                        result = self.woocommerce.create_order(wc_order)
                        if result:
                            self.migration_report['orders']['successful'] += 1
                            self.log(f"Created order: {order.get('order_number', 'Unknown')}")
                        else:
                            self.migration_report['orders']['failed'] += 1
                            
                except Exception as e:
                    self.log(f"Failed to migrate order {order.get('id', 'unknown')}: {e}", 'ERROR')
                    self.migration_report['orders']['failed'] += 1
                    self.migration_report['errors'].append(f"Order migration error: {str(e)}")
                    
        except Exception as e:
            self.log(f"Error in order migration: {e}", 'ERROR')
    
    def map_order_line_items(self, wc_order, shopify_order):
        """Map Shopify line items to WooCommerce products"""
        for item in wc_order.get('line_items', []):
            shopify_variant_id = None
            shopify_product_id = None
            
            # Extract Shopify IDs from meta_data
            for meta in item.get('meta_data', []):
                if meta.get('key') == 'shopify_variant_id':
                    shopify_variant_id = meta.get('value')
                elif meta.get('key') == 'shopify_product_id':
                    shopify_product_id = meta.get('value')
            
            # Map to WooCommerce product/variation ID
            if shopify_variant_id and shopify_variant_id in self.id_mappings['variants']:
                item['variation_id'] = self.id_mappings['variants'][shopify_variant_id]
            elif shopify_product_id and shopify_product_id in self.id_mappings['products']:
                item['product_id'] = self.id_mappings['products'][shopify_product_id]
    
    def migrate_coupons(self, dry_run=False):
        """Migrate Shopify discount codes to WooCommerce coupons"""
        try:
            discounts = self.shopify.get_discounts()
            
            if not discounts:
                self.log("No discount codes found to migrate")
                return
                
            self.migration_report['coupons']['attempted'] = len(discounts)
            
            for discount in discounts:
                try:
                    if dry_run:
                        # Validate coupon mapping in dry run
                        wc_coupon = DataMapper.map_coupon(discount)
                        discount_name = discount.get('title', discount.get('code', 'Unknown'))
                        if wc_coupon:
                            self.log(f"[DRY RUN] Would create coupon: {discount_name}")
                            self.migration_report['coupons']['successful'] += 1
                        else:
                            self.log(f"[DRY RUN] Would fail to create coupon: {discount_name} (mapping failed)")
                            self.migration_report['coupons']['failed'] += 1
                    else:
                        wc_coupon = DataMapper.map_coupon(discount)
                        if not wc_coupon:
                            self.migration_report['coupons']['failed'] += 1
                            continue
                            
                        result = self.woocommerce.create_coupon(wc_coupon)
                        if result:
                            self.migration_report['coupons']['successful'] += 1
                            discount_name = discount.get('title', discount.get('code', 'Unknown'))
                            self.log(f"Created coupon: {discount_name}")
                        else:
                            self.migration_report['coupons']['failed'] += 1
                            
                except Exception as e:
                    self.log(f"Failed to migrate discount {discount.get('id', 'unknown')}: {e}", 'ERROR')
                    self.migration_report['coupons']['failed'] += 1
                    self.migration_report['errors'].append(f"Coupon migration error: {str(e)}")
                    
        except Exception as e:
            self.log(f"Error in coupon migration: {e}", 'ERROR')
    
    def migrate_pages(self, dry_run=False):
        """Migrate Shopify pages and blog articles to WordPress"""
        try:
            pages = self.shopify.get_pages()
            blogs = self.shopify.get_blogs()
            
            # Separate pages and articles for different handling
            all_pages = pages
            all_articles = []
            
            # Add blog articles
            for blog in blogs:
                articles = self.shopify.get_blog_articles(blog.get('id'))
                all_articles.extend(articles)
            
            all_content = all_pages + all_articles
            self.migration_report['pages']['attempted'] = len(all_content)
            
            # Check if WordPress is configured
            if not self.wordpress:
                for content in all_content:
                    content_title = content.get('title', 'Unknown')
                    if dry_run:
                        self.log(f"[DRY RUN] Would skip (WordPress not configured): {content_title}")
                    else:
                        self.log(f"[SKIP] WordPress not configured: {content_title}")
                    self.migration_report['pages']['failed'] += 1
                return
            
            # Migrate pages
            for page in all_pages:
                try:
                    page_title = page.get('title', 'Unknown')
                    page_slug = page.get('handle', '')
                    
                    # Check for existing page
                    existing_page = None
                    if page_title:
                        existing_page = next((p for p in self.existing_pages if p.get('title', {}).get('rendered') == page_title), None)
                    if not existing_page and page_slug:
                        existing_page = next((p for p in self.existing_pages if p.get('slug') == page_slug), None)
                    
                    if existing_page:
                        mode_text = "DRY RUN" if dry_run else "LIVE"
                        self.log(f"[{mode_text}] Skipped existing page: {page_title}")
                        # Success counted at end
                    elif dry_run:
                        wp_page = DataMapper.map_page(page)
                        if wp_page:
                            self.log(f"[DRY RUN] Would create page: {page_title}")
                            # Success counted at end
                        else:
                            self.log(f"[DRY RUN] Would fail to create page: {page_title} (mapping failed)")
                            self.migration_report['pages']['failed'] += 1
                            continue  # Skip success increment
                    else:
                        wp_page = DataMapper.map_page(page)
                        if not wp_page:
                            self.migration_report['pages']['failed'] += 1
                            continue
                            
                        result = self.wordpress.create_page(wp_page)
                        if result:
                            self.log(f"Created page: {page_title}")
                            # Success counted at end
                        else:
                            self.migration_report['pages']['failed'] += 1
                            self.log(f"Failed to create page: {page_title}", 'ERROR')
                            continue  # Skip success increment
                    
                    # Count as successful (either skipped existing or created new)
                    self.migration_report['pages']['successful'] += 1
                            
                except Exception as e:
                    self.log(f"Failed to migrate page {page.get('id', 'unknown')}: {e}", 'ERROR')
                    self.migration_report['pages']['failed'] += 1
                    self.migration_report['errors'].append(f"Page migration error: {str(e)}")
            
            # Migrate blog articles as posts
            for article in all_articles:
                try:
                    article_title = article.get('title', 'Unknown')
                    article_slug = article.get('handle', '')
                    
                    if dry_run:
                        wp_post = DataMapper.map_blog_article(article)
                        if wp_post:
                            self.log(f"[DRY RUN] Would create blog post: {article_title}")
                            # Success counted at end
                        else:
                            self.log(f"[DRY RUN] Would fail to create blog post: {article_title} (mapping failed)")
                            self.migration_report['pages']['failed'] += 1
                            continue  # Skip success increment
                    else:
                        wp_post = DataMapper.map_blog_article(article)
                        if not wp_post:
                            self.migration_report['pages']['failed'] += 1
                            continue
                            
                        result = self.wordpress.create_post(wp_post)
                        if result:
                            self.log(f"Created blog post: {article_title}")
                            # Success counted at end
                        else:
                            self.migration_report['pages']['failed'] += 1
                            self.log(f"Failed to create blog post: {article_title}", 'ERROR')
                            continue  # Skip success increment
                    
                    # Count as successful (either created page or blog post)
                    self.migration_report['pages']['successful'] += 1
                            
                except Exception as e:
                    self.log(f"Failed to migrate article {article.get('id', 'unknown')}: {e}", 'ERROR')
                    self.migration_report['pages']['failed'] += 1
                    self.migration_report['errors'].append(f"Article migration error: {str(e)}")
                    
        except Exception as e:
            self.log(f"Error in page migration: {e}", 'ERROR')
    
    def generate_migration_report(self, dry_run=False):
        """Generate and log the migration report"""
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
            self.log(f"ERRORS: {len(self.migration_report['errors'])}")
            for error in self.migration_report['errors'][:5]:  # Show first 5 errors
                self.log(f"  - {error}")
        
        # Save report to file in logs directory
        import os
        os.makedirs("logs", exist_ok=True)
        report_file = os.path.join("logs", f"migration_report_{'dry_run' if dry_run else 'live'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        try:
            with open(report_file, 'w') as f:
                json.dump(self.migration_report, f, indent=2, default=str)
            self.log(f"Report saved to: {report_file}")
        except Exception as e:
            self.log(f"Failed to save report: {e}", 'ERROR')