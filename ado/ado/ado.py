"""
This module contains tool functions to access ADO.
"""

import base64
import math
from io import BytesIO
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
import requests
from PIL import Image
from bs4 import BeautifulSoup
import validators

from settings import Settings, REQUEST_TIMEOUT, ADO_PAGE_SIZE
from ocr import perform_mem_ocr
from logger import Logger

@dataclass
class Ado:
    """
    Class to manage the ADO API connections
    """

    settings: Settings = field(default_factory=Settings)
    logger: Logger = field(default_factory=Logger)
    base_url: str = field(default_factory=str)

    def __init__(self, settings: Settings, logger: Logger):
        """
        Initialize the Logger with a Streamlit message container.
        
        Parameters:
        mc (st.container): The Streamlit container for displaying messages.
        """
        self.logger = logger
        self.settings = settings
        self.base_url = self.settings.get_ado_base_url() + self.settings.get_ado_org()

    def build_header(self, is_patch=False):
        """
        Builds the header for the ADO authentication.
        """

        user_and_pat = f"{self.settings.get_ado_username()}:{self.settings.get_ado_pat()}"
        encoded_bytes = base64.b64encode(user_and_pat.encode("utf-8"))

        # Encode the string as bytes, then encode it in base64
        encoded_bytes = base64.b64encode(user_and_pat.encode("utf-8"))

        if is_patch:
            return {"Content-Type": "application/json-patch+json",
                    "authorization": "Basic " + encoded_bytes.decode("utf-8")}

        return {"authorization": "Basic " + encoded_bytes.decode("utf-8")}

    def get_base_url(self):
        """
        Returns the base URL for ADO.
        """

        return self.base_url

    def query(self, st_project, query_id=None):
        """
        Query Azure DevOps for work item information based on the provided query ID.
        """

        header = self.build_header()
        if not query_id:
            query_id = st_project['ado_query_id']

        url = self.base_url + f"/_apis/wit/wiql?id={query_id}"

        try:
            response = requests.get(url, headers=header, timeout=REQUEST_TIMEOUT)
        except ValueError:
            self.logger.exception(f"{ValueError}")
            return None

        if response.status_code == 200:
            return response.json()

        return None

    def get_wits(self, ids):
        """
        Retrieve information about a list of work items in Azure DevOps.
        """
        if not ids:
            self.logger.info("Query returned no results")
            return []

        header = self.build_header()
        wits = []
        batches = math.ceil(len(ids) / ADO_PAGE_SIZE)
        base_url = self.base_url + "/_apis/wit/workitems?ids="

        for batch in range(batches):
            start_index = batch * ADO_PAGE_SIZE
            end_index = min((batch + 1) * ADO_PAGE_SIZE, len(ids))
            id_list = ",".join(map(str, ids[start_index:end_index]))

            url = f"{base_url}{id_list}"
            response = None

            try:
                response = requests.get(url, headers=header, timeout=REQUEST_TIMEOUT)
            except ValueError as e:
                self.logger.error(f"{e}")
                continue

            if response.status_code == 200:
                wit_data = response.json()
                wits.extend(wit_data['value'])

                if len(wit_data['value']) != len(ids[start_index:end_index]):
                    self.logger.error(
                        f"ADO: MISMATCH: Requested: {len(ids[start_index:end_index])}, "
                        f"Returned: {len(wit_data)}")
            else:
                self.logger.error(f"Querying ADO failed: {response.text}")

        return wits

    def get_wit(self, item_id):
        """
        Retrieve information about a single work item in Azure DevOps.
        """

        if not item_id or item_id <= 0:
            return None

        header = self.build_header()

        wit = []

        url = self.base_url + "/_apis/wit/workitems?ids=" + str(item_id)

        try:
            response = requests.get(url, headers=header, timeout=REQUEST_TIMEOUT)

            if response.status_code == 200:
                wit_data = response.json()
                wit.extend(wit_data['value'])

                if len(wit) == 1:
                    return wit[0]
            else:
                self.logger.error(f"ADO: ERROR: {response.text}")

        except ValueError:
            self.logger.error(ValueError)

        return None

    def get_comments_thread(self, item_id):
        """
        Retrieve comments thread for a specific work item in Azure DevOps.
        """

        if item_id <= 0:
            return None

        header = self.build_header()
        url = self.base_url + f"/_apis/wit/workItems/{item_id}/comments?"

        response = requests.get(url, headers=header, timeout=REQUEST_TIMEOUT)

        if response.status_code == 200:
            comments_data = response.json()

            if 'comments' in comments_data:
                return comments_data['comments']
        else:
            self.logger.error(f"ADO: ERROR: {response.text}")

        return None

    def update_wit_field(self, item_id, field_name, new_value):
        """
        Update a specific field of a work item in Azure DevOps.
        """

        if not self.settings or item_id <= 0 or not field_name or not new_value:
            return None

        # Modify the URL to fetch comments for the specified work item ID
        url = self.base_url + f"/_apis/wit/workItems/{item_id}?api-version=6.0"

        # Prepare the request headers
        header = self.build_header(True)

        data = [
            {
                "op": "add",
                "path": f"/fields/{field_name}",
                "value": new_value
            }
        ]
        response = requests.patch(url, json=data, headers=header, timeout=REQUEST_TIMEOUT)

        if response.status_code == 200:
            self.logger.success("Work item updated successfully")
            return response

        self.logger.error(
            f"Failed to update work item. Status code: {response.status_code}, "
            f"Response: {response.text}")
        return None

    def get_work_item_description(self, work_item_details) -> str:
        """
        Retrieves and cleans the work item description from Azure DevOps.

        This function extracts the description field from the given work item details.
        It checks for two possible fields that may contain the description: 'System.Description'
        and 'Microsoft.VSTS.TCM.ReproSteps'. The extracted text is then cleaned by removing
        HTML tags.

        Parameters:
            work_item_details (dict): Dictionary containing information about the work item,
            including its fields.

        Returns:
            str: The extracted and cleaned description of the work item.

        Notes:
            This function assumes that either 'System.Description' or
            'Microsoft.VSTS.TCM.ReproSteps' field contains the work item's description.
        """

        html_text = ""

        if 'System.Description' in work_item_details['fields']:
            html_text = work_item_details['fields']['System.Description']
        elif 'Microsoft.VSTS.TCM.ReproSteps' in work_item_details['fields']:
            html_text = work_item_details['fields']['Microsoft.VSTS.TCM.ReproSteps']

        no_html, pil_images = self.clean_html(html_text)

        return no_html, pil_images

    def get_days_since_closure(self, work_item_details) -> int:
        """
        Checks if a ticket in Azure DevOps is old (closed more than 7 days ago).

        This function takes a dictionary containing information about a work item,
            and checks if it has been closed and returns the number of days that the
            ticket has been closed for.

        Parameters:
            work_item_details (dict): Dictionary containing information about the work item,
                including its fields.

        Returns:
            bool: Whether the ticket should be skipped (True) or processed further (False).
        """

        # Check if the ticket has a closed date
        if 'Microsoft.VSTS.Common.ClosedDate' in work_item_details['fields']:
            closed_date_str = work_item_details['fields']['Microsoft.VSTS.Common.ClosedDate']

            # Parse the string to a datetime object and make it timezone-aware
            closed_date = datetime.strptime(
                closed_date_str,
                '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc)

            # Now, both datetimes are timezone-aware
            days_since_closed = (datetime.now(timezone.utc) - closed_date).days

            return days_since_closed

        return None

    def get_assigned_to(self, work_item_details):
        """Get the assigned user for a work item in Azure DevOps.

        This function takes a dictionary containing information about a work item
        and returns the name of the user who is assigned to that work item. If no
        assignment is found, it defaults to "unassigned".

        Parameters:
            work_item_details (dict): Dictionary containing information about the work item,
                including its fields.

        Returns:
            str: The name of the user assigned to the work item, or "unassigned" if not found.
        """

        assigned_to = "unassigned"

        try:
            if 'System.AssignedTo' in work_item_details['fields']:
                assigned_to = work_item_details['fields']['System.AssignedTo']['displayName']
        except ValueError as e:
            self.logger.exception(f"{e}")

        return assigned_to


    def format_comments(self, comments, ignore_older_than: int = 7):
        """
        Format a list of Azure DevOps comments for easier reading.

        This function takes a list of comments and returns a formatted string.
        It removes HTML tags from each comment, converts the revised date to a datetime object,
        and skips any comments that are older than 7 days. The remaining comments are then
        formatted into a readable string with their respective dates.

        Parameters:
            comments (list): A list of Azure DevOps comments.
            ignore_older_than (int): tickets older than the specificed number of days are ignored.

        Returns:
            str: A formatted string containing the filtered and cleaned comments.
        """

        if not comments:
            return None, None

        formatted_comments = []
        pil_images = []

        n_days_ago = datetime.now() - timedelta(days=ignore_older_than)

        for comment in comments:
            # Convert revisedDate to datetime
            revised_date_str = comment['revisedDate']

            # Try parsing with milliseconds first, then without
            try:
                revised_date = datetime.strptime(revised_date_str, '%Y-%m-%dT%H:%M:%S.%fZ')
            except ValueError:
                # If it fails, try parsing without milliseconds
                revised_date = datetime.strptime(revised_date_str, '%Y-%m-%dT%H:%M:%SZ')

            # Skip comments that are more than 7 days old by default
            if revised_date < n_days_ago:
                continue

            # extra text at the end because of the remove html also returning images now
            no_html, pil_images = self.clean_html(comment['text'])

            revised_date = revised_date.strftime('%Y-%m-%d %H:%M:%S')

            commenter = comment['revisedBy']['displayName']

            formatted_comment = f"{commenter} on {revised_date}: {no_html}  \n"
            formatted_comments.append(formatted_comment)

        return "\n".join(formatted_comments), pil_images

    def query_with_wiql(self, wiql_query):
        """
        Query Azure DevOps for work item information using a WIQL query.

        Parameters:
            settings (dict): ADO settings containing username and PAT.
            wiql_query (str): The WIQL query as a string.

        Returns:
            dict or None: The JSON response from Azure DevOps, or None if an error occurred.
        """

        # Build the header for authorization
        header = self.build_header()

        # Construct the URL
        url = self.base_url + "/_apis/wit/wiql?api-version=6.0"

        # Prepare the request body
        body = {"query": wiql_query}

        try:
            # Send the request to ADO
            response = requests.post(url, json=body, headers=header, timeout=REQUEST_TIMEOUT)

            # Check for successful response
            if response.status_code == 200:
                return response.json()
            else:
                self.logger.error(
                    f"Failed to query with WIQL. Status code: {response.status_code}, "
                    f"Response: {response.text}")
        except ValueError as e:
            self.logger.exception(f"{e}")

        return None

    def download_image(self, url):
        """
        Download an image from Azure DevOps given its URL.
        """

        header = self.build_header()
        try:
            response = requests.get(url, headers=header, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()  # Raise an error for bad status codes

            return response.content

        except requests.RequestException as e:
            self.logger.exception(f"{e}")

    def get_mem_image_files(self, urls, return_bytes = False):
        """
        Downloads image files from the given URLs and returns them as either BytesIO objects
         or PIL Image objects.

        Parameters:
            urls (list): A list of URLs pointing to the image files.
            return_bytes (bool, optional): If True, returns the image files as BytesIO objects.
             Defaults to False.

        Returns:
            list: A list of either BytesIO objects or PIL Image objects representing the downloaded
             image files.
                  Returns None if the urls parameter is empty.
        """
        if not urls:
            return None

        image_files = []

        for url in urls:
            image_data = self.download_image(url)

            if image_data:
                if return_bytes:
                    image_files.append(BytesIO(image_data))
                else:
                    image_files.append(Image.open(BytesIO(image_data)))

        return image_files

    def clean_html(self, html_text: str):
        """
        Cleans HTML text by removing newlines, removing HTML tags, and performing OCR on images.

        Args:
            html_text (str): The HTML text to be cleaned.

        Returns:
            tuple: A tuple containing two elements:
                - str: The cleaned HTML text with OCR text replacing image URLs.
                - list: A list of PIL Image objects representing the images extracted from the HTML.
                    Returns None if no image URLs are found.
        """
        image_info = self.get_image_info(html_text)

        html_text = html_text.replace('\n', ' ') # remove \n if any

        no_html = self.remove_html(html_text)

        if not image_info:
            return no_html, None

        image_files = self.get_mem_image_files(image_info['urls'], return_bytes=True)

        if not image_files:
            return no_html, None

        no_html = self.remove_html_keep_urls(html_text)

        image_pil_files = []

        for url, image_file in zip(image_info['urls'], image_files):
            # Perform OCR on the image in memory
            ocr_text = perform_mem_ocr(image_file.getvalue())

            if ocr_text:

                ocr_text = "\n<<<BEGIN_IMAGE_TEXT>>>\n" + ocr_text + "\n<<<END_IMAGE_TEXT>>>\n"

                # Replace the image URL in the original text with the OCR text
                no_html = no_html.replace(url, ocr_text)

            image_pil_files.append(Image.open(image_file))

        return no_html, image_pil_files

    def remove_html(self, html_text):

        if not html_text:
            return None

        soup = BeautifulSoup(html_text, 'html.parser')

        no_html = soup.get_text(separator=" ", strip=True)

        return no_html

    def get_image_info(self, html_text):

        # TODO: sometimes the image is embedded in the text
        # this case is not being handled yet

        if not html_text:
            return None

        soup = BeautifulSoup(html_text, 'html.parser')

        # Find all image tags
        img_tags = soup.find_all('img')

        if img_tags:

            img_urls = []

            # Extract the src attribute from each image tag
            for img in img_tags:
                if img.has_attr('src'):
                    img_urls.append(img['src'])

            if img_urls:
                image_info = {}
                image_info['tags'] = [str(tag) for tag in img_tags]
                image_info['urls'] = img_urls

                return image_info

    def remove_html_keep_urls(self, html_text):
        """
        Removes HTML tags from the given text but keeps valid URLs.

        Args:
            html_text (str): The HTML text to be cleaned.

        Returns:
            str: The text without HTML tags but with valid URLs preserved.
        """
        if not html_text:
            return None

        soup = BeautifulSoup(html_text, 'html.parser')

        # Replace image tags with their src attribute
        for img in soup.find_all('img'):
            if 'src' in img:
                img.replace_with(img['src'])
            else:
                print(f'SRC NOT FOUND IN IMG: {html_text}')

        # Replace anchor tags with their href attribute, but only keep valid URLs
        for a in soup.find_all('a'):
            href = a.get('href', '')
            if validators.url(href):
                a.replace_with(href)
            else:
                a.replace_with(a.get_text())

        # Get the text with URLs preserved
        no_html_text = soup.get_text(separator=" ", strip=True)

        return no_html_text
