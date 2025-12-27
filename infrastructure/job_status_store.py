"""Job status persistence for long-running tasks."""
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class JobStatus:
    """Representation of a persisted job status."""
    job_type: str
    status: str
    message: str
    progress: Optional[float]
    updated_at: str
    metadata: Dict[str, Any]


class JobStatusStore:
    """Persist and load job status snapshots."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = Path(base_dir) if base_dir else Path.home() / ".cindergrace" / "jobs"

    def get_status(self, project_path: Optional[str], job_type: str) -> Optional[JobStatus]:
        """Load the latest job status for a project/job_type."""
        path = self._get_job_path(project_path, job_type)
        if not path.exists():
            return None

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

        return JobStatus(
            job_type=payload.get("job_type", job_type),
            status=payload.get("status", "unknown"),
            message=payload.get("message", ""),
            progress=payload.get("progress"),
            updated_at=payload.get("updated_at", ""),
            metadata=payload.get("metadata", {}) or {},
        )

    def set_status(
        self,
        project_path: Optional[str],
        job_type: str,
        status: str,
        message: str = "",
        progress: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Persist a job status snapshot."""
        path = self._get_job_path(project_path, job_type)
        path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "job_type": job_type,
            "status": status,
            "message": message,
            "progress": progress,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _get_job_path(self, project_path: Optional[str], job_type: str) -> Path:
        """Resolve job status file path."""
        if project_path:
            return Path(project_path) / "jobs" / f"{job_type}.json"
        return self.base_dir / f"{job_type}.json"
