"""Error handling utilities and decorators for the pipeline"""
from functools import wraps
from typing import Callable, Any, Optional, Union, Tuple
import traceback

from pydantic import ValidationError

from domain.exceptions import PipelineException
from infrastructure.logger import get_logger

logger = get_logger(__name__)


def _format_validation_error(error: ValidationError) -> str:
    """
    Format Pydantic ValidationError as user-friendly message

    Args:
        error: Pydantic ValidationError

    Returns:
        Formatted error message in German
    """
    errors = error.errors()

    if len(errors) == 1:
        # Single error - show it directly
        err = errors[0]
        field = err['loc'][0] if err['loc'] else 'Eingabe'
        msg = err['msg']
        return f"**❌ Validierungsfehler:** {msg}"
    else:
        # Multiple errors - list them
        error_lines = ["**❌ Validierungsfehler:**"]
        for err in errors:
            field = err['loc'][0] if err['loc'] else 'Eingabe'
            msg = err['msg']
            error_lines.append(f"- {field}: {msg}")
        return "\n".join(error_lines)


def handle_errors(
    default_message: str = "Ein Fehler ist aufgetreten",
    log_traceback: bool = True,
    return_tuple: bool = False
):
    """
    Decorator for consistent error handling in addon methods

    Args:
        default_message: Default error message for unexpected errors
        log_traceback: Whether to log full traceback for unexpected errors
        return_tuple: If True, returns (result, error_msg) tuple. If False, returns error_msg on error.

    Usage:
        @handle_errors("Konnte Projekt nicht erstellen")
        def create_project(self, name: str):
            if not name:
                raise ProjectCreationError("Projektname darf nicht leer sein")
            return self.project_manager.create_project(name)

        # With tuple return (useful when you need to update multiple outputs):
        @handle_errors("Fehler beim Laden", return_tuple=True)
        def load_data(self):
            data = load_something()
            return data, "✅ Erfolgreich geladen"
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                result = func(*args, **kwargs)

                # If function already returns tuple, pass through
                if return_tuple and not isinstance(result, tuple):
                    return (result, None)

                return result

            except ValidationError as e:
                # Pydantic validation errors - format nicely
                error_msg = _format_validation_error(e)
                logger.warning(f"{func.__name__}: Validation failed - {e}")

                if return_tuple:
                    return (None, error_msg)
                return error_msg

            except PipelineException as e:
                # Known pipeline errors - log as warning
                error_msg = f"**❌ Fehler:** {str(e)}"
                logger.warning(f"{func.__name__}: {e}")

                if return_tuple:
                    return (None, error_msg)
                return error_msg

            except Exception as e:
                # Unexpected errors - log as error with traceback
                error_type = type(e).__name__
                error_msg = f"**❌ Fehler:** {default_message} ({error_type}: {str(e)})"

                if log_traceback:
                    logger.error(
                        f"Unexpected error in {func.__name__}: {e}",
                        exc_info=True
                    )
                else:
                    logger.error(f"Unexpected error in {func.__name__}: {error_type}: {e}")

                if return_tuple:
                    return (None, error_msg)
                return error_msg

        return wrapper
    return decorator


def safe_execute(
    func: Callable,
    error_message: str = "Operation fehlgeschlagen",
    *args,
    **kwargs
) -> Tuple[Optional[Any], Optional[str]]:
    """
    Execute a function safely and return (result, error) tuple

    Args:
        func: Function to execute
        error_message: Error message prefix
        *args: Positional arguments for func
        **kwargs: Keyword arguments for func

    Returns:
        Tuple of (result, error_message). On success: (result, None), on error: (None, error_msg)

    Usage:
        result, error = safe_execute(
            lambda: project_store.create_project(name),
            error_message="Konnte Projekt nicht erstellen"
        )
        if error:
            return error
        return f"✅ Projekt erstellt: {result['name']}"
    """
    try:
        result = func(*args, **kwargs)
        return (result, None)

    except ValidationError as e:
        error_msg = _format_validation_error(e)
        logger.warning(f"{func.__name__ if hasattr(func, '__name__') else 'lambda'}: Validation failed - {e}")
        return (None, error_msg)

    except PipelineException as e:
        error_msg = f"**❌ {error_message}:** {str(e)}"
        logger.warning(f"{func.__name__ if hasattr(func, '__name__') else 'lambda'}: {e}")
        return (None, error_msg)

    except Exception as e:
        error_type = type(e).__name__
        error_msg = f"**❌ {error_message}:** {error_type}: {str(e)}"
        logger.error(
            f"Unexpected error in {func.__name__ if hasattr(func, '__name__') else 'lambda'}: {e}",
            exc_info=True
        )
        return (None, error_msg)


def format_error(error: Exception) -> str:
    """
    Format an exception as user-friendly error message

    Args:
        error: Exception to format

    Returns:
        Formatted error string suitable for UI display
    """
    if isinstance(error, ValidationError):
        return _format_validation_error(error)

    if isinstance(error, PipelineException):
        return f"**❌ Fehler:** {str(error)}"

    error_type = type(error).__name__
    return f"**❌ Fehler:** {error_type}: {str(error)}"


def log_and_format_error(error: Exception, context: str = "") -> str:
    """
    Log an exception and return formatted error message

    Args:
        error: Exception to log and format
        context: Optional context string (e.g., function name)

    Returns:
        Formatted error string suitable for UI display
    """
    if isinstance(error, ValidationError):
        logger.warning(f"{context}: Validation failed - {error}" if context else f"Validation failed - {error}")
    elif isinstance(error, PipelineException):
        logger.warning(f"{context}: {error}" if context else str(error))
    else:
        logger.error(
            f"{context}: {error}" if context else str(error),
            exc_info=True
        )

    return format_error(error)


__all__ = [
    "handle_errors",
    "safe_execute",
    "format_error",
    "log_and_format_error",
]
