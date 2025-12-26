"""Custom exception hierarchy for CINDERGRACE pipeline"""


class PipelineException(Exception):
    """Base exception for all pipeline-related errors"""
    pass


# ========================================
# Project & Configuration Errors
# ========================================

class ProjectError(PipelineException):
    """Base exception for project-related errors"""
    pass


class ProjectNotFoundError(ProjectError):
    """Raised when a project cannot be found"""
    pass


class ProjectCreationError(ProjectError):
    """Raised when project creation fails"""
    pass


class ConfigurationError(PipelineException):
    """Raised when configuration is invalid or missing"""
    pass


# ========================================
# Storyboard & Selection Errors
# ========================================

class StoryboardError(PipelineException):
    """Base exception for storyboard-related errors"""
    pass


class StoryboardLoadError(StoryboardError):
    """Raised when storyboard file cannot be loaded"""
    pass


class StoryboardValidationError(StoryboardError):
    """Raised when storyboard content is invalid"""
    pass


class SelectionError(PipelineException):
    """Base exception for selection-related errors"""
    pass


class SelectionLoadError(SelectionError):
    """Raised when selection file cannot be loaded"""
    pass


class SelectionExportError(SelectionError):
    """Raised when selection export fails"""
    pass


# ========================================
# ComfyUI & Workflow Errors
# ========================================

class ComfyUIError(PipelineException):
    """Base exception for ComfyUI-related errors"""
    pass


class ComfyUIConnectionError(ComfyUIError):
    """Raised when connection to ComfyUI fails"""
    pass


class WorkflowError(ComfyUIError):
    """Base exception for workflow-related errors"""
    pass


class WorkflowLoadError(WorkflowError):
    """Raised when workflow file cannot be loaded"""
    pass


class WorkflowExecutionError(WorkflowError):
    """Raised when workflow execution fails"""
    pass


class WorkflowTimeoutError(WorkflowError):
    """Raised when workflow execution times out"""
    pass


# ========================================
# Generation & Processing Errors
# ========================================

class GenerationError(PipelineException):
    """Base exception for generation-related errors"""
    pass


class KeyframeGenerationError(GenerationError):
    """Raised when keyframe generation fails"""
    pass


class VideoGenerationError(GenerationError):
    """Raised when video generation fails"""
    pass


class ModelValidationError(PipelineException):
    """Raised when required models are missing or invalid"""
    pass


# ========================================
# File & IO Errors
# ========================================

class FileOperationError(PipelineException):
    """Base exception for file operation errors"""
    pass


class FileNotFoundError(FileOperationError):
    """Raised when a required file is not found"""
    pass


class FileCopyError(FileOperationError):
    """Raised when file copy operation fails"""
    pass


# ========================================
# Validation Errors
# ========================================

class ValidationError(PipelineException):
    """Base exception for validation errors"""
    pass


class InputValidationError(ValidationError):
    """Raised when user input validation fails"""
    pass


# ========================================
# External API Errors
# ========================================

class ExternalAPIError(PipelineException):
    """Base exception for external API errors"""
    pass


class OpenRouterAPIError(ExternalAPIError):
    """Raised when OpenRouter API call fails"""

    def __init__(self, message: str, status_code: int = None, response_body: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class OpenRouterAuthError(OpenRouterAPIError):
    """Raised when OpenRouter authentication fails (invalid API key)"""
    pass


class OpenRouterRateLimitError(OpenRouterAPIError):
    """Raised when OpenRouter rate limit is exceeded"""
    pass


__all__ = [
    # Base
    "PipelineException",
    # Project
    "ProjectError",
    "ProjectNotFoundError",
    "ProjectCreationError",
    "ConfigurationError",
    # Storyboard & Selection
    "StoryboardError",
    "StoryboardLoadError",
    "StoryboardValidationError",
    "SelectionError",
    "SelectionLoadError",
    "SelectionExportError",
    # ComfyUI
    "ComfyUIError",
    "ComfyUIConnectionError",
    "WorkflowError",
    "WorkflowLoadError",
    "WorkflowExecutionError",
    "WorkflowTimeoutError",
    # Generation
    "GenerationError",
    "KeyframeGenerationError",
    "VideoGenerationError",
    "ModelValidationError",
    # File
    "FileOperationError",
    "FileNotFoundError",
    "FileCopyError",
    # Validation
    "ValidationError",
    "InputValidationError",
    # External API
    "ExternalAPIError",
    "OpenRouterAPIError",
    "OpenRouterAuthError",
    "OpenRouterRateLimitError",
]
