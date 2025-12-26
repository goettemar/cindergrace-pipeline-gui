"""Helpers to format video generation plans."""

from typing import List, Dict, Any, Optional, Tuple


def format_plan_summary(plan: List[Dict[str, Any]]) -> str:
    """Build a markdown summary for a video generation plan."""
    total = len(plan)
    ready = len([entry for entry in plan if entry.get("ready")])
    completed = len([entry for entry in plan if entry.get("status") == "completed"])
    missing_list = sorted({entry["shot_id"] for entry in plan if entry.get("start_frame_source") == "missing"})
    total_duration = sum(entry.get("duration", 0) for entry in plan)
    md = [
        "### Plan Overview",
        f"- **Shots:** {total}",
        f"- **Ready:** {ready}",
        f"- **Completed:** {completed}",
        f"- **Total Duration:** ~{total_duration:.1f}s",
    ]
    if missing_list:
        md.append(f"- ❗ **Missing Start Frames:** {', '.join(missing_list)}")
    return "\n".join(md)


def format_plan_shot(plan: List[Dict[str, Any]], plan_entry_id: str) -> Tuple[str, Optional[str]]:
    """Format a single plan entry for UI preview."""
    entry = next((item for item in plan if (item.get("plan_id") or item.get("shot_id")) == plan_entry_id), None)
    if not entry:
        return "Shot not found.", None
    lines = [
        f"### Shot {entry['shot_id']} – {entry['filename_base']}",
        f"- **Prompt:** {entry['prompt'][:160]}{'…' if len(entry['prompt']) > 160 else ''}",
        f"- **Resolution:** {entry['width']}×{entry['height']}",
        f"- **Duration:** {entry['duration']}s",
        f"- **Variant:** {entry.get('selected_file', 'n/a')}",
        f"- **Status:** {entry.get('status', 'pending')}",
    ]
    motion = entry.get("wan_motion")
    if motion:
        lines.append(f"- **Wan Motion:** {motion.get('type', 'n/a')} (Strength {motion.get('strength', '-')})")
        motion_desc = motion.get("notes") or motion.get("type")
        if motion_desc and motion_desc != motion.get("type"):
            lines.append(f"  - {motion_desc}")
    if not entry.get("ready"):
        lines.append("- ❌ No valid start frame found.")
    preview_path = entry.get("start_frame") if entry.get("ready") else None
    return "\n".join(lines), preview_path


__all__ = ["format_plan_summary", "format_plan_shot"]
