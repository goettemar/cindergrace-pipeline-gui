"""Service for importing existing images and creating storyboard shots."""
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any

from PIL import Image

from domain.models import Storyboard
from infrastructure.logger import get_logger
from services.storyboard_editor_service import StoryboardEditorService

logger = get_logger(__name__)


@dataclass
class ImportedImage:
    """Represents an imported image with metadata."""
    original_path: str
    filename: str
    width: int
    height: int
    suggested_filename_base: str
    suggested_prompt: str = ""
    suggested_description: str = ""
    order: int = 0


class ImageImportService:
    """Service to import images and generate storyboard shots."""

    SUPPORTED_FORMATS = (".png", ".jpg", ".jpeg", ".webp", ".bmp")

    def __init__(self):
        self.storyboard_service = StoryboardEditorService()

    def scan_folder(self, folder_path: str) -> List[ImportedImage]:
        """Scan a folder for images and return ImportedImage list."""
        if not os.path.isdir(folder_path):
            logger.warning(f"Folder not found: {folder_path}")
            return []

        images = []
        for idx, filename in enumerate(sorted(os.listdir(folder_path))):
            if not filename.lower().endswith(self.SUPPORTED_FORMATS):
                continue

            filepath = os.path.join(folder_path, filename)
            if not os.path.isfile(filepath):
                continue

            try:
                img = self._load_image_metadata(filepath, idx)
                if img:
                    images.append(img)
            except Exception as e:
                logger.warning(f"Could not load image {filename}: {e}")

        logger.info(f"Scanned {len(images)} images from {folder_path}")
        return images

    def _load_image_metadata(self, filepath: str, order: int) -> Optional[ImportedImage]:
        """Load image and extract metadata."""
        with Image.open(filepath) as img:
            width, height = img.size

        filename = os.path.basename(filepath)
        name_without_ext = os.path.splitext(filename)[0]

        # Generate suggested filename_base (sanitized, lowercase, dashes)
        suggested_base = self._sanitize_filename(name_without_ext)

        return ImportedImage(
            original_path=filepath,
            filename=filename,
            width=width,
            height=height,
            suggested_filename_base=suggested_base,
            suggested_prompt="",
            suggested_description=f"Imported from {filename}",
            order=order,
        )

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize filename to valid filename_base format."""
        # Remove special characters, replace spaces with dashes
        sanitized = re.sub(r"[^\w\s-]", "", name.lower())
        sanitized = re.sub(r"[\s_]+", "-", sanitized)
        sanitized = re.sub(r"-+", "-", sanitized).strip("-")
        return sanitized or "imported-image"

    def import_images(
        self,
        images: List[ImportedImage],
        target_dir: str,
        rename: bool = True
    ) -> List[Tuple[ImportedImage, str]]:
        """
        Copy images to target directory, optionally renaming them.

        Returns list of (ImportedImage, new_path) tuples.
        """
        os.makedirs(target_dir, exist_ok=True)
        results = []

        for img in images:
            ext = os.path.splitext(img.filename)[1].lower()

            if rename:
                # Use suggested_filename_base with variant suffix
                new_filename = f"{img.suggested_filename_base}_v1_00001_{ext}"
            else:
                new_filename = img.filename

            new_path = os.path.join(target_dir, new_filename)

            # Avoid overwriting existing files
            counter = 1
            while os.path.exists(new_path):
                counter += 1
                if rename:
                    new_filename = f"{img.suggested_filename_base}_v{counter}_00001_{ext}"
                else:
                    name, ext = os.path.splitext(img.filename)
                    new_filename = f"{name}_{counter}{ext}"
                new_path = os.path.join(target_dir, new_filename)

            shutil.copy2(img.original_path, new_path)
            logger.info(f"Imported: {img.filename} -> {new_filename}")
            results.append((img, new_path))

        return results

    def create_storyboard_from_images(
        self,
        images: List[ImportedImage],
        project_name: str,
        default_duration: float = 3.0,
        use_image_resolution: bool = True,
        default_width: int = 960,
        default_height: int = 540,
    ) -> Storyboard:
        """Create a new storyboard with shots for each imported image."""
        storyboard = self.storyboard_service.create_new_storyboard(project_name)

        for idx, img in enumerate(images):
            shot_id = f"{idx + 1:03d}"

            # Use image resolution or defaults
            if use_image_resolution:
                width, height = img.width, img.height
            else:
                width, height = default_width, default_height

            self.storyboard_service.add_shot(
                storyboard=storyboard,
                shot_id=shot_id,
                filename_base=img.suggested_filename_base,
                description=img.suggested_description or f"Imported from {img.filename}",
                prompt=img.suggested_prompt or f"[Describe: {img.suggested_filename_base}]",
                duration=default_duration,
                width=width,
                height=height,
                negative_prompt="blurry, low quality, distorted",
                presets={
                    "style": "cinematic",
                    "lighting": "natural",
                    "mood": "none",
                    "camera": "static",
                    "motion": "subtle",
                },
                wan={
                    "seed": -1,
                    "cfg": 6.0,
                    "steps": 20,
                },
            )

        logger.info(f"Created storyboard '{project_name}' with {len(images)} shots")
        return storyboard

    def create_selection_json(
        self,
        imported_files: List[Tuple[ImportedImage, str]],
        project_name: str,
    ) -> Dict[str, Any]:
        """
        Create a selected_keyframes.json structure for imported images.
        This allows skipping the Keyframe Generator and Selector phases.
        """
        selections = []
        for img, new_path in imported_files:
            shot_id = f"{img.order + 1:03d}"
            selections.append({
                "shot_id": shot_id,
                "filename_base": img.suggested_filename_base,
                "selected_variant": 1,
                "selected_file": os.path.basename(new_path),
                "source_path": new_path,
                "export_path": new_path,
            })

        return {
            "project": project_name,
            "total_shots": len(selections),
            "exported_at": datetime.now().isoformat(),
            "selections": selections,
        }


class ImageAnalyzer:
    """Optional AI-powered image analysis for prompt generation."""

    def __init__(self, comfy_api=None):
        self.comfy_api = comfy_api
        self._analyzer_available = False

    def is_available(self) -> bool:
        """Check if AI analysis is available (Florence-2 or similar)."""
        # TODO: Check for Florence-2 or other vision model in ComfyUI
        return self._analyzer_available

    def analyze_image(self, image_path: str) -> Dict[str, str]:
        """
        Analyze image and return suggested prompt/description.

        Returns:
            Dict with keys: prompt, description, detected_objects, mood
        """
        # Placeholder for future AI integration
        # Options:
        # 1. Florence-2 via ComfyUI
        # 2. LLaVA/Qwen-VL via ComfyUI
        # 3. Claude Vision API
        # 4. Local BLIP model

        return {
            "prompt": "",
            "description": "",
            "detected_objects": "",
            "mood": "",
        }

    def analyze_batch(self, image_paths: List[str]) -> List[Dict[str, str]]:
        """Analyze multiple images."""
        return [self.analyze_image(path) for path in image_paths]
