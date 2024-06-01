"""
Module to manage the settings file.
"""

from dataclasses import dataclass, field
import xmlrpc.client
import tomllib as tl
import os
import sys
import re

from logger import Logger

# Newlogic's Odoo URL
URL = "https://erp.newlogic.com"

# XML-RPC endpoints
COMMON = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/common')
MODELS = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/object')

# Example defaults
DEFAULT_SETTINGS = {
    'odoo': {
        'company_id': 0,
        'partner_id': 0,
        'project_id': 0,
    },
}

ID_SEARCH_PATTERN = re.compile(r'^\d{1,6}\b')
TITLE_SEARCH_PATTERN = re.compile(r'^(\d{1,6}) - (.+)$')
DESCRIPTION_SEARCH_PATTERN = re.compile(r'https?://[^\s]+/(\d{1,6})')

REQUEST_TIMEOUT = 30  # seconds
ADO_PAGE_SIZE = 50  # maximum number of wits per query

def get_link_search_pattern(task_id):
    """
    Returns the link search pattern integrating the task id
    """
    return re.compile(r'https?://[^\s]+/' + task_id)

@dataclass
class Settings:
    """
    Manage all the settings
    """

    # to host all the settings
    base: dict = field(default_factory=dict)
    logger: Logger = field(default_factory=Logger)

    # to load settings at instantiation time
    def __init__(self, file_name: str, logger: Logger):
        self.logger = logger
        self.base = self.read_settings(file_name)

    def get_base_path(self):
        """
        Gets the base path of the execution.
        """
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
        return os.path.abspath(".")

    def read_settings(self, file_name: str) -> dict:
        """
        Reads the settings file.
        """
        base_path = self.get_base_path()
        self.base = DEFAULT_SETTINGS.copy()
        full_path = os.path.join(base_path, file_name)

        try:
            with open(full_path, "rb") as file:
                file_settings = tl.load(file)
                for section, settings in file_settings.items():
                    if section in self.base:
                        self.base[section].update(settings)
                    else:
                        self.base[section] = settings

            self.logger.info(f"Validating {file_name}...")

            if self.validate_settings():
                return self.base

        except FileNotFoundError:
            self.logger.exception(f"Please make sure you have a file called {file_name}")
        except ValueError:
            self.logger.exception(ValueError)
        return None

    def validate_settings(self) -> bool:
        """
        Validate the settings and suggest values if they are missing.
        """
        if not self.base:
            return False

        errors = False

        errors |= self.validate_odoo_settings()

        errors |= self.validate_ado_settings()

        return not errors

    def validate_odoo_settings(self) -> bool:
        """
        Validate the Odoo settings and suggest values if they are missing.
        """
        if not self.base:
            return False

        errors = False

        self.logger.info("Validating Odoo settings")

        # Validate Odoo settings
        odoo_fields = ['username', 'db', 'api_key']
        for odoo_field in odoo_fields:
            if not self.base['odoo'].get(odoo_field):
                self.logger.warning(f"MISSING: Odoo field: {odoo_field}")
                errors = True

        if not errors:
            uid = self.authenticate_user(self.base['odoo'])
            if uid is None:
                errors = True
            else:
                self.base['odoo']['uid'] = uid
                errors |= self.validate_company_partner_project_ids()

        return errors

    def validate_ado_settings(self) -> bool:
        """
        Validate the Azure DevOps settings.
        """
        if not self.base:
            return False

        errors = False

        self.logger.info("Validating ADO settings")

        # Validate Odoo settings
        ado_fields = ['username', 'pat', 'base_url', 'organisation']
        for ado_field in ado_fields:
            if not self.base['ado'].get(ado_field):
                self.logger.warning(f"MISSING: ADO field: {ado_field}")
                errors = True

        return errors

    def authenticate_user(self, odoo_settings):
        """
        Authenticate the user and return UID.
        """
        try:
            uid = COMMON.authenticate(
                odoo_settings['db'],
                odoo_settings['username'],
                odoo_settings['api_key'],
                {})
            if uid == 0:
                self.logger.error(f"Failed to authenticate user {odoo_settings['username']}. Check credentials.")
                return None
            self.logger.info(f"User id: {uid}")
            return uid
        except ValueError:
            self.logger.exception(ValueError)
            return None

    def validate_company_partner_project_ids(self):
        """
        Validates company_id, partner_id, and project_id, fetching their information if missing.
        """
        errors = self.fetch_company_info()
        errors |= self.fetch_partner_info()
        errors |= self.fetch_project_info()
        return errors

    def fetch_company_info(self):
        """
        Fetches and validates company information from Odoo.
        """
        errors = False
        if self.base['odoo']['company_id'] in [0, '']:
            self.logger.warning("MISSING: odoo: company_id")
            try:
                companies = MODELS.execute_kw(
                    self.base['odoo']['db'], self.base['odoo']['uid'], self.base['odoo']['api_key'],
                    'res.company', 'search_read', [[]],
                    {'fields': ['name', 'id']})
                if companies:
                    self.logger.info("Available companies:")
                    for company in companies:
                        self.logger.info(f"Company id: {company['id']}, Company name: {company['name']}")
                else:
                    self.logger.warning("No companies found.")
                errors = True
            except ValueError:
                self.logger.exception(ValueError)
                errors = True
        return errors

    def fetch_partner_info(self):
        """
        Fetches and validates partner information from Odoo.
        """
        errors = False
        if self.base['odoo']['partner_id'] in [0, '']:
            self.logger.warning("MISSING: odoo: partner_id")
            try:
                partners = MODELS.execute_kw(
                    self.base['odoo']['db'], self.base['odoo']['uid'], self.base['odoo']['api_key'],
                    'res.partner', 'search_read',
                    [[['is_company', '=', True]]],
                    {'fields': ['id', 'name']})
                if partners:
                    self.logger.info("Available partners:")
                    for partner in partners:
                        self.logger.info(f"Partner id: {partner['id']}, Partner name: {partner['name']}")
                else:
                    self.logger.warning("No partners found.")
                errors = True
            except ValueError:
                self.logger.exception(ValueError)
                errors = True
        return errors

    def validate_projects(self):
        """
        Validates the presence of projects and their required fields.
        """
        errors = False
        if 'projects' not in self.base:
            return True

        for odoo_project in self.base['projects']:
            for odoo_field in ['source', 'odoo_project_id']:
                if not odoo_project.get(odoo_field):
                    self.logger.warning(f"MISSING: project field: {odoo_field}")
                    errors = True
        return errors

    def log_missing_project_id_and_fetch(self, st_project):
        """
        Logs missing project IDs and fetches available project IDs from Odoo.
        """
        errors = False
        if st_project['odoo_project_id'] in [0, '']:
            self.logger.warning("MISSING: odoo: project_id")
            try:
                odoo_projects = MODELS.execute_kw(
                    self.base['odoo']['db'], self.base['odoo']['uid'], self.base['odoo']['api_key'],
                    'project.project', 'search_read',
                    [[['user_id', '=', self.base['odoo']['uid']]]],
                    {'fields': ['name', 'id']})
                if odoo_projects:
                    self.logger.info(f"Projects with PM: {self.base['odoo']['username']}")
                    for odoo_project in odoo_projects:
                        self.logger.info(f"Project id: {odoo_project['id']}, NAME: {odoo_project['name']}")
                else:
                    self.logger.warning("No projects found")
                errors = True
            except ValueError:
                self.logger.exception(ValueError)
                errors = True
        return errors

    def fetch_and_store_project_name(self, index, st_project):
        """
        Fetches and stores the project name for an existing project ID.
        """
        errors = False
        try:
            odoo_project = MODELS.execute_kw(
                self.base['odoo']['db'], self.base['odoo']['uid'], self.base['odoo']['api_key'],
                'project.project', 'search_read',
                [[['id', '=', int(st_project['odoo_project_id'])]]],
                {'fields': ['name']})
            if odoo_project:
                project_name = odoo_project[0]['name']
                self.logger.info(f"Project name: {project_name}")
                self.base['projects'][index]['project_name'] = project_name
            else:
                self.logger.warning("No project found with ID {st_project['odoo_project_id']}")
                errors = True
        except ValueError:
            self.logger.exception(ValueError)
            errors = True
        return errors

    def fetch_project_info(self):
        """
        Validates project information in the settings file.
        Fetches information from Odoo for the user to complete the settings file.
        """
        errors = self.validate_projects()

        if errors:
            self.logger.warning(("MISSING: projects or projects information",
                            "Projects must contain: ",
                            "source, odoo_project_id, ado_query_id OR gitea_repository"))

        for index, st_project in enumerate(self.base.get('projects', [])):
            errors |= self.log_missing_project_id_and_fetch(st_project)
            errors |= self.fetch_and_store_project_name(index, st_project)

        return errors

    def get_odoo(self):
        return self.base['odoo']

    def get_projects(self):
        return self.base['projects']

    def get_odoo_db(self):
        return self.base['odoo']['db']

    def get_odoo_uid(self):
        return self.base['odoo']['uid']

    def get_odoo_api_key(self):
        return self.base['odoo']['api_key']

    def get_ado_base_url(self):
        return self.base['ado']['base_url']

    def get_ado_username(self):
        return self.base['ado']['username']

    def get_ado_org(self):
        return self.base['ado']['organisation']

    def get_ado_pat(self):
        return self.base['ado']['pat']

    def get_gitea_api_url(self):
        return self.base['gitea']['GITEA_API_URL']

    def get_gitea_base_url(self):
        return self.base['gitea']['BASE_URL']

    def get_gitea_tokenl(self):
        return self.base['gitea']['GITEA_TOKEN']

    def get_gitea_org(self):
        return self.base['gitea']['organisation']
