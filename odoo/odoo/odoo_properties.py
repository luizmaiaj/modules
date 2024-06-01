"""
Module for the odoo properties class
"""
from typing import List
from dataclasses import dataclass

@dataclass
class PropertyItem:
    """
    Class to store the property item for custom Odoo properties.
    """
    property_string: str
    value: str

class PropertyList:
    """
    Class to store the property list of custom Odoo properties
    """
    def __init__(self, prop: List[PropertyItem]) -> None:
        self.properties = prop

    def __iter__(self):
        """Return the iterator object for properties list"""
        return iter(self.properties)

    def validate_property(self, property_string: str) -> bool:
        """Check if a propertyString with a certain value is found within the properties list"""
        return any(property.property_string == property_string for property in self.properties)
