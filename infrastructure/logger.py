"""Structured logging system for CINDERGRACE pipeline"""
import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional


class PipelineLogger:
    """Centralized logging configuration for the pipeline"""

    _instance: Optional[logging.Logger] = None
    _initialized: bool = False

    @classmethod
    def get_logger(cls, name: str = "cindergrace") -> logging.Logger:
        """
        Get or create logger instance with proper configuration

        Args:
            name: Logger name (typically __name__ from calling module)

        Returns:
            Configured logger instance
        """
        if not cls._initialized:
            cls._setup_root_logger()
            cls._initialized = True

        # Always return a child of the cindergrace logger
        if name != "cindergrace" and not name.startswith("cindergrace."):
            name = f"cindergrace.{name}"

        return logging.getLogger(name)

    @classmethod
    def _setup_root_logger(cls):
        """Configure root logger with console and file handlers"""
        root_logger = logging.getLogger("cindergrace")
        # Set to DEBUG so file handler can capture debug messages
        # Console handler filters to INFO for cleaner output
        root_logger.setLevel(logging.DEBUG)

        # Prevent duplicate handlers
        if root_logger.handlers:
            return

        # Console handler - colorful output for terminal
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

        # File handler - detailed output with rotation
        log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
        os.makedirs(log_dir, exist_ok=True)

        file_handler = RotatingFileHandler(
            os.path.join(log_dir, "pipeline.log"),
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    @classmethod
    def set_level(cls, level: int):
        """
        Change logging level dynamically

        Args:
            level: logging.DEBUG, logging.INFO, logging.WARNING, etc.
        """
        root_logger = logging.getLogger("cindergrace")
        root_logger.setLevel(level)
        for handler in root_logger.handlers:
            if isinstance(handler, logging.StreamHandler) and not isinstance(handler, RotatingFileHandler):
                handler.setLevel(level)


# Convenience function for direct import
def get_logger(name: str = "cindergrace") -> logging.Logger:
    """
    Get logger instance - convenience wrapper

    Usage:
        from infrastructure.logger import get_logger
        logger = get_logger(__name__)
        logger.info("Starting process...")
    """
    return PipelineLogger.get_logger(name)


__all__ = ["PipelineLogger", "get_logger"]
