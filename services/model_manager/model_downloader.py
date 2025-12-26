"""Model Downloader - Search and download models from Civitai and Huggingface"""
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from queue import Queue
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import quote, urlparse

import requests

from infrastructure.logger import get_logger

logger = get_logger(__name__)


class DownloadSource(Enum):
    """Source of the model download"""
    CIVITAI = "civitai"
    HUGGINGFACE = "huggingface"
    UNKNOWN = "unknown"


class DownloadStatus(Enum):
    """Status of a download task"""
    PENDING = "pending"
    SEARCHING = "searching"
    FOUND = "found"
    NOT_FOUND = "not_found"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class SearchResult:
    """Result from searching for a model"""
    filename: str
    source: DownloadSource
    download_url: str
    model_name: str
    model_id: str
    version_id: Optional[str] = None
    size_bytes: int = 0
    download_count: int = 0
    rating: float = 0.0
    description: str = ""
    thumbnail_url: str = ""

    @property
    def size_formatted(self) -> str:
        """Format size in human-readable format"""
        if self.size_bytes == 0:
            return "Unknown"
        for unit in ['B', 'KB', 'MB', 'GB']:
            if self.size_bytes < 1024:
                return f"{self.size_bytes:.1f} {unit}"
            self.size_bytes /= 1024
        return f"{self.size_bytes:.1f} TB"


