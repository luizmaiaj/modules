"""
Module used to interact with Odoo timesheets
"""
import datetime
from datetime import timedelta
from dataclasses import dataclass, field

from settings import MODELS
from logger import Logger

@dataclass
class Timesheets:
    """
    Class to manage Odoo timesheets
    """

    logger: Logger = field(default_factory=Logger)
    uid: int = field(default_factory=int)
    api_key: str = field(default_factory=str)
    db: str = field(default_factory=str)

    def __init__(self, st_odoo, logger: Logger):
        self.logger = logger

        self.uid = st_odoo['uid']
        self.api_key = st_odoo['api_key']
        self.db = st_odoo['db']

    def read_timesheets(self, domain, fields):
        """
        Reading timesheets
        """

        try:
            return MODELS.execute_kw(
                self.db, self.uid, self.api_key,
                'account.analytic.line', 'search_read',
                domain,
                fields)
        except ValueError:
            self.logger.exception(f"{ValueError}")

        return None

    def update_timesheets_without_description(self):
        """
        Update the timesheets in Odoo that do not have a description
        """

        # Do not retrieve timesheets older than 2 months
        # Get the current date and subtract 2 months
        two_months_ago = datetime.date.today() - timedelta(days=60)

        # Format the date as a string that Odoo can understand (YYYY-MM-DD)
        start_date = two_months_ago.strftime("%Y-%m-01")

        # Define the domain for searching tasks
        domain = [[['name', '=', '/'],
                ['validated_status', '=', 'draft'],
                ['date', '>=', start_date],
                ['user_id', '=', self.uid]]]

        # Fields to fetch
        fields = {'fields': ['name', 'id', 'task_id', 'validated_status']}

        # Search for timesheets
        timesheets = self.read_timesheets(domain, fields)

        if not timesheets:
            self.logger.info("No timesheets to update")
            return

        # Iterate through each task and update the description
        for timesheet in timesheets:

            timesheet_id = timesheet['id']

            if timesheet['task_id']:

                # Update the timesheet title using the task id
                try:
                    MODELS.execute_kw(
                        self.db, self.uid, self.api_key,
                        'account.analytic.line', 'write', 
                        [[timesheet_id], {'name': timesheet['task_id'][1]}])

                    self.logger.info(f"Updated timesheet {timesheet_id} with name: {timesheet['task_id'][1]}")
                except ValueError:
                    self.logger.exception(f"{ValueError}")

        self.logger.info("Updated {len(timesheets)} timesheets")

    def update_timesheet(self, timesheet_id, values):
        """
        Example of updating a timesheet
        """

        try:
            MODELS.execute_kw(
                self.db, self.uid, self.api_key,
                'account.analytic.line', 'write', [[timesheet_id], values])

        except ValueError:
            self.logger.exception(f"{ValueError}")

    def get_timesheets_from_task(self, task_id):
        """
        Search for timesheets associated with the task
        """
        try:
            timesheets = MODELS.execute_kw(
                self.db, self.uid, self.api_key,
                'account.analytic.line', 'search_read',
                [[['task_id', '=', task_id]]])
        except ValueError:
            self.logger.exception(f"{ValueError}")
            return None

        return timesheets
