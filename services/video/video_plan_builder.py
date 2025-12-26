"""Video plan builder: create generation plan from storyboard and selections."""
import math
import os
from typing import List, Optional

from domain.models import Storyboard, SelectionSet, PlanSegment, GenerationPlan, Shot
from infrastructure.logger import get_logger

logger = get_logger(__name__)

# Default constants for segment calculation
DEFAULT_MAX_FRAMES = 73  # Maximum frames per WAN segment
DEFAULT_FPS = 24  # Default frames per second


class VideoPlanBuilder:
    """Build video generation plans from storyboard and keyframe selections.

    Creates plan entries per shot, splitting longer shots into multiple segments.
    For shots longer than one segment duration (max_frames / fps), the system
    uses last-frame-to-first-frame chaining to extend videos seamlessly.
    """

    def __init__(
        self,
        max_frames: int = DEFAULT_MAX_FRAMES,
        fps: int = DEFAULT_FPS,
    ):
        """
        Initialize the plan builder.

        Args:
            max_frames: Maximum frames per video segment (default: 73)
            fps: Frames per second for duration calculation (default: 24)
        """
        self.max_frames = max_frames
        self.fps = fps

    @property
    def segment_duration(self) -> float:
        """Calculate maximum duration per segment based on frames and fps."""
        return self.max_frames / self.fps

    def build(
        self,
        storyboard: Storyboard,
        selection: SelectionSet,
        fps: Optional[int] = None,
    ) -> GenerationPlan:
        """
        Build a generation plan from storyboard and keyframe selections.

        Splits shots into multiple segments if duration exceeds segment_duration.
        First segment uses the keyframe, subsequent segments will use the
        last frame from the previous segment (chaining).

        Args:
            storyboard: Loaded storyboard with shot definitions
            selection: Selected keyframes from Phase 2
            fps: Override FPS for this build (uses instance default if None)

        Returns:
            GenerationPlan with all segments ready for execution
        """
        # Use provided fps or instance default
        effective_fps = fps or self.fps
        segment_duration = self.max_frames / effective_fps

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
            shot_segments = self._build_shot_segments(
                shot=shot,
                selection_entry=selection_entry,
                start_frame_path=start_frame_path,
                segment_duration=segment_duration,
            )
            segments.extend(shot_segments)

        total_segments = len(segments)
        shots_with_chaining = sum(1 for s in segments if s.segment_total > 1 and s.segment_index == 1)
        logger.info(
            f"Built plan: {total_segments} segments from {len(storyboard.shots)} shots "
            f"({shots_with_chaining} shots require chaining)"
        )
        return GenerationPlan(segments=segments)

    def _build_shot_segments(
        self,
        shot: Shot,
        selection_entry,
        start_frame_path: str,
        segment_duration: float,
    ) -> List[PlanSegment]:
        """
        Build all segments for a single shot, splitting if needed.

        Args:
            shot: Shot definition
            selection_entry: Selected keyframe entry
            start_frame_path: Path to the keyframe image
            segment_duration: Maximum duration per segment in seconds

        Returns:
            List of PlanSegments (1 if no splitting needed, multiple for longer shots)
        """
        # Calculate how many segments are needed
        num_segments = max(1, math.ceil(shot.duration / segment_duration))

        # If only one segment needed, return simple segment
        if num_segments == 1:
            return [
                PlanSegment(
                    plan_id=shot.shot_id,
                    shot_id=shot.shot_id,
                    filename_base=shot.filename_base,
                    prompt=shot.prompt,
                    width=shot.width,
                    height=shot.height,
                    duration=shot.duration,
                    segment_index=1,
                    segment_total=1,
                    target_duration=shot.duration,
                    effective_duration=shot.duration,
                    segment_requested_duration=shot.duration,
                    start_frame=start_frame_path,
                    start_frame_source="selection",
                    chain_id=shot.shot_id,
                    wan_motion=shot.wan_motion,
                    ready=True,
                    selected_file=selection_entry.selected_file,
                    selected_variant=selection_entry.selected_variant,
                    clip_name=f"{shot.shot_id}_{shot.filename_base}",
                    needs_extension=False,
                    status="pending",
                )
            ]

        # Split into multiple segments
        segments: List[PlanSegment] = []
        remaining_duration = shot.duration

        for seg_idx in range(1, num_segments + 1):
            is_first = seg_idx == 1
            is_last = seg_idx == num_segments

            # Calculate this segment's duration
            if is_last:
                seg_duration = remaining_duration
            else:
                seg_duration = min(segment_duration, remaining_duration)
            remaining_duration -= seg_duration

            # First segment uses keyframe, subsequent use last frame from previous
            if is_first:
                seg_start_frame = start_frame_path
                seg_start_source = "selection"
                seg_ready = True
            else:
                seg_start_frame = None  # Will be set during execution
                seg_start_source = "chain_wait"
                seg_ready = False  # Not ready until previous segment completes

            # Unique clip name for each segment
            suffix = "" if is_first else chr(ord("A") + seg_idx - 1)
            clip_name = f"{shot.shot_id}{suffix}_{shot.filename_base}"
            plan_id = shot.shot_id if is_first else f"{shot.shot_id}{suffix}"

            segment = PlanSegment(
                plan_id=plan_id,
                shot_id=shot.shot_id,
                filename_base=shot.filename_base,
                prompt=shot.prompt,
                width=shot.width,
                height=shot.height,
                duration=seg_duration,
                segment_index=seg_idx,
                segment_total=num_segments,
                target_duration=shot.duration,
                effective_duration=seg_duration,
                segment_requested_duration=seg_duration,
                start_frame=seg_start_frame,
                start_frame_source=seg_start_source,
                chain_id=shot.shot_id,
                wan_motion=shot.wan_motion,
                ready=seg_ready,
                selected_file=selection_entry.selected_file if is_first else None,
                selected_variant=selection_entry.selected_variant if is_first else None,
                clip_name=clip_name,
                needs_extension=not is_last,  # All but last segment need extension
                status="pending",
            )
            segments.append(segment)

        logger.info(
            f"Shot {shot.shot_id}: {shot.duration}s → {num_segments} segments "
            f"(segment_duration={segment_duration:.2f}s)"
        )
        return segments

    def _placeholder_segment(self, shot: Shot, status: str) -> PlanSegment:
        """Create placeholder segment for missing selection/startframe."""
        num_segments = max(1, math.ceil(shot.duration / self.segment_duration))
        return PlanSegment(
            plan_id=shot.shot_id,
            shot_id=shot.shot_id,
            filename_base=shot.filename_base,
            prompt=shot.prompt,
            width=shot.width,
            height=shot.height,
            duration=shot.duration,
            segment_index=1,
            segment_total=num_segments,
            target_duration=shot.duration,
            effective_duration=shot.duration,
            segment_requested_duration=shot.duration,
            start_frame=None,
            start_frame_source="missing",
            chain_id=shot.shot_id,
            wan_motion=shot.wan_motion,
            ready=False,
            selected_file=None,
            selected_variant=None,
            clip_name=f"{shot.shot_id}_{shot.filename_base}",
            needs_extension=num_segments > 1,
            status=status,
        )


__all__ = ["VideoPlanBuilder", "DEFAULT_MAX_FRAMES", "DEFAULT_FPS"]
