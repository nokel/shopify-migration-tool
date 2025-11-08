# Shopify to WooCommerce Migration Tool

A comprehensive GUI-based migration tool to transfer ALL data from a Shopify store to WooCommerce with minimal manual intervention.

![Migration Tool Interface](screenshot.png)

## ✨ Features

### Complete Data Migration
- ✅ **Products** with full variant support (size, color, material, etc.)
- ✅ **Customers** with billing/shipping addresses
- ✅ **Orders** with complete order history
- ✅ **Categories** (collections) 
- ✅ **Coupons** and discount codes
- ✅ **Product images** and galleries
- ✅ **SEO data** (meta titles, descriptions)
- ✅ **Stock quantities** and inventory tracking

### User-Friendly Interface
- 🖥️ **GUI Application** - No command line needed
- 🔄 **Dry Run Mode** - Test migration without making changes
- 📊 **Real-time Progress** - Live progress bar and detailed logs
- 💾 **Save/Load Credentials** - Secure credential management
- 📝 **Detailed Reports** - Complete migration summary

### Smart Variant Handling
- 🎯 **Automatic Detection** - Finds all product variants
- 🔗 **Proper Mapping** - Maps Shopify options to WooCommerce attributes
- 📦 **Stock Management** - Maintains variant-specific inventory
- 🏷️ **SKU Preservation** - Keeps all SKUs intact

## 🚀 Quick Start

### Windows Users
1. Double-click `run.bat`
2. Enter your API credentials
3. Click "Dry run" to test
4. Click "Migrate" to run

### Mac/Linux Users
1. Run `chmod +x run.sh && ./run.sh`
2. Enter your API credentials
3. Click "Dry run" to test
4. Click "Migrate" to run

### Manual Installation
```bash
# Clone the repository
git clone <repository-url>
cd shopify_woocommerce_migrator

# Install dependencies
pip install -r requirements.txt

# Run the GUI
python main.py
```

## 📋 Before You Start

### 1. Get Shopify API Credentials
1. Go to your Shopify Admin → Apps
2. Click "Develop apps for your store"
3. Create a new app with these scopes:
   - `read_products`
   - `read_customers`
   - `read_orders`
   - `read_content`
   - `read_discounts`
4. Copy the Admin API access token

### 2. Get WooCommerce API Credentials
1. Go to WooCommerce → Settings → Advanced → REST API
2. Click "Add key"
3. Set permissions to "Read/Write"
4. Copy Consumer Key and Consumer Secret

### 3. Backup Your WooCommerce Site
**⚠️ CRITICAL: Always backup before migration!**

## 🎯 What Gets Migrated

| Data Type | Shopify → WooCommerce | Notes |
|-----------|----------------------|-------|
| Products | ✅ Complete | Including variants, images, SEO |
| Variants | ✅ Full Support | All size/color/material options |
| Categories | ✅ Collections → Categories | Maintains hierarchy |
| Customers | ✅ With Addresses | Billing & shipping addresses |
| Orders | ✅ Complete History | All statuses, line items, payments |
| Coupons | ✅ Discount Codes | All types and restrictions |
| Images | ✅ Product Images | Downloads and uploads automatically |
| SEO Data | ✅ Meta Information | Preserves SEO optimization |

## 🔧 Advanced Configuration

### Batch Processing
Modify these settings in the GUI or `.env` file:
- `BATCH_SIZE`: Number of items per batch (default: 50)
- `DELAY_BETWEEN_REQUESTS`: API rate limiting delay
- `MAX_RETRIES`: Retry attempts for failed requests

### Large Store Optimization
For stores with 1000+ products:
1. Run migration during low-traffic hours
2. Increase `DELAY_BETWEEN_REQUESTS` to 2-3 seconds
3. Consider migrating in phases (products first, then orders)

## 📊 Migration Process

### Phase 1: Preparation
- ✅ Test API connections
- ✅ Analyze data structure
- ✅ Create category mappings

### Phase 2: Core Data (Dry Run Available)
1. **Categories** - Create WooCommerce categories from Shopify collections
2. **Products** - Migrate products with variants and images
3. **Customers** - Import customer profiles and addresses

### Phase 3: Transaction Data (Dry Run Available)
4. **Orders** - Import complete order history
5. **Coupons** - Migrate discount codes and promotions

### Phase 4: Verification
6. **Data Validation** - Verify all data migrated correctly
7. **Report Generation** - Create detailed migration report

## 🛠️ Troubleshooting

### Common Issues

**"Failed to connect to APIs"**
- Verify API credentials are correct
- Check that WooCommerce REST API is enabled
- Ensure proper user permissions

**"Migration running slowly"**
- Increase `DELAY_BETWEEN_REQUESTS` in settings
- Run during off-peak hours
- Consider smaller batch sizes

**"Some products missing variants"**
- Check Shopify product has multiple variants
- Verify variant data isn't corrupt
- Review migration logs for specific errors

**"Images not uploading"**
- Check WooCommerce media permissions
- Verify sufficient disk space
- Ensure stable internet connection

### Bluehost Specific Issues
- Increase PHP memory limit: `php_value memory_limit 512M`
- Check file permissions: 755 for directories, 644 for files
- Monitor resource usage in cPanel

## 📈 Performance Guidelines

| Store Size | Est. Time | Recommended Settings |
|------------|-----------|---------------------|
| < 100 products | 5-15 min | Default settings |
| 100-500 products | 15-45 min | Delay: 1s, Batch: 25 |
| 500-1000 products | 1-2 hours | Delay: 2s, Batch: 20 |
| 1000+ products | 2+ hours | Delay: 3s, Batch: 10 |

## 🔒 Security & Privacy

- ✅ All API credentials stored locally only
- ✅ No data sent to third parties
- ✅ Secure HTTPS-only API communication
- ✅ Credentials can be saved encrypted locally
- ✅ Remove API access after migration

## 📞 Support

### Before Reporting Issues
1. Check the migration logs in the output panel
2. Try running a dry run first
3. Verify API credentials are correct
4. Ensure both platforms are accessible

### Getting Help
- Check `logs/` directory for detailed error logs
- Review the generated migration report
- Test with a smaller subset of data first

## 📄 License & Disclaimer

This tool is provided as-is. Always test on a staging environment first. The authors are not responsible for any data loss or issues arising from the use of this tool.

**⚠️ Important: Always backup your WooCommerce site before running any migration!**