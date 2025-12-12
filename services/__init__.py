"""Service layer for pipeline business logic."""
# ComfyUIAPI was moved to infrastructure layer
from infrastructure.comfy_api import ComfyUIAPI

__all__ = ["ComfyUIAPI"]
