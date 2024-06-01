"""
Module to provide data interfacing between Gitea and Odoo
"""

from dataclasses import dataclass, field

import json
from progress.bar import Bar

from odoo import Odoo
from logger import Logger

@dataclass
class Gitea2Odoo:
    """
    Class to make the trasnformation of data from Ado to Odoo format
    """

    logger: Logger = field(default_factory=Logger)
    odoo: Odoo = field(default_factory=Odoo)

    def __init__(self, odoo: Odoo, logger: Logger):
        """
        Initialize the Logger with a Streamlit message container.
        
        Parameters:
        mc (st.container): The Streamlit container for displaying messages.
        """
        self.logger = logger
        self.odoo = odoo

    def convert_to_odoo_stage(self, gitea_state, to_compare: bool):
        """
        Convert from Gitea state to Odoo stage, if created to compare add the extra information
        """
        if gitea_state in ["closed"]:
            return [388, "Done"] if to_compare else 388

        if gitea_state in ["open"]:
            return [102, "To Do"] if to_compare else 102 # To Do

        return [949, "In Progress"] if to_compare else 949 # In Progress

    def convert_to_odoo_priority(self):
        """
        Convert from Gitea priority to Odoo string priority
        NOTE: returning only low priority for now
        TODO: return the proper priority
        """

        # if priority in [1, 2]:
        #     return "1" # 'high'

        return "0" # 'low'

    def update_odoo_task_from_gitea_issue(self, st_project, odoo_task, gitea_issue) -> bool:
        """
        Update Odoo task from gitea ticket information
        """

        # Prepare the data for creating/updating a task in Odoo
        new_odoo_task = self.build_task_data(st_project, gitea_issue, odoo_task if odoo_task else None)

        if odoo_task and gitea_issue:
            if not self.is_odoo_up_to_date(st_project, odoo_task, gitea_issue):

                return self.odoo.update_odoo_task(new_odoo_task)

        return False

    def create_or_update_odoo_task_from_gitea_issue(self, st_project, odoo_task, gitea_issue) -> bool:
        """
        Creates or updates odoo task with gitea information
        """

        if odoo_task:
            return self.update_odoo_task_from_gitea_issue(st_project, odoo_task, gitea_issue)

        # Prepare the data for creating a task in Odoo
        new_odoo_task = self.build_task_data(st_project, gitea_issue)

        # Create a new task
        return self.odoo.create_odoo_task(new_odoo_task)

    def create_or_update_odoo_tasks_from_gitea_issues(self, st_project, gitea_issues):
        """
        Creates or updates an Odoo task from GITEA information
        NOTE: writing the kanban state label does not seem to work
        """

        count = 0

        p_bar = Bar("Updating Odoo tasks", max=len(gitea_issues))

        for issue in gitea_issues:
            issue_number = str(issue.get('number'))

            odoo_tasks = self.odoo.search_odoo_task(st_project, issue_number)

            if len(odoo_tasks) > 1:
                self.logger.error(f"More than one task found for gitea id {issue_number}: SKIPPING this ticket")
                p_bar.next()
                continue

            if self.create_or_update_odoo_task_from_gitea_issue(
                st_project, odoo_tasks[0] if len(odoo_tasks) == 1 else None, issue):
                count += 1

            p_bar.next()

        p_bar.finish()

        if count > 0:
            self.logger.info(f"Updated/Created {count} task(s)")
        else:
            self.logger.info("No tasks created or updated")

    def build_task_data(self, st_project, gitea_issue, old_task_data = None, to_compare: bool = False):
        """
        Builds the task data to either:
            - Update Odoo
            - Compare with data coming from GITEA
        NOTE 1: cannot write to 'x_xml_id'
        NOTE 2: cannot write to 'kanban_state_label'
        """

        gitea_number = gitea_issue.get('number')
        url = f'href="{gitea_issue.get('html_url')}" target="_blank" class="btn btn-primary'
        gitea_link = f'<a {url}">GITEA #{gitea_number}</a>'

        if gitea_number > 0:

            new_task_data = {
                'name': f"{gitea_number} - {gitea_issue['title']}",
                'description': gitea_link,
                'x_studio_external_id': str(gitea_number),
                'priority': self.convert_to_odoo_priority(),
                'stage_id': self.convert_to_odoo_stage(
                    gitea_issue['state'], to_compare),
                'x_studio_external_system': str(st_project['source']).capitalize()
            }

            self.odoo.update_odoo_task_data(st_project, old_task_data, new_task_data, to_compare)

            return new_task_data

        return None

    def is_odoo_up_to_date(self, st_project, odoo_task, gitea_issue) -> bool:
        """
        Checks if the information in Odoo matches the information coming from GITEA
        """

        new_task_data = self.build_task_data(st_project, gitea_issue, odoo_task, True)

        equal = new_task_data == odoo_task

        if not equal:
            self.logger.debug(f"\nOLD\n{json.dumps(odoo_task, indent=2)}\nNEW\n{json.dumps(new_task_data, indent=2)}")

        return equal
