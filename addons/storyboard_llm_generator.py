"""Storyboard LLM Generator Addon - Generate storyboards from natural language via OpenRouter."""
import json
import os
from pathlib import Path
from typing import Optional, Tuple

import gradio as gr

from addons.base_addon import BaseAddon
from addons.components import format_project_status_from_dict
from addons.components.storyboard_draft_editor import (
    create_draft_editor,
    validate_draft_json,
    format_storyboard_json,
    json_to_shot_table,
)
from domain.exceptions import OpenRouterAPIError, OpenRouterAuthError
from infrastructure.config_manager import ConfigManager
from infrastructure.logger import get_logger
from infrastructure.project_store import ProjectStore
from services.storyboard_llm_service import StoryboardLLMService

logger = get_logger(__name__)


class StoryboardLLMGeneratorAddon(BaseAddon):
    """Generate storyboards from natural language using OpenRouter LLMs."""

    def __init__(self):
        super().__init__(
            name="Storyboard LLM Generator",
            description="Generate storyboards from natural language descriptions",
            category="tools"
        )
        self.config = ConfigManager()
        self.project_store = ProjectStore(self.config)
        self.llm_service = StoryboardLLMService(self.config)

    def get_tab_name(self) -> str:
        return "🤖 AI Storyboard"

    def _get_model_choices(self):
        """Get available models for dropdown."""
        models = self.config.get_openrouter_models()
        if not models:
            return ["No models configured - check Settings"]
        return models

    def _check_api_key(self) -> Tuple[bool, str]:
        """Check if OpenRouter API key is configured."""
        # Refresh config to get latest value
        self.config = ConfigManager()
        key = self.config.get_openrouter_api_key()
        if key:
            return True, ""
        return False, "⚠️ **OpenRouter API Key nicht konfiguriert** - Bitte in Settings hinterlegen"

    def _get_api_warning(self) -> str:
        """Get API warning message (for dynamic updates)."""
        return self._check_api_key()[1]

    def _on_tab_load(self) -> Tuple[str, str]:
        """Called when tab loads - refresh project header and API warning."""
        # Refresh stores to get current state
        self.config = ConfigManager()
        self.project_store = ProjectStore(self.config)
        return self._get_project_header(), self._get_api_warning()

    def _get_project_header(self) -> str:
        """Get project header HTML."""
        project = self.project_store.get_active_project(refresh=True)
        return format_project_status_from_dict(
            project=project,
            tab_name="🤖 AI Storyboard Generator",
        )

    def render(self) -> gr.Blocks:
        with gr.Blocks() as interface:
            # Header with current project
            project_header = gr.HTML(self._get_project_header())

            # API key warning (will be updated on tab select)
            api_warning = gr.Markdown(
                value=self._check_api_key()[1],
                visible=True,
            )

            # Update header and warning when tab is selected
            interface.load(
                fn=self._on_tab_load,
                outputs=[project_header, api_warning],
            )

            # Main content
            with gr.Row(equal_height=False):
                # Left column: Input
                with gr.Column(scale=1):
                    gr.Markdown("### 💡 Idee eingeben")

                    idea_input = gr.TextArea(
                        label="Beschreibe deine Video-Idee",
                        placeholder="""Beschreibe deine Video-Idee in natürlicher Sprache.

Beispiel:
"Ein kurzer Werbespot für ein Café.
Szene 1: Außenansicht des Cafés bei Sonnenaufgang
Szene 2: Barista bereitet einen Cappuccino zu
Szene 3: Zufriedener Kunde genießt seinen Kaffee am Fenster"

Je detaillierter, desto besser das Ergebnis!""",
                        lines=10,
                    )

                    with gr.Row():
                        model_dropdown = gr.Dropdown(
                            choices=self._get_model_choices(),
                            value=self._get_model_choices()[0] if self._get_model_choices() else None,
                            label="LLM Modell",
                            scale=2,
                        )
                        refresh_models_btn = gr.Button("🔄", scale=0, size="sm")

                    with gr.Row():
                        generate_btn = gr.Button(
                            "✨ Storyboard generieren",
                            variant="primary",
                            size="lg",
                        )
                        clear_btn = gr.Button(
                            "🗑️ Leeren",
                            variant="secondary",
                            size="lg",
                        )

                    generation_status = gr.Markdown(value="")

                # Right column: Draft editor
                with gr.Column(scale=1):
                    gr.Markdown("### 📝 Draft-Vorschau")

                    # Use shared draft editor component
                    draft_components = create_draft_editor(
                        initial_json="{}",
                        show_import_btn=True,
                        import_btn_label="📥 In Projekt importieren",
                        json_lines=25,
                        interactive=True,
                    )

                    import_status = gr.Markdown(value="")

            # Event handlers
            generate_btn.click(
                fn=self.generate_storyboard,
                inputs=[idea_input, model_dropdown],
                outputs=[
                    draft_components.json_editor,
                    draft_components.shot_table,
                    draft_components.validation_status,
                    generation_status,
                ],
            )

            clear_btn.click(
                fn=self.clear_all,
                outputs=[
                    idea_input,
                    draft_components.json_editor,
                    draft_components.shot_table,
                    draft_components.validation_status,
                    generation_status,
                ],
            )

            refresh_models_btn.click(
                fn=self.refresh_models,
                outputs=[model_dropdown],
            )

            # Validate on JSON change
            draft_components.json_editor.change(
                fn=validate_draft_json,
                inputs=[draft_components.json_editor],
                outputs=[draft_components.validation_status, draft_components.shot_table],
            )

            # Import button
            draft_components.import_btn.click(
                fn=self.import_to_project,
                inputs=[draft_components.json_editor],
                outputs=[import_status],
            )

        return interface

    def generate_storyboard(
        self,
        idea: str,
        model: str,
    ) -> Tuple[str, list, str, str]:
        """Generate storyboard from idea.

        Returns:
            Tuple of (json_str, shot_table, validation_status, generation_status)
        """
        # Check API key (refresh config first)
        has_key, warning = self._check_api_key()
        if not has_key:
            return "{}", [], "", "❌ OpenRouter API Key nicht konfiguriert"

        # Validate inputs
        if not idea or not idea.strip():
            return "{}", [], "", "❌ Bitte eine Idee eingeben"

        if not model or model.startswith("No models"):
            return "{}", [], "", "❌ Kein Modell ausgewählt - bitte in Settings konfigurieren"

        try:
            logger.info(f"Generating storyboard with {model}")

            # Create fresh service with current config
            llm_service = StoryboardLLMService(self.config)

            # Generate via LLM
            storyboard_dict, errors, warnings = llm_service.generate_draft(
                idea=idea.strip(),
                model=model,
            )

            # Format JSON
            json_str = json.dumps(storyboard_dict, indent=2, ensure_ascii=False)

            # Create shot table
            shot_table = json_to_shot_table(json_str)

            # Build status messages
            if errors:
                validation_status = "**⚠️ Validierungsfehler:**\n" + "\n".join(f"- {e}" for e in errors)
                generation_status = f"⚠️ Storyboard generiert, aber mit {len(errors)} Validierungsfehler(n)"
            else:
                shot_count = len(storyboard_dict.get("shots", []))
                total_duration = sum(s.get("duration", 3.0) for s in storyboard_dict.get("shots", []))

                validation_status = f"✅ **Valide** - {shot_count} Shots, {total_duration:.1f}s Gesamtdauer"
                if warnings:
                    validation_status += "\n\n**Hinweise:**\n" + "\n".join(f"- {w}" for w in warnings[:5])

                generation_status = f"✅ Storyboard mit {shot_count} Shots erfolgreich generiert!"

            return json_str, shot_table, validation_status, generation_status

        except OpenRouterAuthError as e:
            logger.error(f"OpenRouter auth error: {e}")
            return "{}", [], "", "❌ **API Key ungültig** - Bitte in Settings prüfen"

        except OpenRouterAPIError as e:
            logger.error(f"OpenRouter API error: {e}")
            return "{}", [], "", f"❌ **API Fehler:** {e}"

        except Exception as e:
            logger.error(f"Unexpected error during generation: {e}")
            return "{}", [], "", f"❌ **Fehler:** {e}"

    def clear_all(self) -> Tuple[str, str, list, str, str]:
        """Clear all inputs and outputs."""
        return "", "{}", [], "", ""

    def refresh_models(self) -> dict:
        """Refresh model dropdown."""
        # Refresh config to get latest models
        self.config = ConfigManager()
        choices = self._get_model_choices()
        return gr.update(choices=choices, value=choices[0] if choices else None)

    def import_to_project(self, json_str: str) -> str:
        """Import storyboard to current project."""
        try:
            # Validate JSON first
            config = ConfigManager()
            llm_service = StoryboardLLMService(config)
            is_valid, errors, _ = llm_service.validate_draft(json_str)
            if not is_valid:
                return f"❌ **Validierungsfehler:**\n" + "\n".join(f"- {e}" for e in errors)

            # Get current project (fresh ProjectStore)
            project_store = ProjectStore(config)
            project = project_store.get_active_project(refresh=True)
            if not project:
                return "❌ **Kein Projekt aktiv** - Bitte zuerst ein Projekt auswählen"

            # Parse JSON
            storyboard_data = json.loads(json_str)
            project_name = storyboard_data.get("project", "generated_storyboard")

            # Clean filename
            filename = project_name.lower().replace(" ", "_")
            filename = "".join(c for c in filename if c.isalnum() or c == "_")
            filename = f"{filename}_storyboard.json"

            # Determine save path - project storyboards folder
            project_path = Path(project.get("path", ""))
            storyboards_dir = project_path / "storyboards"
            storyboards_dir.mkdir(parents=True, exist_ok=True)

            output_path = storyboards_dir / filename

            # Check for existing file
            counter = 1
            while output_path.exists():
                filename = f"{project_name.lower().replace(' ', '_')}_{counter}_storyboard.json"
                output_path = storyboards_dir / filename
                counter += 1

            # Save
            saved_path = llm_service.save_storyboard(storyboard_data, str(output_path))

            logger.info(f"Storyboard imported to {saved_path}")
            return f"✅ **Importiert!**\n\nGespeichert unter:\n`{saved_path}`"

        except json.JSONDecodeError as e:
            return f"❌ **JSON Fehler:** {e}"
        except Exception as e:
            logger.error(f"Import failed: {e}")
            return f"❌ **Fehler:** {e}"


__all__ = ["StoryboardLLMGeneratorAddon"]
