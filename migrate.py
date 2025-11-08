import argparse
from config import Config
from shopify_client import ShopifyClient
from woocommerce_client import WooCommerceClient
from data_mapper import DataMapper
from logger import setup_logger

logger = setup_logger("migration")

def migrate_products(dry_run=False):
    # Initialize clients
    shopify = ShopifyClient(Config.SHOPIFY_STORE_URL, Config.SHOPIFY_ACCESS_TOKEN)
    woocommerce = WooCommerceClient(
        Config.WOOCOMMERCE_URL,
        Config.WOOCOMMERCE_CONSUMER_KEY,
        Config.WOOCOMMERCE_CONSUMER_SECRET,
	dry_run=dry_run
    )
    
    products = shopify.get_products()
    logger.info(f"Found {len(products)} products")
    
    for product in products:
        wc_product = DataMapper.map_product(product)
        if not wc_product:
            continue

        if dry_run:
            logger.info(f"[DRY RUN] Would create product: {wc_product.get('name')}")
        else:
            woocommerce.create_product(wc_product)

    logger.info(f"[DRY RUN] Would create product: {product['id']} / {wc_product.get('name')}")
    logger.info(f"Migration complete! (dry_run={dry_run})")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    Config.validate()
    migrate_products(dry_run=args.dry_run)