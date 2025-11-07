import requests
import time
from requests.auth import HTTPBasicAuth
from logger import setup_logger

logger = setup_logger(__name__)

class WooCommerceClient:
    def __init__(self, url, consumer_key, consumer_secret, max_retries=3, delay=1):
        self.url = url.rstrip('/')
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.max_retries = max_retries
        self.delay = delay
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
    
    def create_product(self, product_data):
        """Create a product in WooCommerce"""
        try:
            response = self._make_request('POST', 'products', json=product_data)
            logger.debug(f"Created product: {product_data.get('name', 'Unknown')}")
            return response
        except Exception as e:
            logger.error(f"Failed to create product {product_data.get('name', 'Unknown')}: {e}")
            return None
    
    def create_customer(self, customer_data):
        """Create a customer in WooCommerce"""
        try:
            response = self._make_request('POST', 'customers', json=customer_data)
            logger.debug(f"Created customer: {customer_data.get('email', 'Unknown')}")
            return response
        except Exception as e:
            logger.error(f"Failed to create customer {customer_data.get('email', 'Unknown')}: {e}")
            return None
    
    def create_order(self, order_data):
        """Create an order in WooCommerce"""
        try:
            response = self._make_request('POST', 'orders', json=order_data)
            logger.debug(f"Created order: {order_data.get('number', 'Unknown')}")
            return response
        except Exception as e:
            logger.error(f"Failed to create order {order_data.get('number', 'Unknown')}: {e}")
            return None
    
    def create_coupon(self, coupon_data):
        """Create a coupon in WooCommerce"""
        try:
            response = self._make_request('POST', 'coupons', json=coupon_data)
            logger.debug(f"Created coupon: {coupon_data.get('code', 'Unknown')}")
            return response
        except Exception as e:
            logger.error(f"Failed to create coupon {coupon_data.get('code', 'Unknown')}: {e}")
            return None
    
    def create_product_category(self, category_data):
        """Create a product category in WooCommerce"""
        try:
            response = self._make_request('POST', 'products/categories', json=category_data)
            logger.debug(f"Created category: {category_data.get('name', 'Unknown')}")
            return response
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