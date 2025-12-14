"""Duplicate Detector - Find duplicate model files via hashing."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

from infrastructure.logger import get_logger
from services.model_manager.model_classifier import ModelStatus
from services.model_manager.model_scanner import ModelScanner

logger = get_logger(__name__)


class DuplicateDetector:
    """Detect duplicate model files by size + hash."""

    PARTIAL_CHUNK = 100 * 1024 * 1024  # 100MB

    def __init__(self, use_partial_hash: bool = True):
        self.use_partial_hash = use_partial_hash
        self.logger = logger

    def find_duplicates(
        self,
        models_by_type: Dict[str, List[Dict]],
        prefer_used: bool = True,
        use_partial_hash: Optional[bool] = None
    ) -> List[Dict]:
        """
        Find duplicate files grouped by hash.

        Args:
            models_by_type: Output from ModelScanner/ModelClassifier grouped by type.
            prefer_used: When suggesting keepers, prefer models marked as USED.
            use_partial_hash: Override default partial hashing (first/last 100MB).

        Returns:
            List of duplicate groups:
            [
                {
                    "hash": "...",
                    "size_bytes": 123,
                    "files": [{"type": "...", "path": "...", "filename": "...", "status": "..."}],
                    "suggested_keep": {file_dict}
                }
            ]
        """
        if use_partial_hash is None:
            use_partial_hash = self.use_partial_hash

        # Flatten files and group by size to minimize hashing work
        by_size: Dict[int, List[Dict]] = {}
        for model_type, models in (models_by_type or {}).items():
            for model in models:
                size = model.get("size_bytes") or self._safe_size(model.get("path"))
                if size is None:
                    continue
                item = {
                    "type": model_type,
                    "path": model.get("path"),
                    "filename": model.get("filename"),
                    "size_bytes": size,
                    "status": model.get("status"),
                }
                by_size.setdefault(size, []).append(item)

        duplicates: List[Dict] = []

        # Only hash groups with matching sizes
        for size, candidates in by_size.items():
            if len(candidates) < 2:
                continue

            hashes: Dict[str, List[Dict]] = {}
            for candidate in candidates:
                file_path = candidate.get("path")
                if not file_path:
                    continue
                try:
                    file_hash = self._hash_file(file_path, partial=use_partial_hash)
                except Exception as exc:
                    self.logger.error(f"Hash failed for {file_path}: {exc}")
                    continue
                hashes.setdefault(file_hash, []).append(candidate)

            for file_hash, group in hashes.items():
                if len(group) < 2:
                    continue
                suggested = self.suggest_keep(group, prefer_used)
                duplicates.append({
                    "hash": file_hash,
                    "size_bytes": size,
                    "files": group,
                    "suggested_keep": suggested,
                })

        return duplicates

    def suggest_keep(self, group: List[Dict], prefer_used: bool = True) -> Optional[Dict]:
        """
        Suggest which file to keep from a duplicate group.

        Preference:
            1. Status USED if available
            2. First item as fallback
        """
        if not group:
            return None

        if prefer_used:
            for item in group:
                status = item.get("status")
                if status in (ModelStatus.USED, ModelStatus.USED.value if isinstance(status, str) else None):
                    return item

        return group[0]

    def _hash_file(self, path: str, partial: bool = True) -> str:
        """Hash a file using SHA256 with optional partial hashing."""
        hasher = hashlib.sha256()
        file_path = Path(path)

        if not file_path.exists() or not file_path.is_file():
            raise FileNotFoundError(f"File not found: {path}")

        if partial and file_path.stat().st_size > self.PARTIAL_CHUNK * 2:
            with open(file_path, "rb") as f:
                hasher.update(f.read(self.PARTIAL_CHUNK))
                f.seek(max(file_path.stat().st_size - self.PARTIAL_CHUNK, 0))
                hasher.update(f.read(self.PARTIAL_CHUNK))
                hasher.update(str(file_path.stat().st_size).encode())
        else:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
                    hasher.update(chunk)

        return hasher.hexdigest()

    @staticmethod
    def _safe_size(path: Optional[str]) -> Optional[int]:
        """Safely fetch file size."""
        if not path:
            return None
        try:
            return os.path.getsize(path)
        except OSError:
            return None
