"""Video plan builder: split shots into segments and build generation plan."""
import math
import os
from typing import List, Optional

from domain.models import Storyboard, SelectionSet, PlanSegment, GenerationPlan, Shot
from infrastructure.logger import get_logger

logger = get_logger(__name__)


class VideoPlanBuilder:
    """Build video generation plans with automatic segmentation for long shots."""

    def __init__(self, max_segment_seconds: float = 3.0):
        """
        Initialize the plan builder.

        Args:
            max_segment_seconds: Maximum duration per segment (default: 3.0s)
        """
        self.max_segment_seconds = max_segment_seconds

    def build(self, storyboard: Storyboard, selection: SelectionSet) -> GenerationPlan:
        """
        Build a generation plan from storyboard and keyframe selections.

        For shots longer than max_segment_seconds, automatically splits into
        multiple segments with LastFrame chaining.

        Args:
            storyboard: Loaded storyboard with shot definitions
            selection: Selected keyframes from Phase 2

        Returns:
            GenerationPlan with all segments ready for execution
        """
        selection_map = {entry.shot_id: entry for entry in selection.selections}
        segments: List[PlanSegment] = []

        for shot in storyboard.shots:
            selection_entry = selection_map.get(shot.shot_id)

            if not selection_entry:
                logger.warning(f"No selection found for shot {shot.shot_id}")
                segments.append(self._placeholder_segment(shot, "no_selection"))
                continue

            start_frame_path = selection_entry.export_path or selection_entry.source_path

            if not start_frame_path or not os.path.exists(start_frame_path):
                logger.warning(f"Startframe missing for shot {shot.shot_id}: {start_frame_path}")
                segments.append(self._placeholder_segment(shot, "startframe_missing"))
                continue

            # Calculate number of segments needed
            chain_total = max(1, math.ceil(shot.duration / self.max_segment_seconds))
            remaining = shot.duration
            needs_extension = shot.duration > self.max_segment_seconds

            # Build segment chain
            for idx in range(chain_total):
                plan_id = shot.shot_id if idx == 0 else f"{shot.shot_id}{chr(ord('A') + idx)}"
                filename_base = (
                    shot.filename_base if idx == 0
                    else f"{shot.filename_base}_seg{idx + 1:02d}"
                )
                clip_name = f"{plan_id}_{shot.filename_base}"

                requested_duration = round(
                    min(self.max_segment_seconds, remaining if remaining > 0 else self.max_segment_seconds),
                    2
                )

                effective_duration = (
                    min(shot.duration, self.max_segment_seconds)
                    if chain_total == 1
                    else self.max_segment_seconds
                )

                # First segment uses selection startframe, others wait for chain
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

        logger.info(f"Built plan: {len(segments)} segments from {len(storyboard.shots)} shots")
        return GenerationPlan(segments=segments)

    def _placeholder_segment(self, shot: Shot, status: str) -> PlanSegment:
        """
        Create placeholder entry for missing startframes/selections.

        Args:
            shot: Shot with missing data
            status: Status reason (e.g., "no_selection", "startframe_missing")

        Returns:
            Placeholder PlanSegment
        """
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


__all__ = ["VideoPlanBuilder"]
