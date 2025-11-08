#!/usr/bin/env python3
"""
Shopify Theme Scraper - Downloads all design assets from a live Shopify store

This script crawls your Shopify website and extracts:
- HTML structure
- CSS stylesheets
- JavaScript files
- Images and media
- Fonts
- Color schemes
- Typography settings
- Layout specifications
"""

import requests
import re
import os
import json
from urllib.parse import urljoin, urlparse
from pathlib import Path
from bs4 import BeautifulSoup
from logger import setup_logger
import hashlib
import time

logger = setup_logger("theme_scraper")

class ThemeScraper:
    def __init__(self, store_url, output_dir="scraped_theme"):
        self.store_url = store_url.rstrip('/')
        self.output_dir = output_dir
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.downloaded_files = set()
        self.colors = set()
        self.fonts = set()
        
        # Create output directories
        self.dirs = {
            'html': Path(output_dir) / 'html',
            'css': Path(output_dir) / 'css',
            'js': Path(output_dir) / 'js',
            'images': Path(output_dir) / 'images',
            'fonts': Path(output_dir) / 'fonts',
            'data': Path(output_dir) / 'data'
        }
        for dir_path in self.dirs.values():
            dir_path.mkdir(parents=True, exist_ok=True)
    
    def download_file(self, url, directory, filename=None):
        """Download a file to specified directory"""
        try:
            if url in self.downloaded_files:
                return
            
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            if not filename:
                filename = os.path.basename(urlparse(url).path) or 'index.html'
            
            filepath = directory / filename
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            self.downloaded_files.add(url)
            logger.info(f"Downloaded: {filename}")
            return filepath
            
        except Exception as e:
            logger.error(f"Failed to download {url}: {e}")
            return None
    
    def extract_colors_from_css(self, css_content):
        """Extract color codes from CSS"""
        # Find hex colors
        hex_colors = re.findall(r'#[0-9A-Fa-f]{3,6}\b', css_content)
        # Find rgb/rgba colors
        rgb_colors = re.findall(r'rgba?\([^)]+\)', css_content)
        
        for color in hex_colors:
            self.colors.add(color.upper())
        for color in rgb_colors:
            self.colors.add(color)
    
    def extract_fonts_from_css(self, css_content):
        """Extract font families from CSS"""
        # Find font-family declarations
        font_families = re.findall(r'font-family:\s*([^;]+);', css_content, re.IGNORECASE)
        for font in font_families:
            cleaned = font.strip().strip('"').strip("'")
            self.fonts.add(cleaned)
        
        # Find @font-face declarations
        font_faces = re.findall(r'@font-face\s*{([^}]+)}', css_content, re.IGNORECASE)
        for face in font_faces:
            family_match = re.search(r'font-family:\s*([^;]+);', face, re.IGNORECASE)
            if family_match:
                self.fonts.add(family_match.group(1).strip().strip('"').strip("'"))
    
    def scrape_page(self, url, page_name="index"):
        """Scrape a single page and extract all assets"""
        logger.info(f"Scraping page: {url}")
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Save HTML
            html_file = self.dirs['html'] / f"{page_name}.html"
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(soup.prettify())
            
            # Extract and download CSS files
            for link in soup.find_all('link', rel='stylesheet'):
                css_url = link.get('href')
                if css_url:
                    css_url = urljoin(url, css_url)
                    css_content = self.download_css(css_url)
                    if css_content:
                        self.extract_colors_from_css(css_content)
                        self.extract_fonts_from_css(css_content)
            
            # Extract inline styles
            for style in soup.find_all('style'):
                if style.string:
                    self.extract_colors_from_css(style.string)
                    self.extract_fonts_from_css(style.string)
            
            # Extract and download JavaScript files
            for script in soup.find_all('script', src=True):
                js_url = urljoin(url, script['src'])
                if 'shopify' in js_url or self.store_url in js_url:
                    self.download_file(js_url, self.dirs['js'])
            
            # Extract and download images
            for img in soup.find_all('img'):
                img_url = img.get('src') or img.get('data-src')
                if img_url:
                    img_url = urljoin(url, img_url)
                    self.download_image(img_url)
            
            # Extract background images from inline styles
            for element in soup.find_all(style=True):
                style_attr = element['style']
                bg_images = re.findall(r'url\(["\']?([^"\')]+)["\']?\)', style_attr)
                for bg_url in bg_images:
                    full_url = urljoin(url, bg_url)
                    self.download_image(full_url)
            
            return soup
            
        except Exception as e:
            logger.error(f"Failed to scrape {url}: {e}")
            return None
    
    def download_css(self, url):
        """Download CSS file and return content"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            filename = os.path.basename(urlparse(url).path) or f"style_{hashlib.md5(url.encode()).hexdigest()[:8]}.css"
            filepath = self.dirs['css'] / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(response.text)
            
            logger.info(f"Downloaded CSS: {filename}")
            
            # Download linked resources (fonts, images)
            self.extract_css_resources(response.text, url)
            
            return response.text
            
        except Exception as e:
            logger.error(f"Failed to download CSS {url}: {e}")
            return None
    
    def extract_css_resources(self, css_content, base_url):
        """Extract and download resources referenced in CSS"""
        # Find URLs in CSS
        urls = re.findall(r'url\(["\']?([^"\')]+)["\']?\)', css_content)
        
        for resource_url in urls:
            full_url = urljoin(base_url, resource_url)
            
            # Determine if it's a font or image
            ext = os.path.splitext(urlparse(full_url).path)[1].lower()
            
            if ext in ['.woff', '.woff2', '.ttf', '.otf', '.eot']:
                self.download_file(full_url, self.dirs['fonts'])
            elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp']:
                self.download_image(full_url)
    
    def download_image(self, url):
        """Download image file"""
        try:
            # Skip data URLs and external non-Shopify images
            if url.startswith('data:'):
                return
            
            if url in self.downloaded_files:
                return
            
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # Generate filename
            parsed = urlparse(url)
            filename = os.path.basename(parsed.path)
            
            if not filename or '.' not in filename:
                ext = '.jpg'
                content_type = response.headers.get('content-type', '')
                if 'png' in content_type:
                    ext = '.png'
                elif 'gif' in content_type:
                    ext = '.gif'
                elif 'svg' in content_type:
                    ext = '.svg'
                elif 'webp' in content_type:
                    ext = '.webp'
                filename = f"image_{hashlib.md5(url.encode()).hexdigest()[:8]}{ext}"
            
            filepath = self.dirs['images'] / filename
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            self.downloaded_files.add(url)
            logger.debug(f"Downloaded image: {filename}")
            
        except Exception as e:
            logger.debug(f"Failed to download image {url}: {e}")
    
    def scrape_full_site(self):
        """Scrape main pages of the Shopify store"""
        pages = {
            'home': f"{self.store_url}/",
            'collections': f"{self.store_url}/collections",
            'products': f"{self.store_url}/collections/all",
            'cart': f"{self.store_url}/cart",
            'search': f"{self.store_url}/search",
        }
        
        logger.info("Starting full site scrape...")
        
        for page_name, page_url in pages.items():
            self.scrape_page(page_url, page_name)
            time.sleep(1)  # Be polite to the server
        
        # Try to find and scrape a sample product page
        try:
            response = self.session.get(f"{self.store_url}/collections/all")
            soup = BeautifulSoup(response.content, 'html.parser')
            product_links = soup.find_all('a', href=re.compile(r'/products/'))
            
            if product_links:
                first_product = urljoin(self.store_url, product_links[0]['href'])
                self.scrape_page(first_product, 'product_sample')
        except:
            pass
    
    def generate_design_spec(self):
        """Generate design specification document"""
        spec = {
            'store_url': self.store_url,
            'colors': sorted(list(self.colors)),
            'fonts': sorted(list(self.fonts)),
            'downloaded_files': len(self.downloaded_files),
            'directories': {
                'html': str(self.dirs['html']),
                'css': str(self.dirs['css']),
                'js': str(self.dirs['js']),
                'images': str(self.dirs['images']),
                'fonts': str(self.dirs['fonts'])
            }
        }
        
        spec_file = self.dirs['data'] / 'design_specification.json'
        with open(spec_file, 'w', encoding='utf-8') as f:
            json.dump(spec, indent=2, fp=f)
        
        logger.info(f"Generated design specification: {spec_file}")
        
        # Generate human-readable report
        report_file = self.dirs['data'] / 'DESIGN_REPORT.md'
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(f"# Shopify Theme Design Specification\n\n")
            f.write(f"**Store URL:** {self.store_url}\n\n")
            
            f.write(f"## Color Palette ({len(self.colors)} colors)\n\n")
            f.write("```css\n")
            for color in sorted(list(self.colors))[:50]:  # Limit to top 50
                f.write(f"{color}\n")
            f.write("```\n\n")
            
            f.write(f"## Typography ({len(self.fonts)} font families)\n\n")
            for font in sorted(list(self.fonts)):
                f.write(f"- {font}\n")
            f.write("\n")
            
            f.write(f"## Downloaded Assets\n\n")
            f.write(f"- **Total files:** {len(self.downloaded_files)}\n")
            f.write(f"- **HTML files:** {len(list(self.dirs['html'].glob('*.html')))}\n")
            f.write(f"- **CSS files:** {len(list(self.dirs['css'].glob('*.css')))}\n")
            f.write(f"- **JavaScript files:** {len(list(self.dirs['js'].glob('*.js')))}\n")
            f.write(f"- **Images:** {len(list(self.dirs['images'].iterdir()))}\n")
            f.write(f"- **Fonts:** {len(list(self.dirs['fonts'].iterdir()))}\n\n")
            
            f.write(f"## WooCommerce Migration Guide\n\n")
            f.write(self.generate_woocommerce_guide())
        
        logger.info(f"Generated design report: {report_file}")
        return spec_file, report_file
    
    def generate_woocommerce_guide(self):
        """Generate step-by-step WooCommerce recreation guide"""
        guide = """
