"""
Data mapping functions to convert Shopify data structures to WooCommerce format
"""
import re
import secrets
import string
from datetime import datetime
from logger import setup_logger

logger = setup_logger(__name__)

def generate_secure_password(length=16):
    """Generate a secure random password for customer accounts"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(secrets.choice(alphabet) for _ in range(length))
    return password

def safe_str(value, default=''):
    """Convert value to string, handling None and other types safely"""
    if value is None:
        return default
    return str(value)

def generate_sku_for_unmapped_item(item_name, shopify_variant_id):
    """Generate a placeholder SKU for unmapped items
    
    WooCommerce requires either a valid product_id or a non-empty SKU.
    For items that can't be mapped, generate a SKU based on the item name.
    
    Args:
        item_name: Name of the line item
        shopify_variant_id: Shopify variant ID (for uniqueness)
        
    Returns:
        str: Generated SKU
    """
    import re
    
    # Clean item name - keep only alphanumeric and spaces
    clean_name = re.sub(r'[^a-zA-Z0-9\s]', '', item_name)
    # Take first few words
    words = clean_name.split()[:3]
    name_part = '-'.join(words).upper()[:20]
    
    # Add variant ID for uniqueness
    if shopify_variant_id:
        sku = f"UNMAPPED-{name_part}-{shopify_variant_id}"
    else:
        # Fallback - use timestamp
        import time
        sku = f"UNMAPPED-{name_part}-{int(time.time())}"
    
    return sku

def generate_placeholder_email(first_name, last_name, customer_id, used_emails=None):
    """Generate a placeholder email for customers without email addresses
    
    Args:
        first_name: Customer's first name
        last_name: Customer's last name
        customer_id: Shopify customer ID (fallback)
        used_emails: Set of already used placeholder emails (for deduplication)
    
    Returns:
        str: Placeholder email in format: firstname lastname@noemail.no
    """
    if used_emails is None:
        used_emails = set()
    
    # Create base name from first_name and last_name
    first = (first_name or '').strip().lower()
    last = (last_name or '').strip().lower()
    
    # Remove non-alphanumeric characters
    import re
    first = re.sub(r'[^a-z0-9]', '', first)
    last = re.sub(r'[^a-z0-9]', '', last)
    
    # Create base email
    if first and last:
        base = f"{first}{last}"
    elif first:
        base = first
    elif last:
        base = last
    else:
        # No name available, use customer ID
        base = f"customer{customer_id}"
    
    # Generate unique email
    email = f"{base}@noemail.no"
    
    # If email already used, append number
    if email in used_emails:
        counter = 1
        while f"{base}{counter}@noemail.no" in used_emails:
            counter += 1
        email = f"{base}{counter}@noemail.no"
    
    used_emails.add(email)
    return email

class DataMapper:
    
    @staticmethod
    def _map_product_status(shopify_status):
        """Map Shopify product status to WooCommerce status
        
        Shopify statuses:
        - active: Product is published and visible
        - draft: Product is not published (work in progress)
        - archived: Product is no longer sold but kept for records
        - unlisted: Product is published but not discoverable (link-only)
        
        WooCommerce statuses:
        - publish: Public, visible to everyone
        - draft: Not published, only visible to admins
        - private: Published but only visible to admins
        
        Args:
            shopify_status: Shopify product status string
            
        Returns:
            str: WooCommerce status
        """
        status_map = {
            'active': 'publish',    # Active products are public
            'draft': 'draft',       # Draft products stay draft
            'archived': 'draft',    # Archived products as draft (not sold)
            'unlisted': 'private'   # Unlisted = published but admin-only (1:1 mapping)
        }
        return status_map.get(shopify_status, 'draft')  # Default to draft if unknown
    
    @staticmethod
    def _map_catalog_visibility(shopify_status):
        """Map Shopify status to WooCommerce catalog visibility
        
        Args:
            shopify_status: Shopify product status string
            
        Returns:
            str: WooCommerce catalog visibility
        """
        visibility_map = {
            'active': 'visible',    # Active products are visible in catalog
            'draft': 'hidden',      # Draft products hidden
            'archived': 'hidden',   # Archived products hidden
            'unlisted': 'hidden'    # Unlisted products hidden (not discoverable)
        }
        return visibility_map.get(shopify_status, 'hidden')  # Default to hidden if unknown
    
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
                # Map Shopify status to WooCommerce status (1:1 mapping)
                # Shopify: active/draft/archived/unlisted → WooCommerce: publish/draft/private
                'status': DataMapper._map_product_status(shopify_product.get('status')),
                'catalog_visibility': DataMapper._map_catalog_visibility(shopify_product.get('status')),
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
                    # Ensure name is always a string
                    image_alt = image.get('alt', '') or ''
                    image_name = image_alt or f"Product image {i+1}"
                    
                    wc_product['images'].append({
                        'src': image.get('src', ''),
                        'name': str(image_name),  # Ensure it's always a string
                        'alt': str(image_alt)     # Ensure it's always a string
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
    def map_customer(shopify_customer, used_emails=None):
        """Map Shopify customer to WooCommerce format
        
        Args:
            shopify_customer: Shopify customer data
            used_emails: Set of already used placeholder emails (for deduplication)
        
        Returns:
            dict: WooCommerce customer data or None if mapping fails
        """
        try:
            # Get or generate email (required field)
            email = shopify_customer.get('email')
            customer_name = f"{shopify_customer.get('first_name', '')} {shopify_customer.get('last_name', '')}".strip()
            customer_id = shopify_customer.get('id', 'unknown')
            
            if not email:
                # Generate placeholder email
                email = generate_placeholder_email(
                    shopify_customer.get('first_name'),
                    shopify_customer.get('last_name'),
                    customer_id,
                    used_emails
                )
                logger.info(f"Customer {customer_id} ({customer_name}) has no email - created placeholder: {email}")
            
            # Get primary address
            addresses = shopify_customer.get('addresses', [])
            default_address = addresses[0] if addresses else {}
            
            wc_customer = {
                'email': email,
                'password': generate_secure_password(),  # Required by WooCommerce API
                'first_name': shopify_customer.get('first_name', ''),
                'last_name': shopify_customer.get('last_name', ''),
                'username': email.split('@')[0] if '@' in email else email[:50],  # Fallback if no @ symbol
                'billing': {
                    'first_name': safe_str(default_address.get('first_name') or shopify_customer.get('first_name')),
                    'last_name': safe_str(default_address.get('last_name') or shopify_customer.get('last_name')),
                    'company': safe_str(default_address.get('company')),
                    'address_1': safe_str(default_address.get('address1')),
                    'address_2': safe_str(default_address.get('address2')),
                    'city': safe_str(default_address.get('city')),
                    'state': safe_str(default_address.get('province')),
                    'postcode': safe_str(default_address.get('zip')),
                    'country': safe_str(default_address.get('country_code')),
                    'email': email,
                    'phone': safe_str(default_address.get('phone') or shopify_customer.get('phone'))
                },
                'shipping': {
                    'first_name': safe_str(default_address.get('first_name') or shopify_customer.get('first_name')),
                    'last_name': safe_str(default_address.get('last_name') or shopify_customer.get('last_name')),
                    'company': safe_str(default_address.get('company')),
                    'address_1': safe_str(default_address.get('address1')),
                    'address_2': safe_str(default_address.get('address2')),
                    'city': safe_str(default_address.get('city')),
                    'state': safe_str(default_address.get('province')),
                    'postcode': safe_str(default_address.get('zip')),
                    'country': safe_str(default_address.get('country_code'))
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
            
            # Get customer ID from mapping or create as guest - handle None customer
            customer_id = 0
            customer_data = shopify_order.get('customer')
            if customer_data and isinstance(customer_data, dict):
                shopify_customer_id = customer_data.get('id')
                if customer_id_map and shopify_customer_id:
                    customer_id = customer_id_map.get(str(shopify_customer_id), 0)
            
            # Map line items (convert tips to custom line items, detect job notes)
            line_items = []
            job_notes = []  # Collect job notes from $0 line items
            
            for item in shopify_order.get('line_items', []):
                item_name = item.get('name', '')
                item_price = float(item.get('price', 0))
                product_id = item.get('product_id')
                sku = item.get('sku', '')
                
                # Detect job notes ONLY: $0 items with no product_id that are NOT tips
                # These are work notes stored as line items in Shopify
                if item_price == 0.0 and not product_id and item_name.lower() not in ['tip', 'tips']:
                    logger.debug(f"Detected job note as $0 line item: {item_name[:50]}...")
                    job_notes.append(item_name)
                    continue
                
                # Include ALL other items, including tips as custom line items
                # Tips, labour, custom parts, etc. all represent legitimate order value
                
                # Include ALL other items, even custom ones without SKU/product_id
                # These represent legitimate orders (labour, custom parts, 3D prints, etc.)
                
                # WooCommerce requires EITHER product_id > 0 OR non-empty SKU
                # If both are missing/empty, generate a placeholder SKU
                if not sku:
                    # Generate SKU for unmapped items
                    sku = generate_sku_for_unmapped_item(item_name, item.get('variant_id'))
                    logger.debug(f"Generated SKU for unmapped item '{item_name}': {sku}")
                
                line_items.append({
                    'product_id': 0,  # Will need to be mapped from Shopify product ID
                    'quantity': item.get('quantity', 1),
                    'name': item_name,
                    'price': str(item.get('price', '0')),
                    'total': str(float(item.get('price', 0)) * item.get('quantity', 1)),
                    'sku': sku,  # Include SKU for fallback mapping (generated if needed)
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
            
            # Billing and shipping addresses - handle None values
            billing_address = shopify_order.get('billing_address') or {}
            shipping_address = shopify_order.get('shipping_address') or billing_address or {}
            
            # If no billing address, create minimal one from available order data
            if not billing_address:
                billing_address = {
                    'first_name': '',
                    'last_name': '',
                    'email': shopify_order.get('contact_email', shopify_order.get('email', '')),
                    'phone': shopify_order.get('phone', ''),
                    'company': '',
                    'address1': '',
                    'address2': '',
                    'city': '',
                    'province': '',
                    'zip': '',
                    'country_code': shopify_order.get('currency', 'US')  # Fallback to currency region
                }
            
            # Get billing email - WooCommerce requires valid email or it will be omitted
            billing_email = shopify_order.get('contact_email') or shopify_order.get('email') or billing_address.get('email') or ''
            billing_email = safe_str(billing_email).strip()
            
            # If no valid email, omit the field rather than sending empty string
            # WooCommerce will accept orders without billing email for guest orders
            wc_billing = {
                'first_name': safe_str(billing_address.get('first_name')),
                'last_name': safe_str(billing_address.get('last_name')),
                'company': safe_str(billing_address.get('company')),
                'address_1': safe_str(billing_address.get('address1')),
                'address_2': safe_str(billing_address.get('address2')),
                'city': safe_str(billing_address.get('city')),
                'state': safe_str(billing_address.get('province')),
                'postcode': safe_str(billing_address.get('zip')),
                'country': safe_str(billing_address.get('country_code')),
                'phone': safe_str(billing_address.get('phone'))
            }
            
            # Only include email if it's not empty (WooCommerce validates email format)
            if billing_email:
                wc_billing['email'] = billing_email
            
            wc_order = {
                'status': wc_status,
                'currency': shopify_order.get('currency', 'USD'),
                'customer_id': customer_id,
                'billing': wc_billing,
                'shipping': {
                    'first_name': safe_str(shipping_address.get('first_name')),
                    'last_name': safe_str(shipping_address.get('last_name')),
                    'company': safe_str(shipping_address.get('company')),
                    'address_1': safe_str(shipping_address.get('address1')),
                    'address_2': safe_str(shipping_address.get('address2')),
                    'city': safe_str(shipping_address.get('city')),
                    'state': safe_str(shipping_address.get('province')),
                    'postcode': safe_str(shipping_address.get('zip')),
                    'country': safe_str(shipping_address.get('country_code'))
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
            
            # Add job notes to order (if any were found in $0 line items)
            if job_notes:
                wc_order['_job_notes'] = job_notes  # Temporary field for migration engine
            
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
            
            # Validate essential fields
            if not wc_order.get('line_items'):
                logger.warning(f"Order {shopify_order.get('order_number', 'unknown')} has no line items, skipping")
                return None
            
            return wc_order
            
        except Exception as e:
            logger.error(f"Error mapping order {shopify_order.get('id', 'unknown')}: {e}")
            # Return None only for critical errors, not missing data
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
                option_value = variant.get(option_key)
                
                if option_value and option_value != 'Default Title':
                    # Use a generic attribute name for now
                    # In real implementation, you'd get this from product.options
                    attribute_name = f'Attribute {i}'
                    
                    if attribute_name not in attributes:
                        attributes[attribute_name] = {
                            'name': attribute_name,
                            'options': [],
                            'visible': True,
                            'variation': True
                        }
                    
                    if option_value not in attributes[attribute_name]['options']:
                        attributes[attribute_name]['options'].append(option_value)
        
        return list(attributes.values())
    
    @staticmethod
    def map_product_variant(shopify_variant, parent_product_options=None):
        """Map a Shopify variant to WooCommerce variation format"""
        try:
            wc_variation = {
                'sku': shopify_variant.get('sku', ''),
                'regular_price': str(shopify_variant.get('price', '0')),
                'stock_quantity': shopify_variant.get('inventory_quantity', 0),
                'stock_status': 'instock' if shopify_variant.get('inventory_quantity', 0) > 0 else 'outofstock',
                'weight': str(shopify_variant.get('weight', '0')),
                'manage_stock': True,
                'attributes': [],
                'meta_data': [
                    {
                        'key': 'shopify_variant_id',
                        'value': str(shopify_variant.get('id', ''))
                    },
                    {
                        'key': 'shopify_barcode',
                        'value': shopify_variant.get('barcode', '')
                    }
                ]
            }
            
            # Handle variant attributes
            for i in range(1, 4):
                option_value = shopify_variant.get(f'option{i}')
                if option_value and option_value != 'Default Title':
                    # Map to the correct attribute name
                    # In a real implementation, you'd get the attribute name from parent_product_options
                    attribute_name = f'Attribute {i}'
                    if parent_product_options and len(parent_product_options) >= i:
                        attribute_name = parent_product_options[i-1].get('name', f'Attribute {i}')
                    
                    wc_variation['attributes'].append({
                        'name': attribute_name,
                        'option': option_value
                    })
            
            # Handle variant image
            if shopify_variant.get('image_id'):
                wc_variation['image'] = {
                    'src': shopify_variant.get('image_src', ''),
                    'alt': f"Variant {shopify_variant.get('sku', 'image')}"
                }
            
            return wc_variation
            
        except Exception as e:
            logger.error(f"Error mapping variant {shopify_variant.get('id', 'unknown')}: {e}")
            return None
    
    @staticmethod
    def map_page(shopify_page):
        """Map Shopify page to WordPress format"""
        try:
            wp_page = {
                'title': {
                    'rendered': shopify_page.get('title', '')
                },
                'content': {
                    'rendered': shopify_page.get('body_html', '')
                },
                'slug': shopify_page.get('handle', ''),
                'status': 'publish' if shopify_page.get('published_at') else 'draft',
                'type': 'page',
                'meta': {
                    'shopify_page_id': str(shopify_page.get('id', '')),
                    'shopify_created_at': shopify_page.get('created_at', ''),
                    'shopify_updated_at': shopify_page.get('updated_at', '')
                }
            }
            
            return wp_page
            
        except Exception as e:
            logger.error(f"Error mapping page {shopify_page.get('id', 'unknown')}: {e}")
            return None
    
    @staticmethod
    def map_blog_article(shopify_article):
        """Map Shopify blog article to WordPress post format"""
        try:
            wp_post = {
                'title': {
                    'rendered': shopify_article.get('title', '')
                },
                'content': {
                    'rendered': shopify_article.get('body_html', '')
                },
                'slug': shopify_article.get('handle', ''),
                'status': 'publish' if shopify_article.get('published_at') else 'draft',
                'type': 'post',
                'excerpt': {
                    'rendered': shopify_article.get('summary', '')
                },
                'meta': {
                    'shopify_article_id': str(shopify_article.get('id', '')),
                    'shopify_blog_id': str(shopify_article.get('blog_id', '')),
                    'shopify_created_at': shopify_article.get('created_at', ''),
                    'shopify_updated_at': shopify_article.get('updated_at', '')
                }
            }
            
            # Handle author
            if shopify_article.get('author'):
                wp_post['meta']['shopify_author'] = shopify_article.get('author')
            
            # Handle tags
            if shopify_article.get('tags'):
                wp_post['meta']['shopify_tags'] = shopify_article.get('tags')
            
            return wp_post
            
        except Exception as e:
            logger.error(f"Error mapping article {shopify_article.get('id', 'unknown')}: {e}")
            return None

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