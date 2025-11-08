"""
WordPress REST API client for page migration
"""
import requests
import time
from requests.auth import HTTPBasicAuth
from logger import setup_logger

logger = setup_logger(__name__)

class WordPressClient:
    def __init__(self, url, username, password, max_retries=3, delay=1.0):
        """
        Initialize WordPress API client
        
        Args:
            url: WordPress site URL (same as WooCommerce URL typically)
            username: WordPress admin username  
            password: WordPress application password (not regular password!)
        """
        self.url = url.rstrip('/')
        self.username = username
        self.password = password
        self.max_retries = max_retries
        self.delay = delay
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(username, password)
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'Shopify-WordPress-Migrator/1.0'
        })
        
    def _make_request(self, method, endpoint, **kwargs):
        """Make API request with retry logic"""
        url = f"{self.url}/wp-json/wp/v2/{endpoint}"
        
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
        
    def test_connection(self):
        """Test connection to WordPress"""
        try:
            response = self._make_request('GET', 'users/me')
            if response:
                logger.info(f"Successfully connected to WordPress as user: {response.get('name', 'Unknown')}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to connect to WordPress: {e}")
            return False
    
    def create_page(self, page_data):
        """Create a WordPress page"""
        try:
            response = self._make_request('POST', 'pages', json=page_data)
            if response:
                logger.debug(f"Created page: {page_data.get('title', {}).get('rendered', 'Unknown')}")
            return response
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error creating page: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Failed to create page {page_data.get('title', 'Unknown')}: {e}")
            return None
    
    def create_post(self, post_data):
        """Create a WordPress post (for blog articles)"""
        try:
            response = self._make_request('POST', 'posts', json=post_data)
            if response:
                logger.debug(f"Created post: {post_data.get('title', {}).get('rendered', 'Unknown')}")
            return response
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error creating post: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Failed to create post {post_data.get('title', 'Unknown')}: {e}")
            return None
    
    def get_existing_pages(self):
        """Get all existing pages"""
        try:
            pages = []
            page = 1
            per_page = 100
            
            while True:
                params = {'page': page, 'per_page': per_page}
                response = self._make_request('GET', 'pages', params=params)
                
                if not response:
                    break
                    
                pages.extend(response)
                
                if len(response) < per_page:
                    break
                    
                page += 1
                
            return pages
        except Exception as e:
            logger.error(f"Failed to get existing pages: {e}")
            return []
    
    def get_existing_posts(self):
        """Get all existing posts"""
        try:
            posts = []
            page = 1
            per_page = 100
            
            while True:
                params = {'page': page, 'per_page': per_page}
                response = self._make_request('GET', 'posts', params=params)
                
                if not response:
                    break
                    
                posts.extend(response)
                
                if len(response) < per_page:
                    break
                    
                page += 1
                
            return posts
        except Exception as e:
            logger.error(f"Failed to get existing posts: {e}")
            return []