### Step 1: Choose a WooCommerce Theme

Based on your Shopify design, choose one of these theme approaches:

**Option A: Use a Flexible Theme + Page Builder**
- Install **Astra** (free) or **Kadence** (free) theme
- Install **Elementor** (free page builder)
- Recreate layouts visually using the page builder

**Option B: Use a Pre-built WooCommerce Theme**
- Browse WooCommerce themes at ThemeForest
- Look for themes with similar layout to your Shopify store
- Customize colors and fonts to match

### Step 2: Apply Your Color Scheme

1. Go to **Appearance → Customize → Colors**
2. Apply the extracted colors from `design_specification.json`
3. Set:
   - Primary color
   - Secondary color
   - Text color
   - Background color
   - Link color
   - Button colors

### Step 3: Set Up Typography

1. Go to **Appearance → Customize → Typography**
2. Apply the fonts from `design_specification.json`
3. For Google Fonts, install them via:
   - **Appearance → Customize → Typography**
   - Or use a plugin like "Easy Google Fonts"

4. For custom fonts:
   - Upload font files from `fonts/` directory
   - Use "Custom Fonts" plugin or theme settings
   - Add @font-face declarations in Additional CSS

### Step 4: Import Images and Media

1. Upload all images from `images/` directory to:
   - **Media → Add New**
   - Bulk upload via FTP to `/wp-content/uploads/`

