"""
Tools to access and update Odoo data
"""

from dataclasses import dataclass, field
from typing import List
import json
import datetime

from settings import MODELS, ID_SEARCH_PATTERN, TITLE_SEARCH_PATTERN
from settings import DESCRIPTION_SEARCH_PATTERN, get_link_search_pattern
from logger import Logger

from .project import Project
from .source import Source
from .timesheets import Timesheets

TASK_PAGING_LIMIT = 200

@dataclass
class Odoo:
    """
    Class that gives access to Odoo's external API
    Uses a wrapper for projects and timesheets
    """

    username: str = field(default_factory=str)
    uid: int = field(default_factory=int)
    api_key: str = field(default_factory=str)
    db: str = field(default_factory=str)
    company_id: int = field(default_factory=int)
    partner_id: int = field(default_factory=int)
    projects: List[Project] = field(default_factory=list)
    timesheets: Timesheets = field(default_factory=Timesheets, init=False)
    logger: Logger = field(default_factory=Logger)

    def __init__(self, st_odoo, st_projects, logger):
        self.username = st_odoo['username']
        self.uid = st_odoo['uid']
        self.api_key = st_odoo['api_key']
        self.db = st_odoo['db']
        self.company_id = st_odoo['company_id']
        self.partner_id = st_odoo['partner_id']

        self.projects = [Project(st_project) for st_project in st_projects]
        self.logger = logger
        self.timesheets = Timesheets(st_odoo, self.logger)

    def get_fields(self, *additional_fields):
        """
        Returns a list of default fields with additional fields if provided.
        Args:
        *additional_fields (str): Variable number of additional field names to include.
        
        Returns:
        list: List of fields including both base and additional fields if provided.
        """

        base_fields = ['name', 'id', 'description', 'priority', 'project_id',
                    'stage_id', 'task_properties']
        # Add any extra field names provided to the base fields list
        return base_fields + list(additional_fields)

    def get_ext_id_field_name(self, st_project) -> str:
        """
        Return the name of the field being used to store the external id
        """

        return Source(st_project['source']).value

    def get_odoo_projects(self):
        """
        Get a list of projects by company id and partner id
        """

        try:
            return MODELS.execute_kw(
                self.db, self.uid, self.api_key,
                'project.project', 'search_read',
                [[['partner_id', '=', self.partner_id],
                ['x_studio_azure_devops_org', '=', 'worldfoodprogramme']]],
                {'fields': ['name', 'id']})

        except ValueError:
            self.logger.error(ValueError)
            return None

    def get_project_tasks(self, domain, fields: str):
        """
        Get project tasks based on the domain and fields in the parameters
        """

        tasks = []
        offset = 0

        while True:
            try:
                _tasks = MODELS.execute_kw(
                    self.db, self.uid, self.api_key,
                    'project.task', 'search_read',
                    domain,
                    {'fields': fields,
                    'limit': TASK_PAGING_LIMIT, 'offset': offset}
                )
            except ValueError:
                self.logger.error(ValueError)
                break

            if _tasks:
                tasks += _tasks
                offset += len(_tasks)
            else:
                break

        return tasks

    def get_project_tasks_without_ext_id(self, st_project):
        """
        Returns project tasks with no ado id
        TODO: how to have this done in just one query: using =?
        """

        ext_field_name = self.get_ext_id_field_name(st_project)
        domain = [[['project_id', '=', st_project['odoo_project_id']], [ext_field_name, '=?', '0']]]
        fields = ['name', 'id', 'description', 'priority', 'project_id', 'stage_id',
            'task_properties', ext_field_name]

        tasks = self.get_project_tasks(domain, fields)

        return tasks

    def get_project_tasks_with_ext_id(self, st_project):
        """
        Returns project tasks with no ado id
        """

        ext_field_name = self.get_ext_id_field_name(st_project)

        tasks = self.get_project_tasks(
            [[['project_id', '=', st_project['odoo_project_id']], [ext_field_name, '!=', '0']]],
            ['name', 'id', 'description', 'priority', 'project_id', 'stage_id',
            'task_properties', ext_field_name]
            )

        # removing items with external id == False
        filtered_tasks = [item for item in tasks if item[ext_field_name] is not False]

        return filtered_tasks

    def get_all_project_tasks(self, st_project):
        """
        Returns all project tasks
            - x_studio_external_system: gitea, ado
            - x_studio_external_id: str
        """

        ext_id_field_name = self.get_ext_id_field_name(st_project)

        if not ext_id_field_name:
            return None

        return self.get_project_tasks(
            [[['project_id', '=', st_project['odoo_project_id']]]],
            ['name', 'id', 'description', 'priority', 'project_id', 'stage_id',
            'task_properties', ext_id_field_name]
            )

    def get_all_project_tasks_with_all_fields(self, project_id):
        """
        Returns project all project tasks with all fields
        """
        return self.get_project_tasks(
            [[['project_id', '=', project_id]]],
            [])

    def update_task_ext_id(self, st_project, task):
        """
        Updates the id inside odoo to match the id in the task name
        Returns the id that was found
        """

        ext_id_field_name = self.get_ext_id_field_name(st_project)

        task_id = task['id']
        ext_id_from_name = 0

        # Extract the 6-digit number from the task's name
        match = ID_SEARCH_PATTERN.search(task['name'])

        if match and ext_id_field_name:
            current_ext_id = task.get(ext_id_field_name)

            if isinstance(current_ext_id, str):
                current_ext_id = int(current_ext_id)

            ext_id_from_name = int(match.group(0))

            # Check if the current id matches the found number
            if current_ext_id != ext_id_from_name:
                # Update the id field
                try:
                    MODELS.execute_kw(
                        self.db, self.uid, self.api_key,
                        'project.task', 'write',
                        [[task_id], {ext_id_field_name: ext_id_from_name}])

                    self.logger.info(f"UPDATED: ID {task_id}, {task['name']}")

                except ValueError:
                    self.logger.exception(ValueError)
            else:
                self.logger.debug(f"NO UPDATE NEEDED: ID {task_id}, {task['name']}")

        else:
            self.logger.warning(f"NO ID FOUND: ID {task_id}, {task['name']}")

        return ext_id_from_name

    def update_odoo_task(self, task_data) -> bool:
        """
        Update task information
        """

        if not task_data:
            self.logger.error("No task data")
            return False

        if 'id' not in task_data:
            self.logger.error("Task data missing the task id")
            return False

        # remove id from task to avoid issues when updating tasks with validated timesheets
        task_id = task_data.pop('id', None)

        # Update the existing task
        try:
            MODELS.execute_kw(
                self.db, self.uid, self.api_key,
                'project.task', 'write', [[task_id], task_data])

            return True

        except ValueError:
            self.logger.exception(ValueError)
            self.logger.debug(json.dumps(task_data, indent=2))

        return False

    def create_odoo_task(self, task_data) -> bool:
        """
        Creates a new task in Odoo
        """

        if not task_data:
            self.logger.error("No task data")
            return False

        try:
            task_id = MODELS.execute_kw(
                self.db, self.uid, self.api_key,
                'project.task', 'create', [task_data])

            self.logger.info(f"CREATED TASK {task_id}: {task_data['name']}")

            return True

        except ValueError:
            self.logger.exception(ValueError)
            self.logger.debug(json.dumps(task_data, indent=2))

        return False

    def get_user_id(self, email: str) -> int:
        """
        Search for user id based on email
        """

        user_records = MODELS.execute_kw(
            self.db, self.uid, self.api_key,
            'res.users', 'search_read',  [[['login', '=', email]]], {'fields': ['id', 'name']})

        # returns 0 if more than one result is found
        if len(user_records) > 1:
            return 0

        # Returns the first result
        for user in user_records:
            return user['id']

        return 0

    def update_odoo_task_data(self, st_project, old_task_data, new_task_data, to_compare:bool = False):
        """
        Builds task data for:
            - Updating Odoo
            - OR comparing with data retrieved from Odoo
        """

        # Revert to data from the Odoo task if it exists
        if old_task_data:
            new_task_data['id'] = old_task_data['id']
            pid = old_task_data['project_id']
            new_task_data['project_id'] = pid if to_compare else pid[0]
        else:
            # If created to compare, add the extra information
            proj_id = st_project['odoo_project_id']

            if to_compare:
                new_task_data['project_id'] = [proj_id, st_project['project_name']]
            else:
                new_task_data['project_id'] = proj_id

    def search_odoo_task(self, 
            st_project, task_field_value, include_properties:bool = False):
        """
        Searches for odoo task based on specified field and value
        """

        ext_id_field_name = self.get_ext_id_field_name(st_project)

        fields = {'fields': ['id', 'name', 'project_id', ext_id_field_name,
                            'priority', 'description', 'stage_id']}

        # TO BE REMOVED: TODO
        if st_project['source'] == 'gitea':
            fields['fields'].append('x_studio_external_system')

        if include_properties:
            fields['fields'].append('task_properties')

        # Check if the task already exists in Odoo
        try:
            odoo_tasks = MODELS.execute_kw(
                self.db, self.uid, self.api_key,
                'project.task', 'search_read', 
                [[['project_id', '=', st_project['odoo_project_id']],
                    [ext_id_field_name, '=', task_field_value]]],
                fields)

            return odoo_tasks

        except ValueError:
            self.logger.exception(ValueError)

        return None

    def move_timesheet(self, timesheet_id, new_task_id):
        """
        Move a timesheet entry to a different task.
        """
        try:
            # The 'write' method updates records with given ids and data
            result = MODELS.execute_kw(
                self.db, self.uid, self.api_key,
                'account.analytic.line', 'write',
                [[timesheet_id], {'task_id': new_task_id}])
            if result:
                self.logger.info(f"Successfully moved timesheet {timesheet_id} to task {new_task_id}")
            else:
                self.logger.warning(f"Failed to move timesheet {timesheet_id} to task {new_task_id}")
        except ValueError:
            self.logger.error(ValueError)
            return False

        return True

    def get_recent_project_tasks(self, st_project, recent_days=3):
        """
        Get project tasks based on the domain and fields in the parameters.
        Optionally filter tasks that were created or updated within the last `recent_days` days.

        Args:
        st: Session token.
        domain: Domain conditions list.
        fields: List of fields to retrieve.
        recent_days: Number of days to look back for recently updated tasks.

        Returns:
        A list of tasks.
        """

        ext_field_name = self.get_ext_id_field_name(st_project)

        date_limit = datetime.datetime.now() - datetime.timedelta(days=recent_days)
        date_limit_str = date_limit.strftime('%Y-%m-%d %H:%M:%S')

        domain = [[
            ['project_id', '=', st_project['odoo_project_id']],
            ['create_date', '>=', date_limit_str]
        ]]

        return self.get_project_tasks(
            domain,
            self.get_fields(ext_field_name, 'write_date', 'create_date')
            )

    def check_task_content(self, st_project, task):
        """
        Checks if a task in Odoo contains the necessary information:
            - Name that follows the pattern: `id` - `title`
                - `id` an external id number from 1 to 6 digits
                - `title` a text string
            - Description with a link to the external system
                - The external system id will be in the link
            - External system
                - External system name: ADO or Gitea
                - External system ID: same as `id` 
        """

        # Check task name pattern
        name_match = TITLE_SEARCH_PATTERN.match(task['name'])
        if not name_match:
            self.logger.info(f"Task missing information: {task['id']} - {task['name']}")
            return False

        task_id, task_title = name_match.groups()

        # Check description for a link containing the external system ID
        link_pattern = get_link_search_pattern(task_id)
        if isinstance(task['description'], bool) or not link_pattern.search(task['description']):
            self.logger.info(f"Task missing information: {task['id']} - {task_title}")
            return False

        # Check external system: TODO
        # external_system = task['external_system']
        # if external_system['name'] not in ['ADO', 'Gitea']:
        #     print("External system name is not recognized.")
        #     return False

        ext_id_field_name = self.get_ext_id_field_name(st_project)
        ext_id = task.get(ext_id_field_name)

        # make sure the ids are ints before comparing them
        task_id = int(task_id) if isinstance(task_id, str) else task_id
        ext_id = int(ext_id) if isinstance(ext_id, str) else ext_id

        if ext_id != task_id:
            self.logger.info(f"Task missing information: {task['id']} - {task['name']}")
            return False

        return True

    def get_task_ext_id(self, st_project, task) -> int:
        """
        Generic function to retrieve the task external id.
        Tries to get the external id from the task dictionary first, and if it's not found,
        it attempts to extract it from the task's name.
        """
        # Try to retrieve the external ID using the field name specific to the project
        if (ext_id := task.get(self.get_ext_id_field_name(st_project))):
            return ext_id

        # Try to get the external ID from the task's name
        if (ext_id := self.get_task_ext_id_from_name(task)):
            return ext_id

        # Try to get the external ID from the task's description
        if (ext_id := self.get_task_ext_id_from_description(task)):
            return ext_id

        return None

    def get_task_ext_id_from_name(self, task) -> int | None:
        """
        Retrieves the external id from the task name
        """

        if (match := ID_SEARCH_PATTERN.search(task['name'])):
            return int(match.group(0))

        return None

    def get_task_ext_id_from_description(self, task) -> int | None:
        """
        Retrieves the external id from the task description
        """

        # if the field is empty Odoo may return a boolean
        if isinstance(task['description'], bool):
            return None

        # Check description for a link containing the external system ID
        if (match := DESCRIPTION_SEARCH_PATTERN.search(task['description'])):
            return int(match.group(0))

        return None

    def log_timesheet(self, task_id, duration_minutes, description, date_to_log: str = datetime.datetime.now().strftime('%Y-%m-%d')):
        """
        Logs a timesheet entry with the given duration in minutes
            and associates it with the specified task.
        
        Args:
            st (dict): The session token and authentication information.
            task_id (int): The ID of the task to associate with the timesheet.
            duration_minutes (int): The duration in minutes to log in the timesheet.
        """

        # Calculate the number of hours from minutes
        duration_hours = duration_minutes / 60

        # Prepare the timesheet entry data
        timesheet_data = {
            'task_id': task_id,
            'unit_amount': duration_hours,
            'date': date_to_log,
            'name': description
        }

        self.logger.debug(f'Timesheet data: {timesheet_data}')

        try:
            # Create the timesheet entry
            timesheet_id = MODELS.execute_kw(
                self.db, self.uid, self.api_key,
                'account.analytic.line',
                'create', [timesheet_data]
            )

            self.logger.info(f"Logged timesheet entry {timesheet_id} for task {task_id}")

            # Get the total time logged by the user for date_to_log
            total_time_logged = MODELS.execute_kw(
                self.db, self.uid, self.api_key,
                'account.analytic.line', 
                'search_read', 
                [
                    [
                        ('date', '=', date_to_log),
                        ('user_id', '=', self.uid)
                    ]
                ],
                {'fields': ['unit_amount']}
            )

            total_time_logged_hours = sum(x['unit_amount'] for x in total_time_logged)

            return total_time_logged_hours

        except ValueError as e:
            self.logger.exception(e)
            return None

    def get_task_id_by_name(self, task_name):
        """
        Fetches the task ID based on the given task name.
        
        Args:
            st (dict): The session token and authentication information.
            task_name (str): The name of the task to search for.
        
        Returns:
            int: The task ID if found, otherwise None.
        """

        try:
            # Perform the search for the task using the task name
            task_records = MODELS.execute_kw(
                self.db, self.uid, self.api_key,
                'project.task',
                'search_read',
                [[['name', '=', task_name]]],
                {'fields': ['id']}
            )

            # Return the first matching task's ID if found
            if task_records:
                return task_records[0]['id']

            self.logger.info(f"No task found with the name {task_name}")
            return None

        except ValueError as e:
            self.logger.exception(e)
            return None

    def get_task_id_by_ext_id(self, ext_id):
        """
        Returns project tasks with no ado id
        """

        if not isinstance(ext_id, str):
            ext_id = str(ext_id)

        ext_field_name = 'x_studio_azure_devops_id'

        tasks = self.get_project_tasks(
            [[['project_id', '!=', '0'], [ext_field_name, '=', ext_id]]],
            ['name', 'id', 'description', 'priority', 'project_id', 'stage_id',
            'task_properties', ext_field_name]
            )

        # removing items with external id == False
        filtered_tasks = [item for item in tasks if item[ext_field_name] is not False]

        return filtered_tasks
