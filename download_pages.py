import requests
from bs4 import BeautifulSoup
import urllib.parse
import os
import re
import base64
from pathlib import Path

def clone_page_to_single_html(url, output_file="cloned_page.html"):
    """
    Clone a webpage and save as a single HTML file with all assets embedded.
    
    Args:
        url: The URL of the page to clone
        output_file: Path to save the output HTML file
    """
    
    # Headers to mimic a real browser
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
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
            if css_url:
                full_css_url = urllib.parse.urljoin(url, css_url)
                try:
                    css_content = fetch_resource(full_css_url, headers)
                    if css_content:
                        # Embed CSS directly
                        style_tag = soup.new_tag('style')
                        style_tag.string = css_content
                        link.replace_with(style_tag)
                        css_count += 1
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
            if src:
                full_img_url = urllib.parse.urljoin(url, src)
                try:
                    img_data = fetch_resource_binary(full_img_url, headers)
                    if img_data:
                        # Convert to base64 and embed
                        content_type = get_content_type(full_img_url)
                        b64_data = base64.b64encode(img_data).decode('utf-8')
                        img['src'] = f"data:{content_type};base64,{b64_data}"
                        img_count += 1
                except Exception as e:
                    print(f"  Failed to fetch image {full_img_url}: {e}")
        
        # Process background images in style tags
        for style_tag in soup.find_all('style'):
            if style_tag.string:
                style_tag.string = process_css_urls(style_tag.string, url, headers)
        
        # Process JavaScript files (embed them)
        print("Processing JavaScript files...")
        js_count = 0
        for script in soup.find_all('script', src=True):
            js_url = script.get('src')
            if js_url:
                full_js_url = urllib.parse.urljoin(url, js_url)
                try:
                    js_content = fetch_resource(full_js_url, headers)
                    if js_content:
                        # Embed JavaScript directly
                        new_script = soup.new_tag('script')
                        new_script.string = js_content
                        script.replace_with(new_script)
                        js_count += 1
                except Exception as e:
                    print(f"  Failed to fetch JS {full_js_url}: {e}")
        
        # Process other resources (favicon, etc.)
        for link in soup.find_all('link', href=True):
            href = link.get('href')
            if '.ico' in href.lower() or 'favicon' in href.lower():
                full_url = urllib.parse.urljoin(url, href)
                try:
                    img_data = fetch_resource_binary(full_url, headers)
                    if img_data:
                        content_type = get_content_type(full_url)
                        b64_data = base64.b64encode(img_data).decode('utf-8')
                        link['href'] = f"data:{content_type};base64,{b64_data}"
                except:
                    pass
        
        # Save the complete HTML
        print(f"Saving to {output_file}...")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(str(soup))
        
        print(f"Success! Page cloned to {output_file}")
        print(f"  - Embedded CSS files: {css_count}")
        print(f"  - Embedded images: {img_count}")
        print(f"  - Embedded JS files: {js_count}")
        
        return True
        
    except requests.RequestException as e:
        print(f"Error fetching URL: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False

def fetch_resource(url, headers):
    """Fetch text-based resource (CSS, JS)"""
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or 'utf-8'
        return response.text
    except:
        return None

def fetch_resource_binary(url, headers):
    """Fetch binary resource (images)"""
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return response.content
    except:
        return None

def process_css_urls(css_content, base_url, headers):
    """Process CSS to embed url() references"""
    if not css_content:
        return css_content
    
    # Find all url(...) patterns
    url_pattern = re.compile(r'url\([\'"]?(.*?)[\'"]?\)', re.IGNORECASE)
    
    def replace_url(match):
        url_path = match.group(1)
        # Skip data URLs
        if url_path.startswith('data:'):
            return match.group(0)
        
        full_url = urllib.parse.urljoin(base_url, url_path)
        try:
            # Detect if it's likely an image
            if any(ext in full_url.lower() for ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico']):
                img_data = fetch_resource_binary(full_url, headers)
                if img_data:
                    content_type = get_content_type(full_url)
                    b64_data = base64.b64encode(img_data).decode('utf-8')
                    return f"url(data:{content_type};base64,{b64_data})"
            else:
                # Try as text (fonts, etc.)
                text_data = fetch_resource(full_url, headers)
                if text_data:
                    return f"url(data:text/plain;base64,{base64.b64encode(text_data.encode('utf-8')).decode('utf-8')})"
        except:
            pass
        return match.group(0)
    
    return url_pattern.sub(replace_url, css_content)

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
    else:
        return 'image/png'  # default

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