2. Update references in your pages and products

### Step 5: Recreate Page Layouts

Using the HTML files in `html/` directory as reference:

1. **Homepage:**
   - Use page builder (Elementor) or block editor
   - Recreate sections from `html/home.html`
   - Add widgets, sliders, featured products

2. **Product Pages:**
   - Customize WooCommerce product template
   - Match layout from `html/product_sample.html`
   - Use hooks or page builder for customization

3. **Collection/Category Pages:**
   - Configure WooCommerce archive templates
   - Match grid layout and filters
   - Reference `html/collections.html`

### Step 6: Apply Custom CSS

1. Copy relevant CSS from `css/` directory
2. Add to **Appearance → Customize → Additional CSS**
3. Adapt Shopify-specific classes to WooCommerce classes:
   - `.product-card` → `.woocommerce-product`
   - `.cart-drawer` → `.widget_shopping_cart`
   - etc.

### Step 7: Set Up Navigation

1. Recreate menus from `html/home.html` header
2. Go to **Appearance → Menus**
3. Add product categories, pages, custom links

### Step 8: Configure WooCommerce Settings

1. Match your Shopify checkout flow
2. Set up payment gateways
3. Configure shipping zones
4. Customize email templates to match branding

### Step 9: Install Missing Functionality

Compare features from Shopify and install WooCommerce plugins:
- Product reviews, wishlists, quick view
- Ajax cart, product filters
- See `SHOPIFY_TO_WOOCOMMERCE_MAPPING.md` for plugin recommendations

### Step 10: Test and Refine

1. Compare side-by-side with Shopify site
2. Adjust colors, spacing, fonts as needed
3. Test on mobile devices
4. Optimize images and performance

---

**Estimated Time:** 10-40 hours depending on complexity and your familiarity with WordPress

**Consider Hiring:** For exact 1:1 recreation, consider hiring a WordPress developer ($2,000-$10,000)
"""
        return guide

def main():
    """Main entry point for theme scraper"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python theme_scraper.py <shopify-store-url>")
        print("Example: python theme_scraper.py https://your-store.myshopify.com")
        sys.exit(1)
    
    store_url = sys.argv[1]
    
    scraper = ThemeScraper(store_url)
    
    logger.info("=" * 70)
    logger.info("Shopify Theme Scraper")
    logger.info("=" * 70)
    logger.info(f"Target: {store_url}")
    logger.info(f"Output: {scraper.output_dir}")
    logger.info("=" * 70)
    
    # Scrape the site
    scraper.scrape_full_site()
    
    # Generate specification
    spec_file, report_file = scraper.generate_design_spec()
    
    logger.info("=" * 70)
    logger.info("Scraping Complete!")
    logger.info("=" * 70)
    logger.info(f"✓ Colors extracted: {len(scraper.colors)}")
    logger.info(f"✓ Fonts extracted: {len(scraper.fonts)}")
    logger.info(f"✓ Files downloaded: {len(scraper.downloaded_files)}")
    logger.info(f"\nDesign specification: {spec_file}")
    logger.info(f"Migration guide: {report_file}")
    logger.info(f"\nAll assets saved to: {scraper.output_dir}/")
    logger.info("=" * 70)

if __name__ == "__main__":
    main()
