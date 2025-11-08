#!/usr/bin/env python3
"""
Test script to verify API connections to both Shopify and WooCommerce
"""

from config import Config
from shopify_client import ShopifyClient
from woocommerce_client import WooCommerceClient
from logger import setup_logger

def main():
    logger = setup_logger("connection_test")
    
    try:
        # Validate configuration
        Config.validate()
        logger.info("Configuration validation passed")
        
        # Test Shopify connection
        logger.info("Testing Shopify connection...")
        shopify = ShopifyClient(
            Config.SHOPIFY_STORE_URL,
            Config.SHOPIFY_ACCESS_TOKEN,
            max_retries=Config.MAX_RETRIES,
            delay=Config.DELAY_BETWEEN_REQUESTS
        )
        
        shopify_success = shopify.test_connection()
        
        # Test WooCommerce connection  
        logger.info("Testing WooCommerce connection...")
        woocommerce = WooCommerceClient(
            Config.WOOCOMMERCE_URL,
            Config.WOOCOMMERCE_CONSUMER_KEY,
            Config.WOOCOMMERCE_CONSUMER_SECRET,
            max_retries=Config.MAX_RETRIES,
            delay=Config.DELAY_BETWEEN_REQUESTS
        )
        
        woocommerce_success = woocommerce.test_connection()
        
        # Summary
        logger.info("=== Connection Test Results ===")
        logger.info(f"Shopify: {'SUCCESS' if shopify_success else 'FAILED'}")
        logger.info(f"WooCommerce: {'SUCCESS' if woocommerce_success else 'FAILED'}")
        
        if shopify_success and woocommerce_success:
            logger.info("All connections successful! Ready to migrate.")
            return True
        else:
            logger.error("One or more connections failed. Check your configuration.")
            return False
            
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)