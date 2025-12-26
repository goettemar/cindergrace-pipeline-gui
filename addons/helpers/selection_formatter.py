"""Helpers to format keyframe selection summaries/previews."""

from typing import Dict, Any


def format_selection_summary(selections: Dict[str, Dict[str, Any]], storyboard: Dict[str, Any]) -> str:
    """Format a markdown summary of selected keyframes."""
    if not selections:
        total = len(storyboard.get("shots", [])) if storyboard else 0
        return f"No keyframes selected yet. ({total} shots total)"

    total = len(storyboard.get("shots", [])) if storyboard else 0
    selected = len(selections)
    lines = [f"**{selected}/{total} shots selected**"]
    for shot_id in sorted(selections.keys()):
        entry = selections[shot_id]
        lines.append(f"- `{shot_id}` → {entry['selected_file']}")
    return "\n".join(lines)


def build_preview_payload(storyboard: Dict[str, Any], selections: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Build preview payload data structure for selection export."""
    project = storyboard.get("project", "Unknown Project") if storyboard else "Unknown Project"
    shots = storyboard.get("shots", []) if storyboard else []
    all_shot_ids = {s.get("shot_id") for s in shots}
    selected_shot_ids = set(selections.keys()) if selections else set()
    missing_shot_ids = sorted(all_shot_ids - selected_shot_ids)

    payload = {
        "project": project,
        "total_shots": len(shots),
        "selected_shots": len(selected_shot_ids),
        "missing_shots": missing_shot_ids,
        "selections": [],
    }

    for shot_id in sorted(selections.keys()) if selections else []:
        entry = selections[shot_id]
        payload["selections"].append(
            {
                "shot_id": entry["shot_id"],
                "filename_base": entry["filename_base"],
                "selected_variant": entry["selected_variant"],
                "selected_file": entry["selected_file"],
                "source_path": entry["source_path"],
            }
        )

    return payload


__all__ = ["format_selection_summary", "build_preview_payload"]
