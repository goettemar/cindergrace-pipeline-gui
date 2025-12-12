"""Video generation service: plan building + execution helpers."""
import copy
import glob
import math
import os
import re
import shutil
import subprocess
from typing import Dict, Any, List, Optional, Tuple

from domain.models import Storyboard, SelectionSet, PlanSegment, GenerationPlan, Shot
from infrastructure.model_validator import ModelValidator
from infrastructure.project_store import ProjectStore
from infrastructure.state_store import VideoGeneratorStateStore
from infrastructure.comfy_api import ComfyUIAPI


class VideoPlanBuilder:
    def __init__(self, max_segment_seconds: float = 3.0):
        self.max_segment_seconds = max_segment_seconds

    def build(self, storyboard: Storyboard, selection: SelectionSet) -> GenerationPlan:
        selection_map = {entry.shot_id: entry for entry in selection.selections}
        segments: List[PlanSegment] = []

        for shot in storyboard.shots:
            selection_entry = selection_map.get(shot.shot_id)
            if not selection_entry:
                segments.append(self._placeholder_segment(shot, "no_selection"))
                continue

            start_frame_path = selection_entry.export_path or selection_entry.source_path
            if not start_frame_path or not os.path.exists(start_frame_path):
                segments.append(self._placeholder_segment(shot, "startframe_missing"))
                continue

            chain_total = max(1, math.ceil(shot.duration / self.max_segment_seconds))
            remaining = shot.duration
            needs_extension = shot.duration > self.max_segment_seconds

            for idx in range(chain_total):
                plan_id = shot.shot_id if idx == 0 else f"{shot.shot_id}{chr(ord('A') + idx)}"
                filename_base = (
                    shot.filename_base if idx == 0 else f"{shot.filename_base}_seg{idx + 1:02d}"
                )
                clip_name = f"{plan_id}_{shot.filename_base}"
                requested_duration = round(min(self.max_segment_seconds, remaining if remaining > 0 else self.max_segment_seconds), 2)
                effective_duration = (
                    min(shot.duration, self.max_segment_seconds)
                    if chain_total == 1 else
                    self.max_segment_seconds
                )
                start_frame = start_frame_path if idx == 0 else None
                start_source = "selection" if idx == 0 else "chain_wait"
                ready = bool(start_frame) if idx == 0 else False
                start_frame_source = start_source if (start_frame or idx > 0) else "missing"

                segments.append(
                    PlanSegment(
                        plan_id=plan_id,
                        shot_id=shot.shot_id,
                        filename_base=filename_base,
                        prompt=shot.prompt,
                        width=shot.width,
                        height=shot.height,
                        duration=shot.duration,
                        segment_index=idx + 1,
                        segment_total=chain_total,
                        target_duration=requested_duration,
                        effective_duration=round(effective_duration, 2),
                        segment_requested_duration=requested_duration,
                        start_frame=start_frame,
                        start_frame_source=start_frame_source,
                        chain_id=shot.shot_id,
                        wan_motion=shot.wan_motion,
                        ready=ready,
                        selected_file=selection_entry.selected_file,
                        selected_variant=selection_entry.selected_variant,
                        clip_name=clip_name,
                        needs_extension=needs_extension,
                        status="pending",
                    )
                )
                remaining = max(0.0, remaining - self.max_segment_seconds)
        return GenerationPlan(segments=segments)

    def _placeholder_segment(self, shot: Shot, status: str) -> PlanSegment:
        """Create placeholder entry for missing startframes/selections."""
        duration = shot.duration
        target = min(duration, self.max_segment_seconds)
        return PlanSegment(
            plan_id=shot.shot_id,
            shot_id=shot.shot_id,
            filename_base=shot.filename_base,
            prompt=shot.prompt,
            width=shot.width,
            height=shot.height,
            duration=duration,
            segment_index=1,
            segment_total=max(1, math.ceil(duration / self.max_segment_seconds)),
            target_duration=target,
            effective_duration=min(duration, self.max_segment_seconds),
            segment_requested_duration=target,
            start_frame=None,
            start_frame_source="missing",
            chain_id=shot.shot_id,
            wan_motion=shot.wan_motion,
            ready=False,
            selected_file=None,
            selected_variant=None,
            clip_name=f"{shot.shot_id}_{shot.filename_base}",
            needs_extension=duration > self.max_segment_seconds,
            status=status,
        )


