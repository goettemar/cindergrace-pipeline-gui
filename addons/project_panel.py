"""Project selection/creation addon."""
import json
import os
import sys
from typing import Dict, List, Optional

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

        with gr.Blocks() as interface:
            gr.Markdown("# 📁 Projektverwaltung")
            gr.Markdown(
                "Definiere hier dein aktives Projekt. Jeder Eintrag entspricht einem Ordner unter "
                "`<ComfyUI>/output/<projekt>` – inklusive `project.json`. "
                "Alle nachfolgenden Tabs schreiben/lesen ausschließlich in diesen Projektordner."
            )

            comfy_output_md = gr.Markdown(self._comfy_root_info())

            with gr.Group():
                gr.Markdown("## Aktives Projekt")
                project_overview = gr.Markdown(self._project_overview(project))
                project_json = gr.Code(
                    value=self._project_json(project),
                    language="json",
                    label="project.json",
                    lines=12
                )

            with gr.Group():
                gr.Markdown("## Globale Vorgaben")
                storyboard_dropdown = gr.Dropdown(
                    choices=self._storyboard_choices(),
                    value=self.config.get_current_storyboard(),
                    label="Storyboard wählen (gilt für alle Tabs)",
                    interactive=True
                )
                with gr.Row():
                    refresh_storyboard_btn = gr.Button("🔄 Storyboards neu laden", size="sm")
                    save_storyboard_btn = gr.Button("💾 Storyboard übernehmen", variant="secondary")

                resolution_dropdown = gr.Dropdown(
                    choices=self._resolution_choices(),
                    value=self.config.get_resolution_preset(),
                    label="Globale Auflösung (gilt für Keyframes & Video)",
                    info="Einheitliche Breite/Höhe für alle Shots",
                )
                save_resolution_btn = gr.Button("💾 Auflösung übernehmen", variant="secondary")
                globals_status = gr.Markdown(self._globals_status())

            with gr.Group():
                gr.Markdown("## Bestehendes Projekt laden")
                project_dropdown = gr.Dropdown(
                    choices=self._project_choices(),
                    value=project["slug"] if project else None,
                    label="Projekt auswählen"
                )
                with gr.Row():
                    refresh_btn = gr.Button("🔄 Liste aktualisieren", size="sm")
                    load_btn = gr.Button("📂 Projekt laden", variant="primary")

            with gr.Group():
                gr.Markdown("## Neues Projekt anlegen")
                new_name = gr.Textbox(label="Projektname", placeholder="z.B. CINDERGRACE Testprojekt")
                create_btn = gr.Button("➕ Projekt erstellen", variant="secondary")

            status_md = gr.Markdown("")

            # Wiring
            refresh_btn.click(
                fn=self._refresh_projects,
                outputs=[project_dropdown]
            )

            load_btn.click(
                fn=self._load_project,
                inputs=[project_dropdown],
                outputs=[status_md, project_overview, project_json, project_dropdown]
            )

            create_btn.click(
                fn=self._create_project,
                inputs=[new_name],
                outputs=[status_md, project_overview, project_json, project_dropdown, new_name]
            )

            refresh_storyboard_btn.click(
                fn=lambda: gr.update(choices=self._storyboard_choices(), value=self.config.get_current_storyboard()),
                outputs=[storyboard_dropdown]
            )

            save_storyboard_btn.click(
                fn=self._save_storyboard,
                inputs=[storyboard_dropdown],
                outputs=[globals_status]
            )

            save_resolution_btn.click(
                fn=self._save_resolution,
                inputs=[resolution_dropdown],
                outputs=[globals_status, resolution_dropdown]
            )

        return interface

    # -----------------------------
    # UI callbacks
    # -----------------------------
    def _refresh_projects(self) -> gr.Dropdown:
        project = self.project_manager.get_active_project(refresh=True)
        return gr.update(choices=self._project_choices(), value=project["slug"] if project else None)

    def _load_project(self, slug: Optional[str]):
        if not slug:
            project = self.project_manager.get_active_project(refresh=True)
            return (
                "**❌ Fehler:** Bitte ein Projekt auswählen.",
                self._project_overview(project),
                self._project_json(project),
                gr.update(value=project["slug"] if project else None)
            )

        project = self.project_manager.set_active_project(slug)
        if not project:
            return (
                f"**❌ Fehler:** Projekt `{slug}` wurde nicht gefunden.",
                self._project_overview(None),
                "{}",
                gr.update(choices=self._project_choices(), value=None)
            )

        return (
            f"**✅ Aktiv:** {project['name']} (`{project['slug']}`) geladen.",
            self._project_overview(project),
            self._project_json(project),
            gr.update(value=project["slug"])
        )

    @handle_errors("Konnte Projekt nicht erstellen")
    def _create_project(self, name: str):
        logger.info(f"Creating new project: {name}")

        # Validate input with Pydantic
        validated = ProjectCreateInput(name=name)
        validated_name = validated.name

        project = self.project_manager.create_project(validated_name)
        logger.info(f"✓ Project created: {project['name']} ({project['slug']})")

        return (
            f"**✅ Erstellt:** {project['name']} (`{project['slug']}`)",
            self._project_overview(project),
            self._project_json(project),
            gr.update(choices=self._project_choices(), value=project["slug"]),
            ""
        )

    # -----------------------------
    # Helper formatting
    # -----------------------------
    def _project_choices(self) -> List[str]:
        return [entry["slug"] for entry in self.project_manager.list_projects()]

    def _storyboard_choices(self) -> List[str]:
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
                choices.append(full)
                seen.add(full)
        return choices

    def _resolution_choices(self) -> List[str]:
        return [
            "1080p_landscape",
            "1080p_portrait",
            "720p_landscape",
            "720p_portrait",
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


__all__ = ["ProjectAddon"]
