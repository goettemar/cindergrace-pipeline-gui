"""Structured logging system for CINDERGRACE pipeline"""
import logging
import os
from collections import deque
from logging.handlers import RotatingFileHandler
from typing import Optional, List


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

        # UI handler - for displaying logs in the Gradio UI
        ui_handler = UILogHandler.get_instance()
        root_logger.addHandler(ui_handler)

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


class UILogHandler(logging.Handler):
    """Handler that stores recent log messages for UI display."""

    _instance: Optional["UILogHandler"] = None
    MAX_LINES = 100  # Keep last 100 lines in buffer

    def __init__(self):
        super().__init__()
        self._buffer: deque = deque(maxlen=self.MAX_LINES)
        self.setLevel(logging.INFO)
        self.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%H:%M:%S'
        ))

    @classmethod
    def get_instance(cls) -> "UILogHandler":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = UILogHandler()
        return cls._instance

    def emit(self, record: logging.LogRecord) -> None:
        """Store formatted log record in buffer."""
        try:
            msg = self.format(record)
            self._buffer.append(msg)
        except Exception:
            pass

    def get_logs(self, lines: int = 50, newest_first: bool = True) -> List[str]:
        """Get last N log lines."""
        logs = list(self._buffer)[-lines:]
        if newest_first:
            logs = logs[::-1]
        return logs

    def get_logs_text(self, lines: int = 50, newest_first: bool = True) -> str:
        """Get last N log lines as single string."""
        return "\n".join(self.get_logs(lines, newest_first))


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


__all__ = ["PipelineLogger", "get_logger", "UILogHandler"]
