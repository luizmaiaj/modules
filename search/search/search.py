import csv
import hashlib
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from googleapiclient.discovery import build
from PIL import Image
from validator_collection import errors, validators

API_KEY_GOOGLE = os.getenv('API_KEY_GOOGLE')
CX_GOOGLE = os.getenv('CX_GOOGLE')
API_KEY_BING = os.getenv('API_KEY_BING')
SEARXNG_URL = os.getenv('SEARXNG_URL')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
}

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

def search_image_searxng(query, max_results=10):
    if not is_searxng_alive():
        print("SearXNG instance is not available or is rejecting requests.")
        return []

    try:
        params = {
            'q': query,
            'format': 'json',
            'engines': 'images',
            'results': max_results
        }

        url = urljoin(SEARXNG_URL, 'search')

        response = requests.get(url, params=params, headers=HEADERS)
        response.raise_for_status()
        results = response.json().get('results', [])

        image_results = []
        for result in results:
            image_results.append({
                'url': result.get('url'),
                'thumbnail': result.get('thumbnail_src'),
                'source': result.get('source'),
                'title': result.get('title')
            })

        return image_results

    except requests.HTTPError as e:
        if e.response.status_code == 403:
            print("SearXNG returned a 403 Forbidden error. The instance may be configured to reject certain types of requests.")
        else:
            print(f"HTTP error occurred while searching images on SearXNG: {e}")
        return []
    except requests.RequestException as e:
        print(f"An error occurred while searching images on SearXNG: {e}")
        return []

def search_image_yandex(query, max_results=10):
    base_url = "https://yandex.com/images/search"
    params = {
        "text": query,
        "nomisspell": 1,
        "noreask": 1,
    }

    try:
        response = requests.get(base_url, params=params, headers=HEADERS)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        results = []
        for item in soup.select('.serp-item')[:max_results]:
            image_data = json.loads(item['data-bem'])
            if 'img_href' in image_data['serp-item']:
                image_url = image_data['serp-item']['img_href']
                results.append({
                    'url': image_url,
                    'thumbnail': image_url,
                    'source': 'Yandex',
                    'title': image_data['serp-item'].get('snippet', {}).get('title', '')
                })

        return results

    except requests.RequestException as e:
        print(f"An error occurred while searching images on Yandex: {e}")
        return []

def search_image_bing(query, max_results=10):
    base_url = "https://www.bing.com/images/search"
    params = {
        "q": query,
        "qft": "+filterui:photo-photo",
        "form": "IRFLTR",
        "first": 1
    }

    try:
        response = requests.get(base_url, params=params, headers=HEADERS)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        results = []
        for item in soup.select('.iusc')[:max_results]:
            image_data = json.loads(item['m'])
            results.append({
                'url': image_data['murl'],
                'thumbnail': image_data['turl'],
                'source': 'Bing',
                'title': image_data['t']
            })

        return results

    except requests.RequestException as e:
        print(f"An error occurred while searching images on Bing: {e}")
        return []

def search_image_brave(query, max_results=10):
    base_url = "https://search.brave.com/images"
    params = {
        "q": query,
        "source": "web"
    }

    try:
        response = requests.get(base_url, params=params, headers=HEADERS)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        results = []
        for item in soup.select('.image-cont')[:max_results]:
            img = item.select_one('img')
            if img and 'src' in img.attrs:
                results.append({
                    'url': img['src'],
                    'thumbnail': img['src'],
                    'source': 'Brave',
                    'title': img.get('alt', '')
                })

        return results

    except requests.RequestException as e:
        print(f"An error occurred while searching images on Brave: {e}")
        return []

def search_image_qwant(query, max_results=10):
    base_url = "https://www.qwant.com/"
    params = {
        "q": query,
        "t": "images"
    }

    try:
        response = requests.get(base_url, params=params, headers=HEADERS)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        results = []
        for item in soup.select('.image__result')[:max_results]:
            img = item.select_one('img')
            if img and 'src' in img.attrs:
                results.append({
                    'url': img['src'],
                    'thumbnail': img['src'],
                    'source': 'Qwant',
                    'title': img.get('alt', '')
                })

        return results

    except requests.RequestException as e:
        print(f"An error occurred while searching images on Qwant: {e}")
        return []

def search_google(query, api_key, cx, max_results=10, start=1, return_content=False):
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

def search_duckduckgo(keywords, safesearch='off', max_results=10, return_content=False):
    ddgs = DDGS()
    results = ddgs.text(keywords, safesearch=safesearch, max_results=max_results)

    urls = [result.get('href') for result in results]

    if not return_content:
        return urls
    
    return get_contents(urls)

