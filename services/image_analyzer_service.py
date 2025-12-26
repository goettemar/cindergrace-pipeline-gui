"""Service for AI-powered image analysis via ComfyUI Florence-2."""
import copy
import json
import os
import shutil
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from infrastructure.comfy_api.client import ComfyUIAPI
from infrastructure.config_manager import ConfigManager
from infrastructure.logger import get_logger

logger = get_logger(__name__)


@dataclass
class AnalysisResult:
    """Result of image analysis."""
    success: bool
    caption: str  # more_detailed_caption for prompt
    description: str = ""  # short caption for description
    error: Optional[str] = None


class ImageAnalyzerService:
    """Service to analyze images using Florence-2 via ComfyUI."""

    WORKFLOW_FILE = "config/workflow_templates/gca_florence2_caption.json"

    def __init__(self, config: Optional[ConfigManager] = None):
        self.config = config or ConfigManager()
        self.api = ComfyUIAPI(self.config.get_comfy_url())
        self._workflow: Optional[Dict[str, Any]] = None

    def is_available(self) -> bool:
        """Check if Florence-2 analysis is available (ComfyUI connected)."""
        try:
            result = self.api.test_connection()
            return result.get("connected", False)
        except Exception:
            return False

    def _load_workflow(self) -> Dict[str, Any]:
        """Load the Florence-2 caption workflow."""
        if self._workflow is None:
            workflow_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                self.WORKFLOW_FILE
            )
            self._workflow = self.api.load_workflow(workflow_path)
        return copy.deepcopy(self._workflow)

    def _upload_image(self, image_path: str) -> str:
        """
        Copy image to ComfyUI input folder for processing.

        Returns:
            Filename as it appears in ComfyUI input folder
        """
        comfy_root = self.config.get_comfy_root()
        input_dir = os.path.join(comfy_root, "input")
        os.makedirs(input_dir, exist_ok=True)

        # Use unique filename to avoid conflicts
        filename = f"analyze_{int(time.time())}_{os.path.basename(image_path)}"
        target_path = os.path.join(input_dir, filename)

        shutil.copy2(image_path, target_path)
        logger.debug(f"Copied image to ComfyUI input: {filename}")

        return filename

    def _cleanup_image(self, filename: str) -> None:
        """Remove temporary image from ComfyUI input folder."""
        try:
            comfy_root = self.config.get_comfy_root()
            input_path = os.path.join(comfy_root, "input", filename)
            if os.path.exists(input_path):
                os.remove(input_path)
                logger.debug(f"Cleaned up temporary image: {filename}")
        except Exception as e:
            logger.warning(f"Could not cleanup image {filename}: {e}")

    def _extract_captions_from_history(self, history: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract both captions from ComfyUI history output.

        Returns:
            Tuple of (description, prompt) - short caption and detailed caption
        """
        if not history:
            logger.debug("No history found")
            return None, None

        outputs = history.get("outputs", {})
        logger.debug(f"History outputs: {outputs}")

        description = None  # from node 4 (caption task)
        prompt = None  # from node 12 (more_detailed_caption task)

        # Node 4 = description (short caption), Node 12 = prompt (detailed caption)
        for node_id, node_output in outputs.items():
            logger.debug(f"Node {node_id} output: {node_output}")

            if "text" in node_output:
                text_data = node_output["text"]
                text_value = self._extract_text_value(text_data)

                if text_value:
                    # Node 4 is description, Node 12 is prompt
                    if node_id == "4":
                        description = text_value
                        logger.debug(f"Found description (node 4): {text_value[:50]}...")
                    elif node_id == "12":
                        prompt = text_value
                        logger.debug(f"Found prompt (node 12): {text_value[:50]}...")

        # If we couldn't identify by node ID, use first two texts found
        if description is None or prompt is None:
            texts = []
            for node_id, node_output in outputs.items():
                if "text" in node_output:
                    text_value = self._extract_text_value(node_output["text"])
                    if text_value:
                        texts.append((len(text_value), text_value))

            # Sort by length - shorter is description, longer is prompt
            texts.sort(key=lambda x: x[0])
            if len(texts) >= 2:
                description = texts[0][1]
                prompt = texts[1][1]
            elif len(texts) == 1:
                # Only one text found - use as both
                prompt = texts[0][1]
                description = texts[0][1]

        return description, prompt

    def _extract_text_value(self, text_data: Any) -> Optional[str]:
        """Extract string value from various text data formats."""
        if isinstance(text_data, str):
            return text_data
        elif isinstance(text_data, list) and len(text_data) > 0:
            first_item = text_data[0]
            if isinstance(first_item, str):
                return first_item
            elif isinstance(first_item, dict):
                return str(first_item.get("text", ""))
        elif isinstance(text_data, dict):
            if "filename" in text_data:
                # File reference - read the file
                return self._read_text_file_from_comfy(text_data)
            return str(text_data.get("text", ""))
        return None

    def _read_text_file_from_comfy(self, file_info: Dict[str, Any]) -> Optional[str]:
        """Read a text file from ComfyUI output folder."""
        try:
            filename = file_info.get("filename", "")
            subfolder = file_info.get("subfolder", "")
            file_type = file_info.get("type", "output")

            comfy_root = self.config.get_comfy_root()

            # Build path based on type
            if file_type == "output":
                base_dir = os.path.join(comfy_root, "output")
            elif file_type == "input":
                base_dir = os.path.join(comfy_root, "input")
            else:
                base_dir = os.path.join(comfy_root, "output")

            if subfolder:
                file_path = os.path.join(base_dir, subfolder, filename)
            else:
                file_path = os.path.join(base_dir, filename)

            logger.debug(f"Reading text file: {file_path}")

            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                logger.debug(f"Read caption from file: {content[:50]}...")
                return content
            else:
                logger.warning(f"Text file not found: {file_path}")
                return None

        except Exception as e:
            logger.error(f"Failed to read text file: {e}")
            return None

    def analyze_image(
        self,
        image_path: str,
        callback: Optional[Callable[[float, str], None]] = None,
    ) -> AnalysisResult:
        """
        Analyze a single image using Florence-2.

        Args:
            image_path: Path to the image file
            callback: Optional progress callback(progress_pct, status_text)

        Returns:
            AnalysisResult with caption or error
        """
        if not os.path.exists(image_path):
            return AnalysisResult(
                success=False,
                caption="",
                error=f"Image not found: {image_path}"
            )

        uploaded_filename = None
        try:
            # Step 1: Upload image to ComfyUI
            if callback:
                callback(0.1, "Uploading image...")
            uploaded_filename = self._upload_image(image_path)

            # Step 2: Load and update workflow
            if callback:
                callback(0.2, "Loading workflow...")
            workflow = self._load_workflow()

            # Update LoadImage node (node "1") with the uploaded filename
            if "1" in workflow:
                workflow["1"]["inputs"]["image"] = uploaded_filename
            else:
                # Fallback: search for LoadImage node
                for node_id, node_data in workflow.items():
                    if node_data.get("class_type") == "LoadImage":
                        node_data["inputs"]["image"] = uploaded_filename
                        break

            # Step 3: Queue workflow
            if callback:
                callback(0.3, "Queuing analysis...")
            prompt_id = self.api.queue_prompt(workflow)

            # Step 4: Monitor progress
            def progress_wrapper(pct, status):
                if callback:
                    # Scale progress from 30% to 90%
                    scaled = 0.3 + (pct * 0.6)
                    callback(scaled, status)

            result = self.api.monitor_progress(
                prompt_id,
                callback=progress_wrapper,
                timeout=120  # 2 minutes should be enough for captioning
            )

            if result["status"] != "success":
                return AnalysisResult(
                    success=False,
                    caption="",
                    error=result.get("error", "Unknown error during analysis")
                )

            # Step 5: Extract captions from history
            if callback:
                callback(0.95, "Extracting captions...")

            history = self.api.get_history(prompt_id)
            description, prompt = self._extract_captions_from_history(history)

            if prompt or description:
                if callback:
                    callback(1.0, "Analysis complete")

                # Use prompt (detailed) as main caption, description as short version
                caption_str = str(prompt) if prompt else str(description) if description else ""
                desc_str = str(description) if description else caption_str

                preview = caption_str[:50] if len(caption_str) > 50 else caption_str
                logger.info(f"Captions extracted - Description: {desc_str[:30]}... | Prompt: {preview}...")

                return AnalysisResult(
                    success=True,
                    caption=caption_str,
                    description=desc_str
                )
            else:
                return AnalysisResult(
                    success=False,
                    caption="",
                    description="",
                    error="Could not extract captions from workflow output"
                )

        except Exception as e:
            logger.error(f"Image analysis failed: {e}", exc_info=True)
            return AnalysisResult(
                success=False,
                caption="",
                description="",
                error=str(e)
            )
        finally:
            # Cleanup uploaded image
            if uploaded_filename:
                self._cleanup_image(uploaded_filename)

    def analyze_batch(
        self,
        image_paths: List[str],
        callback: Optional[Callable[[int, int, str, str], None]] = None,
    ) -> List[AnalysisResult]:
        """
        Analyze multiple images.

        Args:
            image_paths: List of image paths
            callback: Optional callback(current_index, total, image_name, status)

        Returns:
            List of AnalysisResult objects
        """
        results = []
        total = len(image_paths)

        for idx, image_path in enumerate(image_paths):
            image_name = os.path.basename(image_path)

            if callback:
                callback(idx, total, image_name, "Analyzing...")

            def single_callback(pct, status):
                if callback:
                    callback(idx, total, image_name, f"{status} ({pct*100:.0f}%)")

            result = self.analyze_image(image_path, callback=single_callback)
            results.append(result)

            if callback:
                status = "Done" if result.success else f"Error: {result.error}"
                callback(idx + 1, total, image_name, status)

        return results
