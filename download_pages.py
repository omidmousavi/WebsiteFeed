import requests
from bs4 import BeautifulSoup
import urllib.parse
import os
import re
import base64
from pathlib import Path
from urllib.parse import urlparse

def clone_page_to_single_html(url, output_file="cloned_page.html"):
    """
    Clone a webpage and save as a single HTML file with all assets embedded.
    
    Args:
        url: The URL of the page to clone
        output_file: Path to save the output HTML file
    """
    
    # Headers to mimic a real browser
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }
    
    try:
        # Fetch the main HTML page
        print(f"Fetching {url}...")
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or 'utf-8'
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Process CSS files
        print("Processing CSS files...")
        css_count = 0
        for link in soup.find_all('link', rel='stylesheet'):
            css_url = link.get('href')
            if css_url and not css_url.startswith('data:'):
                full_css_url = urllib.parse.urljoin(url, css_url)
                try:
                    css_content = fetch_resource(full_css_url, headers)
                    if css_content:
                        # Process any @import or url() in the CSS
                        css_content = process_css_urls(css_content, full_css_url, headers)
                        # Embed CSS directly
                        style_tag = soup.new_tag('style')
                        style_tag.string = css_content
                        link.replace_with(style_tag)
                        css_count += 1
                        print(f"  Embedded: {full_css_url}")
                except Exception as e:
                    print(f"  Failed to fetch CSS {full_css_url}: {e}")
        
        # Process inline styles with background images
        print("Processing inline styles...")
        for tag in soup.find_all(style=True):
            style_content = tag['style']
            tag['style'] = process_css_urls(style_content, url, headers)
        
        # Process IMG tags
        print("Processing images...")
        img_count = 0
        for img in soup.find_all('img'):
            src = img.get('src')
            srcset = img.get('srcset')
            
            # Handle src attribute
            if src and not src.startswith('data:'):
                full_img_url = urllib.parse.urljoin(url, src)
                try:
                    img_data = fetch_resource_binary(full_img_url, headers)
                    if img_data:
                        # Convert to base64 and embed
                        content_type = get_content_type(full_img_url)
                        b64_data = base64.b64encode(img_data).decode('utf-8')
                        img['src'] = f"data:{content_type};base64,{b64_data}"
                        img_count += 1
                        print(f"  Embedded image: {full_img_url}")
                except Exception as e:
                    print(f"  Failed to fetch image {full_img_url}: {e}")
            
            # Handle srcset attribute (responsive images)
            if srcset:
                # Take the first image from srcset as fallback
                srcset_parts = srcset.split(',')
                if srcset_parts:
                    first_src = srcset_parts[0].strip().split(' ')[0]
                    if not first_src.startswith('data:'):
                        full_img_url = urllib.parse.urljoin(url, first_src)
                        try:
                            img_data = fetch_resource_binary(full_img_url, headers)
                            if img_data:
                                content_type = get_content_type(full_img_url)
                                b64_data = base64.b64encode(img_data).decode('utf-8')
                                img['srcset'] = f"data:{content_type};base64,{b64_data}"
                        except Exception as e:
                            print(f"  Failed to fetch srcset image {full_img_url}: {e}")
        
        # Process background images in style tags
        for style_tag in soup.find_all('style'):
            if style_tag.string:
                style_tag.string = process_css_urls(style_tag.string, url, headers)
        
        # Process JavaScript files (embed them)
        print("Processing JavaScript files...")
        js_count = 0
        for script in soup.find_all('script', src=True):
            js_url = script.get('src')
            if js_url and not js_url.startswith('data:'):
                full_js_url = urllib.parse.urljoin(url, js_url)
                try:
                    js_content = fetch_resource(full_js_url, headers)
                    if js_content:
                        # Embed JavaScript directly
                        new_script = soup.new_tag('script')
                        new_script.string = js_content
                        script.replace_with(new_script)
                        js_count += 1
                        print(f"  Embedded JS: {full_js_url}")
                except Exception as e:
                    print(f"  Failed to fetch JS {full_js_url}: {e}")
        
        # Process other resources (favicon, etc.)
        for link in soup.find_all('link', href=True):
            href = link.get('href')
            rel = link.get('rel', [])
            if href and not href.startswith('data:'):
                if any(x in href.lower() for x in ['.ico', 'favicon']) or (rel and 'icon' in str(rel).lower()):
                    full_url = urllib.parse.urljoin(url, href)
                    try:
                        img_data = fetch_resource_binary(full_url, headers)
                        if img_data:
                            content_type = get_content_type(full_url)
                            b64_data = base64.b64encode(img_data).decode('utf-8')
                            link['href'] = f"data:{content_type};base64,{b64_data}"
                            print(f"  Embedded favicon: {full_url}")
                    except:
                        pass
        
        # Save the complete HTML
        print(f"Saving to {output_file}...")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(str(soup))
        
        print(f"\nSuccess! Page cloned to {output_file}")
        print(f"  - Embedded CSS files: {css_count}")
        print(f"  - Embedded images: {img_count}")
        print(f"  - Embedded JS files: {js_count}")
        
        # Calculate file size
        file_size = os.path.getsize(output_file) / (1024 * 1024)
        print(f"  - Final file size: {file_size:.2f} MB")
        
        return True
        
    except requests.RequestException as e:
        print(f"Error fetching URL: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

def fetch_resource(url, headers):
    """Fetch text-based resource (CSS, JS)"""
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or 'utf-8'
        return response.text
    except Exception as e:
        print(f"    Error fetching {url}: {e}")
        return None

def fetch_resource_binary(url, headers):
    """Fetch binary resource (images)"""
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return response.content
    except Exception as e:
        print(f"    Error fetching binary {url}: {e}")
        return None

def process_css_urls(css_content, base_url, headers):
    """Process CSS to embed url() references"""
    if not css_content:
        return css_content
    
    # Find all url(...) patterns
    url_pattern = re.compile(r'url\([\'"]?(.*?)[\'"]?\)', re.IGNORECASE)
    
    # Also handle @import
    import_pattern = re.compile(r'@import\s+[\'"]?(.*?)[\'"]?;', re.IGNORECASE)
    
    def replace_import(match):
        import_url = match.group(1)
        if import_url.startswith('data:') or import_url.startswith('http://') or import_url.startswith('https://'):
            # Try to fetch and embed imported CSS
            full_url = urllib.parse.urljoin(base_url, import_url)
            imported_css = fetch_resource(full_url, headers)
            if imported_css:
                # Recursively process the imported CSS
                return process_css_urls(imported_css, full_url, headers)
        return match.group(0)
    
    def replace_url(match):
        url_path = match.group(1).strip()
        # Skip data URLs and absolute external URLs that might be problematic
        if url_path.startswith('data:'):
            return match.group(0)
        
        full_url = urllib.parse.urljoin(base_url, url_path)
        
        # Skip external domains if needed (optional)
        # parsed_base = urlparse(base_url)
        # parsed_full = urlparse(full_url)
        # if parsed_base.netloc != parsed_full.netloc:
        #     return match.group(0)
        
        try:
            # Detect if it's likely an image
            if any(ext in full_url.lower() for ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico', '.bmp']):
                img_data = fetch_resource_binary(full_url, headers)
                if img_data:
                    content_type = get_content_type(full_url)
                    b64_data = base64.b64encode(img_data).decode('utf-8')
                    return f"url(data:{content_type};base64,{b64_data})"
            elif any(ext in full_url.lower() for ext in ['.woff', '.woff2', '.ttf', '.eot', '.otf']):
                # Handle font files
                font_data = fetch_resource_binary(full_url, headers)
                if font_data:
                    content_type = get_font_content_type(full_url)
                    b64_data = base64.b64encode(font_data).decode('utf-8')
                    return f"url(data:{content_type};base64,{b64_data})"
            else:
                # Try as text (SVG, etc.)
                text_data = fetch_resource(full_url, headers)
                if text_data:
                    return f"url(data:text/plain;base64,{base64.b64encode(text_data.encode('utf-8')).decode('utf-8')})"
        except Exception as e:
            print(f"    Error processing URL {full_url}: {e}")
            pass
        return match.group(0)
    
    # Process @import statements first
    css_content = import_pattern.sub(replace_import, css_content)
    # Then process url() references
    css_content = url_pattern.sub(replace_url, css_content)
    
    return css_content

def get_content_type(url):
    """Determine content type from file extension"""
    url_lower = url.lower()
    if '.png' in url_lower:
        return 'image/png'
    elif '.jpg' in url_lower or '.jpeg' in url_lower:
        return 'image/jpeg'
    elif '.gif' in url_lower:
        return 'image/gif'
    elif '.svg' in url_lower:
        return 'image/svg+xml'
    elif '.webp' in url_lower:
        return 'image/webp'
    elif '.ico' in url_lower:
        return 'image/x-icon'
    elif '.bmp' in url_lower:
        return 'image/bmp'
    else:
        return 'image/png'  # default

def get_font_content_type(url):
    """Determine font content type from file extension"""
    url_lower = url.lower()
    if '.woff2' in url_lower:
        return 'font/woff2'
    elif '.woff' in url_lower:
        return 'font/woff'
    elif '.ttf' in url_lower:
        return 'font/ttf'
    elif '.eot' in url_lower:
        return 'application/vnd.ms-fontobject'
    elif '.otf' in url_lower:
        return 'font/otf'
    else:
        return 'application/octet-stream'

# Example usage
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        url_to_clone = sys.argv[1]
        output_filename = sys.argv[2] if len(sys.argv) > 2 else "cloned_page.html"
    else:
        # Example URLs to test
        url_to_clone = input("Enter URL to clone: ").strip()
        output_filename = input("Enter output filename (default: cloned_page.html): ").strip()
        if not output_filename:
            output_filename = "cloned_page.html"
    
    clone_page_to_single_html(url_to_clone, output_filename)