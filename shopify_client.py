import requests
import time
from urllib.parse import urljoin
from logger import setup_logger

logger = setup_logger(__name__)

class ShopifyClient:
    def __init__(self, store_url, access_token, max_retries=3, delay=1.0):
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
    
    def _make_graphql_request(self, query, variables=None):
        """Make GraphQL API request
        
        Args:
            query: GraphQL query string
            variables: Optional variables dict
            
        Returns:
            GraphQL response data or None on error
        """
        url = f"{self.store_url}/admin/api/2023-10/graphql.json"
        
        payload = {'query': query}
        if variables:
            payload['variables'] = variables
        
        for attempt in range(self.max_retries):
            try:
                response = self.session.post(url, json=payload)
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    logger.warning(f"GraphQL rate limited. Waiting {retry_after} seconds...")
                    time.sleep(retry_after)
                    continue
                
                response.raise_for_status()
                result = response.json()
                
                # Check for GraphQL errors
                if 'errors' in result:
                    error_messages = [err.get('message', 'Unknown error') for err in result['errors']]
                    logger.error(f"GraphQL errors: {'; '.join(error_messages)}")
                    return None
                
                return result.get('data')
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"GraphQL request failed (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.delay * (2 ** attempt))
                else:
                    logger.error(f"GraphQL request failed after {self.max_retries} attempts: {e}")
                    return None
        
        time.sleep(self.delay)
        return None
        
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
        """Get all discount codes with their associated price rules"""
        logger.info("Fetching discount codes from Shopify...")
        all_discounts = []
        
        try:
            # Get price rules (modern discount system)
            price_rules = self.get_paginated_data('price_rules.json')
            if price_rules:
                logger.info(f"Retrieved {len(price_rules)} price rules")
                
                # For each price rule, fetch its discount codes
                for price_rule in price_rules:
                    price_rule_id = price_rule.get('id')
                    try:
                        # Get discount codes for this price rule
                        discount_codes = self.get_paginated_data(f'price_rules/{price_rule_id}/discount_codes.json')
                        
                        # Merge price rule settings with each discount code
                        for discount_code in discount_codes:
                            combined = {
                                **price_rule,  # Price rule settings (value, type, usage limits, etc.)
                                'code': discount_code.get('code'),  # Actual coupon code
                                'discount_code_id': discount_code.get('id'),
                                'usage_count': discount_code.get('usage_count', 0)
                            }
                            all_discounts.append(combined)
                            
                    except Exception as e:
                        logger.warning(f"Could not fetch discount codes for price rule {price_rule_id}: {e}")
                
                logger.info(f"Retrieved total of {len(all_discounts)} discount codes")
                return all_discounts
                
        except Exception as e:
            logger.warning(f"Price rules not available: {e}")
        
        try:
            # Fallback to old discount codes endpoint
            discounts = self.get_paginated_data('discount_codes.json')
            if discounts:
                logger.info(f"Retrieved {len(discounts)} discount codes (legacy endpoint)")
                return discounts
        except Exception as e:
            logger.warning(f"Legacy discount codes not available: {e}")
        
        logger.info("No discount codes found or endpoint not available")
        return []
        
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
    
    def get_order_timeline_events(self, shopify_order_id):
        """Get all timeline events for an order (GraphQL with REST fallback)
        
        Fetches complete order timeline including:
        - System events (payment, fulfillment, status changes)
        - Staff comments (CommentEvent)
        - All other order activity
        
        Args:
            shopify_order_id: Shopify order ID (numeric)
            
        Returns:
            List of event dicts with 'created_at', 'message', 'event_type', 'author' keys
            Sorted newest first
        """
        events = []
        
        # Try GraphQL first (gets everything including staff comments)
        try:
            logger.debug(f"Fetching timeline events via GraphQL for order {shopify_order_id}")
            
            query = """
            query getOrderEvents($orderId: ID!) {
              order(id: $orderId) {
                events(first: 250) {
                  edges {
                    node {
                      __typename
                      id
                      createdAt
                      message
                    }
                  }
                }
              }
            }
            """
            
            variables = {
                'orderId': f"gid://shopify/Order/{shopify_order_id}"
            }
            
            result = self._make_graphql_request(query, variables)
            
            if result and 'order' in result and result['order']:
                graphql_events = result['order'].get('events', {}).get('edges', [])
                
                for edge in graphql_events:
                    node = edge.get('node', {})
                    event_type = node.get('__typename', 'Event')
                    
                    event = {
                        'created_at': node.get('createdAt'),
                        'message': node.get('message', ''),
                        'event_type': event_type,
                        'author': None  # Author requires read_users scope
                    }
                    
                    events.append(event)
                
                logger.info(f"Retrieved {len(events)} timeline events via GraphQL for order {shopify_order_id}")
                
                # Sort oldest first (chronological order)
                events.sort(key=lambda x: x['created_at'], reverse=False)
                return events
            else:
                logger.warning(f"GraphQL returned no order data for order {shopify_order_id}")
        
        except Exception as e:
            logger.error(f"GraphQL timeline fetch failed for order {shopify_order_id}: {e}")
        
        # Fallback to REST API (gets system events but NOT staff comments)
        try:
            logger.debug(f"Falling back to REST API for order {shopify_order_id} timeline events")
            
            response = self._make_request('GET', f'orders/{shopify_order_id}/events.json')
            rest_events = response.get('events', [])
            
            for event in rest_events:
                events.append({
                    'created_at': event.get('created_at'),
                    'message': event.get('message', ''),
                    'event_type': 'Event',  # REST API doesn't provide type
                    'author': None
                })
            
            logger.info(f"Retrieved {len(events)} timeline events via REST for order {shopify_order_id}")
            logger.warning(f"REST API fallback used - staff comments will NOT be included")
            
            # Sort oldest first (chronological order)
            events.sort(key=lambda x: x['created_at'], reverse=False)
            return events
        
        except Exception as e:
            logger.error(f"REST timeline fetch also failed for order {shopify_order_id}: {e}")
            return []
    
    def merge_note_events(self, events):
        """Merge 'added a note' events with the actual note content
        
        When Shopify creates two events:
        1. "Author added a note to this order."
        2. "The actual note content" (may be seconds or minutes later)
        
        Merge them into one event with the actual content attributed to the author.
        
        Also merges "Received new order" events with "Created this order from draft" events
        since they represent the same action in Shopify Admin UI.
        
        Args:
            events: List of event dicts (must be sorted chronologically)
            
        Returns:
            Merged list of events with related events combined
        """
        from datetime import datetime, timedelta
        import re
        
        merged = []
        skip_indices = set()
        
        for i, event in enumerate(events):
            if i in skip_indices:
                continue
            
            message = event.get('message', '').strip()
            
            # Check if this is a "created this order from draft" event
            if 'created this order from draft order' in message.lower():
                # Look for "Received new order" in the next few events (within same minute)
                event_time = datetime.fromisoformat(event.get('created_at', '').replace('Z', '+00:00'))
                
                merged_event = event.copy()
                
                for j in range(i + 1, min(i + 5, len(events))):  # Check next 5 events max
                    next_event = events[j]
                    next_message = next_event.get('message', '').strip()
                    next_time = datetime.fromisoformat(next_event.get('created_at', '').replace('Z', '+00:00'))
                    
                    # Check if within 60 seconds
                    time_diff = (next_time - event_time).total_seconds()
                    
                    if time_diff > 60:  # More than 1 minute later
                        break
                    
                    # Check if this is "Received new order" event
                    if re.match(r'^Received new order', next_message, re.IGNORECASE):
                        # Merge them into one note
                        merged_event['message'] = f"{message}\n{next_message}"
                        skip_indices.add(j)  # Skip the merged event
                        break
                
                merged.append(merged_event)
            
            # Check if this is an "added a note" event
            elif 'added a note to this order' in message.lower():
                # Extract author name from message (format: "Name added a note...")
                author_match = re.match(r'(.+?)\s+added a note', message, re.IGNORECASE)
                author_name = author_match.group(1) if author_match else None
                
                # Look for the actual note content in the next few events (within 5 minutes)
                event_time = datetime.fromisoformat(event.get('created_at', '').replace('Z', '+00:00'))
                
                for j in range(i + 1, min(i + 10, len(events))):  # Check next 10 events max
                    next_event = events[j]
                    next_message = next_event.get('message', '').strip()
                    next_time = datetime.fromisoformat(next_event.get('created_at', '').replace('Z', '+00:00'))
                    
                    # Check if within 5 minutes and looks like note content
                    time_diff = (next_time - event_time).total_seconds()
                    
                    if time_diff > 300:  # More than 5 minutes later
                        break
                    
                    # Check if this looks like note content (not a system event)
                    is_system_event = any(keyword in next_message.lower() for keyword in 
                                         ['added a note', 'marked', 'sent', 'created', 'received', 
                                          'confirmation', 'payment', 'was generated', 'email'])
                    
                    if not is_system_event and next_message:
                        # Found the note content! Merge it
                        merged_event = event.copy()
                        if author_name:
                            merged_event['message'] = f"{author_name} added a note: {next_message}"
                            merged_event['author'] = author_name
                        else:
                            merged_event['message'] = f"Note: {next_message}"
                        
                        merged.append(merged_event)
                        skip_indices.add(j)  # Skip the merged event
                        break
                else:
                    # No matching note content found, keep as-is
                    merged.append(event)
            else:
                # Not a mergeable event, add as-is
                merged.append(event)
        
        return merged