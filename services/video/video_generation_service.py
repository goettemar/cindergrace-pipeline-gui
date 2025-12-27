"""Video generation service: execute video plans via ComfyUI."""
import copy
import os
import random
import re
from typing import Dict, Any, List, Optional, Tuple, TYPE_CHECKING

from domain.models import Storyboard, SelectionSet, PlanSegment, GenerationPlan
from infrastructure.model_validator import ModelValidator
from infrastructure.project_store import ProjectStore
from infrastructure.state_store import VideoGeneratorStateStore
from infrastructure.comfy_api import ComfyUIAPI
from infrastructure.logger import get_logger
from infrastructure.job_status_store import JobStatusStore
from services.video.video_plan_builder import VideoPlanBuilder
from services.video.file_operations import VideoFileHandler
from services.video.last_frame_extractor import LastFrameExtractor
from services.cleanup_service import CleanupService

logger = get_logger(__name__)


class VideoGenerationService:
    """Execute video generation plans via ComfyUI.

    Supports last-frame-to-first-frame chaining for videos longer than
    3 seconds, enabling seamless multi-segment video generation.
    """

    def __init__(
        self,
        project_store: ProjectStore,
        model_validator: ModelValidator,
        state_store: VideoGeneratorStateStore,
        plan_builder: Optional[VideoPlanBuilder] = None,
    ):
        """Initialize the video generation service."""
        self.project_store = project_store
        self.model_validator = model_validator
        self.state_store = state_store
        self.plan_builder = plan_builder or VideoPlanBuilder()
        self._file_handler = VideoFileHandler(project_store)
        self._cleanup_service = CleanupService(project_store)
        self._job_store = JobStatusStore()

    def run_generation(
        self,
        plan_state: List[Dict[str, Any]],
        workflow_template: Dict[str, Any],
        fps: int,
        project: Dict[str, Any],
        comfy_api: ComfyUIAPI,
        resolution: Optional[Tuple[int, int]] = None,
    ) -> Tuple[List[Dict[str, Any]], List[str], Optional[str]]:
        """Execute ComfyUI workflow for all ready plan entries.

        Supports last-frame-to-first-frame chaining for multi-segment shots.
        """
        working_plan = copy.deepcopy(plan_state)
        logs: List[str] = []
        last_video_path: Optional[str] = None
        self._job_store.set_status(
            project.get("path"),
            "video_generation",
            "running",
            message=f"Video generation started ({len(working_plan)} segments)",
            metadata={"segments": len(working_plan)},
        )

        # Cleanup old video and image files before starting generation
        cleanup_count = self._cleanup_service.cleanup_before_video_generation(project)
        if cleanup_count > 0:
            logs.append(f"🧹 {cleanup_count} alte Datei(en) archiviert")

        extractor = LastFrameExtractor()

        # Process segments
        idx = 0
        while idx < len(working_plan):
            entry = working_plan[idx]
            clip_label = self._format_clip_label(entry)
            segment_info = self._format_segment_info(entry)

            if not entry.get("ready"):
                if entry.get("start_frame_source") in {"pending_last_frame", "chain_wait"}:
                    logs.append(f"- ⏳ {clip_label}{segment_info} wartet auf vorheriges Segment")
                else:
                    logs.append(f"- ⏭️ {clip_label}{segment_info} übersprungen (kein Startframe)")
                idx += 1
                continue

            duration = entry.get("duration") or entry.get("effective_duration") or 3.0
            logs.append(f"- ▶️ {clip_label}{segment_info} ({duration:.1f}s @ {fps}fps)")

            try:
                job_result = self._run_video_job(
                    workflow_template=workflow_template,
                    entry=entry,
                    fps=fps,
                    project=project,
                    comfy_api=comfy_api,
                    extractor=extractor,
                    resolution=resolution,
                )

                if isinstance(job_result, tuple):
                    video_paths, last_frame_path = job_result
                else:
                    video_paths, last_frame_path = job_result, None

                if video_paths:
                    entry["status"] = "completed"
                    entry["output_files"] = video_paths
                    last_video_path = video_paths[-1]
                    logs.append(f"  ✓ {clip_label}{segment_info}: {len(video_paths)} Video-Datei(en)")

                    # Handle chaining: capture last frame and prepare next segment
                    if entry.get("needs_extension") or entry.get("segment_total", 1) > 1:
                        if last_frame_path:
                            entry["last_frame"] = last_frame_path
                            logs.append(f"  📷 Last Frame gespeichert: {os.path.basename(last_frame_path)}")
                            target_id = self._propagate_chain_start_frame(working_plan, entry, last_frame_path)
                            if target_id:
                                logs.append(f"  🔗 Startframe an Segment {target_id} übergeben")
                        else:
                            logs.append("  ⚠️ LastFrame konnte nicht extrahiert werden")
                else:
                    entry["status"] = "generated_no_copy"
                    logs.append(f"  ⚠️ {clip_label}{segment_info}: Workflow lief, aber keine Video-Datei gefunden")

            except Exception as exc:
                entry["status"] = f"error: {exc}"
                logs.append(f"  ✗ {clip_label}{segment_info}: {exc}")
                logger.error(f"Video generation failed for {clip_label}: {exc}", exc_info=True)

            idx += 1

        completed = sum(1 for entry in working_plan if entry.get("status") == "completed")
        failed = sum(1 for entry in working_plan if str(entry.get("status", "")).startswith("error"))
        warnings = sum(1 for entry in working_plan if entry.get("status") == "generated_no_copy")
        if failed or warnings:
            status = "completed_with_issues"
            message = f"Completed {completed}/{len(working_plan)} segments, {failed} failed, {warnings} warnings"
        else:
            status = "completed"
            message = f"Completed {completed}/{len(working_plan)} segments"

        self._job_store.set_status(
            project.get("path"),
            "video_generation",
            status,
            message=message,
            metadata={
                "segments_total": len(working_plan),
                "segments_completed": completed,
                "segments_failed": failed,
                "segments_warning": warnings,
            },
        )

        return working_plan, logs, last_video_path

    def _format_segment_info(self, entry: Dict[str, Any]) -> str:
        """Format segment information for multi-segment shots."""
        segment_total = entry.get("segment_total", 1)
        if segment_total <= 1:
            return ""
        segment_index = entry.get("segment_index", 1)
        return f" [Seg {segment_index}/{segment_total}]"

    def _propagate_chain_start_frame(
        self,
        plan: List[Dict[str, Any]],
        current_entry: Dict[str, Any],
        last_frame_path: str,
    ) -> Optional[str]:
        """Assign last-frame start to the next segment in the chain."""
        current_index = current_entry.get("segment_index", 1)
        current_shot = current_entry.get("shot_id")

        for entry in plan:
            if entry.get("shot_id") == current_shot and entry.get("segment_index") == current_index + 1:
                entry["start_frame"] = last_frame_path
                entry["start_frame_source"] = "chain"
                entry["ready"] = True
                entry["status"] = "pending"
                return entry.get("plan_id")
        return None

    def _run_video_job(
        self,
        workflow_template: Dict[str, Any],
        entry: Dict[str, Any],
        fps: int,
        project: Dict[str, Any],
        comfy_api: ComfyUIAPI,
        extractor: Optional[LastFrameExtractor] = None,
        resolution: Optional[Tuple[int, int]] = None,
    ) -> Tuple[List[str], Optional[str]]:
        """Execute a single video generation job."""
        workflow = copy.deepcopy(workflow_template)
        duration = entry.get("duration") or entry.get("effective_duration") or 3.0
        frames = max(1, int(round(duration * fps)))

        # Use resolution from parameter (project config) or fallback to entry
        if resolution:
            width, height = resolution
        else:
            width = int(entry.get("width", 1024))
            height = int(entry.get("height", 576))

        # Handle start frame - upload to RunPod if needed
        start_frame_path = entry.get("start_frame")
        if start_frame_path and self.project_store.config.is_runpod_backend():
            start_frame_path = self._upload_start_frame_to_runpod(comfy_api, start_frame_path)

        updated_workflow = self._apply_video_params(
            comfy_api=comfy_api,
            workflow=workflow,
            prompt=entry.get("prompt", ""),
            width=width,
            height=height,
            filename_prefix=entry.get("clip_name", entry.get("shot_id", "clip")),
            start_frame_path=start_frame_path,
            fps=fps,
            frames=frames,
            wan_motion=entry.get("wan_motion"),
        )

        prompt_id = comfy_api.queue_prompt(updated_workflow)
        logger.info(f"Video job queued: {prompt_id}, waiting for completion...")
        result = comfy_api.monitor_progress(prompt_id, timeout=1800)
        logger.info(f"Video job {prompt_id} monitor returned: status={result.get('status')}")

        if result["status"] != "success":
            raise RuntimeError(result.get("error", "ComfyUI-Job fehlgeschlagen"))

        # RunPod integration: Download outputs from remote ComfyUI
        if self.project_store.config.is_runpod_backend():
            self._download_runpod_outputs(comfy_api, prompt_id)

        video_paths = self._copy_video_outputs(entry, project)

        if not video_paths:
            raise RuntimeError(
                "Keine Videodatei gefunden. Prüfe ComfyUI (fehlende Modelle/Nodes?) "
                "oder passe den Workflow an."
            )

        last_frame_path = None
        if extractor and entry.get("segment_total", 1) > 1:
            last_frame_path = extractor.extract(video_paths[-1])

        return video_paths, last_frame_path

    def _download_runpod_outputs(self, comfy_api: ComfyUIAPI, prompt_id: str) -> None:
        """Download outputs from RunPod ComfyUI to local output directory.

        Args:
            comfy_api: ComfyUI API client
            prompt_id: Job ID to download outputs for
        """
        try:
            local_output_dir = self.project_store.comfy_output_dir()
            logger.info(f"Downloading RunPod outputs for job {prompt_id} to {local_output_dir}")
            downloaded = comfy_api.download_job_outputs(prompt_id, local_output_dir)
            if downloaded:
                logger.info(f"Downloaded {len(downloaded)} file(s) from RunPod")
            else:
                logger.warning("No files downloaded from RunPod")
        except Exception as e:
            logger.error(f"Failed to download RunPod outputs: {e}", exc_info=True)

    def _upload_start_frame_to_runpod(
        self, comfy_api: ComfyUIAPI, local_path: str
    ) -> Optional[str]:
        """Upload a start frame image to RunPod ComfyUI.

        Args:
            comfy_api: ComfyUI API client
            local_path: Local path to the image file

        Returns:
            Remote filename if successful, original path otherwise
        """
        try:
            if not os.path.exists(local_path):
                logger.warning(f"Start frame not found: {local_path}")
                return local_path

            logger.info(f"Uploading start frame to RunPod: {local_path}")
            remote_filename = comfy_api.upload_image(local_path)

            if remote_filename:
                logger.info(f"Start frame uploaded: {remote_filename}")
                return remote_filename
            else:
                logger.warning("Failed to upload start frame, using local path")
                return local_path
        except Exception as e:
            logger.error(f"Failed to upload start frame: {e}", exc_info=True)
            return local_path

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
        """Inject clip-specific values into the workflow template."""
        # Generate random seed to prevent ComfyUI caching
        random_seed = random.randint(1, 2**32 - 1)
        logger.debug(f"Using random seed {random_seed} to prevent caching")

        updated = comfy_api.update_workflow_params(
            workflow,
            prompt=prompt,
            width=width,
            height=height,
            filename_prefix=filename_prefix,
            seed=random_seed,
        )

        for node_data in updated.values():
            inputs = node_data.get("inputs", {})
            node_type = node_data.get("class_type", "")

            # Inject random seed to prevent caching
            if "seed" in inputs:
                inputs["seed"] = random_seed
            if "noise_seed" in inputs:
                inputs["noise_seed"] = random_seed

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

            # Sanitize filename for video output nodes
            if node_type in {"SaveVideo", "VHS_VideoCombine"}:
                safe_prefix = re.sub(r"[^\w\-]+", "_", filename_prefix)
                inputs["filename_prefix"] = safe_prefix

            # Set filename for last frame SaveImage nodes
            if node_type == "SaveImage" and "filename_prefix" in inputs:
                safe_prefix = re.sub(r"[^\w\-]+", "_", filename_prefix)
                inputs["filename_prefix"] = f"{safe_prefix}_lastframe"

            # Enforce resolution on latent/vae/video nodes
            for key in ("width", "W"):
                if key in inputs:
                    inputs[key] = width
            for key in ("height", "H"):
                if key in inputs:
                    inputs[key] = height

        return updated

    def _format_clip_label(self, entry: Dict[str, Any]) -> str:
        """Format human-readable label for log messages."""
        return f"Shot {entry.get('shot_id')}"

    def _copy_video_outputs(self, entry: Dict[str, Any], project: Dict[str, Any]) -> List[str]:
        """Backward-compatible wrapper for video output copying."""
        return self._file_handler.copy_video_outputs(entry, project)

    def _build_video_filename(self, base_name: str, entry: Dict[str, Any], ext: str, dest_dir: str) -> str:
        """Backward-compatible wrapper for filename generation."""
        return self._file_handler._build_video_filename(base_name, entry, ext, dest_dir)


__all__ = ["VideoGenerationService"]
