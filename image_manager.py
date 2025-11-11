"""
Image Manager - Downloads images from Shopify and uploads to WordPress Media Library
"""
import os
import requests
import time
import mimetypes
from pathlib import Path
from logger import setup_logger

logger = setup_logger(__name__)

class ImageManager:
    def __init__(self, wordpress_url, consumer_key, consumer_secret, wp_username=None, wp_app_password=None):
        """Initialize image manager with WordPress credentials
        
        Args:
            wordpress_url: WordPress site URL
            consumer_key: WooCommerce consumer key (fallback auth)
            consumer_secret: WooCommerce consumer secret (fallback auth)
            wp_username: WordPress username (preferred for Media API)
            wp_app_password: WordPress application password (preferred for Media API)
        """
        self.wordpress_url = wordpress_url.rstrip('/')
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.wp_username = wp_username
        self.wp_app_password = wp_app_password.replace(' ', '') if wp_app_password else None
        
        # Determine which auth to use
        if self.wp_username and self.wp_app_password:
            self.auth = (self.wp_username, self.wp_app_password)
            logger.info("Using WordPress username/app password for Media API")
        else:
            self.auth = (self.consumer_key, self.consumer_secret)
            logger.info("Using WooCommerce consumer key/secret for Media API")
        
        # Create images directory one level up from main script
        script_dir = Path(__file__).parent
        self.images_dir = script_dir.parent / "shopify_images"
        self.images_dir.mkdir(exist_ok=True)
        
        logger.info(f"Image directory: {self.images_dir}")
    
    def download_image(self, image_url, product_name, image_index=0):
        """Download image from Shopify to local directory
        
        Args:
            image_url: URL of the image to download
            product_name: Name of product (for filename)
            image_index: Index of image (for multiple images)
            
        Returns:
            Path to downloaded file or None if failed
        """
        try:
            # Sanitize product name for filename
            safe_name = "".join(c for c in product_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_name = safe_name.replace(' ', '_')[:50]  # Limit length
            
            # Get file extension from URL
            ext = Path(image_url.split('?')[0]).suffix or '.jpg'
            
            # Create filename
            filename = f"{safe_name}_{image_index}{ext}"
            filepath = self.images_dir / filename
            
            # Check if already downloaded
            if filepath.exists():
                logger.debug(f"Image already exists: {filename}")
                return filepath
            
            # Download image
            logger.debug(f"Downloading image: {image_url}")
            response = requests.get(image_url, timeout=30, stream=True)
            response.raise_for_status()
            
            # Save to file
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"Downloaded image: {filename} ({os.path.getsize(filepath)} bytes)")
            return filepath
            
        except Exception as e:
            logger.error(f"Failed to download image {image_url}: {e}")
            return None
    
    def upload_to_wordpress(self, filepath, alt_text='', title=''):
        """Upload local image file to WordPress Media Library
        
        Args:
            filepath: Path to local image file
            alt_text: Alt text for image
            title: Title for image
            
        Returns:
            WordPress media ID or None if failed
        """
        try:
            filepath = Path(filepath)
            
            if not filepath.exists():
                logger.error(f"Image file not found: {filepath}")
                return None
            
            # Prepare file for upload
            filename = filepath.name
            
            # Check if image already exists in media library by filename
            existing_media = self._find_existing_media(filename)
            if existing_media:
                logger.info(f"Image already exists in media library: {filename} (ID: {existing_media['id']})")
                return existing_media
            
            # Determine MIME type
            mime_type, _ = mimetypes.guess_type(str(filepath))
            if not mime_type:
                mime_type = 'image/jpeg'
            
            # Read file content
            with open(filepath, 'rb') as f:
                file_data = f.read()
            
            # Upload to WordPress Media API
            url = f"{self.wordpress_url}/wp-json/wp/v2/media"
            
            headers = {
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Content-Type': mime_type,
                'User-Agent': 'Shopify-WooCommerce-Migrator/1.0'  # Bypass Mod_Security
            }
            
            response = requests.post(
                url,
                auth=self.auth,
                headers=headers,
                data=file_data,
                timeout=60
            )
            
            response.raise_for_status()
            media = response.json()
            
            media_id = media.get('id')
            media_url = media.get('source_url')
            
            logger.info(f"Uploaded image to WordPress: {filename} (ID: {media_id})")
            
            # Update alt text and title if provided
            if alt_text or title:
                update_url = f"{self.wordpress_url}/wp-json/wp/v2/media/{media_id}"
                update_data = {}
                if alt_text:
                    update_data['alt_text'] = alt_text
                if title:
                    update_data['title'] = title
                
                if update_data:
                    requests.post(
                        update_url,
                        auth=self.auth,
                        headers={'User-Agent': 'Shopify-WooCommerce-Migrator/1.0'},
                        json=update_data,
                        timeout=30
                    )
            
            return {
                'id': media_id,
                'src': media_url,
                'name': title or filename,
                'alt': alt_text
            }
            
        except Exception as e:
            logger.error(f"Failed to upload image {filepath}: {e}")
            return None
    
    def process_product_images(self, product_name, shopify_images):
        """Download and upload all images for a product
        
        Args:
            product_name: Name of the product
            shopify_images: List of Shopify image dicts with 'src', 'alt', etc.
            
        Returns:
            List of WordPress image dicts with 'id', 'src', 'name', 'alt'
        """
        wordpress_images = []
        
        for idx, img in enumerate(shopify_images):
            try:
                image_url = img.get('src')
                alt_text = img.get('alt') or ''
                
                if not image_url:
                    continue
                
                # Download image locally
                local_path = self.download_image(image_url, product_name, idx)
                
                if not local_path:
                    logger.warning(f"Skipping image {idx} for {product_name} - download failed")
                    continue
                
                # Upload to WordPress (will check for existing first)
                wp_image = self.upload_to_wordpress(
                    local_path,
                    alt_text=alt_text,
                    title=f"{product_name} - Image {idx + 1}"
                )
                
                if wp_image:
                    wordpress_images.append(wp_image)
                    logger.debug(f"Image {idx} for {product_name} ready (ID: {wp_image.get('id')})")
                else:
                    # Upload failed - check if it exists in media library anyway
                    filename = Path(local_path).name
                    existing = self._find_existing_media(filename)
                    if existing:
                        logger.info(f"Upload failed but found existing image for {product_name} - using existing (ID: {existing.get('id')})")
                        wordpress_images.append(existing)
                    else:
                        logger.warning(f"Skipping image {idx} for {product_name} - upload failed and not found in media library")
                
                # Small delay between uploads to avoid overwhelming server
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error processing image {idx} for {product_name}: {e}")
                continue
        
        return wordpress_images
    
    def _find_existing_media(self, filename):
        """Check if media with this filename already exists
        
        Args:
            filename: Name of file to search for
            
        Returns:
            Media dict with 'id', 'src', 'name', 'alt' or None if not found
        """
        try:
            # Get base filename without extension
            base_name = Path(filename).stem
            
            # Search for media by filename (without extension)
            url = f"{self.wordpress_url}/wp-json/wp/v2/media"
            params = {
                'search': base_name,
                'per_page': 100,
                'orderby': 'date',
                'order': 'desc'  # Get most recent first
            }
            
            response = requests.get(
                url,
                auth=self.auth,
                params=params,
                headers={'User-Agent': 'Shopify-WooCommerce-Migrator/1.0'},
                timeout=30
            )
            
            if response.status_code == 200:
                media_items = response.json()
                
                # Look for filename match (base name matches, ignoring WordPress suffixes like -1, -2, -scaled)
                for media in media_items:
                    media_filename = media.get('media_details', {}).get('file', '')
                    media_title = media.get('title', {}).get('rendered', '')
                    
                    # Check if the base name is in the filename or title
                    if base_name in media_filename or base_name in media_title:
                        logger.info(f"Found existing media: {filename} → {media_title} (ID: {media['id']})")
                        return {
                            'id': media['id'],
                            'src': media['source_url'],
                            'name': media_title,
                            'alt': media.get('alt_text', '')
                        }
            
            return None
            
        except Exception as e:
            logger.debug(f"Could not search for existing media {filename}: {e}")
            return None
    
    def cleanup_old_images(self, days=7):
        """Clean up downloaded images older than specified days
        
        Args:
            days: Number of days to keep images (default 7)
        """
        try:
            cutoff_time = time.time() - (days * 24 * 60 * 60)
            removed_count = 0
            
            for filepath in self.images_dir.iterdir():
                if filepath.is_file():
                    if filepath.stat().st_mtime < cutoff_time:
                        filepath.unlink()
                        removed_count += 1
            
            if removed_count > 0:
                logger.info(f"Cleaned up {removed_count} old images")
                
        except Exception as e:
            logger.error(f"Error cleaning up images: {e}")
