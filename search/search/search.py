import os
from PIL import Image
import requests
from io import BytesIO
from dotenv import find_dotenv, load_dotenv

from googleapiclient.discovery import build
from duckduckgo_search import DDGS
import hashlib
import re

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

def search_image_duckduckgo(keywords, max_results=1):
    ddgs = DDGS()
    results = ddgs.images(keywords, max_results=max_results)
    return results

def search_text_google(query, api_key, cx, num_results=10):
    try:
        service = build("customsearch", "v1", developerKey=api_key)
        res = service.cse().list(
            q=query,
            cx=cx,
            num=num_results
        ).execute()
        return res.get('items', [])
    except ValueError as e:
        print(f"An error occurred: {e}")
        return []

def search_text_duckduckgo(keywords, max_results=10):
    ddgs = DDGS()
    results = ddgs.text(keywords, max_results=max_results)
    return results

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
