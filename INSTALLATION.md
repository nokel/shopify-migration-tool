# Installation Guide for Shopify to WooCommerce Migration

## Prerequisites

### 1. WooCommerce Setup (Bluehost)
Your WooCommerce site must be properly configured before migration:

#### Enable WooCommerce REST API
1. Log into your WordPress admin dashboard
2. Go to **WooCommerce > Settings > Advanced > REST API**
3. Click **Add key**
4. Set the following:
   - Description: "Migration Tool"
   - User: Select an administrator user
   - Permissions: Read/Write
5. Click **Generate API key**
6. **IMPORTANT**: Copy the Consumer key and Consumer secret - you'll need these

#### Verify REST API Access
Test your API access:
```bash
curl https://yourdomain.com/wp-json/wc/v3/products \
  -u consumer_key:consumer_secret
```

### 2. Shopify API Credentials
You need to create a private app in Shopify:

1. From your Shopify admin, go to **Settings**
2. Click **Apps and sales channels**
3. Click **Develop apps**
4. Name it "migrate"
5. Click on **Admin API scopes** under Configuration
6. Enable these scopes:
   - `read_products` - Products and collections
   - `read_customers` - Customer data
   - `read_orders` - Order history
   - `read_content` - Pages and blog posts
   - `read_discounts` - Discount codes
   - `read_shipping` - Shipping settings
   - `read_inventory` - Inventory levels
   (To be safe enable all of the "read" access scopes)
7. Click **Save**
8. Click **Install app**
9. Copy the Admin API access token into the .env file. (You'll only be shown it once, so if you forget it or save it somewhere you shouldn't and forget it, make sure you delete the "app" and then make another one and save it in so you don't accidentally leak sensitive information.

## Installation Steps

### 1. Download and Setup the Migration Tool

```bash
# Clone or download this migration tool
cd /path/to/migration/tool

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# Install required packages
pip install -r requirements.txt
```
NOTE: If you don't want to use a virtual environment, that's fine, I didn't use one, it should still work as expected as long as everything is installed correctly from the requirements.txt. But instead of running the .bat or .sh files, just run "python main.py" or double click on the main.py/main.pyw file. Both should work the same way.

### 2. Configure API Credentials

Create a `.env` file in the project root:

```bash
# Shopify Configuration
SHOPIFY_STORE_URL=https://your-store.myshopify.com
SHOPIFY_ACCESS_TOKEN=your_admin_api_access_token

# WooCommerce Configuration  
WOOCOMMERCE_URL=https://yourdomain.com
WOOCOMMERCE_CONSUMER_KEY=ck_your_consumer_key
WOOCOMMERCE_CONSUMER_SECRET=cs_your_consumer_secret

# Migration Settings
BATCH_SIZE=50
LOG_LEVEL=INFO
DRY_RUN=false
```

#### File Permissions
Ensure proper file permissions on your server:
```bash
# Set proper permissions for WordPress files
find /path/to/wordpress/ -type d -exec chmod 755 {} \;
find /path/to/wordpress/ -type f -exec chmod 644 {} \;
```

#### PHP Memory Limit
For large migrations, increase PHP memory limit:
1. Access cPanel File Manager
2. Edit `.htaccess` in your WordPress root
3. Add: `php_value memory_limit 512M`

#### Database Optimization
Before migration, optimize your database:
1. Go to cPanel > phpMyAdmin
2. Select your WordPress database
3. Click "Operations" > "Optimize table"

### 4. Pre-Migration Checklist

- [ ] WooCommerce REST API is enabled and tested
- [ ] Shopify private app is created with proper scopes
- [ ] API credentials are configured in `.env`
- [ ] WordPress site is backed up
- [ ] Database is optimized
- [ ] Sufficient server resources available
- [ ] Migration tool tested on staging site (recommended)

### 5. Running the Migration

```bash
# Activate virtual environment
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Test connectivity first
python test_connections.py

# Run dry run (recommended first)
python migrate.py --dry-run

# Run actual migration
python migrate.py
```

### 6. Post-Migration Steps

1. **Verify Data**: Check products, customers, and orders in WooCommerce admin
2. **Update URLs**: Update any hardcoded Shopify URLs in content
3. **Test Functionality**: Test checkout, customer accounts, etc.
4. **SEO Setup**: Configure redirects from old Shopify URLs
5. **Payment Gateway**: Configure WooCommerce payment methods
6. **Shipping Setup**: Verify shipping zones and methods
7. **Tax Configuration**: Set up tax rules in WooCommerce

### Common Issues

**API Connection Errors**
- Verify API credentials are correct
- Check that REST API is enabled in WooCommerce
- Ensure proper user permissions

**Memory/Timeout Issues**
- Increase PHP memory limit
- Reduce BATCH_SIZE in .env
- Run migration during low-traffic hours

**Missing Data**
- Check migration logs for errors
- Some data may need manual review
- Custom fields may require additional mapping

### Getting Help
- Check migration logs in `logs/` directory
- Review error messages in console output
- Ensure both platforms are accessible during migration

## Security Notes

- Keep API credentials secure
- Run migration over HTTPS only  
- Remove API keys after migration is complete
- Monitor server logs during migration
