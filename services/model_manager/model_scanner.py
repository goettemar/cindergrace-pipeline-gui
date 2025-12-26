"""Model Scanner - Scan filesystem for actual model files"""
import os
from typing import Dict, List
from pathlib import Path

from infrastructure.logger import get_logger

logger = get_logger(__name__)


class ModelScanner:
    """Scans ComfyUI models directory for actual model files"""

    # Model file extensions by type
    MODEL_EXTENSIONS = {
        "checkpoints": [".safetensors", ".ckpt", ".pt", ".pth", ".bin"],
        "loras": [".safetensors", ".pt", ".pth"],
        "vae": [".safetensors", ".pt", ".pth", ".ckpt"],
        "controlnet": [".safetensors", ".pth"],
        "upscale_models": [".pth", ".pt", ".safetensors"],
        "clip": [".safetensors", ".pt", ".pth"],
        "unet": [".safetensors", ".pt", ".pth", ".gguf"],
        "diffusion_models": [".safetensors", ".pt", ".pth", ".gguf"],  # Wan, Flux, etc.
        "style_models": [".safetensors", ".ckpt"],
        "embeddings": [".pt", ".safetensors"],
        "text_encoders": [".safetensors", ".pt", ".pth", ".gguf"],  # T5, CLIP text encoders
    }

    def __init__(self, comfyui_models_dir: str):
        """
        Initialize model scanner

        Args:
            comfyui_models_dir: Path to ComfyUI models directory
        """
        self.models_dir = Path(comfyui_models_dir)
        self.logger = logger

    def scan_all_models(self) -> Dict[str, List[Dict[str, any]]]:
        """
        Scan all model directories for files

        Returns:
            Dict mapping model type to list of model files
            Format: {
                "checkpoints": [
                    {"filename": "model.safetensors", "path": "/full/path", "size_bytes": 12345},
                    ...
                ]
            }
        """
        results = {}

        if not self.models_dir.exists():
            self.logger.warning(f"Models directory does not exist: {self.models_dir}")
            return results

        # Scan each model type directory
        for model_type, extensions in self.MODEL_EXTENSIONS.items():
            model_type_dir = self.models_dir / model_type
            if not model_type_dir.exists():
                self.logger.debug(f"Model type directory does not exist: {model_type_dir}")
                continue

            models = self.scan_model_directory(str(model_type_dir), extensions)
            if models:
                results[model_type] = models
                total_size = sum(m["size_bytes"] for m in models)
                self.logger.info(f"Found {len(models)} {model_type} ({self._format_size(total_size)})")

        return results

    def scan_model_directory(self, directory: str, extensions: List[str]) -> List[Dict[str, any]]:
        """
        Scan a single model directory for files

        Args:
            directory: Directory to scan
            extensions: List of file extensions to look for

        Returns:
            List of model file information
        """
        models = []
        dir_path = Path(directory)

        if not dir_path.exists():
            return models

        # Recursively find all files with matching extensions
        for ext in extensions:
            for file_path in dir_path.rglob(f"*{ext}"):
                if file_path.is_file():
                    try:
                        size = file_path.stat().st_size
                        models.append({
                            "filename": file_path.name,
                            "path": str(file_path),
                            "relative_path": str(file_path.relative_to(dir_path)),
                            "size_bytes": size,
                            "size_formatted": self._format_size(size),
                        })
                    except Exception as e:
                        self.logger.error(f"Error reading file {file_path}: {e}")

        return models

    def get_model_info(self, model_type: str, filename: str) -> Dict[str, any]:
        """
        Get information about a specific model file

        Args:
            model_type: Type of model (checkpoints, loras, etc.)
            filename: Model filename

        Returns:
            Model information dict or None if not found
        """
        all_models = self.scan_all_models()

        if model_type not in all_models:
            return None

        for model in all_models[model_type]:
            if model["filename"] == filename:
                return model

        return None

    def model_exists(self, model_type: str, filename: str) -> bool:
        """
        Check if a model file exists

        Args:
            model_type: Type of model
            filename: Model filename

        Returns:
            True if file exists, False otherwise
        """
        return self.get_model_info(model_type, filename) is not None

    def get_total_size_by_type(self) -> Dict[str, int]:
        """
        Get total size of models by type

        Returns:
            Dict mapping model type to total size in bytes
        """
        all_models = self.scan_all_models()
        sizes = {}

        for model_type, models in all_models.items():
            total = sum(m["size_bytes"] for m in models)
            sizes[model_type] = total

        return sizes

    def get_all_model_filenames(self) -> Dict[str, List[str]]:
        """
        Get all model filenames by type (without full paths/metadata)

        Returns:
            Dict mapping model type to list of filenames
        """
        all_models = self.scan_all_models()
        filenames = {}

        for model_type, models in all_models.items():
            filenames[model_type] = [m["filename"] for m in models]

        return filenames

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """
        Format file size in human-readable format

        Args:
            size_bytes: Size in bytes

        Returns:
            Formatted string (e.g., "1.5 GB")
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"
