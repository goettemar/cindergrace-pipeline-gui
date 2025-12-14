"""Archive Manager - Move/restore model files to/from archive"""
import json
import os
import shutil
from typing import List, Dict, Tuple
from pathlib import Path

from infrastructure.logger import get_logger

logger = get_logger(__name__)


class ArchiveManager:
    """Manages archiving and restoring model files"""

    def __init__(
        self,
        archive_root: str,
        comfyui_models_root: str
    ):
        """
        Initialize archive manager

        Args:
            archive_root: Root directory for archived models
            comfyui_models_root: Root directory of ComfyUI models
        """
        self.archive_root = Path(archive_root)
        self.models_root = Path(comfyui_models_root)
        self.logger = logger
        self.operation_log_file = self.archive_root / "archive_operations.jsonl"

    def move_to_archive(
        self,
        model_path: str,
        model_type: str,
        dry_run: bool = False
    ) -> Tuple[bool, str]:
        """
        Move a model file to archive

        Args:
            model_path: Full path to model file
            model_type: Model type (checkpoints, loras, etc.)
            dry_run: If True, don't actually move files

        Returns:
            Tuple of (success, message)
        """
        src_path = Path(model_path)

        if not src_path.exists():
            return False, f"Source file not found: {model_path}"

        # Determine archive destination
        # Preserve directory structure: archive/checkpoints/model.safetensors
        archive_type_dir = self.archive_root / model_type
        dest_path = archive_type_dir / src_path.name

        # Check if file already exists in archive
        if dest_path.exists():
            return False, f"File already exists in archive: {dest_path}"

        if dry_run:
            self.logger.info(f"[DRY RUN] Would move {src_path} → {dest_path}")
            return True, f"Would move to: {dest_path}"

        try:
            # Create archive directory if needed
            archive_type_dir.mkdir(parents=True, exist_ok=True)

            # Move file
            shutil.move(str(src_path), str(dest_path))
            self.logger.info(f"Moved to archive: {src_path.name} → {dest_path}")

            return True, f"Moved to archive: {dest_path}"

        except Exception as e:
            self.logger.error(f"Failed to move {src_path} to archive: {e}")
            return False, f"Error: {str(e)}"

    def restore_from_archive(
        self,
        filename: str,
        model_type: str,
        dry_run: bool = False
    ) -> Tuple[bool, str]:
        """
        Restore a model file from archive to ComfyUI models directory

        Args:
            filename: Model filename
            model_type: Model type (checkpoints, loras, etc.)
            dry_run: If True, don't actually copy files

        Returns:
            Tuple of (success, message)
        """
        # Normalize filename (handle Windows paths from workflows)
        filename_normalized = filename.replace("\\", "/")
        # Extract just the filename if it contains a path
        if "/" in filename_normalized:
            filename_normalized = filename_normalized.split("/")[-1]

        # Find source in archive (check both structured and flat)
        archive_type_dir = self.archive_root / model_type
        src_path = archive_type_dir / filename_normalized

        if not src_path.exists():
            # Try flat archive structure
            flat_src_path = self.archive_root / filename_normalized
            if flat_src_path.exists():
                src_path = flat_src_path
            else:
                return False, f"File not found in archive: {src_path}"

        # Destination in ComfyUI models
        models_type_dir = self.models_root / model_type
        dest_path = models_type_dir / filename_normalized

        # Check if file already exists in models
        if dest_path.exists():
            return False, f"File already exists in models: {dest_path}"

        if dry_run:
            self.logger.info(f"[DRY RUN] Would copy {src_path} → {dest_path}")
            return True, f"Would restore to: {dest_path}"

        try:
            # Create models directory if needed
            models_type_dir.mkdir(parents=True, exist_ok=True)

            # Copy file (keep in archive as backup)
            shutil.copy2(str(src_path), str(dest_path))
            self.logger.info(f"Restored from archive: {filename} → {dest_path}")

            return True, f"Restored to: {dest_path}"

        except Exception as e:
            self.logger.error(f"Failed to restore {filename} from archive: {e}")
            return False, f"Error: {str(e)}"

    def check_if_in_archive(self, filename: str, model_type: str) -> bool:
        """
        Check if a model file exists in archive

        Args:
            filename: Model filename
            model_type: Model type

        Returns:
            True if file exists in archive
        """
        # Normalize filename (handle Windows paths from workflows)
        filename_normalized = filename.replace("\\", "/")
        # Extract just the filename if it contains a path
        if "/" in filename_normalized:
            filename_normalized = filename_normalized.split("/")[-1]

        # Check structured archive (with subdirectories)
        archive_path = self.archive_root / model_type / filename_normalized
        if archive_path.exists():
            return True

        # Check flat archive (all files in root directory)
        flat_archive_path = self.archive_root / filename_normalized
        return flat_archive_path.exists()

    def get_archive_path(self, filename: str, model_type: str) -> str:
        """
        Get full archive path for a model

        Args:
            filename: Model filename
            model_type: Model type

        Returns:
            Full path string
        """
        return str(self.archive_root / model_type / filename)

    def scan_archive(self) -> Dict[str, List[str]]:
        """
        Scan archive directory for all archived models

        Returns:
            Dict mapping model type to list of filenames
        """
        archived_models = {}

        if not self.archive_root.exists():
            self.logger.warning(f"Archive directory does not exist: {self.archive_root}")
            return archived_models

        # Scan each model type subdirectory
        for model_type_dir in self.archive_root.iterdir():
            if not model_type_dir.is_dir():
                continue

            model_type = model_type_dir.name
            files = []

            for file_path in model_type_dir.iterdir():
                if file_path.is_file():
                    files.append(file_path.name)

            if files:
                archived_models[model_type] = sorted(files)

        return archived_models

    def batch_move_to_archive(
        self,
        models: List[Dict[str, str]],
        dry_run: bool = False
    ) -> Dict[str, List[str]]:
        """
        Move multiple models to archive

        Args:
            models: List of dicts with 'path' and 'type' keys
            dry_run: If True, don't actually move files

        Returns:
            Dict with 'success' and 'failed' lists of filenames
        """
        results = {
            "success": [],
            "failed": [],
        }

        for model in models:
            model_path = model["path"]
            model_type = model["type"]

            success, message = self.move_to_archive(model_path, model_type, dry_run)

            if success:
                results["success"].append(Path(model_path).name)
            else:
                results["failed"].append(f"{Path(model_path).name}: {message}")

        self.logger.info(f"Batch move: {len(results['success'])} success, {len(results['failed'])} failed")

        return results

    def batch_restore_from_archive(
        self,
        models: List[Dict[str, str]],
        dry_run: bool = False
    ) -> Dict[str, List[str]]:
        """
        Restore multiple models from archive

        Args:
            models: List of dicts with 'filename' and 'type' keys
            dry_run: If True, don't actually copy files

        Returns:
            Dict with 'success' and 'failed' lists of filenames
        """
        results = {
            "success": [],
            "failed": [],
        }

        for model in models:
            filename = model["filename"]
            model_type = model["type"]

            success, message = self.restore_from_archive(filename, model_type, dry_run)

            if success:
                results["success"].append(filename)
            else:
                results["failed"].append(f"{filename}: {message}")

        self.logger.info(f"Batch restore: {len(results['success'])} success, {len(results['failed'])} failed")

        return results

    def get_archive_size(self) -> int:
        """
        Get total size of archived models in bytes

        Returns:
            Total size in bytes
        """
        total_size = 0

        if not self.archive_root.exists():
            return total_size

        for file_path in self.archive_root.rglob("*"):
            if file_path.is_file():
                try:
                    total_size += file_path.stat().st_size
                except Exception as e:
                    self.logger.error(f"Error getting size of {file_path}: {e}")

        return total_size

    # ------------------------------------------------------------------ #
    # Phase 2 batch enhancements
    # ------------------------------------------------------------------ #
    def archive_all_unused_by_type(
        self,
        model_type: str,
        unused_models: List[Dict[str, str]] = None,
        progress_callback=None,
        dry_run: bool = False
    ) -> Dict[str, List[str]]:
        """
        Archive all unused models for a given type.

        Args:
            model_type: Model type folder.
            unused_models: Optional pre-filtered list from classifier.
            progress_callback: Optional callback(current, total, filename).
            dry_run: Skip actual moves.
        """
        if unused_models is None:
            # Fallback: archive everything in models_root/model_type
            type_dir = self.models_root / model_type
            files = [{"path": str(p), "type": model_type} for p in type_dir.glob("*") if p.is_file()]
        else:
            files = [m for m in unused_models if m.get("type") == model_type]

        total = len(files)
        results = {"success": [], "failed": []}

        for idx, model in enumerate(files, start=1):
            progress_filename = Path(model.get("path", "")).name
            if progress_callback:
                progress_callback(idx, total, progress_filename)
            ok, msg = self.move_to_archive(model.get("path"), model_type, dry_run=dry_run)
            if ok:
                results["success"].append(progress_filename)
            else:
                results["failed"].append(f"{progress_filename}: {msg}")

        self._log_operation("archive_all_unused_by_type", {"type": model_type, "result": results})
        return results

    def restore_all_missing(
        self,
        missing_models: List[Dict[str, str]] = None,
        progress_callback=None,
        dry_run: bool = False
    ) -> Dict[str, List[str]]:
        """
        Restore all missing models that exist in archive.

        Args:
            missing_models: Optional list from classifier.
            progress_callback: Optional callback(current, total, filename).
        """
        if missing_models is None:
            # Heuristic: anything in archive not present in models_root counts as missing
            missing_models = []
            for model_type_dir in self.archive_root.glob("*"):
                if not model_type_dir.is_dir():
                    continue
                for file_path in model_type_dir.glob("*"):
                    models_path = self.models_root / model_type_dir.name / file_path.name
                    if not models_path.exists():
                        missing_models.append({"filename": file_path.name, "type": model_type_dir.name})

        total = len(missing_models)
        results = {"success": [], "failed": []}

        for idx, model in enumerate(missing_models, start=1):
            filename = model.get("filename")
            model_type = model.get("type")
            if progress_callback:
                progress_callback(idx, total, filename)
            ok, msg = self.restore_from_archive(filename, model_type, dry_run=dry_run)
            if ok:
                results["success"].append(filename)
            else:
                results["failed"].append(f"{filename}: {msg}")

        self._log_operation("restore_all_missing", {"result": results})
        return results

    def delete_from_archive(
        self,
        models: List[Dict[str, str]],
        confirm: bool = True,
        progress_callback=None
    ) -> Dict[str, List[str]]:
        """
        Permanently delete models from archive.

        Args:
            models: List with filename/type keys.
            confirm: Require confirmation flag.
        """
        if not confirm:
            return {"success": [], "failed": ["Deletion not confirmed"]}

        results = {"success": [], "failed": []}
        total = len(models)

        for idx, model in enumerate(models, start=1):
            filename = model.get("filename")
            model_type = model.get("type")
            archive_path = self.archive_root / model_type / filename
            if progress_callback:
                progress_callback(idx, total, filename)

            try:
                if archive_path.exists():
                    archive_path.unlink()
                    results["success"].append(filename)
                else:
                    results["failed"].append(f"{filename}: not found")
            except Exception as e:
                results["failed"].append(f"{filename}: {e}")

        self._log_operation("delete_from_archive", {"result": results})
        return results

    def get_operation_log(self) -> List[Dict]:
        """Return list of recent operations logged to archive."""
        if not self.operation_log_file.exists():
            return []
        entries = []
        try:
            with open(self.operation_log_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entries.append(json.loads(line.strip()))
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            self.logger.error(f"Failed reading operation log: {e}")
        return entries

    def create_archive_index(self) -> str:
        """Create JSON index of archived models."""
        index = {}
        for model_type_dir in self.archive_root.glob("*"):
            if not model_type_dir.is_dir():
                continue
            files = []
            for file_path in model_type_dir.glob("*"):
                if not file_path.is_file():
                    continue
                try:
                    files.append({
                        "filename": file_path.name,
                        "size_bytes": file_path.stat().st_size,
                        "modified": file_path.stat().st_mtime,
                    })
                except OSError:
                    continue
            index[model_type_dir.name] = files

        index_path = self.archive_root / "archive_index.json"
        try:
            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(index, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to write archive index: {e}")

        self._log_operation("create_archive_index", {"path": str(index_path)})
        return str(index_path)

    def _log_operation(self, action: str, payload: Dict):
        """Append operation detail to log file in archive root."""
        from datetime import datetime
        try:
            self.operation_log_file.parent.mkdir(parents=True, exist_ok=True)
            log_entry = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "action": action,
                "payload": payload,
            }
            with open(self.operation_log_file, "a", encoding="utf-8") as f:
                json.dump(log_entry, f)
                f.write("\n")
        except Exception as e:
            self.logger.error(f"Failed to log archive operation {action}: {e}")
