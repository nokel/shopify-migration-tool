"""
Data mapping functions to convert Shopify data structures to WooCommerce format
"""
import re
from datetime import datetime
from logger import setup_logger

logger = setup_logger(__name__)

class DataMapper:
    
    @staticmethod
    def map_product(shopify_product):
        """Map Shopify product to WooCommerce format"""
        try:
            # Base product data
            wc_product = {
                'name': shopify_product.get('title', ''),
                'type': 'simple',  # Will be changed to 'variable' if variants exist
                'description': shopify_product.get('body_html', ''),
                'short_description': '',
                'sku': shopify_product.get('variants', [{}])[0].get('sku', ''),
                'regular_price': str(shopify_product.get('variants', [{}])[0].get('price', '0')),
                'manage_stock': True,
                'stock_quantity': shopify_product.get('variants', [{}])[0].get('inventory_quantity', 0),
                'stock_status': 'instock' if shopify_product.get('variants', [{}])[0].get('inventory_quantity', 0) > 0 else 'outofstock',
                'weight': str(shopify_product.get('variants', [{}])[0].get('weight', '0')),
                'status': 'publish' if shopify_product.get('status') == 'active' else 'draft',
                'catalog_visibility': 'visible',
                'featured': False,
                'virtual': False,
                'downloadable': False,
                'sold_individually': False,
                'tax_status': 'taxable',
                'tax_class': '',
                'reviews_allowed': True,
                'purchase_note': '',
                'meta_data': [
                    {
                        'key': 'shopify_product_id',
                        'value': str(shopify_product.get('id', ''))
                    }
                ]
            }
            
            # Handle variants
            variants = shopify_product.get('variants', [])
            if len(variants) > 1:
                wc_product['type'] = 'variable'
                # For variable products, remove single-variant specific data
                del wc_product['sku']
                del wc_product['regular_price']
                del wc_product['stock_quantity']
                del wc_product['weight']
                
                # Set up attributes for variations
                wc_product['attributes'] = DataMapper._create_product_attributes(variants)
                
            # Handle images
            images = shopify_product.get('images', [])
            if images:
                wc_product['images'] = []
                for i, image in enumerate(images):
                    wc_product['images'].append({
                        'src': image.get('src', ''),
                        'name': image.get('alt', f"Product image {i+1}"),
                        'alt': image.get('alt', '')
                    })
            
            # Handle categories (collections)
            # Note: Categories will need to be created separately first
            
            # Handle tags
            tags = shopify_product.get('tags', '')
            if tags:
                tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
                wc_product['tags'] = [{'name': tag} for tag in tag_list]
                
            # Handle SEO data
            wc_product['meta_data'].extend([
                {
                    'key': '_yoast_wpseo_title',
                    'value': shopify_product.get('title', '')
                },
                {
                    'key': '_yoast_wpseo_metadesc', 
                    'value': DataMapper._extract_meta_description(shopify_product.get('body_html', ''))
                }
            ])
            
            return wc_product
            
        except Exception as e:
            logger.error(f"Error mapping product {shopify_product.get('id', 'unknown')}: {e}")
            return None
    
    @staticmethod
    def map_customer(shopify_customer):
        """Map Shopify customer to WooCommerce format"""
        try:
            # Get primary address
            addresses = shopify_customer.get('addresses', [])
            default_address = addresses[0] if addresses else {}
            
            wc_customer = {
                'email': shopify_customer.get('email', ''),
                'first_name': shopify_customer.get('first_name', ''),
                'last_name': shopify_customer.get('last_name', ''),
                'username': shopify_customer.get('email', '').split('@')[0] if shopify_customer.get('email') else '',
                'billing': {
                    'first_name': default_address.get('first_name', shopify_customer.get('first_name', '')),
                    'last_name': default_address.get('last_name', shopify_customer.get('last_name', '')),
                    'company': default_address.get('company', ''),
                    'address_1': default_address.get('address1', ''),
                    'address_2': default_address.get('address2', ''),
                    'city': default_address.get('city', ''),
                    'state': default_address.get('province', ''),
                    'postcode': default_address.get('zip', ''),
                    'country': default_address.get('country_code', ''),
                    'email': shopify_customer.get('email', ''),
                    'phone': default_address.get('phone', shopify_customer.get('phone', ''))
                },
                'shipping': {
                    'first_name': default_address.get('first_name', shopify_customer.get('first_name', '')),
                    'last_name': default_address.get('last_name', shopify_customer.get('last_name', '')),
                    'company': default_address.get('company', ''),
                    'address_1': default_address.get('address1', ''),
                    'address_2': default_address.get('address2', ''),
                    'city': default_address.get('city', ''),
                    'state': default_address.get('province', ''),
                    'postcode': default_address.get('zip', ''),
                    'country': default_address.get('country_code', '')
                },
                'meta_data': [
                    {
                        'key': 'shopify_customer_id',
                        'value': str(shopify_customer.get('id', ''))
                    },
                    {
                        'key': 'shopify_created_at',
                        'value': shopify_customer.get('created_at', '')
                    }
                ]
            }
            
            return wc_customer
            
        except Exception as e:
            logger.error(f"Error mapping customer {shopify_customer.get('id', 'unknown')}: {e}")
            return None
    
    @staticmethod
    def map_order(shopify_order, customer_id_map=None):
        """Map Shopify order to WooCommerce format"""
        try:
            # Map order status
            status_map = {
                'pending': 'pending',
                'authorized': 'on-hold',
                'partially_paid': 'on-hold',
                'paid': 'processing',
                'partially_refunded': 'refunded',
                'refunded': 'refunded',
                'voided': 'cancelled',
                'fulfilled': 'completed',
                'partially_fulfilled': 'processing',
                'unfulfilled': 'processing'
            }
            
            shopify_status = shopify_order.get('fulfillment_status', shopify_order.get('financial_status', 'pending'))
            wc_status = status_map.get(shopify_status, 'pending')
            
            # Get customer ID from mapping or create as guest
            customer_id = 0
            shopify_customer_id = shopify_order.get('customer', {}).get('id')
            if customer_id_map and shopify_customer_id:
                customer_id = customer_id_map.get(str(shopify_customer_id), 0)
            
            # Map line items
            line_items = []
            for item in shopify_order.get('line_items', []):
                line_items.append({
                    'product_id': 0,  # Will need to be mapped from Shopify product ID
                    'quantity': item.get('quantity', 1),
                    'name': item.get('name', ''),
                    'price': str(item.get('price', '0')),
                    'total': str(float(item.get('price', 0)) * item.get('quantity', 1)),
                    'meta_data': [
                        {
                            'key': 'shopify_variant_id',
                            'value': str(item.get('variant_id', ''))
                        },
                        {
                            'key': 'shopify_product_id',
                            'value': str(item.get('product_id', ''))
                        }
                    ]
                })
            
            # Billing and shipping addresses
            billing_address = shopify_order.get('billing_address', {})
            shipping_address = shopify_order.get('shipping_address', billing_address)
            
            wc_order = {
                'status': wc_status,
                'currency': shopify_order.get('currency', 'USD'),
                'customer_id': customer_id,
                'billing': {
                    'first_name': billing_address.get('first_name', ''),
                    'last_name': billing_address.get('last_name', ''),
                    'company': billing_address.get('company', ''),
                    'address_1': billing_address.get('address1', ''),
                    'address_2': billing_address.get('address2', ''),
                    'city': billing_address.get('city', ''),
                    'state': billing_address.get('province', ''),
                    'postcode': billing_address.get('zip', ''),
                    'country': billing_address.get('country_code', ''),
                    'email': shopify_order.get('contact_email', billing_address.get('email', '')),
                    'phone': billing_address.get('phone', '')
                },
                'shipping': {
                    'first_name': shipping_address.get('first_name', ''),
                    'last_name': shipping_address.get('last_name', ''),
                    'company': shipping_address.get('company', ''),
                    'address_1': shipping_address.get('address1', ''),
                    'address_2': shipping_address.get('address2', ''),
                    'city': shipping_address.get('city', ''),
                    'state': shipping_address.get('province', ''),
                    'postcode': shipping_address.get('zip', ''),
                    'country': shipping_address.get('country_code', '')
                },
                'line_items': line_items,
                'shipping_lines': [],
                'payment_method': shopify_order.get('gateway', 'unknown'),
                'payment_method_title': shopify_order.get('gateway', 'Unknown Payment Method'),
                'set_paid': shopify_order.get('financial_status') in ['paid', 'partially_paid'],
                'meta_data': [
                    {
                        'key': 'shopify_order_id',
                        'value': str(shopify_order.get('id', ''))
                    },
                    {
                        'key': 'shopify_order_number',
                        'value': str(shopify_order.get('order_number', ''))
                    },
                    {
                        'key': 'shopify_created_at',
                        'value': shopify_order.get('created_at', '')
                    }
                ]
            }
            
            # Handle shipping
            shipping_lines = shopify_order.get('shipping_lines', [])
            if shipping_lines:
                for shipping in shipping_lines:
                    wc_order['shipping_lines'].append({
                        'method_id': 'flat_rate',
                        'method_title': shipping.get('title', 'Shipping'),
                        'total': str(shipping.get('price', '0'))
                    })
            
            # Handle taxes
            tax_lines = shopify_order.get('tax_lines', [])
            if tax_lines:
                wc_order['tax_lines'] = []
                for tax in tax_lines:
                    wc_order['tax_lines'].append({
                        'rate_code': tax.get('title', 'Tax'),
                        'rate_id': 0,
                        'label': tax.get('title', 'Tax'),
                        'compound': False,
                        'tax_total': str(tax.get('price', '0'))
                    })
            
            return wc_order
            
        except Exception as e:
            logger.error(f"Error mapping order {shopify_order.get('id', 'unknown')}: {e}")
            return None
    
    @staticmethod
    def map_coupon(shopify_discount):
        """Map Shopify discount code to WooCommerce coupon"""
        try:
            # Map discount type
            discount_type_map = {
                'percentage': 'percent',
                'fixed_amount': 'fixed_cart',
                'shipping': 'fixed_cart'
            }
            
            wc_coupon = {
                'code': shopify_discount.get('code', ''),
                'discount_type': discount_type_map.get(shopify_discount.get('value_type'), 'fixed_cart'),
                'amount': str(shopify_discount.get('value', '0')),
                'individual_use': not shopify_discount.get('applies_to_shipping', False),
                'exclude_sale_items': False,
                'minimum_amount': str(shopify_discount.get('minimum_order_amount', '0')),
                'usage_limit': shopify_discount.get('usage_limit'),
                'usage_count': shopify_discount.get('used_count', 0),
                'date_expires': shopify_discount.get('ends_at'),
                'free_shipping': shopify_discount.get('applies_to_shipping', False),
                'description': f"Migrated from Shopify discount: {shopify_discount.get('code', '')}",
                'meta_data': [
                    {
                        'key': 'shopify_discount_id',
                        'value': str(shopify_discount.get('id', ''))
                    }
                ]
            }
            
            return wc_coupon
            
        except Exception as e:
            logger.error(f"Error mapping discount {shopify_discount.get('id', 'unknown')}: {e}")
            return None
    
    @staticmethod
    def _create_product_attributes(variants):
        """Create product attributes from Shopify variants"""
        attributes = {}
        
        for variant in variants:
            for i in range(1, 4):  # Shopify supports up to 3 options
                option_key = f'option{i}'
                option_name = f'option{i}_name'  # This would come from the product options
                
                option_value = variant.get(option_key)
                if option_value:
                    if option_name not in attributes:
                        attributes[option_name] = {
                            'name': option_name.replace('_', ' ').title(),
                            'options': [],
                            'visible': True,
                            'variation': True
                        }
                    
                    if option_value not in attributes[option_name]['options']:
                        attributes[option_name]['options'].append(option_value)
        
        return list(attributes.values())
    
    @staticmethod
    def _extract_meta_description(html_content, max_length=160):
        """Extract meta description from HTML content"""
        if not html_content:
            return ''
        
        # Remove HTML tags
        clean_text = re.sub('<[^<]+?>', '', html_content)
        # Remove extra whitespace
        clean_text = ' '.join(clean_text.split())
        
        # Truncate to appropriate length
        if len(clean_text) > max_length:
            clean_text = clean_text[:max_length].rsplit(' ', 1)[0] + '...'
            
        return clean_text