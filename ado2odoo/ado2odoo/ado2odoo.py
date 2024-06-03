"""
Module to provide data interfacing between ADO and Odoo
"""

from dataclasses import dataclass, field

import json

import streamlit as st

from odoo import Odoo, PropertyList
from logger import Logger
from settings import Settings

@dataclass
class Ado2Odoo:
    """
    Class to make the trasnformation of data from Ado to Odoo format
    """

    settings: Settings = field(default_factory=Settings)
    logger: Logger = field(default_factory=Logger)
    odoo: Odoo = field(default_factory=Odoo)

    def __init__(self, settings: Settings, odoo: Odoo, logger: Logger):
        """
        Initialize the Logger with a Streamlit message container.
        
        Parameters:
        mc (st.container): The Streamlit container for displaying messages.
        """
        self.logger = logger
        self.settings = settings
        self.odoo = odoo

    def convert_to_odoo_stage(self, ado_state, to_compare: bool):
        """
        Convert from ADO state to Odoo stage, if created to compare add the extra information
        """
        if ado_state in ["Closed", "Done", "Removed"]:
            return [388, "Done"] if to_compare else 388

        if ado_state in ["New", "To Do"]:
            return [102, "To Do"] if to_compare else 102 # To Do

        if ado_state in ["On Hold", "Awaiting Decision"]:
            return [1113, "On Hold"] if to_compare else 1113 # On Hold

        return [949, "In Progress"] if to_compare else 949 # In Progress

    def convert_to_odoo_stage_label(self, ado_state) -> str:
        """
        "kanban_state_label": "In Progress",
        Convert from ADO state to Odoo stage label
        """
        state: str = "In Progress"

        if ado_state in ["Closed", "Done", "Removed"]:
            state = "Ready"
        elif ado_state in ["On Hold", "Awaiting Decision"]:
            state = "Blocked"

        return state

    def convert_to_odoo_priority(self, ado_priority):
        """
        Convert from ADO integer priority to Odoo string priority
        """
        if ado_priority in [1, 2]:
            return "1" # 'high'

        return "0" # 'low'

    def convert_project(self, ado_task) -> str:
        """
        Convert the ADO project to a usable project in Odoo
        """

        if not ado_task:
            return ""

        # if the TECBProject field exists then use its value as the project name
        if 'Custom.TECBProject' in ado_task['fields']:

            project = ado_task['fields'].get('Custom.TECBProject')

            return project if len(project) > 0 else ""

        # otherwise use the System.TeamProject
        if 'System.Title' in ado_task['fields']:
            return ado_task['fields']['System.TeamProject']

        # return empty string if neither of these fields exist
        return ""

    def update_task_property(self, task, property_name: str, new_value: str):
        """
        Update one task property
        """

        updated = False

        if not new_value:
            self.logger.error(f"Task {task['id']}, Name: {task['name']}, Property: {property_name}: Invalid new value")
            return {
                "task": task,
                "updated": updated
                }

        # for task_properties list in the current task
        # and check if each item's name matches the expected value
        for task_property in task["task_properties"]:

            if task_property["string"] == property_name:

                if "value" not in task_property:
                    task_property.append("value")

                if "value" in task_property and task_property["value"] != new_value:
                    task_property["value"] = new_value

                    updated = True

                    break

        return {
            "task": task,
            "updated": updated
            }

    def update_task_properties(self, task, props: PropertyList):
        """
        Updates all task properties
        """

        if not props or not self.validate_task_properties(task, props):
            self.logger.error("Task {task['id']}, Name: {task['name']}")
            return {
                "task": task,
                "updated": False
                }

        updated = False

        # task_properties list in the current task
        # and check if each item's name matches the expected value
        for task_property in task["task_properties"]:

            for prop in props:

                if task_property["string"] == prop.property_string:

                    if "value" not in task_property:
                        task_property.append("value")

                    # if value coming from ADO is None replace by empty string
                    new_value = "" if not prop.value else prop.value

                    if "value" in task_property and task_property["value"] != new_value:
                        task_property["value"] = new_value

                        updated = True

                        break # no duplicate property names (string) ?

        return {
            "task": task,
            "updated": updated
            }

    def update_odoo_task_from_ado_ticket(self, st_project, odoo_task, ado_ticket) -> bool:
        """
        Update Odoo task from ado ticket information
        """

        # Prepare the data for creating/updating a task in Odoo
        new_odoo_task = self.build_task_data(st_project, ado_ticket, odoo_task if odoo_task else None)

        if odoo_task and ado_ticket:
            if not self.is_odoo_up_to_date(st_project, odoo_task, ado_ticket):

                return self.odoo.update_odoo_task(new_odoo_task)

        return False

    def create_or_update_odoo_task_from_ado_ticket(self, st_project, odoo_task, ado_ticket) -> bool:
        """
        Creates or updates odoo task with ado information
        """

        if odoo_task:
            return self.update_odoo_task_from_ado_ticket(st_project, odoo_task, ado_ticket)

        # Prepare the data for creating a task in Odoo
        new_odoo_task = self.build_task_data(st_project, ado_ticket)

        # Create a new task
        return self.odoo.create_odoo_task(new_odoo_task)

    def create_or_update_odoo_tasks_from_ado_tickets(self, st_project, ado_tickets):
        """
        ## uses streamlit progress
        Creates or updates an Odoo task from ADO information
        NOTE: writing the kanban state label does not seem to work
        """

        count = 0

        # TODO: use the progress bar from streamlit
        progress_bar = st.progress(0.0, 'Updating Odoo tasks from ADO')

        for index, ado_task in enumerate(ado_tickets):
            ado_id = str(ado_task.get('id'))

            odoo_tasks = self.odoo.search_odoo_task(st_project, ado_id, True)

            if len(odoo_tasks) > 1:
                self.logger.error(f"More than one task found for ado id {ado_id}: SKIPPING this ticket")
                continue

            if self.create_or_update_odoo_task_from_ado_ticket(
                st_project, odoo_tasks[0] if len(odoo_tasks) == 1 else None, ado_task):
                count += 1
            
            progress_bar.progress((index+1)/len(ado_tickets), 'Updating Odoo tasks from ADO')

        if count > 0:
            self.logger.success(f"Updated/Created {count} task(s)")
        else:
            self.logger.success("No tasks created or updated")

    def validate_task_properties(self, task, props: PropertyList):
        """
        Check if the task contains all properties
        """

        if "task_properties" not in task:
            return False

        for task_property in task['task_properties']:
            if not props.validate_property(task_property['string']):
                return False

        return True

    def build_task_data(self, st_project, ado_task, old_task_data = None, to_compare: bool = False):
        """
        Builds the task data to either:
            - Update Odoo
            - Compare with data coming from ADO
        NOTE 1: cannot write to 'x_xml_id'
        NOTE 2: cannot write to 'kanban_state_label'
        """

        ado_id = str(ado_task.get('id'))
        base_url = self.settings.get_ado_base_url() + "worldfoodprogramme/SCOPE/_workitems/edit/" + ado_id
        ado_link = f'<a href="{base_url}" target="_blank" class="btn btn-primary">ADO #{ado_id}</a>'

        if ado_task.get('id') > 0:

            new_task_data = {
                'name': f"{ado_id} - {ado_task['fields'].get('System.Title')}",
                'description': ado_link,
                'x_studio_azure_devops_id': ado_task.get('id'),
                'priority': self.convert_to_odoo_priority(
                    ado_task['fields'].get('Microsoft.VSTS.Common.Priority')),
                'stage_id': self.convert_to_odoo_stage(
                    ado_task['fields'].get('System.State'), to_compare)
            }

            self.odoo.update_odoo_task_data(st_project, old_task_data, new_task_data, to_compare)

            if not old_task_data or (old_task_data and old_task_data["task_properties"]):

                ado_project = self.convert_project(ado_task)

                if not ado_task['fields'].get('Custom.Subproject'):
                    ado_subproject = False
                else:
                    ado_subproject = ado_task['fields'].get('Custom.Subproject')

                new_task_data["task_properties"] = [
                    {
                        "name": "6be2210c2574eae7",
                        "type": "char",
                        "string": "ADO Project",
                        "default": "",
                        "value": ado_project
                    },
                    {
                        "name": "711a9edc3c9870c7",
                        "type": "char",
                        "string": "ADO Subproject",
                        "default": "",
                        "value": ado_subproject
                    }
                ]

            return new_task_data

        return None

    def is_odoo_up_to_date(self, st_project, odoo_task, ado_task) -> bool:
        """
        Checks if the information in Odoo matches the information coming from ADO
        """

        new_task_data = self.build_task_data(st_project, ado_task, odoo_task, True)

        equal = new_task_data == odoo_task

        if not equal:
            self.logger.debug(f"\nOLD\n{json.dumps(odoo_task, indent=2)}\nNEW\n{json.dumps(new_task_data, indent=2)}")

        return equal
