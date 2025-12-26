"""Model Manager Services - Phase 1 MVP + Download Support

Analyze, classify, and manage ComfyUI model files.
Download missing models from Civitai and Huggingface.
"""

from services.model_manager.workflow_scanner import WorkflowScanner
from services.model_manager.model_scanner import ModelScanner
from services.model_manager.model_classifier import ModelClassifier, ModelStatus
from services.model_manager.archive_manager import ArchiveManager
from services.model_manager.duplicate_detector import DuplicateDetector
from services.model_manager.storage_analyzer import StorageAnalyzer
from services.model_manager.workflow_mapper import WorkflowMapper
from services.model_manager.report_exporter import ReportExporter
from services.model_manager.model_filter import ModelFilter
from services.model_manager.model_downloader import (
    ModelDownloader,
    DownloadSource,
    DownloadStatus,
    DownloadTask,
    SearchResult,
    CivitaiClient,
    HuggingfaceClient,
)

__all__ = [
    "WorkflowScanner",
    "ModelScanner",
    "ModelClassifier",
    "ModelStatus",
    "ArchiveManager",
    "DuplicateDetector",
    "StorageAnalyzer",
    "WorkflowMapper",
    "ReportExporter",
    "ModelFilter",
    # Download support
    "ModelDownloader",
    "DownloadSource",
    "DownloadStatus",
    "DownloadTask",
    "SearchResult",
    "CivitaiClient",
    "HuggingfaceClient",
]
