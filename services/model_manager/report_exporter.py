"""Report Exporter - Export analysis results to CSV/JSON/HTML."""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from infrastructure.logger import get_logger

logger = get_logger(__name__)


class ReportExporter:
    """Exports model analysis results into multiple formats."""

    def __init__(self, analysis_params: Optional[Dict[str, Any]] = None):
        self.analysis_params = analysis_params or {}
        self.logger = logger

    @staticmethod
    def _timestamp() -> str:
        return datetime.utcnow().isoformat() + "Z"

    def _ensure_parent(self, filepath: str) -> Path:
        path = Path(filepath)
        if path.parent:
            path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def export_to_csv(self, data: List[Dict[str, Any]], filepath: str) -> str:
        """Export a list of models to CSV."""
        if not data:
            raise ValueError("No data to export")

        path = self._ensure_parent(filepath)
        fieldnames = sorted({k for row in data for k in row.keys()})

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in data:
                writer.writerow(row)

        self.logger.info(f"CSV export created at {path}")
        return str(path)

    def export_to_json(self, data: Any, filepath: str) -> str:
        """Export full analysis data to JSON."""
        payload = {
            "generated_at": self._timestamp(),
            "analysis_params": self.analysis_params,
            "data": data,
        }
        path = self._ensure_parent(filepath)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        self.logger.info(f"JSON export created at {path}")
        return str(path)

    def export_to_html(self, data: List[Dict[str, Any]], filepath: str, title: str = "Model Report") -> str:
        """Export model list to standalone HTML with inline styling."""
        timestamp = self._timestamp()
        path = self._ensure_parent(filepath)

        rows_html = "".join(
            "<tr>" + "".join(f"<td>{row.get(col, '')}</td>" for col in sorted(row.keys())) + "</tr>"
            for row in data
        )
        headers_html = "".join(f"<th>{col}</th>" for col in sorted(data[0].keys())) if data else ""

        html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>{title}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #0f172a; }}
    h1 {{ margin-bottom: 8px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
    th, td {{ border: 1px solid #e2e8f0; padding: 8px; text-align: left; }}
    th {{ background: #f1f5f9; }}
    .meta {{ font-size: 0.9em; color: #475569; }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <div class="meta">Generated at: {timestamp}</div>
  <div class="meta">Parameters: {json.dumps(self.analysis_params)}</div>
  <table>
    <thead><tr>{headers_html}</tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
</body>
</html>
"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)

        self.logger.info(f"HTML export created at {path}")
        return str(path)

    def export_summary(self, stats: Dict[str, Any], filepath: str) -> str:
        """Export summary statistics (JSON)."""
        summary = {
            "generated_at": self._timestamp(),
            "analysis_params": self.analysis_params,
            "summary": stats,
        }
        path = self._ensure_parent(filepath)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        self.logger.info(f"Summary export created at {path}")
        return str(path)
