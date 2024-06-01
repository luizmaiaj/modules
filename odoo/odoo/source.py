from dataclasses import dataclass
from enum import Enum

class CaseInsensitiveEnum(Enum):
    """
    Class to add the case insensitivity to Enum
    """
    def __new__(cls, value):
        member = object.__new__(cls)
        member._value_ = value
        return member

    @classmethod
    def _missing_(cls, value):
        for member in cls:
            if member.name == value.upper():
                return member
        # Optionally raise an error if no match is found
        raise ValueError(f"No matching enum found for {value}")

class Source(CaseInsensitiveEnum):
    """
    Case insensitive class to convert source field name
    """
    ADO = 'x_studio_azure_devops_id'
    GITEA = 'x_studio_external_id'
