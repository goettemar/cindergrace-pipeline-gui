import json
import os

from services.model_manager.report_exporter import ReportExporter


def test_report_exporter_creates_files(tmp_path):
    exporter = ReportExporter({"root": "/models"})
    data = [{"filename": "a", "size": 1}, {"filename": "b", "size": 2}]

    csv_path = exporter.export_to_csv(data, tmp_path / "models.csv")
    assert os.path.exists(csv_path)

    json_path = exporter.export_to_json({"models": data}, tmp_path / "models.json")
    with open(json_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    assert "generated_at" in payload

    html_path = exporter.export_to_html(data, tmp_path / "models.html")
    assert os.path.exists(html_path)

    summary_path = exporter.export_summary({"total": 2}, tmp_path / "summary.json")
    assert os.path.exists(summary_path)
