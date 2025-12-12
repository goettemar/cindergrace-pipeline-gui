"""Base addon class for all pipeline addons"""
from abc import ABC, abstractmethod
from typing import List, Any


class BaseAddon(ABC):
    """Abstract base class for all pipeline addons"""

    def __init__(self, name: str, description: str):
        """
        Initialize addon

        Args:
            name: Display name of the addon
            description: Brief description of addon functionality
        """
        self.name = name
        self.description = description
        self.enabled = True

    @abstractmethod
    def render(self) -> List[Any]:
        """
        Render the addon's UI components

        Returns:
            List of Gradio components that make up this addon's interface
        """
        pass

    @abstractmethod
    def get_tab_name(self) -> str:
        """
        Get the name to display in the tab

        Returns:
            Tab name string
        """
        pass

    def on_load(self):
        """Called when addon is loaded (optional override)"""
        pass

    def on_unload(self):
        """Called when GUI closes (optional override)"""
        pass

    def __repr__(self):
        return f"<{self.__class__.__name__}: {self.name}>"
