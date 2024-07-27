import os
from PIL import Image
import requests
from io import BytesIO

from googleapiclient.discovery import build
from duckduckgo_search import DDGS
from bs4 import BeautifulSoup
import hashlib
import re

import csv
from urllib.parse import urljoin, urlparse
from validator_collection import validators, checkers, errors
from concurrent.futures import ThreadPoolExecutor, as_completed

API_KEY_GOOGLE = os.getenv('API_KEY_GOOGLE')
CX_GOOGLE = os.getenv('CX_GOOGLE')
API_KEY_BING = os.getenv('API_KEY_BING')

def search_image_google(query, api_key, cx, num_results=1):
    try:
        service = build("customsearch", "v1", developerKey=api_key)
        res = service.cse().list(
            q=query,
            cx=cx,
            searchType='image',
            num=num_results
        ).execute()
        return res.get('items', [])
    except ValueError as e:
        print(f"An error occurred: {e}")
        return []

def search_image_duckduckgo(keywords, safesearch='off', max_results=10):
    ddgs = DDGS()
    results = ddgs.images(keywords, safesearch=safesearch, max_results=max_results)
    return results

def search_text_google(query, api_key, cx, max_results=10, start=1, return_content=False):
    try:
        service = build("customsearch", "v1", developerKey=api_key)
        res = service.cse().list(
            q=query,
            cx=cx,
            num=max_results,
            start=start
        ).execute()

        items = res.get('items', [])

        urls = [item.get('link') for item in items]

        if not return_content:
            return urls

        return get_contents(urls)

    except ValueError as e:
        print(f"An error occurred: {e}")
        return []

def search_text_duckduckgo(keywords, safesearch='off', max_results=10, return_content=False):
    ddgs = DDGS()
    results = ddgs.text(keywords, safesearch=safesearch, max_results=max_results)

    urls = [result.get('href') for result in results]

    if not return_content:
        return urls
    
    return get_contents(urls)

def combined_search(query, max_results):
    google_results = search_text_google(query, API_KEY_GOOGLE, CX_GOOGLE, max_results=max_results, return_content=True)
    duckduckgo_results = search_text_duckduckgo(query, max_results=max_results, return_content=True)
    
    combined_results = []
    for result in google_results + duckduckgo_results:
        combined_results.append({"content": result})
    
    return combined_results

def get_contents(urls):
    contents = []
    for url in urls:
        if url:
            try:
                response = requests.get(url)
                soup = BeautifulSoup(response.text, 'html.parser')
                content = soup.get_text()
                contents.append(content)
            except requests.RequestException as e:
                print(f"Failed to fetch content from {url}: {e}")
    return contents

def download_image(url):
    response = requests.get(url)
    img = Image.open(BytesIO(response.content))
    return img

def generate_folder_name(url):
    # Extract the domain name and path from the URL
    match = re.match(r'https://([^/]+)(/.*)?', url)
    if match:
        domain, path = match.groups()
        path = path if path else ""
    else:
        return None

    # Remove "www." and common domain extensions from the domain name
    domain = re.sub(r'(www\.)?([^.]+\.[^.]+)', r'\2', domain)
    domain = re.sub(r'\.(com|net|org|edu|gov|mil|int|info|biz|pics|co|us|uk|ca|de|jp|fr|au|in)$', '', domain)

    # Remove HTML and file extensions from the path
    path = re.sub(r'\.html?$|/\w+\.\w+$', '', path)

    # Remove common words that don't contribute to the uniqueness of the folder name
    stop_words = ['news', 'pics', 'pictures', 'photos', 'images', 'gallery', 'galleries', 'search', 'pic', 'collection', 'articles', 'best', 'photo', 'video']
    path = re.sub(r'\b(' + '|'.join(stop_words) + r')\b', '', path)

    # Remove non-alphanumeric characters and replace spaces with hyphens
    folder_name = re.sub(r'[^a-zA-Z0-9]', '-', path).strip('-').lower()

    # Truncate the domain and path to fit within the length limit
    max_length = 42
    combined_length = len(domain) + len(folder_name)
    if combined_length > max_length:
        if len(domain) > max_length // 2 and len(folder_name) > max_length // 2:
            domain = domain[:max_length // 2]
            folder_name = folder_name[:max_length // 2]
        elif len(domain) > max_length // 2:
            domain = domain[:max_length - len(folder_name)]
        else:
            folder_name = folder_name[:max_length - len(domain)]

    # Generate a short hash of the URL to ensure uniqueness
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]

    # Combine the domain name, folder name, and hash to create the final folder name
    folder_name = f"{domain}-{folder_name}-{url_hash}"

    # Ensure the total length does not exceed 20 characters
    if len(folder_name) > 50:
        folder_name = folder_name[:50-len(url_hash)-1] + '-' + url_hash

    return folder_name

def validate_url(url):
    try:
        # Validate the URL
        validators.url(url)
        print(f"The URL '{url}' is valid.")
        return True
    except errors.InvalidURLError:
        print(f"The URL '{url}' is invalid.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    return False

def extract_links_to_csv(url, output_file='links.csv', recursive=False):
    def get_links(page_url):
        try:
            response = requests.get(page_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            return [link.get('href') for link in soup.find_all('a') if link.get('href')]
        except requests.RequestException as e:
            print(f"Error fetching the URL {page_url}: {e}")
            return []

    def process_links(link, sub_links):
        unique_data = set()
        for href in sub_links:
            if href != link and href.startswith(link.strip('/')):
                full_url = href
                folder = urlparse(link).path.strip('/')
                if folder:
                    unique_data.add((full_url, folder, 1))  # Depth is always 1
        return unique_data

    def fetch_and_process(link):
        if validate_url(link):
            sub_links = get_links(link)
            return process_links(link, sub_links)
        return set()

    # Process the initial page
    initial_links = get_links(url)
    
    all_data = set()

    if not recursive:
        # If not recursive, just process the initial page links
        for href in initial_links:
            if href:
                # Make sure the URL is absolute
                full_url = urljoin(url, href)
                # Extract the folder (path) from the URL
                folder = urlparse(full_url).path.strip('/')

                if folder:
                    # Set depth to 1 as per requirement
                    depth = 1
                    all_data.add((full_url, folder, depth))
    else:
        # If recursive, use ThreadPoolExecutor to visit each link from the initial page
        with ThreadPoolExecutor(max_workers=50) as executor:
            future_to_link = {executor.submit(fetch_and_process, urljoin(url, link)): link for link in initial_links}
            for future in as_completed(future_to_link):
                result = future.result()
                all_data.update(result)

    all_data = list(all_data)

    # Write data to CSV file
    try:
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile, delimiter=';')
            writer.writerow(['URL', 'Folder', 'Depth'])
            writer.writerows(all_data)
        print(f"CSV file '{output_file}' has been created successfully with {len(all_data)} unique entries.")
    except IOError as e:
        print(f"Error writing to CSV file: {e}")