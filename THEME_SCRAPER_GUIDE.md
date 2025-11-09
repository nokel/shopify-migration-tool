# Shopify Theme Scraper - Complete Guide

## What This Does

The **Theme Scraper** downloads your entire Shopify storefront design including:

**All HTML pages** (homepage, products, collections, cart)  
**All CSS stylesheets** (design, fonts, colors)  
**All images** (products, banners, logos, icons)  
**All fonts** (custom and web fonts)  
**JavaScript files** (functionality and effects)  
**Colour palette** (extracted hex codes and RGB values)  
**Typography specs** (font families, sizes, weights)  

Then it generates a **migration guide** for recreating everything in WooCommerce.

---

## How to Use It

### Step 1: Run the Theme Scraper

```bash
python theme_scraper.py https://your-store.myshopify.com
```

**Replace** `https://your-store.myshopify.com` with your actual Shopify store URL.

### Step 2: Wait for Download

The scraper will:
- Crawl your homepage, product pages, collections, cart
- Download all CSS, images, fonts, and JavaScript
- Extract colours and fonts
- Generate migration guide

**Time:** Usually 2-10 minutes depending on store size

### Step 3: Check the Output

Everything is saved to `scraped_theme/` directory:

```
scraped_theme/
├── html/              # HTML snapshots of all pages
├── css/               # All stylesheets
├── js/                # JavaScript files
├── images/            # All images, logos, icons
├── fonts/             # Custom fonts
└── data/
    ├── design_specification.json  # Technical specs
    └── DESIGN_REPORT.md          # Migration guide
```

---

## What You Get

### 1. Design Specification (`design_specification.json`)

JSON file containing:
- Complete colour palette
- All font families
- File inventory
- Directory paths

**Use this for:** Giving to designers, developers, or automation tools

### 2. Migration Guide (`DESIGN_REPORT.md`)

Human-readable document with:
- Colour codes to copy/paste
- Font names and setup instructions
- File counts and statistics
- **Step-by-step WooCommerce recreation guide**

### 3. All Assets

- **HTML files:** Reference for layout and structure
- **CSS files:** Styles you can adapt for WordPress
- **Images:** Upload directly to WordPress Media Library
- **Fonts:** Install as custom fonts in WooCommerce theme
- **JavaScript:** Functionality you may need to recreate

---

## Recreating Your Shopify Design in WooCommerce

Once you have the scraped assets, follow the guide in `scraped_theme/data/DESIGN_REPORT.md`.

### Quick Overview:

#### Option 1: DIY with Page Builder (10-20 hours)
1. Install **Astra** or **Kadence** theme (free)
2. Install **Elementor** page builder (free)
3. Apply your colours from `design_specification.json`
4. Add your fonts
5. Upload images
6. Recreate pages using HTML files as reference

**Cost:** Free

#### Option 2: Customize Pre-built Theme (5-15 hours)
1. Find similar WooCommerce theme on ThemeForest
2. Apply your colours and fonts
3. Upload your images
4. Adjust layouts to match

**Cost:** $0-99 for theme

#### Option 3: Hire Professional (1-4 weeks)
1. Give developer the `scraped_theme/` folder
2. They recreate exact design in WordPress
3. Professional quality, pixel-perfect match

**Cost:** $2,000-$10,000

---

## Example: Applying Your Colors

From `design_specification.json`:
```json
{
  "colors": [
    "#FF6B6B",  // Primary red
    "#4ECDC4",  // Accent teal
    "#1A1A2E",  // Dark background
    "#FFFFFF"   // White text
  ]
}
```

In WooCommerce:
1. Go to **Appearance → Customize → Colours**
2. Set Primary Colour: `#FF6B6B`
3. Set Accent Colour: `#4ECDC4`
4. Set Background: `#1A1A2E`
5. Set Text Colour: `#FFFFFF`

**Done!** Your WooCommerce store now uses the same colours.

---

## Example: Installing Your Fonts

From `design_specification.json`:
```json
{
  "fonts": [
    "Montserrat, sans-serif",
    "Open Sans, sans-serif"
  ]
}
```

In WooCommerce:
1. Go to **Appearance → Customize → Typography**
2. Set Heading Font: **Montserrat**
3. Set Body Font: **Open Sans**

