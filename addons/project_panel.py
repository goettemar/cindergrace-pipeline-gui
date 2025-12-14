"""Project selection/creation addon."""
import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import gradio as gr

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from addons.base_addon import BaseAddon
from infrastructure.config_manager import ConfigManager
from infrastructure.project_store import ProjectStore
from infrastructure.error_handler import handle_errors
from infrastructure.logger import get_logger
from domain.exceptions import ProjectError, ProjectNotFoundError
from domain.validators import ProjectCreateInput

logger = get_logger(__name__)


class ProjectAddon(BaseAddon):
    """Tab to create/select active pipeline projects."""

    def __init__(self):
        super().__init__(
            name="Project Manager",
            description="Manage CINDERGRACE project folders under ComfyUI/output"
        )
        self.config = ConfigManager()
        self.project_manager = ProjectStore(self.config)

    def get_tab_name(self) -> str:
        return "📁 Projekt"

    def render(self) -> gr.Blocks:
        project = self.project_manager.get_active_project(refresh=True)
        valid_path = self._is_comfy_path_valid()
        output_base = self._derive_output_base()

        with gr.Blocks() as interface:
            gr.Markdown("# 📁 Projektverwaltung")
            gr.Markdown(
                "Definiere hier dein aktives Projekt. Jeder Eintrag entspricht einem Ordner unter "
                "`<ComfyUI>/output/<projekt>` – inklusive `project.json`. "
                "Alle nachfolgenden Tabs schreiben/lesen ausschließlich in diesen Projektordner."
            )

            warning_box = gr.Markdown("", visible=False)

            gr.HTML(
                """
                <style>
                  .compact-button button { min-height: 38px; padding: 6px 10px; }
                  .icon-button button { min-width: 38px; max-width: 42px; min-height: 38px; padding: 6px; }
                  .inline-row { gap: 6px; }
                  .primary-full button { width: 100%; }
                  .status-panel textarea {
                    min-height: 180px;
                    max-height: 220px;
                    overflow-y: auto;
                    font-family: monospace;
                  }
                </style>
                """
            )

            status_bar = gr.Markdown(self._status_bar(project))
            gr.Markdown(self._comfy_root_info())

            with gr.Row():
                with gr.Column():
                    with gr.Group():
                        gr.Markdown("### Projekt")
                        project_overview = gr.Markdown(self._project_overview(project))
                        with gr.Accordion("Details anzeigen", open=False):
                            project_json = gr.Code(
                                value=self._project_json(project),
                                language="json",
                                label="project.json",
                                lines=12
                            )

                        gr.Markdown("**Projekt wechseln**")
                        with gr.Row(elem_classes=["inline-row"]):
                            project_dropdown = gr.Dropdown(
                                choices=self._project_choices(),
                                value=project["slug"] if project else None,
                                label="Projekt auswählen",
                                scale=8,
                                interactive=valid_path,
                            )
                            refresh_btn = gr.Button(
                                "↻",
                                variant="secondary",
                                elem_classes=["icon-button"],
                                interactive=valid_path,
                                scale=1,
                                min_width=42,
                            )
                        with gr.Row():
                            load_btn = gr.Button("📂 Projekt laden", variant="primary", elem_classes=["primary-full"], interactive=valid_path)

                        gr.Markdown("**Neues Projekt anlegen**")
                        new_name = gr.Textbox(label="Projektname", placeholder="z.B. CINDERGRACE Testprojekt", interactive=valid_path)
                        create_btn = gr.Button("➕ Projekt erstellen", variant="primary", elem_classes=["primary-full"], interactive=valid_path)

                with gr.Column():
                    with gr.Group():
                        gr.Markdown("### Projekt-Defaults")
                        gr.Textbox(label="ComfyUI Pfad", value=self.config.get_comfy_root(), interactive=False)
                        gr.Textbox(label="Output Base", value=output_base, interactive=False, info="/output befindet sich innerhalb des ComfyUI Installationspfads.")
                        with gr.Row(elem_classes=["inline-row"]):
                            storyboard_dropdown = gr.Dropdown(
                                choices=self._storyboard_choices(),
                                value=self.config.get_current_storyboard(),
                                label="Storyboard wählen (gilt für alle Tabs)",
                                scale=8,
                                interactive=valid_path
                            )
                            refresh_storyboard_btn = gr.Button(
                                "↻",
                                variant="secondary",
                                elem_classes=["icon-button"],
                                interactive=valid_path,
                                scale=1,
                                min_width=42,
                            )

                        resolution_dropdown = gr.Dropdown(
                            choices=self._resolution_choices(),
                            value=self.config.get_resolution_preset(),
                            label="Globale Auflösung (gilt für Keyframes & Video)",
                            info="Einheitliche Breite/Höhe für alle Shots",
                            interactive=valid_path,
                        )
                        defaults_btn = gr.Button("✅ Defaults anwenden", variant="primary", elem_classes=["primary-full"], interactive=valid_path)
                        globals_status = gr.Markdown(self._globals_status())

            status_log = gr.Textbox(
                label="Status / Aktionen",
                lines=10,
                max_lines=10,
                interactive=False,
                value=self._init_status(),
                elem_classes=["status-panel"]
            )

            lock_check_btn = gr.Button("Pfad prüfen", variant="secondary")

            # Wiring
            refresh_btn.click(
                fn=self._refresh_projects,
                inputs=[status_log],
                outputs=[project_dropdown, status_log]
            )

            load_btn.click(
                fn=self._load_project,
                inputs=[project_dropdown, status_log],
                outputs=[project_overview, project_json, project_dropdown, status_bar, status_log]
            )

            create_btn.click(
                fn=self._create_project,
                inputs=[new_name, status_log],
                outputs=[project_overview, project_json, project_dropdown, new_name, status_bar, status_log]
            )

            refresh_storyboard_btn.click(
                fn=self._refresh_storyboards,
                inputs=[status_log],
                outputs=[storyboard_dropdown, status_log]
            )

            defaults_btn.click(
                fn=self._apply_defaults,
                inputs=[storyboard_dropdown, resolution_dropdown, status_log],
                outputs=[globals_status, resolution_dropdown, status_bar, status_log]
            )

            lock_check_btn.click(
                fn=self._reevaluate_lock_state,
                inputs=[status_log],
                outputs=[
                    warning_box,
                    project_dropdown,
                    refresh_btn,
                    load_btn,
                    new_name,
                    create_btn,
                    storyboard_dropdown,
                    refresh_storyboard_btn,
                    resolution_dropdown,
                    defaults_btn,
                    status_bar,
                    status_log,
                ],
            )

            if not valid_path:
                warning_box.update(value="**⚠️ ComfyUI Installationspfad fehlt/ist ungültig. Bitte zuerst im Settings-Tab setzen.**", visible=True)

        return interface

    # -----------------------------
    # UI callbacks
    # -----------------------------
    def _refresh_projects(self, current_status: str):
        project = self.project_manager.get_active_project(refresh=True)
        status = self._append_status(
            current_status,
            f"Projektliste aktualisiert ({len(self._project_choices())} Einträge)"
        )
        return gr.update(choices=self._project_choices(), value=project["slug"] if project else None), status

    def _load_project(self, slug: Optional[str], current_status: str):
        if not slug:
            project = self.project_manager.get_active_project(refresh=True)
            return (
                self._project_overview(project),
                self._project_json(project),
                gr.update(value=project["slug"] if project else None),
                self._status_bar(project),
                self._append_status(current_status, "❌ Bitte ein Projekt auswählen."),
            )

        project = self.project_manager.set_active_project(slug)
        if not project:
            return (
                self._project_overview(None),
                "{}",
                gr.update(choices=self._project_choices(), value=None),
                self._status_bar(None),
                self._append_status(current_status, f"❌ Projekt `{slug}` wurde nicht gefunden."),
            )

        return (
            self._project_overview(project),
            self._project_json(project),
            gr.update(value=project["slug"]),
            self._status_bar(project),
            self._append_status(current_status, f"✅ Projekt geladen: {project['name']} ({project['slug']})"),
        )

    @handle_errors("Konnte Projekt nicht erstellen")
    def _create_project(self, name: str, current_status: str):
        logger.info(f"Creating new project: {name}")

        # Validate input with Pydantic
        validated = ProjectCreateInput(name=name)
        validated_name = validated.name

        project = self.project_manager.create_project(validated_name)
        logger.info(f"✓ Project created: {project['name']} ({project['slug']})")

        return (
            self._project_overview(project),
            self._project_json(project),
            gr.update(choices=self._project_choices(), value=project["slug"]),
            "",
            self._status_bar(project),
            self._append_status(current_status, f"✅ Projekt erstellt: {project['name']} ({project['slug']})"),
        )

    # -----------------------------
    # Helper formatting
    # -----------------------------
    def _project_choices(self) -> List[str]:
        return [entry["slug"] for entry in self.project_manager.list_projects()]

    def _storyboard_choices(self) -> List[str]:
        output_base = self._derive_output_base()
        dirs: List[str] = []
        if self.config.config_dir and os.path.isdir(self.config.config_dir):
            dirs.append(self.config.config_dir)
        project = self.project_manager.get_active_project(refresh=True)
        if project:
            for candidate in (project.get("path"), os.path.join(project.get("path"), "storyboards")):
                if candidate and os.path.isdir(candidate):
                    dirs.append(candidate)
        choices: List[str] = []
        seen = set()
        for directory in dirs:
            for filename in sorted(os.listdir(directory)):
                if not filename.endswith(".json"):
                    continue
                if "storyboard" not in filename.lower():
                    continue
                full = os.path.join(directory, filename)
                if full in seen:
                    continue
                label = self._short_display_path(full, output_base)
                choices.append((label, full))
                seen.add(full)
        return choices

    def _resolution_choices(self) -> List[str]:
        return [
            "1080p_landscape",
            "1080p_portrait",
            "720p_landscape",
            "720p_portrait",
            "540p_landscape",
            "540p_portrait",
        ]

    def _project_overview(self, project: Optional[Dict[str, str]]) -> str:
        if not project:
            return "**Kein aktives Projekt ausgewählt.**"
        lines = [
            f"**Projekt:** {project.get('name')} (`{project.get('slug')}`)",
            f"- Pfad: `{project.get('path')}`",
            f"- Erstellt: {project.get('created_at', '-')}",
            f"- Zuletzt geöffnet: {project.get('last_opened', '-')}",
        ]
        return "\n".join(lines)

    def _project_json(self, project: Optional[Dict[str, str]]) -> str:
        if not project:
            return "{}"
        data = {k: v for k, v in project.items() if k not in {"path"}}
        return json.dumps(data, indent=2)

    def _comfy_root_info(self) -> str:
        self.config.refresh()
        comfy_root = self.config.get_comfy_root()
        output_path = os.path.join(comfy_root, "output")
        return (
            f"**ComfyUI Output Basis:** `{output_path}`  \n"
            "Alle Projektordner werden hier erstellt. Passe den Pfad im ⚙️ Settings-Tab an, falls nötig."
        )

    def _globals_status(self) -> str:
        self.config.refresh()
        storyboard = self.config.get_current_storyboard() or "Kein Storyboard gesetzt."
        res_key = self.config.get_resolution_preset()
        res_map = {
            "1080p_landscape": "1920x1080 (16:9 Quer)",
            "1080p_portrait": "1080x1920 (9:16 Hoch)",
            "720p_landscape": "1280x720 (16:9 Quer)",
            "720p_portrait": "720x1280 (9:16 Hoch)",
            "540p_landscape": "960x540 (16:9 Quer)",
            "540p_portrait": "540x960 (9:16 Hoch)",
        }
        res_label = res_map.get(res_key, res_key)
        return f"**Storyboard:** `{storyboard}`  \n**Auflösung:** {res_label}"

    def _save_storyboard(self, storyboard: Optional[str]):
        if not storyboard or storyboard.startswith("No storyboards"):
            return "**❌ Fehler:** Bitte ein Storyboard auswählen."
        self.config.set("current_storyboard", storyboard)
        return self._globals_status()

    def _save_resolution(self, resolution_key: str):
        if resolution_key not in self._resolution_choices():
            return "**❌ Fehler:** Ungültige Auflösung.", gr.update(value=self.config.get_resolution_preset())
        self.config.set("global_resolution", resolution_key)
        return self._globals_status(), gr.update(value=resolution_key)

    # -----------------------------
    # New UI helpers
    # -----------------------------
    def _status_bar(self, project: Optional[Dict[str, str]]) -> str:
        """Compact status line for current context."""
        self.config.refresh()
        parts: List[str] = []

        # Projekt
        if project:
            path = project.get("path") or ""
            badge = "✅" if path and os.path.isdir(path) else "⚠️"
            parts.append(f"Aktives Projekt: {badge} {project.get('name')} (`{project.get('slug')}`)")
        else:
            parts.append("Aktives Projekt: ⚠️ keines gewählt")

        # Storyboard - validate path and try to resolve if invalid
        storyboard = self.config.get_current_storyboard()
        if storyboard:
            resolved_path = self._resolve_storyboard_path(storyboard)
            if resolved_path and os.path.exists(resolved_path):
                sb_badge = "✅"
                parts.append(f"Storyboard: {sb_badge} `{os.path.basename(resolved_path)}`")
            else:
                sb_badge = "❌"
                parts.append(f"Storyboard: {sb_badge} `{os.path.basename(storyboard)}` **NICHT GEFUNDEN**")
        else:
            parts.append("Storyboard: ⚠️ keines gesetzt")

        # Auflösung
        res_key = self.config.get_resolution_preset()
        res_label = {
            "1080p_landscape": "1920x1080",
            "1080p_portrait": "1080x1920",
            "720p_landscape": "1280x720",
            "720p_portrait": "720x1280",
            "540p_landscape": "960x540",
            "540p_portrait": "540x960",
        }.get(res_key, res_key)
        parts.append(f"Auflösung: {res_label}")

        return " | ".join(parts)

    def _apply_defaults(self, storyboard: Optional[str], resolution_key: str, current_status: str):
        """Apply storyboard + resolution with one CTA."""
        messages: List[str] = []

        sb_status = self._save_storyboard(storyboard)
        sb_error = isinstance(sb_status, str) and sb_status.startswith("**❌")
        if sb_error:
            messages.append("Storyboard ungültig oder fehlt.")
        else:
            messages.append(f"Storyboard gesetzt: {os.path.basename(storyboard) if storyboard else 'keines ausgewählt'}")

        res_status, res_dropdown = self._save_resolution(resolution_key)
        res_error = isinstance(res_status, str) and res_status.startswith("**❌")
        if res_error:
            messages.append("Auflösung ungültig.")
        else:
            messages.append(f"Auflösung gesetzt: {resolution_key}")

        project = self.project_manager.get_active_project(refresh=True)

        globals_md = self._globals_status() if not sb_error and not res_error else (sb_status if sb_error else res_status)
        status_text = "\n".join(msg for msg in messages if msg)
        return (
            globals_md,
            res_dropdown,
            self._status_bar(project),
            self._append_status(current_status, status_text),
        )

    def _refresh_storyboards(self, current_status: str):
        choices = self._storyboard_choices()
        updated = gr.update(choices=choices, value=self.config.get_current_storyboard())
        msg = f"Storyboards neu geladen: {len(choices)} gefunden"
        return updated, self._append_status(current_status, msg)

    def _append_status(self, current: str, message: str) -> str:
        timestamp = datetime.now().strftime("%H:%M:%S")
        lines = [line for line in (current or "").splitlines() if line.strip()]
        lines.append(f"[{timestamp}] {message}")
        if len(lines) > 100:
            lines = lines[-100:]
        return "\n".join(lines)

    def _init_status(self) -> str:
        return "[--:--:--] Bereit."

    def _derive_output_base(self) -> str:
        comfy_root = self.config.get_comfy_root()
        if not comfy_root:
            return ""
        return os.path.join(comfy_root, "output")

    def _short_display_path(self, abs_path: str, output_base: str) -> str:
        if not abs_path:
            return abs_path
        marker = "/output/"
        if marker in abs_path:
            return abs_path.split(marker, 1)[-1]
        if output_base and abs_path.startswith(output_base):
            return abs_path[len(output_base):].lstrip(os.sep)
        return os.path.basename(abs_path)

    def _is_comfy_path_valid(self) -> bool:
        path = self.config.get_comfy_root()
        return bool(path) and os.path.exists(path)

    def _resolve_storyboard_path(self, storyboard_path: str) -> Optional[str]:
        """Try to resolve storyboard path, checking multiple locations."""
        if not storyboard_path:
            return None

        # If absolute path exists, use it
        if os.path.isabs(storyboard_path) and os.path.exists(storyboard_path):
            return storyboard_path

        # Extract filename for relative resolution
        filename = os.path.basename(storyboard_path)

        # Try config dir
        if self.config.config_dir:
            candidate = os.path.join(self.config.config_dir, filename)
            if os.path.exists(candidate):
                return candidate

        # Try active project path
        project = self.project_manager.get_active_project(refresh=False)
        if project and project.get("path"):
            project_path = project["path"]
            for subdir in ("", "storyboards"):
                candidate = os.path.join(project_path, subdir, filename) if subdir else os.path.join(project_path, filename)
                if os.path.exists(candidate):
                    return candidate

        # If absolute path was given but doesn't exist, return None
        if os.path.isabs(storyboard_path):
            return None

        return None

    def _reevaluate_lock_state(self, current_status: str):
        valid = self._is_comfy_path_valid()
        warning_text = ""
        if not valid:
            warning_text = "**⚠️ ComfyUI Installationspfad fehlt/ist ungültig. Bitte zuerst im Settings-Tab setzen.**"
        warning = gr.update(value=warning_text, visible=not valid)
        inter = gr.update(interactive=valid)
        status = self._append_status(current_status, "Pfad geprüft: gültig" if valid else "Pfad ungültig – bitte Settings prüfen.")
        project = self.project_manager.get_active_project(refresh=True)

        return (
            warning,
            inter,
            inter,
            inter,
            inter,
            inter,
            inter,
            inter,
            inter,
            inter,
            self._status_bar(project),
            status,
        )


__all__ = ["ProjectAddon"]
