#!/usr/bin/env python3
"""Lightweight smoke checks for CINDERGRACE GUI setup."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from infrastructure.config_manager import ConfigManager  # type: ignore  # noqa: E402
from infrastructure.project_store import ProjectStore  # type: ignore  # noqa: E402
from infrastructure.workflow_registry import WorkflowRegistry  # type: ignore  # noqa: E402
from infrastructure.comfy_api import ComfyUIAPI  # type: ignore  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run basic CINDERGRACE GUI smoke checks.")
    parser.add_argument(
        "--ping",
        action="store_true",
        help="Test Verbindung zu ComfyUI (nutzt comfy_url aus settings.json).",
    )
    args = parser.parse_args()

    # Ensure relative paths resolve from repo root
    config = ConfigManager()
    project_store = ProjectStore(config)
    workflow_registry = WorkflowRegistry()

    issues = []
    notes = []

    settings_path = Path(config.config_path).resolve()
    if not settings_path.exists():
        issues.append(f"settings.json fehlt unter {settings_path}")
    else:
        notes.append(f"✓ settings.json gefunden ({settings_path})")

    comfy_root = Path(config.get_comfy_root()).expanduser()
    if not comfy_root.exists():
        issues.append(f"ComfyUI-Root aus settings.json existiert nicht: {comfy_root}")
    else:
        notes.append(f"✓ ComfyUI-Root erreichbar: {comfy_root}")
    notes.append(f"✓ Globale Auflösung: {config.get_resolution_preset()} -> {config.get_resolution_tuple()[0]}x{config.get_resolution_tuple()[1]}")
    sb = config.get_current_storyboard()
    notes.append(f"✓ Storyboard (Projekt-Tab): {sb or 'nicht gesetzt'}")

    workflow_dir = ROOT / workflow_registry.workflow_dir
    workflow_files = workflow_registry.get_files()
    if not workflow_dir.exists():
        issues.append(f"Workflow-Verzeichnis fehlt: {workflow_dir}")
    elif not workflow_files:
        issues.append(f"Keine Workflow-Templates gefunden in {workflow_dir}")
    else:
        notes.append(f"✓ {len(workflow_files)} Workflow-Template(s) gefunden in {workflow_dir}")

    project = project_store.get_active_project(refresh=True)
    if project:
        notes.append(f"✓ Aktives Projekt: {project.get('name')} ({project.get('slug')}) → {project.get('path')}")
    else:
        issues.append("Kein aktives Projekt gesetzt (Tab 📁 Projekt ausführen).")

    if args.ping:
        api = ComfyUIAPI(config.get_comfy_url())
        result = api.test_connection()
        if result.get("connected"):
            notes.append("✓ ComfyUI erreichbar (Ping erfolgreich).")
        else:
            issues.append(f"ComfyUI nicht erreichbar: {result.get('error')}")

    print("CINDERGRACE Smoke Checks\n-------------------------")
    for line in notes:
        print(line)
    if issues:
        print("\n⚠️  Offene Punkte:")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print("\n✅ Alle Basis-Prüfungen erfolgreich.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
