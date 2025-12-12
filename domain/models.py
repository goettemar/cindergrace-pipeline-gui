"""Domain models for storyboard, selections, and video plans."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any


@dataclass
class MotionSettings:
    type: Optional[str] = None
    strength: Optional[float] = None
    notes: Optional[str] = None


@dataclass
class Shot:
    shot_id: str
    filename_base: str
    prompt: str
    width: int = 1024
    height: int = 576
    duration: float = 3.0
    wan_motion: Optional[MotionSettings] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "Shot":
        motion_payload = payload.get("wan_motion") or {}
        motion = MotionSettings(
            type=motion_payload.get("type"),
            strength=motion_payload.get("strength"),
            notes=motion_payload.get("notes"),
        ) if motion_payload else None
        return cls(
            shot_id=payload.get("shot_id", ""),
            filename_base=payload.get("filename_base", payload.get("shot_id", "shot")),
            prompt=payload.get("prompt", ""),
            width=int(payload.get("width", 1024)),
            height=int(payload.get("height", 576)),
            duration=float(payload.get("duration", 3.0)),
            wan_motion=motion,
            raw=payload,
        )


@dataclass
class Storyboard:
    project: str
    shots: List[Shot]
    version: Optional[str] = None
    description: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "Storyboard":
        shots = [Shot.from_dict(shot) for shot in payload.get("shots", [])]
        return cls(
            project=payload.get("project", "Unnamed Project"),
            shots=shots,
            version=payload.get("version"),
            description=payload.get("description"),
            raw=payload,
        )

    def get_shot(self, shot_id: str) -> Optional[Shot]:
        return next((shot for shot in self.shots if shot.shot_id == shot_id), None)


@dataclass
class SelectionEntry:
    shot_id: str
    filename_base: str
    selected_variant: int
    selected_file: str
    source_path: str
    export_path: Optional[str] = None

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "SelectionEntry":
        return cls(
            shot_id=payload.get("shot_id", ""),
            filename_base=payload.get("filename_base", ""),
            selected_variant=int(payload.get("selected_variant", 0)),
            selected_file=payload.get("selected_file", ""),
            source_path=payload.get("source_path", ""),
            export_path=payload.get("export_path"),
        )


@dataclass
class SelectionSet:
    project: str
    selections: List[SelectionEntry]
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "SelectionSet":
        entries = [SelectionEntry.from_dict(entry) for entry in payload.get("selections", [])]
        return cls(
            project=payload.get("project", ""),
            selections=entries,
            raw=payload,
        )

    def get_selection(self, shot_id: str) -> Optional[SelectionEntry]:
        return next((entry for entry in self.selections if entry.shot_id == shot_id), None)


@dataclass
class PlanSegment:
    plan_id: str
    shot_id: str
    filename_base: str
    prompt: str
    width: int
    height: int
    duration: float
    segment_index: int
    segment_total: int
    target_duration: float
    effective_duration: float
    segment_requested_duration: float
    start_frame: Optional[str]
    start_frame_source: str
    wan_motion: Optional[MotionSettings]
    ready: bool
    chain_id: str = ""
    selected_file: Optional[str] = None
    selected_variant: Optional[int] = None
    clip_name: Optional[str] = None
    needs_extension: bool = False
    status: str = "pending"
    output_files: List[str] = field(default_factory=list)
    last_frame: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert the dataclass into a plain dict that matches the legacy plan format."""
        payload = asdict(self)
        payload.setdefault("effective_duration", self.effective_duration)
        payload.setdefault("segment_requested_duration", self.segment_requested_duration)
        payload.setdefault("chain_id", self.chain_id or self.shot_id)
        payload.setdefault("start_frame_source", self.start_frame_source)
        payload.setdefault("ready", self.ready)
        payload.setdefault("status", self.status or "pending")
        payload.setdefault("output_files", self.output_files or [])
        return payload


@dataclass
class GenerationPlan:
    segments: List[PlanSegment]

    def for_shot(self, shot_id: str) -> List[PlanSegment]:
        return [segment for segment in self.segments if segment.shot_id == shot_id]

    def get(self, plan_id: str) -> Optional[PlanSegment]:
        return next((segment for segment in self.segments if segment.plan_id == plan_id), None)

    def to_dict_list(self) -> List[Dict[str, Any]]:
        """Return plan as list of dictionaries for UI/state persistence."""
        return [segment.to_dict() for segment in self.segments]


__all__ = [
    "MotionSettings",
    "Shot",
    "Storyboard",
    "SelectionEntry",
    "SelectionSet",
    "PlanSegment",
    "GenerationPlan",
]