If fonts are custom (in `fonts/` folder):
1. Install **Custom Fonts** plugin
2. Upload font files from `scraped_theme/fonts/`
3. Apply them in theme settings

---

## Example: Using Scraped Images

All your product images, logos, and graphics are in `scraped_theme/images/`:

### Upload to WordPress:
```bash
# Option 1: Via WordPress admin
Go to Media → Add New → Upload files from scraped_theme/images/

# Option 2: Via FTP (faster for many images)
Upload to: /wp-content/uploads/shopify-import/
```

Then use them in your pages, products, and theme customizer.

---

## Advanced: Using the HTML/CSS

### Reference HTML for Layouts

Open files in `scraped_theme/html/`:
- `home.html` - Homepage structure
- `product_sample.html` - Product page layout
- `collections.html` - Collection grid layout
- `cart.html` - Shopping cart design

Use these as blueprints when building pages in Elementor or your theme.

### Adapt CSS for WordPress

CSS files in `scraped_theme/css/` contain all your styles.

**Important:** You can't copy/paste directly because Shopify uses different CSS classes than WooCommerce.

**Instead:**
1. Find specific styles (buttons, cards, headers)
2. Copy the CSS rules
3. Adapt the class names for WooCommerce
4. Add to **Appearance → Customize → Additional CSS**

**Example:**

Shopify CSS:
```css
.product-card {
  border: 1px solid #e0e0e0;
  padding: 20px;
  border-radius: 8px;
}
```

Adapted for WooCommerce:
```css
.woocommerce-product-gallery {
  border: 1px solid #e0e0e0;
  padding: 20px;
  border-radius: 8px;
}
```

---

## Common Questions

### Q: Will this convert my Shopify theme to WordPress automatically?
**A:** No, automatic conversion isn't possible. This tool gives you all the assets and a detailed guide to recreate the design manually (or hire someone to do it).

### Q: Can I use the downloaded HTML directly in WordPress?
**A:** Not directly. You'll need to recreate the layout using WordPress page builders or theme customizer, using the HTML as a reference.

### Q: What about product data (prices, descriptions)?
**A:** Use the main migration tool (`test_connections.py` and data migration scripts) for product data. This scraper is specifically for design/theme assets.

### Q: Do I need to scrape if I have Shopify API access?
**A:** The API gives you data (products, customers, orders). The scraper gives you design (colours, fonts, images, layout). You need both for a complete migration.

### Q: How accurate is the colour extraction?
**A:** Very accurate. It extracts every colour code used in CSS. You may get duplicate shades, so review and consolidate to your main brand colors.

---

## Full Migration Workflow

Here's the complete process for migrating from Shopify to WooCommerce:

### 1. **Scrape Theme** (This tool)
```bash
python theme_scraper.py https://your-store.myshopify.com
```
**Output:** All design assets and migration guide

### 2. **Set Up WooCommerce**
- Install WordPress + WooCommerce
- Choose and install theme
- Apply colors/fonts from scraped data

### 3. **Migrate Data** (Main migration tool)
```bash
# Configure .env with API credentials
python test_connections.py  # Test API access
python migrate.py          # Run data migration
```
**Output:** Products, customers, orders migrated

### 4. **Recreate Design**
- Use scraped assets to match Shopify look
- Build pages with page builder
- Upload images
- Customize templates

### 5. **Test & Launch**
- Compare with Shopify site
- Test checkout, payments, mobile
- Set up 301 redirects
- Go live!

---

## Tips for Success

**Do scrape early** - Get design assets before you lose access to Shopify  
**Do organize colours** - Pick 3-5 main colors from extracted palette  
**Do keep HTML files** - Invaluable reference for layout decisions  

**Don't expect auto-conversion**
**Don't skip testing** - Always test on staging first  
**Don't ignore mobile** - Check responsive design  

---

## Next Steps

1. Run the theme scraper
2. Review the `DESIGN_REPORT.md` file
3. Decide on DIY vs. hire approach
4. Set up WooCommerce and start applying your design
5. Run data migration with the main tool
6. Test everything thoroughly
7. Launch your new WooCommerce store!
