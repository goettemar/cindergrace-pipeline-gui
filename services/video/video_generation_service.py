"""Video generation service: execute video plans via ComfyUI."""
import copy
import glob
import os
import re
import shutil
from typing import Dict, Any, List, Optional, Tuple

from domain.models import Storyboard, SelectionSet, PlanSegment, GenerationPlan
from infrastructure.model_validator import ModelValidator
from infrastructure.project_store import ProjectStore
from infrastructure.state_store import VideoGeneratorStateStore
from infrastructure.comfy_api import ComfyUIAPI
from infrastructure.logger import get_logger
from services.video.video_plan_builder import VideoPlanBuilder
from services.video.last_frame_extractor import LastFrameExtractor

logger = get_logger(__name__)


class VideoGenerationService:
    """Execute video generation plans via ComfyUI with LastFrame chaining."""

    def __init__(
        self,
        project_store: ProjectStore,
        model_validator: ModelValidator,
        state_store: VideoGeneratorStateStore,
        plan_builder: Optional[VideoPlanBuilder] = None,
    ):
        """
        Initialize the video generation service.

        Args:
            project_store: Project path management
            model_validator: Model validation for workflows
            state_store: UI state persistence
            plan_builder: Optional plan builder (creates default if None)
        """
        self.project_store = project_store
        self.model_validator = model_validator
        self.state_store = state_store
        self.plan_builder = plan_builder or VideoPlanBuilder()

    def run_generation(
        self,
        plan_state: List[Dict[str, Any]],
        workflow_template: Dict[str, Any],
        fps: int,
        project: Dict[str, Any],
        comfy_api: ComfyUIAPI,
    ) -> Tuple[List[Dict[str, Any]], List[str], Optional[str]]:
        """
        Execute ComfyUI workflow for all ready plan entries.

        Args:
            plan_state: List of plan segments (dicts)
            workflow_template: ComfyUI workflow JSON template
            fps: Frames per second
            project: Active project metadata
            comfy_api: ComfyUI API instance

        Returns:
            Tuple of (updated_plan, logs, last_video_path)
        """
        working_plan = copy.deepcopy(plan_state)
        logs: List[str] = []
        last_video_path: Optional[str] = None

        # Initialize LastFrame extractor
        cache_dir = self.project_store.ensure_dir(project, "video", "_startframes")
        extractor = LastFrameExtractor(cache_dir)

        if not extractor.is_available():
            logs.append("⚠️ ffmpeg nicht gefunden – LastFrame-Kette wird übersprungen")

        for entry in working_plan:
            clip_label = self._format_clip_label(entry)

            if not entry.get("ready"):
                if entry.get("start_frame_source") == "chain_wait":
                    logs.append(f"- ⏳ {clip_label} wartet auf LastFrame aus vorherigem Segment")
                else:
                    logs.append(f"- ⏭️ {clip_label} übersprungen (kein Startframe)")
                continue

            effective_duration = entry.get("effective_duration") or entry.get("target_duration") or 3.0
            logs.append(f"- ▶️ {clip_label} ({effective_duration}s @ {fps}fps)")

            try:
                video_paths, last_frame_path = self._run_video_job(
                    workflow_template=workflow_template,
                    entry=entry,
                    fps=fps,
                    project=project,
                    comfy_api=comfy_api,
                    extractor=extractor,
                )

                if video_paths:
                    entry["status"] = "completed"
                    entry["output_files"] = video_paths
                    last_video_path = video_paths[-1]
                    logs.append(f"  ✓ {clip_label}: {len(video_paths)} Datei(en)")

                    if last_frame_path:
                        entry["last_frame"] = last_frame_path
                        propagated = self._propagate_chain_start_frame(
                            working_plan, entry, last_frame_path
                        )
                        if propagated:
                            logs.append(
                                f"    ↪️ Startframe an Segment {entry.get('segment_index', 0) + 1}/"
                                f"{entry.get('segment_total', 1)} von Shot {entry['shot_id']} übergeben"
                            )
                    elif entry.get("segment_index", 1) < entry.get("segment_total", 1):
                        logs.append("    ⚠️ LastFrame konnte nicht extrahiert werden (prüfe ffmpeg).")
                else:
                    entry["status"] = "generated_no_copy"
                    logs.append(f"  ⚠️ {clip_label}: Workflow lief, aber keine Video-Datei gefunden")

            except Exception as exc:
                entry["status"] = f"error: {exc}"
                logs.append(f"  ✗ {clip_label}: {exc}")
                logger.error(f"Video generation failed for {clip_label}: {exc}", exc_info=True)

        return working_plan, logs, last_video_path

    # ----------------------------------------
    # Internal helpers
    # ----------------------------------------
    def _run_video_job(
        self,
        workflow_template: Dict[str, Any],
        entry: Dict[str, Any],
        fps: int,
        project: Dict[str, Any],
        comfy_api: ComfyUIAPI,
        extractor: LastFrameExtractor,
    ) -> Tuple[List[str], Optional[str]]:
        """
        Execute a single video generation job.

        Args:
            workflow_template: ComfyUI workflow template
            entry: Plan segment
            fps: Frames per second
            project: Project metadata
            comfy_api: ComfyUI API instance
            extractor: LastFrame extractor

        Returns:
            Tuple of (video_paths, last_frame_path)
        """
        workflow = copy.deepcopy(workflow_template)
        frames = max(
            1,
            int(round((entry.get("effective_duration") or entry.get("target_duration") or 1) * fps))
        )

        updated_workflow = self._apply_video_params(
            comfy_api=comfy_api,
            workflow=workflow,
            prompt=entry.get("prompt", ""),
            width=int(entry.get("width", 1024)),
            height=int(entry.get("height", 576)),
            filename_prefix=entry.get("clip_name", entry.get("shot_id", "clip")),
            start_frame_path=entry.get("start_frame"),
            fps=fps,
            frames=frames,
            wan_motion=entry.get("wan_motion"),
        )

        prompt_id = comfy_api.queue_prompt(updated_workflow)
        result = comfy_api.monitor_progress(prompt_id, timeout=1800)

        if result["status"] != "success":
            raise RuntimeError(result.get("error", "ComfyUI-Job fehlgeschlagen"))

        video_paths = self._copy_video_outputs(entry, project)

        if not video_paths:
            raise RuntimeError(
                "Keine Videodatei gefunden. Prüfe ComfyUI (fehlende Modelle/Nodes?) "
                "oder passe den Workflow an."
            )

        last_frame_path = None
        if entry.get("segment_total", 1) > entry.get("segment_index", 1):
            last_frame_path = extractor.extract(video_paths[-1], entry)

        return video_paths, last_frame_path

    def _apply_video_params(
        self,
        comfy_api: ComfyUIAPI,
        workflow: Dict[str, Any],
        prompt: str,
        width: int,
        height: int,
        filename_prefix: str,
        start_frame_path: Optional[str],
        fps: int,
        frames: int,
        wan_motion: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Inject clip-specific values into the workflow template.

        Args:
            comfy_api: ComfyUI API for workflow updates
            workflow: Base workflow template
            prompt: Text prompt
            width: Video width
            height: Video height
            filename_prefix: Output file prefix
            start_frame_path: Startframe image path
            fps: Frames per second
            frames: Total frame count
            wan_motion: Optional Wan motion parameters

        Returns:
            Updated workflow dict
        """
        updated = comfy_api.update_workflow_params(
            workflow,
            prompt=prompt,
            width=width,
            height=height,
            filename_prefix=filename_prefix,
        )

        for node_data in updated.values():
            inputs = node_data.get("inputs", {})
            node_type = node_data.get("class_type", "")

            # Inject startframe path
            if start_frame_path and node_type in {"LoadImage", "ImageInput", "LoadImageForVideo"}:
                if "image" in inputs:
                    inputs["image"] = start_frame_path
                elif "filename" in inputs:
                    inputs["filename"] = start_frame_path
                elif "path" in inputs:
                    inputs["path"] = start_frame_path

            # Inject FPS
            if fps:
                if "fps" in inputs:
                    inputs["fps"] = fps
                if "frame_rate" in inputs:
                    inputs["frame_rate"] = fps

            # Inject frame count
            if frames:
                for key in ("frame_count", "frames", "num_frames"):
                    if key in inputs:
                        inputs[key] = frames

            # Sanitize filename for SaveVideo nodes
            if node_type == "SaveVideo":
                safe_prefix = re.sub(r"[^\w\-]+", "_", filename_prefix)
                inputs["filename_prefix"] = safe_prefix

            # Enforce resolution on latent/vae/video nodes
            for key in ("width", "W"):
                if key in inputs:
                    inputs[key] = width
            for key in ("height", "H"):
                if key in inputs:
                    inputs[key] = height

        return updated

    def _copy_video_outputs(
        self,
        entry: Dict[str, Any],
        project: Dict[str, Any]
    ) -> List[str]:
        """
        Copy generated video files from ComfyUI/output to project/video folder.

        Args:
            entry: Plan segment
            project: Project metadata

        Returns:
            List of copied video file paths
        """
        try:
            comfy_output = self.project_store.comfy_output_dir()
        except FileNotFoundError as exc:
            logger.warning(f"ComfyUI output directory not found: {exc}")
            return []

        dest_dir = self.project_store.ensure_dir(project, "video")

        extensions = ("mp4", "webm", "mov", "gif")
        copied: List[str] = []
        clip_name = entry.get("clip_name") or entry.get("filename_base") or entry.get("shot_id", "clip")
        base_name = entry.get("filename_base", clip_name)
        project_path = project.get("path", "")

        for ext in extensions:
            patterns = [
                os.path.join(comfy_output, f"{clip_name}*.{ext}"),
                os.path.join(comfy_output, "**", f"{clip_name}*.{ext}"),
                os.path.join(comfy_output, "video", f"{clip_name}*.{ext}"),
                os.path.join(comfy_output, "video", "**", f"{clip_name}*.{ext}"),
                # Fallback to ComfyUI default naming
                os.path.join(comfy_output, "video", f"ComfyUI_*.{ext}"),
                os.path.join(comfy_output, "video", "**", f"ComfyUI_*.{ext}"),
            ]
            seen = set()

            for pattern in patterns:
                for src in glob.glob(pattern, recursive="**" in pattern):
                    if src in seen:
                        continue
                    # Skip files already in project directory
                    if project_path and os.path.commonpath([src, project_path]) == project_path:
                        continue

                    seen.add(src)
                    dest_filename = self._build_video_filename(base_name, entry, ext, dest_dir)
                    dest = os.path.join(dest_dir, dest_filename)
                    shutil.copy2(src, dest)
                    copied.append(dest)
                    logger.info(f"Copied video: {src} → {dest}")

        return copied

    def _build_video_filename(
        self,
        base_name: str,
        entry: Dict[str, Any],
        ext: str,
        dest_dir: str
    ) -> str:
        """
        Generate readable filename for exported clips.

        Args:
            base_name: Base filename
            entry: Plan segment
            ext: File extension
            dest_dir: Destination directory

        Returns:
            Unique filename
        """
        safe_base = re.sub(r"[^a-zA-Z0-9_-]+", "_", base_name) or entry.get("clip_name", "clip")
        candidate = f"{safe_base}.{ext}"
        variant = entry.get("selected_variant")
        counter = 1

        while os.path.exists(os.path.join(dest_dir, candidate)):
            suffix = f"_v{variant}" if variant else f"_{counter}"
            candidate = f"{safe_base}{suffix}.{ext}"
            counter += 1

        return candidate

    def _format_clip_label(self, entry: Dict[str, Any]) -> str:
        """Format human-readable label for log messages."""
        total = entry.get("segment_total", 1)
        index = entry.get("segment_index", 1)
        if total > 1:
            return f"Shot {entry.get('shot_id')} · Segment {index}/{total}"
        return f"Shot {entry.get('shot_id')}"

    def _propagate_chain_start_frame(
        self,
        plan: List[Dict[str, Any]],
        current_entry: Dict[str, Any],
        frame_path: str,
    ) -> Optional[str]:
        """
        Assign extracted last frame to the next segment in chain.

        Args:
            plan: Full plan state
            current_entry: Current segment
            frame_path: Path to extracted last frame

        Returns:
            Plan ID of next segment, or None if no next segment
        """
        if current_entry.get("segment_index", 1) >= current_entry.get("segment_total", 1):
            return None

        next_index = current_entry.get("segment_index", 1) + 1

        for entry in plan:
            if (entry.get("shot_id") == current_entry.get("shot_id")
                    and entry.get("segment_index") == next_index):
                entry["start_frame"] = frame_path
                entry["start_frame_source"] = "chain"
                entry["ready"] = True
                entry["status"] = "pending"
                logger.info(f"Propagated startframe to {entry.get('plan_id')}")
                return entry.get("plan_id") or entry.get("shot_id")

        return None


__all__ = ["VideoGenerationService"]