class VideoGenerationService:
    """Handle execution of video plans via ComfyUI."""

    def __init__(
        self,
        project_store: ProjectStore,
        model_validator: ModelValidator,
        state_store: VideoGeneratorStateStore,
        plan_builder: Optional[VideoPlanBuilder] = None,
    ):
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
        """Execute ComfyUI workflow for all ready plan entries."""
        working_plan = copy.deepcopy(plan_state)
        logs: List[str] = []
        last_video_path: Optional[str] = None

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
                )
                if video_paths:
                    entry["status"] = "completed"
                    entry["output_files"] = video_paths
                    last_video_path = video_paths[-1]
                    logs.append(f"  ✓ {clip_label}: {len(video_paths)} Datei(en)")
                    if last_frame_path:
                        entry["last_frame"] = last_frame_path
                        propagated = self._propagate_chain_start_frame(working_plan, entry, last_frame_path)
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

        return working_plan, logs, last_video_path

    # ----------------------------------------
    # Internal helpers (migrated from addon)
    # ----------------------------------------
    def _run_video_job(
        self,
        workflow_template: Dict[str, Any],
        entry: Dict[str, Any],
        fps: int,
        project: Dict[str, Any],
        comfy_api: ComfyUIAPI,
    ) -> Tuple[List[str], Optional[str]]:
        workflow = copy.deepcopy(workflow_template)
        frames = max(1, int(round((entry.get("effective_duration") or entry.get("target_duration") or 1) * fps)))
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
                "Keine Videodatei gefunden. Prüfe ComfyUI (fehlende Modelle/Nodes?) oder passe den Workflow an."
            )
        last_frame_path = None
        if entry.get("segment_total", 1) > entry.get("segment_index", 1):
            last_frame_path = self._extract_last_frame(video_paths[-1], entry, project)
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
        """Inject clip-specific values into the workflow template."""
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

            if start_frame_path and node_type in {"LoadImage", "ImageInput", "LoadImageForVideo"}:
                if "image" in inputs:
                    inputs["image"] = start_frame_path
                elif "filename" in inputs:
                    inputs["filename"] = start_frame_path
                elif "path" in inputs:
                    inputs["path"] = start_frame_path

            if fps:
                if "fps" in inputs:
                    inputs["fps"] = fps
                if "frame_rate" in inputs:
                    inputs["frame_rate"] = fps

            if frames:
                for key in ("frame_count", "frames", "num_frames"):
                    if key in inputs:
                        inputs[key] = frames

            if node_type == "SaveVideo":
                safe_prefix = re.sub(r"[^\w\-]+", "_", filename_prefix)
                inputs["filename_prefix"] = safe_prefix

            # Enforce resolution on any latent/vae/video nodes
            for key in ("width", "W"):
                if key in inputs:
                    inputs[key] = width
            for key in ("height", "H"):
                if key in inputs:
                    inputs[key] = height

        return updated

    def _copy_video_outputs(self, entry: Dict[str, Any], project: Dict[str, Any]) -> List[str]:
        """Copy generated video files from ComfyUI/output into the active project/video folder."""
        try:
            comfy_output = self.project_store.comfy_output_dir()
        except FileNotFoundError as exc:
            print(f"⚠️  ComfyUI Output nicht gefunden: {exc}")
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
                    if project_path and os.path.commonpath([src, project_path]) == project_path:
                        continue
                    seen.add(src)
                    dest_filename = self._build_video_filename(base_name, entry, ext, dest_dir)
                    dest = os.path.join(dest_dir, dest_filename)
                    shutil.copy2(src, dest)
                    copied.append(dest)

        return copied

    def _extract_last_frame(self, video_path: str, entry: Dict[str, Any], project: Dict[str, Any]) -> Optional[str]:
        """Grab final frame of a clip via ffmpeg for chaining."""
        if shutil.which("ffmpeg") is None:
            print("⚠️  ffmpeg nicht gefunden – LastFrame kann nicht extrahiert werden.")
            return None

        cache_dir = self.project_store.ensure_dir(project, "video", "_startframes")

        plan_id = entry.get("plan_id") or entry.get("shot_id") or "clip"
        target = os.path.join(cache_dir, f"{plan_id}_lastframe.png")
        cmd = [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-sseof",
            "-0.05",
            "-i",
            video_path,
            "-frames:v",
            "1",
            target,
        ]
        try:
            subprocess.run(cmd, check=True)
        except Exception as exc:
            print(f"⚠️  ffmpeg konnte den letzten Frame nicht extrahieren ({exc})")
            return None

        return target if os.path.exists(target) else None

    def _build_video_filename(self, base_name: str, entry: Dict[str, Any], ext: str, dest_dir: str) -> str:
        """Generate readable filename for exported clips."""
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
        """Assign extracted last frame to the next segment in chain."""
        if current_entry.get("segment_index", 1) >= current_entry.get("segment_total", 1):
            return None

        next_index = current_entry.get("segment_index", 1) + 1
        for entry in plan:
            if entry.get("shot_id") == current_entry.get("shot_id") and entry.get("segment_index") == next_index:
                entry["start_frame"] = frame_path
                entry["start_frame_source"] = "chain"
                entry["ready"] = True
                entry["status"] = "pending"
                return entry.get("plan_id") or entry.get("shot_id")
        return None


__all__ = ["VideoPlanBuilder", "VideoGenerationService"]
