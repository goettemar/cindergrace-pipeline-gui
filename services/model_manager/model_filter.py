"""Model Filter - Advanced filtering utilities for model listings."""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

from infrastructure.logger import get_logger
from services.model_manager.model_classifier import ModelStatus

logger = get_logger(__name__)


class ModelFilter:
    """Chainable filters for model classification results."""

    def __init__(self, models: Iterable[Dict]):
        self.base_models = list(models)
        self.filters: List[Callable[[Dict], bool]] = []
        self.logger = logger

    def reset(self) -> "ModelFilter":
        """Clear all filters."""
        self.filters = []
        return self

    def by_status(self, status: ModelStatus) -> "ModelFilter":
        self.filters.append(lambda m: m.get("status") == status)
        return self

    def by_size_range(self, min_bytes: Optional[int] = None, max_bytes: Optional[int] = None) -> "ModelFilter":
        def _filter(model: Dict) -> bool:
            size = model.get("size_bytes", 0)
            if min_bytes is not None and size < min_bytes:
                return False
            if max_bytes is not None and size > max_bytes:
                return False
            return True
        self.filters.append(_filter)
        return self

    def by_modified_date(
        self,
        after: Optional[datetime] = None,
        before: Optional[datetime] = None
    ) -> "ModelFilter":
        def _filter(model: Dict) -> bool:
            path = model.get("path")
            if not path:
                return False
            try:
                mtime = datetime.fromtimestamp(Path(path).stat().st_mtime)
            except OSError:
                return False
            if after and mtime < after:
                return False
            if before and mtime > before:
                return False
            return True
        self.filters.append(_filter)
        return self

    def by_workflow_count(self, min_count: Optional[int] = None, max_count: Optional[int] = None) -> "ModelFilter":
        def _filter(model: Dict) -> bool:
            count = model.get("workflow_count", 0)
            if min_count is not None and count < min_count:
                return False
            if max_count is not None and count > max_count:
                return False
            return True
        self.filters.append(_filter)
        return self

    def by_filename_pattern(self, regex: str) -> "ModelFilter":
        pattern = re.compile(regex)
        self.filters.append(lambda m: bool(pattern.search(m.get("filename", ""))))
        return self

    def apply(self) -> List[Dict]:
        """Apply all filters and return filtered models."""
        models = list(self.base_models)
        for filt in self.filters:
            models = [m for m in models if filt(m)]
        return models
