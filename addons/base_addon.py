"""Base addon class for all pipeline addons"""
from abc import ABC, abstractmethod
from typing import List, Any


# Valid addon categories for tab grouping
ADDON_CATEGORIES = {
    "project": {"name": "1️⃣ Setup", "order": 1},
    "production": {"name": "2️⃣ Generate", "order": 2},
    "training": {"name": "3️⃣ Training", "order": 3},
    "tools": {"name": "⚙️ Tools", "order": 4},
}


class BaseAddon(ABC):
    """Abstract base class for all pipeline addons"""

    def __init__(self, name: str, description: str, category: str = "production"):
        """
        Initialize addon

        Args:
            name: Display name of the addon
            description: Brief description of addon functionality
            category: Addon category for tab grouping:
                      "project" - Project & storyboard management
                      "production" - Keyframe & video generation
                      "training" - Dataset & LoRA training
                      "tools" - Utilities & settings
        """
        self.name = name
        self.description = description
        self.category = category if category in ADDON_CATEGORIES else "production"
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
