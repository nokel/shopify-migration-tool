# Shopify to WooCommerce Migration Tool

A comprehensive migration tool to transfer all data from a Shopify store to WooCommerce, including products, customers, orders, pages, and more.

## What Gets Migrated

This tool migrates the following data:

### Products
- Product details (name, description, SKU, price, weight, dimensions)
- Product variants (size, color, etc.)
- Product images and galleries
- Product categories and tags
- Stock quantities and inventory tracking
- Product SEO settings

### Customers
- Customer profiles (name, email, phone)
- Customer addresses (billing and shipping)
- Customer groups/tags
- Customer registration dates

### Orders
- Order details (items, quantities, prices)
- Order status and dates
- Shipping and billing addresses
- Payment information (method, status)
- Order notes and customer notes
- Refunds and partial refunds

### Store Content
- Pages (About, Contact, etc.)
- Blog posts and articles
- Navigation menus
- Store settings

### Other Data
- Discount codes and coupons
- Shipping zones and methods
- Tax settings
- Store policies

## Installation Requirements

- Python 3.8 or higher
- Access to both Shopify Admin API and WooCommerce REST API
- WooCommerce site with REST API enabled
- Sufficient server resources for large data transfers

## Setup Instructions

See `INSTALLATION.md` for detailed setup instructions.

## Usage

1. Configure your API credentials in `.env`
2. Run the migration: `python migrate.py`
3. Monitor the progress through the console output
4. Review the migration report when complete

## Important Notes

- This is a ONE-TIME migration tool
- Always backup your WooCommerce site before running
- Test on a staging site first
- Large stores may take several hours to migrate
- Some data may need manual review after migration