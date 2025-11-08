import requests
import time
from requests.auth import HTTPBasicAuth
from logger import setup_logger

logger = setup_logger(__name__)

class WooCommerceClient:
    def __init__(self, url, consumer_key, consumer_secret, max_retries=3, delay=1.0, dry_run=False):
        self.url = url.rstrip('/')
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.max_retries = max_retries
        self.delay = delay
        self.dry_run = dry_run
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(consumer_key, consumer_secret)
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'Shopify-WooCommerce-Migrator/1.0'
        })
        
    def _make_request(self, method, endpoint, **kwargs):
        """Make API request with retry logic"""
        url = f"{self.url}/wp-json/wc/v3/{endpoint}"
        
        for attempt in range(self.max_retries):
            try:
                response = self.session.request(method, url, **kwargs)
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    logger.warning(f"Rate limited. Waiting {retry_after} seconds...")
                    time.sleep(retry_after)
                    continue
                    
                response.raise_for_status()
                return response.json() if response.content else None
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request failed (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.delay * (2 ** attempt))  # Exponential backoff
                else:
                    raise
                    
        time.sleep(self.delay)  # Rate limiting
    
    def create_product(self, product_data, include_images=True):
        """Create a product in WooCommerce
        
        Args:
            product_data: Product data dictionary
            include_images: If False, removes images from product_data to avoid timeout issues
        """
        try:
            # Optionally strip images to avoid server timeout during image processing
            if not include_images and 'images' in product_data:
                images = product_data.pop('images')
                logger.debug(f"Stripped {len(images)} images from product {product_data.get('name')} to avoid timeout")
            
            response = self._make_request('POST', 'products', json=product_data)
            logger.debug(f"Created product: {product_data.get('name', 'Unknown')}")
            return response
        except requests.exceptions.HTTPError as e:
            error_text = ""
            try:
                error_text = e.response.text[:500] if e.response.text else "No error details"
            except:
                error_text = "Could not read error response"
            logger.error(f"HTTP error creating product {product_data.get('name', 'Unknown')}: {e.response.status_code} - {error_text}")
            return None
        except Exception as e:
            logger.error(f"Failed to create product {product_data.get('name', 'Unknown')}: {e}")
            return None
    
    def update_product(self, product_id, product_data):
        """Update an existing product in WooCommerce
        
        Args:
            product_id: WooCommerce product ID
            product_data: Product data dictionary (only fields to update)
            
        Returns:
            Updated product object if successful, None otherwise
        """
        try:
            response = self._make_request('PUT', f'products/{product_id}', json=product_data)
            logger.debug(f"Updated product: {product_id}")
            return response
        except requests.exceptions.HTTPError as e:
            error_text = ""
            try:
                error_text = e.response.text[:500] if e.response.text else "No error details"
            except:
                error_text = "Could not read error response"
            logger.error(f"HTTP error updating product {product_id}: {e.response.status_code} - {error_text}")
            return None
        except Exception as e:
            logger.error(f"Failed to update product {product_id}: {e}")
            return None
    
    def update_product_images(self, product_id, images):
        """Update product images separately (to avoid timeout during product creation)
        
        Args:
            product_id: WooCommerce product ID
            images: List of image dicts with 'src', 'name', 'alt'
        """
        try:
            update_data = {'images': images}
            response = self._make_request('PUT', f'products/{product_id}', json=update_data)
            logger.debug(f"Updated images for product ID {product_id}: {len(images)} images")
            return response
        except requests.exceptions.HTTPError as e:
            error_text = ""
            try:
                error_text = e.response.text[:500] if e.response.text else "No error details"
            except:
                error_text = "Could not read error response"
            logger.error(f"HTTP error updating images for product {product_id}: {e.response.status_code} - {error_text}")
            return None
        except Exception as e:
            logger.error(f"Failed to update images for product {product_id}: {e}")
            return None
    
    def create_customer(self, customer_data):
        """Create a customer in WooCommerce"""
        try:
            response = self._make_request('POST', 'customers', json=customer_data)
            logger.debug(f"Created customer: {customer_data.get('email', 'Unknown')}")
            return response
        except requests.exceptions.HTTPError as e:
            error_text = ""
            try:
                error_text = e.response.text[:500] if e.response.text else "No error details"
            except:
                error_text = "Could not read error response"
            logger.error(f"HTTP error creating customer {customer_data.get('email', 'Unknown')}: {e.response.status_code} - {error_text}")
            return None
        except Exception as e:
            logger.error(f"Failed to create customer {customer_data.get('email', 'Unknown')}: {e}")
            return None
    
    def create_order(self, order_data):
        """Create an order in WooCommerce"""
        try:
            response = self._make_request('POST', 'orders', json=order_data)
            logger.debug(f"Created order: {order_data.get('number', 'Unknown')}")
            return response
        except requests.exceptions.HTTPError as e:
            error_text = ""
            try:
                error_text = e.response.text[:500] if e.response.text else "No error details"
            except:
                error_text = "Could not read error response"
            logger.error(f"HTTP error creating order {order_data.get('number', 'Unknown')}: {e.response.status_code} - {error_text}")
            return None
        except Exception as e:
            logger.error(f"Failed to create order {order_data.get('number', 'Unknown')}: {e}")
            return None
    
    def update_order(self, order_id, order_data):
        """Update an existing order in WooCommerce
        
        Args:
            order_id: WooCommerce order ID to update
            order_data: Order data dictionary (only fields to update)
            
        Returns:
            Updated order object if successful, None otherwise
        """
        try:
            response = self._make_request('PUT', f'orders/{order_id}', json=order_data)
            logger.debug(f"Updated order: {order_id}")
            return response
        except requests.exceptions.HTTPError as e:
            error_text = ""
            try:
                error_text = e.response.text[:500] if e.response.text else "No error details"
            except:
                error_text = "Could not read error response"
            logger.error(f"HTTP error updating order {order_id}: {e.response.status_code} - {error_text}")
            return None
        except Exception as e:
            logger.error(f"Failed to update order {order_id}: {e}")
            return None
    
    def add_order_note(self, order_id, note_text, customer_note=False):
        """Add a note to an order
        
        Args:
            order_id: WooCommerce order ID
            note_text: Text of the note
            customer_note: If True, note is visible to customer (default: False for private notes)
            
        Returns:
            Note object if successful, None otherwise
        """
        try:
            note_data = {
                'note': note_text,
                'customer_note': customer_note
            }
            response = self._make_request('POST', f'orders/{order_id}/notes', json=note_data)
            logger.debug(f"Added note to order {order_id}")
            return response
        except requests.exceptions.HTTPError as e:
            error_text = ""
            try:
                error_text = e.response.text[:500] if e.response.text else "No error details"
            except:
                error_text = "Could not read error response"
            logger.error(f"HTTP error adding note to order {order_id}: {e.response.status_code} - {error_text}")
            return None
        except Exception as e:
            logger.error(f"Failed to add note to order {order_id}: {e}")
            return None
    
    def create_coupon(self, coupon_data):
        """Create a coupon in WooCommerce"""
        try:
            response = self._make_request('POST', 'coupons', json=coupon_data)
            logger.debug(f"Created coupon: {coupon_data.get('code', 'Unknown')}")
            return response
        except requests.exceptions.HTTPError as e:
            error_text = ""
            try:
                error_text = e.response.text[:500] if e.response.text else "No error details"
            except:
                error_text = "Could not read error response"
            logger.error(f"HTTP error creating coupon {coupon_data.get('code', 'Unknown')}: {e.response.status_code} - {error_text}")
            return None
        except Exception as e:
            logger.error(f"Failed to create coupon {coupon_data.get('code', 'Unknown')}: {e}")
            return None
    
    def create_product_category(self, category_data):
        """Create a product category in WooCommerce"""
        try:
            response = self._make_request('POST', 'products/categories', json=category_data)
            logger.debug(f"Created category: {category_data.get('name', 'Unknown')}")
            return response
        except requests.exceptions.HTTPError as e:
            error_text = ""
            try:
                error_text = e.response.text[:500] if e.response.text else "No error details"
            except:
                error_text = "Could not read error response"
            logger.error(f"HTTP error creating category {category_data.get('name', 'Unknown')}: {e.response.status_code} - {error_text}")
            return None
        except Exception as e:
            logger.error(f"Failed to create category {category_data.get('name', 'Unknown')}: {e}")
            return None
    
    def create_product_tag(self, tag_data):
        """Create a product tag in WooCommerce"""
        try:
            response = self._make_request('POST', 'products/tags', json=tag_data)
            logger.debug(f"Created tag: {tag_data.get('name', 'Unknown')}")
            return response
        except Exception as e:
            logger.error(f"Failed to create tag {tag_data.get('name', 'Unknown')}: {e}")
            return None
    
    def get_existing_customers(self):
        """Get all existing customers"""
        try:
            customers = []
            page = 1
            per_page = 100
            
            while True:
                params = {'page': page, 'per_page': per_page}
                response = self._make_request('GET', 'customers', params=params)
                
                if not response:
                    break
                    
                customers.extend(response)
                
                if len(response) < per_page:
                    break
                    
                page += 1
                
            return customers
        except Exception as e:
            logger.error(f"Failed to get existing customers: {e}")
            return []
    
    def get_existing_products(self):
        """Get all existing products"""
        try:
            products = []
            page = 1
            per_page = 100
            
            while True:
                params = {'page': page, 'per_page': per_page}
                response = self._make_request('GET', 'products', params=params)
                
                if not response:
                    break
                    
                products.extend(response)
                
                if len(response) < per_page:
                    break
                    
                page += 1
                
            return products
        except Exception as e:
            logger.error(f"Failed to get existing products: {e}")
            return []
    
    def get_existing_categories(self):
        """Get all existing product categories"""
        try:
            categories = []
            page = 1
            per_page = 100
            
            while True:
                params = {'page': page, 'per_page': per_page}
                response = self._make_request('GET', 'products/categories', params=params)
                
                if not response:
                    break
                    
                categories.extend(response)
                
                if len(response) < per_page:
                    break
                    
                page += 1
                
            return categories
        except Exception as e:
            logger.error(f"Failed to get existing categories: {e}")
            return []
    
    def get_existing_orders(self):
        """Get all existing orders with their metadata"""
        try:
            orders = []
            page = 1
            per_page = 100
            
            while True:
                params = {'page': page, 'per_page': per_page}
                response = self._make_request('GET', 'orders', params=params)
                
                if not response:
                    break
                    
                orders.extend(response)
                
                if len(response) < per_page:
                    break
                    
                page += 1
                
            logger.info(f"Fetched {len(orders)} existing orders from WooCommerce")
            return orders
        except Exception as e:
            logger.error(f"Failed to get existing orders: {e}")
            return []
    
    def batch_create_products(self, products_data):
        """Create multiple products in a single batch request"""
        try:
            batch_data = {
                'create': products_data
            }
            response = self._make_request('POST', 'products/batch', json=batch_data)
            logger.info(f"Batch created {len(products_data)} products")
            return response
        except Exception as e:
            logger.error(f"Failed to batch create products: {e}")
            return None
    
    def batch_create_customers(self, customers_data):
        """Create multiple customers in a single batch request"""
        try:
            batch_data = {
                'create': customers_data
            }
            response = self._make_request('POST', 'customers/batch', json=batch_data)
            logger.info(f"Batch created {len(customers_data)} customers")
            return response
        except Exception as e:
            logger.error(f"Failed to batch create customers: {e}")
            return None
    def clear_all_data(self, confirm_phrase="DELETE ALL DATA"):
        """Clear all WooCommerce data - USE WITH EXTREME CAUTION"""
        if confirm_phrase != "DELETE ALL DATA":
            logger.error("Confirmation phrase is required to clear all data")
            return False
            
        try:
            # Delete all products
            products = self.get_existing_products()
            for product in products:
                self._make_request('DELETE', f'products/{product["id"]}', params={'force': True})
            logger.info(f"Deleted {len(products)} products")
            
            # Delete all customers
            customers = self.get_existing_customers()
            for customer in customers:
                self._make_request('DELETE', f'customers/{customer["id"]}', params={'force': True})
            logger.info(f"Deleted {len(customers)} customers")
            
            # Delete all orders
            orders = []
            page = 1
            while True:
                response = self._make_request('GET', 'orders', params={'page': page, 'per_page': 100})
                if not response:
                    break
                orders.extend(response)
                if len(response) < 100:
                    break
                page += 1
            
            for order in orders:
                self._make_request('DELETE', f'orders/{order["id"]}', params={'force': True})
            logger.info(f"Deleted {len(orders)} orders")
            
            return True
        except Exception as e:
            logger.error(f"Failed to clear WooCommerce data: {e}")
            return False
            
    def test_connection(self):
        """Test the connection to WooCommerce"""
        try:
            response = self._make_request('GET', 'system_status')
            if response:
                logger.info("Successfully connected to WooCommerce")
                return True
            else:
                logger.error("Failed to connect to WooCommerce")
                return False
        except Exception as e:
            logger.error(f"Failed to connect to WooCommerce: {e}")
            return False