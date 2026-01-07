from abc import ABC, abstractmethod
import time
from typing import Dict, Any, List

class ActionBase(ABC):
    """
    Base class for all automation actions.
    """
    def __init__(self, params: Dict[str, Any] = None):
        self.params = params or {}
        self.output = {}

    @property
    @abstractmethod
    def name(self) -> str:
        """Display name of the action"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Description of what the action does"""
        pass

    @abstractmethod
    def execute(self, context: Dict[str, Any]) -> bool:
        """
        Execute the action.
        
        Args:
            context: The global context dictionary containing variables and previous outputs.
            
        Returns:
            bool: True if execution was successful, False otherwise.
        """
        pass

    def get_param_schema(self) -> List[Dict[str, Any]]:
        """
        Define the parameters required by this action for the GUI to generate forms.
        Returns a list of dicts, e.g.:
        [
            {"name": "message", "type": "str", "label": "Message to print", "default": ""}
        ]
        """
        return []
