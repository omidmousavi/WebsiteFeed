import os
import requests
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import time

# Read URLs from config file
with open('urls', 'r') as f:
    urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]

print(f'Found {len(urls)} URLs to download')

# Create main directory
os.makedirs('downloaded_pages', exist_ok=True)

for url in urls:
    print(f'\nDownloading: {url}')
    
    # Create safe folder name
    domain = urlparse(url).netloc.replace('.', '_')
    folder = f'downloaded_pages/{domain}'
    os.makedirs(folder, exist_ok=True)
    
    try:
        # Download HTML
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Save HTML
        with open(f'{folder}/index.html', 'w', encoding='utf-8') as f:
            f.write(str(soup))
        
        print(f'✓ Saved: {folder}/index.html')
        
    except Exception as e:
        print(f'✗ Failed: {url} - {e}')
    
    time.sleep(1)

print('\nDone!')
