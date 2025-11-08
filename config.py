import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    # Shopify Configuration
    SHOPIFY_STORE_URL = os.getenv('SHOPIFY_STORE_URL')
    SHOPIFY_ACCESS_TOKEN = os.getenv('SHOPIFY_ACCESS_TOKEN')
    
    # WooCommerce Configuration
    WOOCOMMERCE_URL = os.getenv('WOOCOMMERCE_URL')
    WOOCOMMERCE_CONSUMER_KEY = os.getenv('WOOCOMMERCE_CONSUMER_KEY')
    WOOCOMMERCE_CONSUMER_SECRET = os.getenv('WOOCOMMERCE_CONSUMER_SECRET')
    
    # WordPress Configuration (for Media API)
    WORDPRESS_USERNAME = os.getenv('WORDPRESS_USERNAME')
    WORDPRESS_APP_PASSWORD = os.getenv('WORDPRESS_APP_PASSWORD')
    
    # Migration Settings
    BATCH_SIZE = int(os.getenv('BATCH_SIZE', 50))
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    DRY_RUN = os.getenv('DRY_RUN', 'false').lower() == 'true'
    MAX_RETRIES = int(os.getenv('MAX_RETRIES', 3))
    DELAY_BETWEEN_REQUESTS = float(os.getenv('DELAY_BETWEEN_REQUESTS', 1))
    
    # Validation
    @classmethod
    def validate(cls):
        """Validate that all required configuration is present"""
        required_fields = [
            'SHOPIFY_STORE_URL',
            'SHOPIFY_ACCESS_TOKEN', 
            'WOOCOMMERCE_URL',
            'WOOCOMMERCE_CONSUMER_KEY',
            'WOOCOMMERCE_CONSUMER_SECRET'
        ]
        
        missing_fields = []
        for field in required_fields:
            if not getattr(cls, field):
                missing_fields.append(field)
                
        if missing_fields:
            raise ValueError(f"Missing required configuration: {', '.join(missing_fields)}")
            
        return True