@dataclass
class DownloadTask:
    """A download task in the queue"""
    filename: str
    model_type: str
    status: DownloadStatus = DownloadStatus.PENDING
    search_results: List[SearchResult] = field(default_factory=list)
    selected_result: Optional[SearchResult] = None
    progress: float = 0.0
    error_message: str = ""
    dest_path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for UI"""
        return {
            "filename": self.filename,
            "model_type": self.model_type,
            "status": self.status.value,
            "progress": self.progress,
            "error": self.error_message,
            "source": self.selected_result.source.value if self.selected_result else "",
            "size": self.selected_result.size_formatted if self.selected_result else "",
            "results_count": len(self.search_results),
        }


class CivitaiClient:
    """Client for Civitai API"""

    BASE_URL = "https://civitai.com/api/v1"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self.session = requests.Session()
        if api_key:
            self.session.headers["Authorization"] = f"Bearer {api_key}"
        self.session.headers["User-Agent"] = "CinderGrace-ModelManager/1.0"

    def search_by_filename(self, filename: str) -> List[SearchResult]:
        """
        Search for a model by filename on Civitai.

        Args:
            filename: The model filename to search for

        Returns:
            List of search results sorted by relevance
        """
        results = []

        # Clean filename for search
        # Remove extension and common suffixes
        search_name = self._clean_filename_for_search(filename)

        if not search_name:
            logger.warning(f"Could not extract search term from filename: {filename}")
            return results

        try:
            # Search models endpoint
            params = {
                "query": search_name,
                "limit": 10,
                "sort": "Highest Rated",
            }

            response = self.session.get(
                f"{self.BASE_URL}/models",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            for model in data.get("items", []):
                # Check each model version for matching files
                for version in model.get("modelVersions", []):
                    for file_info in version.get("files", []):
                        file_name = file_info.get("name", "")

                        # Check if this file matches our search
                        if self._filename_matches(filename, file_name):
                            result = SearchResult(
                                filename=file_name,
                                source=DownloadSource.CIVITAI,
                                download_url=file_info.get("downloadUrl", ""),
                                model_name=model.get("name", ""),
                                model_id=str(model.get("id", "")),
                                version_id=str(version.get("id", "")),
                                size_bytes=file_info.get("sizeKB", 0) * 1024,
                                download_count=version.get("downloadCount", 0),
                                rating=model.get("stats", {}).get("rating", 0),
                                description=model.get("description", "")[:200] if model.get("description") else "",
                                thumbnail_url=version.get("images", [{}])[0].get("url", "") if version.get("images") else "",
                            )
                            results.append(result)

            # Sort by download count (popularity) as proxy for "best"
            results.sort(key=lambda x: x.download_count, reverse=True)

        except requests.RequestException as e:
            logger.error(f"Civitai API error searching for {filename}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error searching Civitai for {filename}: {e}")

        return results

    def _clean_filename_for_search(self, filename: str) -> str:
        """Extract searchable name from filename"""
        # Remove extension
        name = Path(filename).stem

        # Remove common suffixes like _fp16, _fp8, _v1, etc.
        patterns_to_remove = [
            r'_fp\d+(_e\dm\dfn)?(_scaled)?',
            r'_bf\d+',
            r'_q\d+',
            r'_v\d+(\.\d+)?',
            r'_\d+b',
            r'_safetensors?',
            r'_ckpt',
            r'_pruned',
            r'_ema',
        ]

        for pattern in patterns_to_remove:
            name = re.sub(pattern, '', name, flags=re.IGNORECASE)

        # Replace underscores with spaces for better search
        name = name.replace('_', ' ').replace('-', ' ')

        # Clean up multiple spaces
        name = re.sub(r'\s+', ' ', name).strip()

        return name

    def _filename_matches(self, search_filename: str, candidate_filename: str) -> bool:
        """Check if a candidate filename matches our search"""
        # Normalize both filenames
        search_norm = search_filename.lower().replace('_', '').replace('-', '').replace(' ', '')
        candidate_norm = candidate_filename.lower().replace('_', '').replace('-', '').replace(' ', '')

        # Exact match
        if search_norm == candidate_norm:
            return True

        # Check if core name matches (without version/precision suffixes)
        search_core = re.sub(r'(fp\d+|bf\d+|v\d+|safetensors|ckpt).*', '', search_norm)
        candidate_core = re.sub(r'(fp\d+|bf\d+|v\d+|safetensors|ckpt).*', '', candidate_norm)

        if search_core and candidate_core and search_core in candidate_core:
            return True

        return False


class HuggingfaceClient:
    """Client for Huggingface API"""

    BASE_URL = "https://huggingface.co"
    API_URL = "https://huggingface.co/api"

    def __init__(self, token: str = ""):
        self.token = token
        self.session = requests.Session()
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"
        self.session.headers["User-Agent"] = "CinderGrace-ModelManager/1.0"

    def search_by_filename(self, filename: str) -> List[SearchResult]:
        """
        Search for a model by filename on Huggingface.

        Args:
            filename: The model filename to search for

        Returns:
            List of search results
        """
        results = []

        # Clean filename for search
        search_name = self._clean_filename_for_search(filename)

        if not search_name:
            return results

        try:
            # Search models endpoint
            params = {
                "search": search_name,
                "filter": "diffusers",  # Focus on diffusion models
                "limit": 20,
                "sort": "downloads",
                "direction": "-1",
            }

            response = self.session.get(
                f"{self.API_URL}/models",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            models = response.json()

            for model in models:
                model_id = model.get("modelId", "")

                # Get file list for this model
                try:
                    files = self._get_model_files(model_id)

                    for file_info in files:
                        file_name = file_info.get("rfilename", "")

                        # Check if filename matches
                        if self._filename_matches(filename, file_name):
                            # Construct download URL
                            download_url = f"{self.BASE_URL}/{model_id}/resolve/main/{quote(file_name)}"

                            result = SearchResult(
                                filename=file_name,
                                source=DownloadSource.HUGGINGFACE,
                                download_url=download_url,
                                model_name=model_id.split("/")[-1] if "/" in model_id else model_id,
                                model_id=model_id,
                                size_bytes=file_info.get("size", 0),
                                download_count=model.get("downloads", 0),
                                rating=model.get("likes", 0),  # Use likes as rating proxy
                                description=model.get("description", "")[:200] if model.get("description") else "",
                            )
                            results.append(result)

                except Exception as e:
                    logger.debug(f"Could not get files for {model_id}: {e}")
                    continue

            # Sort by downloads
            results.sort(key=lambda x: x.download_count, reverse=True)

        except requests.RequestException as e:
            logger.error(f"Huggingface API error searching for {filename}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error searching Huggingface for {filename}: {e}")

        return results

    def _get_model_files(self, model_id: str) -> List[Dict]:
        """Get list of files for a model"""
        try:
            response = self.session.get(
                f"{self.API_URL}/models/{model_id}",
                params={"blobs": True},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            # Filter for model files (safetensors, ckpt, bin)
            files = []
            for sibling in data.get("siblings", []):
                filename = sibling.get("rfilename", "")
                if any(filename.endswith(ext) for ext in ['.safetensors', '.ckpt', '.bin', '.pt', '.pth']):
                    files.append(sibling)

            return files

        except Exception as e:
            logger.debug(f"Error getting files for {model_id}: {e}")
            return []

    def _clean_filename_for_search(self, filename: str) -> str:
        """Extract searchable name from filename"""
        name = Path(filename).stem

        # Remove version/precision suffixes
        patterns = [
            r'[-_]fp\d+',
            r'[-_]bf\d+',
            r'[-_]v\d+',
            r'[-_]\d+b',
        ]

        for pattern in patterns:
            name = re.sub(pattern, '', name, flags=re.IGNORECASE)

        return name.replace('_', ' ').replace('-', ' ').strip()

    def _filename_matches(self, search_filename: str, candidate_filename: str) -> bool:
        """Check if candidate matches search filename"""
        search_stem = Path(search_filename).stem.lower()
        candidate_stem = Path(candidate_filename).stem.lower()

        # Normalize
        search_norm = search_stem.replace('_', '').replace('-', '')
        candidate_norm = candidate_stem.replace('_', '').replace('-', '')

        return search_norm == candidate_norm or search_norm in candidate_norm


class ModelDownloader:
    """
    Orchestrates model searching and downloading from multiple sources.

    Features:
    - Search Civitai and Huggingface by filename
    - Automatic best result selection
    - Configurable parallel downloads
    - Progress tracking
    """

    def __init__(
        self,
        models_root: str,
        civitai_api_key: str = "",
        huggingface_token: str = "",
        max_parallel_downloads: int = 2,
    ):
        """
        Initialize the model downloader.

        Args:
            models_root: ComfyUI models directory path
            civitai_api_key: Optional Civitai API key
            huggingface_token: Optional Huggingface token
            max_parallel_downloads: Maximum concurrent downloads (1-5)
        """
        self.models_root = Path(models_root)
        self.max_parallel = max(1, min(5, max_parallel_downloads))

        self.civitai = CivitaiClient(civitai_api_key)
        self.huggingface = HuggingfaceClient(huggingface_token)

        self.download_queue: Dict[str, DownloadTask] = {}
        self._executor: Optional[ThreadPoolExecutor] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        # Progress callback: fn(task_id, task_dict)
        self.progress_callback: Optional[Callable[[str, Dict], None]] = None

    def search_model(self, filename: str, model_type: str) -> List[SearchResult]:
        """
        Search for a model across all sources.

        Args:
            filename: Model filename to search for
            model_type: Model type (checkpoints, loras, etc.)

        Returns:
            Combined list of search results, sorted by popularity
        """
        all_results = []

        # Search Civitai first (primary source for SD models)
        logger.info(f"Searching Civitai for: {filename}")
        civitai_results = self.civitai.search_by_filename(filename)
        all_results.extend(civitai_results)

        # Search Huggingface
        logger.info(f"Searching Huggingface for: {filename}")
        hf_results = self.huggingface.search_by_filename(filename)
        all_results.extend(hf_results)

        # Sort by download count (best proxy for quality/popularity)
        all_results.sort(key=lambda x: x.download_count, reverse=True)

        logger.info(f"Found {len(all_results)} results for {filename}")
        return all_results

    def get_best_result(self, results: List[SearchResult]) -> Optional[SearchResult]:
        """
        Select the best result from search results.

        Prioritizes by:
        1. Download count (popularity)
        2. Civitai over Huggingface (for SD models)
        """
        if not results:
            return None

        # Already sorted by download count
        return results[0]

    def get_target_path(self, model_type: str, filename: str) -> Path:
        """
        Get the target path for a model download.

        Args:
            model_type: Model type (checkpoints, loras, etc.)
            filename: Model filename

        Returns:
            Full path where model should be saved
        """
        # Map common type variations
        type_mapping = {
            "checkpoint": "checkpoints",
            "lora": "loras",
            "vae": "vae",
            "controlnet": "controlnet",
            "upscaler": "upscale_models",
            "upscale": "upscale_models",
            "clip": "clip",
            "unet": "diffusion_models",  # Most UNETs are in diffusion_models/
            "diffusion_models": "diffusion_models",
            "text_encoders": "text_encoders",
            "embedding": "embeddings",
            "embeddings": "embeddings",
        }

        normalized_type = type_mapping.get(model_type.lower(), model_type)
        return self.models_root / normalized_type / filename

    def add_to_queue(
        self,
        filename: str,
        model_type: str,
        auto_search: bool = True
    ) -> str:
        """
        Add a model to the download queue.

        Args:
            filename: Model filename
            model_type: Model type
            auto_search: If True, immediately search for the model

        Returns:
            Task ID for tracking
        """
        task_id = f"{model_type}/{filename}"

        with self._lock:
            if task_id in self.download_queue:
                return task_id

            task = DownloadTask(
                filename=filename,
                model_type=model_type,
                status=DownloadStatus.PENDING,
            )
            self.download_queue[task_id] = task

        if auto_search:
            self._search_task(task_id)

        return task_id

    def _search_task(self, task_id: str):
        """Search for a model and update task"""
        with self._lock:
            task = self.download_queue.get(task_id)
            if not task:
                return
            task.status = DownloadStatus.SEARCHING

        self._notify_progress(task_id)

        results = self.search_model(task.filename, task.model_type)

        with self._lock:
            task = self.download_queue.get(task_id)
            if not task:
                return

            task.search_results = results

            if results:
                task.status = DownloadStatus.FOUND
                task.selected_result = self.get_best_result(results)
                task.dest_path = str(self.get_target_path(task.model_type, task.filename))
            else:
                task.status = DownloadStatus.NOT_FOUND

        self._notify_progress(task_id)

    def search_all_missing(
        self,
        missing_models: List[Dict[str, str]],
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Dict[str, DownloadTask]:
        """
        Search for all missing models.

        Args:
            missing_models: List of dicts with 'filename' and 'type' keys
            progress_callback: Optional callback(current, total, filename)

        Returns:
            Dict of task_id -> DownloadTask
        """
        total = len(missing_models)

        for idx, model in enumerate(missing_models, start=1):
            filename = model.get("filename", "")
            model_type = model.get("type", "unknown")

            if progress_callback:
                progress_callback(idx, total, filename)

            self.add_to_queue(filename, model_type, auto_search=True)

        return self.download_queue

    def start_downloads(
        self,
        task_ids: Optional[List[str]] = None,
        progress_callback: Optional[Callable[[str, Dict], None]] = None
    ):
        """
        Start downloading models.

        Args:
            task_ids: Optional list of task IDs to download (all FOUND if None)
            progress_callback: Callback for progress updates
        """
        self.progress_callback = progress_callback
        self._stop_event.clear()

        # Get tasks to download
        with self._lock:
            if task_ids:
                tasks_to_download = [
                    (tid, self.download_queue[tid])
                    for tid in task_ids
                    if tid in self.download_queue and self.download_queue[tid].status == DownloadStatus.FOUND
                ]
            else:
                tasks_to_download = [
                    (tid, task)
                    for tid, task in self.download_queue.items()
                    if task.status == DownloadStatus.FOUND
                ]

        if not tasks_to_download:
            logger.info("No tasks ready for download")
            return

        logger.info(f"Starting download of {len(tasks_to_download)} models with {self.max_parallel} parallel downloads")

        # Use thread pool for parallel downloads
        self._executor = ThreadPoolExecutor(max_workers=self.max_parallel)

        try:
            futures = {
                self._executor.submit(self._download_task, task_id): task_id
                for task_id, task in tasks_to_download
            }

            for future in as_completed(futures):
                task_id = futures[future]
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Download failed for {task_id}: {e}")
                    with self._lock:
                        if task_id in self.download_queue:
                            self.download_queue[task_id].status = DownloadStatus.FAILED
                            self.download_queue[task_id].error_message = str(e)
                    self._notify_progress(task_id)
        finally:
            self._executor.shutdown(wait=False)
            self._executor = None

    def _download_task(self, task_id: str):
        """Download a single task"""
        with self._lock:
            task = self.download_queue.get(task_id)
            if not task or not task.selected_result:
                return

            task.status = DownloadStatus.DOWNLOADING
            task.progress = 0.0

        self._notify_progress(task_id)

        result = task.selected_result
        dest_path = Path(task.dest_path)

        try:
            # Ensure directory exists
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Download with progress
            self._download_file(
                url=result.download_url,
                dest_path=dest_path,
                task_id=task_id,
                api_key=self.civitai.api_key if result.source == DownloadSource.CIVITAI else self.huggingface.token,
            )

            with self._lock:
                task = self.download_queue.get(task_id)
                if task:
                    task.status = DownloadStatus.COMPLETED
                    task.progress = 100.0

            logger.info(f"Download completed: {task.filename}")

        except Exception as e:
            logger.error(f"Download failed for {task.filename}: {e}")
            with self._lock:
                task = self.download_queue.get(task_id)
                if task:
                    task.status = DownloadStatus.FAILED
                    task.error_message = str(e)

            # Clean up partial download
            if dest_path.exists():
                try:
                    dest_path.unlink()
                except Exception:
                    pass

        self._notify_progress(task_id)

    def _download_file(
        self,
        url: str,
        dest_path: Path,
        task_id: str,
        api_key: str = "",
    ):
        """Download a file with progress tracking"""
        headers = {"User-Agent": "CinderGrace-ModelManager/1.0"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        response = requests.get(url, headers=headers, stream=True, timeout=60)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        chunk_size = 8192 * 16  # 128KB chunks

        with open(dest_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if self._stop_event.is_set():
                    raise Exception("Download cancelled")

                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)

                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        with self._lock:
                            task = self.download_queue.get(task_id)
                            if task:
                                task.progress = progress

                        # Throttle progress updates
                        if int(progress) % 5 == 0:
                            self._notify_progress(task_id)

    def cancel_downloads(self):
        """Cancel all running downloads"""
        self._stop_event.set()
        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)

    def clear_queue(self):
        """Clear the download queue"""
        with self._lock:
            self.download_queue.clear()

    def get_queue_status(self) -> Dict[str, Dict]:
        """Get status of all tasks in queue"""
        with self._lock:
            return {
                task_id: task.to_dict()
                for task_id, task in self.download_queue.items()
            }

    def get_statistics(self) -> Dict[str, int]:
        """Get download queue statistics"""
        with self._lock:
            stats = {
                "total": len(self.download_queue),
                "pending": 0,
                "searching": 0,
                "found": 0,
                "not_found": 0,
                "downloading": 0,
                "completed": 0,
                "failed": 0,
            }

            for task in self.download_queue.values():
                status_key = task.status.value
                if status_key in stats:
                    stats[status_key] += 1

            return stats

    def _notify_progress(self, task_id: str):
        """Notify progress callback"""
        if self.progress_callback:
            with self._lock:
                task = self.download_queue.get(task_id)
                if task:
                    self.progress_callback(task_id, task.to_dict())
