"""Unit tests for infrastructure.logger"""
import logging
import os

import pytest

from infrastructure.logger import PipelineLogger, get_logger


@pytest.mark.unit
def test_get_logger_returns_child_and_sets_up_once(tmp_path, monkeypatch):
    """Should create cindergrace logger once and prefix child names"""
    # Reset state
    PipelineLogger._initialized = False
    root = logging.getLogger("cindergrace")
    root.handlers = []

    # Redirect logs directory to tmp
    monkeypatch.setattr(
        "infrastructure.logger.os.path.dirname",
        lambda path: str(tmp_path),
    )

    logger = get_logger("module")
    assert logger.name.startswith("cindergrace.")

    # Second call should not add duplicate handlers
    before = len(logging.getLogger("cindergrace").handlers)
    get_logger("module2")
    after = len(logging.getLogger("cindergrace").handlers)
    assert before == after


@pytest.mark.unit
def test_set_level_updates_stream_handlers():
    """set_level should adjust stream handler levels"""
    PipelineLogger.set_level(logging.DEBUG)
    root = logging.getLogger("cindergrace")
    assert root.level == logging.DEBUG
    stream_handlers = [h for h in root.handlers if isinstance(h, logging.StreamHandler)]
    assert stream_handlers
    assert all(h.level == logging.DEBUG for h in stream_handlers)


@pytest.mark.unit
def test_setup_root_logger_skips_when_handler_exists():
    """If handlers already present, setup should not add duplicates."""
    PipelineLogger._initialized = False
    root = logging.getLogger("cindergrace")
    root.handlers = [logging.StreamHandler()]  # pre-populated

    logger = get_logger("already")
    assert len(root.handlers) == 1  # unchanged
    assert logger.name.startswith("cindergrace.")