def search_searxng(query, engines=None, max_results=10, return_content=False):
    """
    engines: comma separated list
    """
    if not is_searxng_alive():
        print("SearXNG instance is not available or is rejecting requests.")
        return []

    try:
        params = {
            'q': query,
            'category_general': 1,
            'language': 'all',
            'time_range': '',
            'safesearch': 0,
            'format': 'json'
        }

        if engines:
            params['engines'] = engines

        # response = requests.get(SEARXNG_URL, params=params, headers=HEADERS)
        response = requests.get(SEARXNG_URL, params=params)
        response.raise_for_status()

        # Parse JSON response
        data = response.json()

        # Extract URLs from the results
        urls = [result['url'] for result in data.get('results', [])[:max_results]]

        if not return_content:
            return urls
        return get_contents(urls)

    except requests.HTTPError as e:
        print(f"HTTP error occurred: {e}")
        print(f"Response content: {e.response.content}")
        return []
    except requests.RequestException as e:
        print(f"An error occurred while searching SearXNG: {e}")
        return []
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON response: {e}")
        print(f"Response content: {response.text}")
        return []
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        print(f"Error type: {type(e)}")
        return []

def search_yandex(query, max_results=10, return_content=False):
    base_url = "https://yandex.com/search/"
    params = {
        "text": query,
        "lr": "21411",  # English results
        "p": 0  # Start from the first page
    }

    try:
        response = requests.get(base_url, params=params, headers=HEADERS)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        results = []
        for item in soup.select('.serp-item')[:max_results]:
            link = item.select_one('.link')
            if link and 'href' in link.attrs:
                url = link['href']
                results.append(url)

        if not return_content:
            return results

        return get_contents(results)

    except requests.RequestException as e:
        print(f"An error occurred while searching Yandex: {e}")
        return []

def search_bing(query, max_results=10, return_content=False):
    base_url = "https://www.bing.com/search"
    params = {
        "q": query,
        "count": max_results
    }

    try:
        response = requests.get(base_url, params=params, headers=HEADERS)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        results = []
        for item in soup.select('.b_algo h2 a')[:max_results]:
            if 'href' in item.attrs:
                url = item['href']
                results.append(url)

        if not return_content:
            return results

        return get_contents(results)

    except requests.RequestException as e:
        print(f"An error occurred while searching Bing: {e}")
        return []

def search_brave(query, max_results=10, return_content=False):
    base_url = "https://search.brave.com/search"
    params = {
        "q": query,
        "source": "web"
    }

    try:
        response = requests.get(base_url, params=params, headers=HEADERS)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        results = []
        for item in soup.select('.snippet')[:max_results]:
            link = item.select_one('.snippet-title')
            if link and 'href' in link.attrs:
                url = link['href']
                results.append(url)

        if not return_content:
            return results

        return get_contents(results)

    except requests.RequestException as e:
        print(f"An error occurred while searching Brave: {e}")
        return []

def search_qwant(query, max_results=10, return_content=False):
    base_url = "https://www.qwant.com/"
    params = {
        "q": query,
        "t": "web"
    }

    try:
        response = requests.get(base_url, params=params, headers=HEADERS)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        results = []
        for item in soup.select('.result__url')[:max_results]:
            if 'href' in item.attrs:
                url = item['href']
                results.append(url)

        if not return_content:
            return results

        return get_contents(results)

    except requests.RequestException as e:
        print(f"An error occurred while searching Qwant: {e}")
        return []

def is_searxng_alive(timeout=5):
    try:
        response = requests.get(SEARXNG_URL, timeout=timeout)
        if response.status_code == 403:
            print("SearXNG instance returned a 403 Forbidden error. Check your NAS and SearXNG configurations.")
            return False
        return response.status_code == 200
    except ValueError as e:
        print(f"Error checking SearXNG availability: {e}")
        return False

def combined_search(query, max_results, return_content=True):
    google_results = search_google(query, API_KEY_GOOGLE, CX_GOOGLE, max_results=max_results, return_content=return_content)
    duckduckgo_results = search_duckduckgo(query, max_results=max_results, return_content=return_content)
    searxng_results = search_searxng(query, max_results=max_results, return_content=return_content)
    yandex_results = search_yandex(query, max_results=max_results, return_content=return_content)
    bing_results = search_bing(query, max_results=max_results, return_content=return_content)
    brave_results = search_brave(query, max_results=max_results, return_content=return_content)
    qwant_results = search_qwant(query, max_results=max_results, return_content=return_content)

    combined_results = []
    for result in google_results + duckduckgo_results + searxng_results + yandex_results + bing_results + brave_results + qwant_results:
        combined_results.append({"content": result})

    return combined_results

def combined_image_search(query, max_results):
    google_results = search_image_google(query, API_KEY_GOOGLE, CX_GOOGLE, num_results=max_results)
    duckduckgo_results = list(search_image_duckduckgo(query, max_results=max_results))

    searxng_results = []
    if is_searxng_alive():
        searxng_results = search_image_searxng(query, max_results=max_results)
    else:
        print("SearXNG instance is not available. Proceeding with other search engines.")

    yandex_results = search_image_yandex(query, max_results=max_results)
    bing_results = search_image_bing(query, max_results=max_results)
    brave_results = search_image_brave(query, max_results=max_results)
    qwant_results = search_image_qwant(query, max_results=max_results)

    return google_results + duckduckgo_results + searxng_results + yandex_results + bing_results + brave_results + qwant_results

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