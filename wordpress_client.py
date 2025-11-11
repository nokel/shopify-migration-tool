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
            # Log what we're sending for debugging
            title = page_data.get('title', 'Unknown')
            content_length = len(page_data.get('content', ''))
            logger.info(f"Creating page: title='{title}' content_length={content_length}")
            logger.debug(f"Page data: {page_data}")
            
            response = self._make_request('POST', 'pages', json=page_data)
            if response:
                logger.info(f"Created page: {title}")
            return response
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error creating page: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            title = page_data.get('title', 'Unknown')
            logger.error(f"Failed to create page {title}: {e}")
            return None
    
    def create_post(self, post_data):
        """Create a WordPress post (for blog articles)"""
        try:
            response = self._make_request('POST', 'posts', json=post_data)
            if response:
                title = post_data.get('title', 'Unknown')
                logger.debug(f"Created post: {title}")
            return response
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error creating post: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            title = post_data.get('title', 'Unknown')
            logger.error(f"Failed to create post {title}: {e}")
            return None
    
    def delete_page(self, page_id):
        """Delete a WordPress page"""
        try:
            response = self._make_request('DELETE', f'pages/{page_id}', params={'force': True})
            logger.debug(f"Deleted page: {page_id}")
            return response
        except Exception as e:
            logger.error(f"Failed to delete page {page_id}: {e}")
            return None
    
    def delete_post(self, post_id):
        """Delete a WordPress post"""
        try:
            response = self._make_request('DELETE', f'posts/{post_id}', params={'force': True})
            logger.debug(f"Deleted post: {post_id}")
            return response
        except Exception as e:
            logger.error(f"Failed to delete post {post_id}: {e}")
            return None
    
    def get_existing_media(self):
        """Get all existing media items"""
        try:
            media = []
            page = 1
            per_page = 100
            
            while True:
                params = {
                    'page': page,
                    'per_page': per_page,
                    'status': 'inherit'  # Media uses 'inherit' status
                }
                response = self._make_request('GET', 'media', params=params)
                
                if not response:
                    break
                    
                media.extend(response)
                
                if len(response) < per_page:
                    break
                    
                page += 1
                
            return media
        except Exception as e:
            logger.error(f"Failed to get existing media: {e}")
            return []
    
    def get_media(self, page=1, per_page=100):
        """Get media items from WordPress media library"""
        try:
            params = {'page': page, 'per_page': per_page}
            response = self._make_request('GET', 'media', params=params)
            return response if response else []
        except Exception as e:
            logger.error(f"Failed to get media (page {page}): {e}")
            return []
    
    def delete_media(self, media_id):
        """Delete a WordPress media item"""
        try:
            response = self._make_request('DELETE', f'media/{media_id}', params={'force': True})
            logger.debug(f"Deleted media: {media_id}")
            return response
        except Exception as e:
            logger.error(f"Failed to delete media {media_id}: {e}")
            return None
    
    def get_existing_pages(self):
        """Get all existing pages (all statuses)"""
        try:
            pages = []
            page = 1
            per_page = 100
            
            while True:
                # Include all statuses: publish, draft, pending, private
                params = {
                    'page': page, 
                    'per_page': per_page,
                    'status': 'publish,draft,pending,private'
                }
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
        """Get all existing posts (all statuses)"""
        try:
            posts = []
            page = 1
            per_page = 100
            
            while True:
                # Include all statuses: publish, draft, pending, private
                params = {
                    'page': page, 
                    'per_page': per_page,
                    'status': 'publish,draft,pending,private'
                }
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