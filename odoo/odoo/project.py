"""
Module to aggregate the information of one project
"""

from dataclasses import dataclass, field
from .source import Source

@dataclass
class Project:
    """
    Class to manage information of a project
    """

    name: str # odoo project name
    id: int # odoo project id
    ext_system: str
    ext_system_field: str
    ext_system_query: str # ado query or gitea repository to retrieve the tickets from
    odoo_tasks: dict = field(default_factory=dict) # tasks retrieved from Odoo
    ext_system_tasks: dict = field(default_factory=dict) # tasks retrieved from the external system

    def __init__(self, st_project):
        self.name = st_project.get('project_name')
        self.id = st_project.get('odoo_project_id')

        self.ext_system = st_project.get('source')
        self.ext_system_field = Source(self.ext_system).value

        if self.ext_system.upper() == Source.ADO.name:
            self.ext_system_query = st_project.get('ado_query_id')
        else:
            self.ext_system_query = st_project.get('gitea_repository')
