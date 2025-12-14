"""Storage Analyzer - Provide storage insights for models."""
from __future__ import annotations

from typing import Dict, List, Optional

from infrastructure.logger import get_logger
from services.model_manager.model_classifier import ModelClassifier, ModelStatus
from services.model_manager.model_scanner import ModelScanner

logger = get_logger(__name__)


class StorageAnalyzer:
    """Computes storage statistics from model classification data."""

    def __init__(self, classifier: ModelClassifier):
        self.classifier = classifier
        self.logger = logger
        self._classification_cache: Optional[Dict] = None

    def _get_classification(self) -> Dict:
        if self._classification_cache is None:
            self._classification_cache = self.classifier.classify_all_models()
        return self._classification_cache

    def get_storage_overview(self) -> Dict:
        """Return total size by status and type."""
        classified = self._get_classification()

        overview = {
            "totals": {
                "used": self._sum_size(classified.get(ModelStatus.USED, [])),
                "unused": self._sum_size(classified.get(ModelStatus.UNUSED, [])),
                "missing": 0,
            },
            "counts": {
                "used": len(classified.get(ModelStatus.USED, [])),
                "unused": len(classified.get(ModelStatus.UNUSED, [])),
                "missing": len(classified.get(ModelStatus.MISSING, [])),
            },
            "by_type": {},
        }

        # Missing models have no size on disk; keep at 0 bytes
        overview["totals"]["missing"] = 0

        for status in [ModelStatus.USED, ModelStatus.UNUSED, ModelStatus.MISSING]:
            for model in classified.get(status, []):
                model_type = model["type"]
                type_entry = overview["by_type"].setdefault(model_type, {
                    "used": {"count": 0, "size_bytes": 0},
                    "unused": {"count": 0, "size_bytes": 0},
                    "missing": {"count": 0, "size_bytes": 0},
                })
                type_entry[status.value]["count"] += 1
                type_entry[status.value]["size_bytes"] += model.get("size_bytes", 0)

        # Add formatted sizes
        overview["formatted"] = {
            "used": ModelScanner._format_size(overview["totals"]["used"]),
            "unused": ModelScanner._format_size(overview["totals"]["unused"]),
            "missing": "N/A",
            "total": ModelScanner._format_size(
                overview["totals"]["used"] + overview["totals"]["unused"]
            ),
        }
        return overview

    def get_largest_models(self, n: int = 10) -> List[Dict]:
        """Return top N largest models across statuses (excluding missing)."""
        classified = self._get_classification()
        models = classified.get(ModelStatus.USED, []) + classified.get(ModelStatus.UNUSED, [])
        sorted_models = sorted(models, key=lambda m: m.get("size_bytes", 0), reverse=True)
        return sorted_models[:n]

    def get_smallest_models(self, n: int = 10) -> List[Dict]:
        """Return smallest models (unused prioritized for cleanup)."""
        classified = self._get_classification()
        unused = classified.get(ModelStatus.UNUSED, [])
        used = classified.get(ModelStatus.USED, [])
        models = unused + used  # prioritize unused first
        sorted_models = sorted(models, key=lambda m: m.get("size_bytes", 0))
        return sorted_models[:n]

    def get_size_distribution(self) -> Dict:
        """Return histogram data for size buckets."""
        classified = self._get_classification()
        models = classified.get(ModelStatus.USED, []) + classified.get(ModelStatus.UNUSED, [])

        buckets = [
            ("<100MB", 0, 100 * 1024 * 1024),
            ("100-500MB", 100 * 1024 * 1024, 500 * 1024 * 1024),
            ("500MB-1GB", 500 * 1024 * 1024, 1024 * 1024 * 1024),
            ("1-2GB", 1024 * 1024 * 1024, 2 * 1024 * 1024 * 1024),
            ("2-4GB", 2 * 1024 * 1024 * 1024, 4 * 1024 * 1024 * 1024),
            ("4-8GB", 4 * 1024 * 1024 * 1024, 8 * 1024 * 1024 * 1024),
            (">8GB", 8 * 1024 * 1024 * 1024, float("inf")),
        ]

        distribution = []
        for name, lower, upper in buckets:
            bucket_models = [
                m for m in models
                if lower <= m.get("size_bytes", 0) < upper
            ]
            distribution.append({
                "bucket": name,
                "count": len(bucket_models),
                "total_bytes": sum(m.get("size_bytes", 0) for m in bucket_models),
                "total_formatted": ModelScanner._format_size(
                    sum(m.get("size_bytes", 0) for m in bucket_models)
                ),
            })

        return {"buckets": distribution}

    def get_type_breakdown(self) -> Dict:
        """Return breakdown per model type (counts and sizes)."""
        classified = self._get_classification()
        breakdown: Dict[str, Dict] = {}

        for status in [ModelStatus.USED, ModelStatus.UNUSED, ModelStatus.MISSING]:
            for model in classified.get(status, []):
                model_type = model["type"]
                entry = breakdown.setdefault(model_type, {
                    "used": {"count": 0, "size_bytes": 0},
                    "unused": {"count": 0, "size_bytes": 0},
                    "missing": {"count": 0, "size_bytes": 0},
                    "total_bytes": 0,
                })
                entry[status.value]["count"] += 1
                entry[status.value]["size_bytes"] += model.get("size_bytes", 0)
                entry["total_bytes"] += model.get("size_bytes", 0)

        # Add formatted sizes
        for entry in breakdown.values():
            entry["formatted_total"] = ModelScanner._format_size(entry["total_bytes"])

        return breakdown

    @staticmethod
    def _sum_size(models: List[Dict]) -> int:
        return sum(m.get("size_bytes", 0) for m in models)
