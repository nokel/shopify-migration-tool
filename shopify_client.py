import requests
import time
from urllib.parse import urljoin
from logger import setup_logger

logger = setup_logger(__name__)

class ShopifyClient:
    def __init__(self, store_url, access_token, max_retries=3, delay=1):
        self.store_url = store_url.rstrip('/')
        self.access_token = access_token
        self.max_retries = max_retries
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            'X-Shopify-Access-Token': access_token,
            'Content-Type': 'application/json'
        })
        
    def _make_request(self, method, endpoint, **kwargs):
        """Make API request with retry logic"""
        url = f"{self.store_url}/admin/api/2023-10/{endpoint}"
        
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
                return response.json()
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request failed (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.delay * (2 ** attempt))  # Exponential backoff
                else:
                    raise
                    
        time.sleep(self.delay)  # Rate limiting
        
    def get_paginated_data(self, endpoint, limit=250):
        """Get all data from a paginated endpoint"""
        all_data = []
        params = {'limit': limit}
        
        while True:
            try:
                response = self._make_request('GET', endpoint, params=params)
                
                # Extract the resource name from endpoint
                resource = endpoint.split('.json')[0].split('/')[-1]
                items = response.get(resource, [])
                
                if not items:
                    break
                    
                all_data.extend(items)
                logger.info(f"Retrieved {len(items)} {resource}, total: {len(all_data)}")
                
                # Check for pagination
                link_header = self.session.get(f"{self.store_url}/admin/api/2023-10/{endpoint}", params=params).headers.get('Link')
                
                if not link_header or 'rel="next"' not in link_header:
                    break
                    
                # Extract next page info
                next_link = None
                for link in link_header.split(','):
                    if 'rel="next"' in link:
                        next_link = link.split('<')[1].split('>')[0]
                        break
                        
                if next_link:
                    # Extract page_info from next link
                    if 'page_info=' in next_link:
                        page_info = next_link.split('page_info=')[1].split('&')[0]
                        params = {'limit': limit, 'page_info': page_info}
                    else:
                        break
                else:
                    break
                    
            except Exception as e:
                logger.error(f"Error fetching {endpoint}: {e}")
                break
                
        return all_data
    
    def get_products(self):
        """Get all products"""
        logger.info("Fetching products from Shopify...")
        return self.get_paginated_data('products.json')
    
    def get_customers(self):
        """Get all customers"""
        logger.info("Fetching customers from Shopify...")
        return self.get_paginated_data('customers.json')
    
    def get_orders(self):
        """Get all orders"""
        logger.info("Fetching orders from Shopify...")
        return self.get_paginated_data('orders.json?status=any')
    
    def get_pages(self):
        """Get all pages"""
        logger.info("Fetching pages from Shopify...")
        return self.get_paginated_data('pages.json')
    
    def get_blogs(self):
        """Get all blogs"""
        logger.info("Fetching blogs from Shopify...")
        return self.get_paginated_data('blogs.json')
        
    def get_blog_articles(self, blog_id):
        """Get all articles for a specific blog"""
        logger.info(f"Fetching articles for blog {blog_id}...")
        return self.get_paginated_data(f'blogs/{blog_id}/articles.json')
    
    def get_collections(self):
        """Get all collections"""
        logger.info("Fetching collections from Shopify...")
        custom_collections = self.get_paginated_data('custom_collections.json')
        smart_collections = self.get_paginated_data('smart_collections.json')
        return custom_collections + smart_collections
    
    def get_discounts(self):
        """Get all discount codes"""
        logger.info("Fetching discount codes from Shopify...")
        return self.get_paginated_data('discount_codes.json')
        
    def test_connection(self):
        """Test the connection to Shopify"""
        try:
            response = self._make_request('GET', 'shop.json')
            shop_name = response.get('shop', {}).get('name', 'Unknown')
            logger.info(f"Successfully connected to Shopify store: {shop_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Shopify: {e}")
            return False