"""
This module contains tool functions to access Gitea.
"""

from dataclasses import dataclass, field

import json
import requests

from progress.spinner import Spinner

from settings import REQUEST_TIMEOUT, Settings
from logger import Logger

@dataclass
class Gitea:
    """
    Class to manage connection with Gitea
    """

    settings: Settings = field(default_factory=Settings)
    logger: Logger = field(default_factory=Logger)

    def __init__(self, settings: Settings, logger: Logger):
        """
        Initialize the Logger with a Streamlit message container.
        
        Parameters:
        mc (st.container): The Streamlit container for displaying messages.
        """
        self.logger = logger
        self.settings = settings

    def build_header(self):
        """
        Builds the header for the Gitea authentication.
        """
        return {
            'accept': 'application/json',
            'Authorization': f"token {self.settings.get_gitea_tokenl()}"
        }

    def fetch_user_info(self):
        """
        Fetches the authenticated user's information to test the token's validity and permissions.
        """
        url = f"{self.settings.get_gitea_api_url()}/user"
        try:
            response = requests.get(url, headers=self.build_header(), timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                user_info = response.json()
                self.logger.debug(f"User Info: {json.dumps(user_info, indent=3)}")
                return user_info

            self.logger.error(f"Failed to fetch user info: {response.text}")

        except requests.exceptions.RequestException as e:
             self.logger.exception(f"{e}")

        return None

    def get_organisations(self):
        """
        List all organisations that the authenticated user is a member of.
        Returns a list of organisations with details including their names.
        """
        url = f"{self.settings.get_gitea_api_url()}/orgs"
        try:
            response = requests.get(url, headers=self.build_header(), timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                organisations = response.json()
                print("Organizations:", json.dumps(organisations, indent=3))
                return organisations

            self.logger.error("Querying Gitea failed: {response.text}")

        except requests.exceptions.RequestException as e:
            self.logger.exception(f"{e}")

        return None

    def get_repositories(self):
        """
        Retrieve all repositories for a given organization in Gitea.
        """
        url = f"{self.settings.get_gitea_api_url()}/orgs/{self.settings.get_gitea_org()}/repos"
        try:
            response = requests.get(url, headers=self.build_header(), timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                repos = response.json()
                print("Repos:", json.dumps(repos, indent=3))
                return repos

            self.logger.error("Querying Gitea failed: {response.text}")

        except requests.exceptions.RequestException as e:
            self.logger.exception(f"{e}")

        return None

    def get_issues(self, repo_name):
        """
        Retrieve issues for a given repository in Gitea.
        """
        url = f"{self.settings.get_gitea_base_url()}/api/v1/repos/{self.settings.get_gitea_org()}/{repo_name}/issues"

        p_spinner = Spinner('Loading ')

        try:
            response = requests.get(url, headers=self.build_header(), timeout=REQUEST_TIMEOUT)
            p_spinner.next()
            if response.status_code == 200:
                issues = response.json()

                return issues

            self.logger.error(f"Querying Gitea failed: {response.text}")

        except requests.exceptions.RequestException as e:
            self.logger.exception(f"{e}")

        finally:
            p_spinner.finish()

        return None

    def update_issue(self, repo_owner, repo_name, issue_index, update_data):
        """
        Update a specific issue in Gitea.
        
        :param update_data: a dictionary with fields to update, e.g., {"state": "closed"}
        """
        base_url = f"{self.settings.get_gitea_api_url()}/repos/"
        url = f"{base_url}{repo_owner}/{repo_name}/issues/{issue_index}"
        try:
            response = requests.patch(
                url, headers=self.build_header(), json=update_data, timeout=REQUEST_TIMEOUT)

            if response.status_code == 200:
                self.logger.info("Issue updated successfully")
                return response.json()

            self.logger.error(f"Failed to update issue. Status code: {response.status_code}, Response: {response.text}")

        except requests.exceptions.RequestException as e:
            self.logger.exception(f"{e}")

        return None

    def get_issue(self, repo_name, issue_id):
        """
        Retrieve a specific issue by ID for a given repository in Gitea.
        """
        base_url = f"{self.settings.get_gitea_base_url()}/api/v1/repos/"
        url = f"{base_url}{self.settings.get_gitea_org()}/{repo_name}/issues/{issue_id}"

        try:
            response = requests.get(url, headers=self.build_header(), timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                issue = response.json()

                return issue

            self.logger.error(f"Querying Gitea failed: {response.text}")

        except requests.exceptions.RequestException as e:
            self.logger.exception(f"{e}")

        return None
