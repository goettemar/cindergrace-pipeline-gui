"""Addon for Kohya LoRA Training.

This addon provides a UI for training character LoRAs using Kohya sd-scripts.
Supports FLUX, SDXL, and SD3 model types.

Note: For dataset generation, use the Dataset Generator addon.
"""
import os
import sys
import subprocess
from typing import List, Optional

import gradio as gr

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from addons.base_addon import BaseAddon
from addons.components import format_project_status
from infrastructure.config_manager import ConfigManager
from infrastructure.logger import get_logger
from infrastructure.job_status_store import JobStatusStore
from services.lora_trainer_service import LoraTrainerService
from services.kohya_trainer_service import (
    KohyaTrainerService,
    KohyaModelType,
    KohyaVRAMPreset,
    KohyaTrainingStatus,
    KohyaTrainingProgress,
)

logger = get_logger(__name__)

# Model type choices
MODEL_TYPE_CHOICES = [
    ("🔥 FLUX (Diffusion Transformer)", "flux"),
    ("🎨 SDXL (Stable Diffusion XL)", "sdxl"),
    ("✨ SD3 (Stable Diffusion 3)", "sd3"),
]

# VRAM preset choices per model type
KOHYA_VRAM_CHOICES = {
    "flux": [
        ("💾 16GB VRAM (RTX 5060 Ti, 4080) - 512px, Prodigy", "16gb"),
        ("🚀 24GB+ VRAM (RTX 4090, 3090) - 768px, AdamW8bit", "24gb"),
    ],
    "sdxl": [
        ("💡 8GB VRAM (RTX 3060, 4060 Ti) - 512px, Prodigy", "8gb"),
        ("💾 16GB VRAM (RTX 4080, 5060 Ti) - 768px, AdamW8bit", "16gb"),
        ("🚀 24GB+ VRAM (RTX 4090, 3090) - 1024px, AdamW8bit", "24gb"),
    ],
    "sd3": [
        ("💡 8GB VRAM (RTX 3060, 4060 Ti) - 512px, Prodigy", "8gb"),
        ("💾 16GB VRAM (RTX 4080, 5060 Ti) - 768px, AdamW8bit", "16gb"),
        ("🚀 24GB+ VRAM (RTX 4090, 3090) - 1024px, AdamW8bit", "24gb"),
    ],
}


class CharacterTrainerAddon(BaseAddon):
    """Addon for training character LoRAs with Kohya sd-scripts."""

    def __init__(self):
        super().__init__(
            name="Character Trainer",
            description="Train character LoRAs with Kohya sd-scripts",
            category="training"
        )
        self.config = ConfigManager()
        self.lora_service = LoraTrainerService(self.config)
        self.kohya_service = KohyaTrainerService(self.config)
        self._job_store = JobStatusStore()

    def get_tab_name(self) -> str:
        return "🎭 LoRA"

    def render(self) -> gr.Blocks:
        with gr.Blocks() as interface:
            gr.HTML(format_project_status(
                tab_name="🎭 Kohya LoRA Training",
                no_project_relation=True,
                include_remote_warning=True,
            ))

            gr.Markdown(
                "Trainiere Character LoRAs mit Kohya sd-scripts. "
                "Supports FLUX, SDXL und SD3 Modele."
            )

            self._render_kohya_training_ui()

        return interface

    def _render_kohya_install_ui(self):
        """Render installation UI when Kohya sd-scripts is not available."""
        with gr.Group():
            gr.Markdown(
                "## ⚠️ Kohya sd-scripts nicht gefunden\n\n"
                "Für LoRA Training wird das Kohya sd-scripts Paket benötigt.\n\n"
                "**Was wird installiert:**\n"
                "- Kohya sd-scripts Repository (~100 MB)\n"
                "- PyTorch mit CUDA-Unterstützung (~2 GB)\n"
                "- Python-Abhängigkeiten (~500 MB)\n\n"
                "**Voraussetzungen:**\n"
                "- NVIDIA GPU mit mindestens 8 GB VRAM\n"
                "- CUDA-fähiger Treiber installiert\n"
                "- Git installiert\n"
                "- Stabile Internetverbindung\n\n"
                "**Dauer:** 10-20 Minuten je nach Internetgeschwindigkeit"
            )

            install_log = gr.Textbox(
                label="Installations-Log",
                lines=12,
                max_lines=20,
                interactive=False,
                show_copy_button=True,
                visible=False
            )

            with gr.Row():
                install_btn = gr.Button(
                    "🔧 sd-scripts automatisch installieren",
                    variant="primary",
                    size="lg"
                )
                manual_info_btn = gr.Button(
                    "📖 Manuelle Installation",
                    variant="secondary",
                    size="lg"
                )

            manual_instructions = gr.Markdown(
                """
**Manuelle Installation (falls automatisch fehlschlägt):**

```bash
cd tools
git clone -b sd3 --depth 1 https://github.com/kohya-ss/sd-scripts.git
cd sd-scripts
python3 -m venv .venv
.venv/bin/pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
.venv/bin/pip install -r requirements.txt
```

Nach der Installation diese Seite neu laden.
                """,
                visible=False
            )

            def toggle_manual():
                return gr.update(visible=True)

            def run_installation():
                logs = []

                def log_callback(msg):
                    logs.append(msg)

                yield gr.update(visible=True, value="🔄 Installation wird gestartet...\n")

                # Run installation
                success, message = self.kohya_service.install_kohya_scripts(log_callback)

                final_log = "\n".join(logs)
                if success:
                    final_log += "\n\n✅ " + message
                    final_log += "\n\n🔄 Bitte lade die Seite neu um das Training zu starten."
                else:
                    final_log += "\n\n❌ " + message

                yield gr.update(value=final_log)

            install_btn.click(
                fn=run_installation,
                inputs=[],
                outputs=[install_log]
            )

            manual_info_btn.click(
                fn=toggle_manual,
                inputs=[],
                outputs=[manual_instructions]
            )

    def _render_kohya_training_ui(self):
        """Render the Kohya-based LoRA training UI."""
        # Check Kohya availability
        kohya_available = self.kohya_service.is_kohya_available()
        if not kohya_available:
            self._render_kohya_install_ui()
            return

        with gr.Row():
            # Left Column: Configuration
            with gr.Column(scale=1):
                with gr.Group():
                    gr.Markdown("### 📂 Training Dataset")

                    kohya_dataset_dropdown = gr.Dropdown(
                        label="Available Datasets",
                        choices=self._get_dataset_choices(),
                        info="Datasets aus dem Dataset Generator"
                    )

                    kohya_refresh_btn = gr.Button("🔄 Aktualisieren", size="sm")

                    kohya_dataset_manual = gr.Textbox(
                        label="Oder manueller Pfad",
                        placeholder="/pfad/zum/dataset",
                        info="Falls Dataset nicht in der Liste"
                    )

                    kohya_dataset_info = gr.Markdown("*Select a dataset*")

                with gr.Group():
                    gr.Markdown("### 🏷️ Charakter-Info")

                    kohya_character_name = gr.Textbox(
                        label="Charakter-Name",
                        placeholder="z.B. 'elena' oder 'max'",
                        info="Used for filename (cg_<name>.safetensors)"
                    )

                    kohya_trigger_word = gr.Textbox(
                        label="Trigger-Wort",
                        placeholder="z.B. 'elena' (ohne cg_ Prefix)",
                        info="Das Wort, das das LoRA in Prompts activated"
                    )

                with gr.Group():
                    gr.Markdown("### 🎯 Model-Typ")

                    kohya_model_type = gr.Dropdown(
                        choices=[label for label, _ in MODEL_TYPE_CHOICES],
                        value=MODEL_TYPE_CHOICES[0][0],  # FLUX default
                        label="Model-Typ",
                        info="FLUX, SDXL oder SD3"
                    )

                with gr.Group():
                    gr.Markdown("### ⚙️ Training-Settings")

                    kohya_vram_preset = gr.Dropdown(
                        choices=[label for label, _ in KOHYA_VRAM_CHOICES["flux"]],
                        value=KOHYA_VRAM_CHOICES["flux"][0][0],  # 16GB default
                        label="GPU VRAM Preset",
                        info="Optimiert Settings automatisch"
                    )

                    kohya_steps = gr.Slider(
                        minimum=500,
                        maximum=5000,
                        step=100,
                        value=1500,
                        label="Training Steps",
                        info="1500-2000 empfohlen"
                    )

                    with gr.Accordion("🔧 Erweiterte Settings", open=False):
                        kohya_network_dim = gr.Slider(
                            minimum=4,
                            maximum=64,
                            step=4,
                            value=16,
                            label="Network Dimension (Rank)",
                            info="16 (16GB) oder 32 (24GB) empfohlen"
                        )

                        kohya_num_repeats = gr.Slider(
                            minimum=1,
                            maximum=30,
                            step=1,
                            value=10,
                            label="Dataset Repeats",
                            info="Wie oft jedes Bild pro Epoche wiederholt wird"
                        )

                        kohya_learning_rate = gr.Slider(
                            minimum=0.00001,
                            maximum=1.0,
                            step=0.00001,
                            value=0.0001,
                            label="Learning Rate",
                            info="0.0001 für AdamW, 1.0 für Prodigy (auto). Niedriger = stabiler"
                        )

                        kohya_save_every = gr.Slider(
                            minimum=100,
                            maximum=1000,
                            step=100,
                            value=500,
                            label="Save Every N Steps",
                            info="Save checkpoint every N steps"
                        )

                        gr.Markdown("#### 🖼️ Test Image Generation")
                        gr.Markdown(
                            "*Generate test images during training, "
                            "to check progress.*"
                        )

                        kohya_sample_every = gr.Slider(
                            minimum=0,
                            maximum=1000,
                            step=100,
                            value=0,
                            label="Sample Every N Steps",
                            info="0 = deactivated, 250-500 empfohlen"
                        )

                        kohya_sample_prompt = gr.Textbox(
                            label="Sample Prompt",
                            placeholder="z.B. 'elena, portrait, high quality'",
                            info="Leer = Trigger-Wort + Standard-Prompt"
                        )

                        gr.Markdown("#### 🎯 Model-Auswahl")
                        gr.Markdown(
                            "*Select the models for training. "
                            "FP8 versions recommended for 16GB VRAM.*"
                        )

                        kohya_base_model = gr.Dropdown(
                            label="Base Model",
                            choices=self._get_flux_model_choices(),
                            info="The base model for LoRA training"
                        )

                        kohya_t5xxl_model = gr.Dropdown(
                            label="T5XXL Text Encoder (FLUX/SD3)",
                            choices=self._get_t5xxl_model_choices(),
                            info="FP8 recommended for 16GB VRAM",
                            visible=True  # FLUX is default
                        )

                        kohya_refresh_models_btn = gr.Button(
                            "🔄 Models aktualisieren",
                            size="sm"
                        )

            # Right Column: Training Control & Logs
            with gr.Column(scale=1):
                with gr.Group():
                    gr.Markdown("### 🎬 Training")

                    with gr.Row():
                        kohya_start_btn = gr.Button(
                            "▶️ Start Training",
                            variant="primary",
                            size="lg"
                        )
                        kohya_cancel_btn = gr.Button(
                            "⏹️ Cancel",
                            variant="stop",
                            size="lg"
                        )

                    gr.Markdown(
                        "⚠️ **Do not refresh during training.** If you refresh, the job "
                        "continues in the backend but this page will lose tracking. "
                        "Check `logs/pipeline.log` for progress."
                    )

                    kohya_status = gr.Markdown("**Status:** Ready")
                    job_status_md = gr.Markdown(self._get_training_job_status_md())

                    kohya_progress = gr.Slider(
                        minimum=0,
                        maximum=100,
                        value=0,
                        label="Progress",
                        interactive=False
                    )

                with gr.Group():
                    gr.Markdown("### 📜 Training Log")

                    kohya_log_output = gr.Textbox(
                        label="Log Output",
                        lines=12,
                        max_lines=15,
                        interactive=False
                    )

                with gr.Group():
                    gr.Markdown("### 🖼️ Latest Test Image")

                    kohya_sample_image = gr.Image(
                        label="Sample Image",
                        type="filepath",
                        height=200,
                        interactive=False
                    )

                with gr.Group():
                    gr.Markdown("### 📊 Ergebnis")

                    kohya_lora_path = gr.Textbox(
                        label="LoRA Datei",
                        interactive=False
                    )

                    kohya_open_folder_btn = gr.Button("📁 Open LoRA folder", size="sm")

        # Event handlers
        def refresh_kohya_datasets():
            choices = self._get_dataset_choices()
            return gr.Dropdown(choices=choices)

        def on_kohya_dataset_select(selected, manual_path):
            path = manual_path if manual_path else self._get_path_from_choice(selected)
            if not path:
                return "*Select a dataset*", "", ""

            is_valid, msg, count = self.lora_service.validate_dataset(path)

            if is_valid:
                name_suggestion = os.path.basename(path).split("_")[0] if "_" in os.path.basename(path) else ""
                info = f"**Dataset:** `{path}`\n\n**Bilder:** {count}"
                return info, name_suggestion, name_suggestion
            else:
                return f"**Dataset:** {msg}", "", ""

        def on_kohya_model_type_change(model_type_label):
            """Update VRAM presets and model dropdowns when model type changes."""
            model_type_value = "flux"
            for label, value in MODEL_TYPE_CHOICES:
                if label == model_type_label:
                    model_type_value = value
                    break

            vram_choices = KOHYA_VRAM_CHOICES.get(model_type_value, KOHYA_VRAM_CHOICES["flux"])
            vram_labels = [label for label, _ in vram_choices]

            base_model_choices = self._get_base_model_choices(model_type_value)

            # T5XXL is only needed for FLUX and SD3, not SDXL
            t5xxl_visible = model_type_value in ["flux", "sd3"]

            return (
                gr.Dropdown(choices=vram_labels, value=vram_labels[0]),
                gr.Dropdown(choices=base_model_choices, value=base_model_choices[0] if base_model_choices else None),
                gr.Dropdown(visible=t5xxl_visible)
            )

        def on_kohya_vram_change(preset_label, model_type_label):
            model_type_value = "flux"
            for label, value in MODEL_TYPE_CHOICES:
                if label == model_type_label:
                    model_type_value = value
                    break
            model_type_enum = KohyaModelType(model_type_value)

            vram_choices = KOHYA_VRAM_CHOICES.get(model_type_value, KOHYA_VRAM_CHOICES["flux"])
            preset_value = "16gb"
            for label, value in vram_choices:
                if label == preset_label:
                    preset_value = value
                    break

            preset_enum = KohyaVRAMPreset(preset_value)
            preset_config = self.kohya_service.get_vram_preset_config(preset_enum, model_type_enum)

            return (
                preset_config.get("max_train_steps", 1500),
                preset_config.get("network_dim", 16),
                preset_config.get("num_repeats", 10) if "num_repeats" not in preset_config else 10,
                preset_config.get("learning_rate", 0.0001)
            )

        def start_kohya_training(
            dataset_dropdown,
            manual_path,
            character_name,
            trigger_word,
            model_type_choice,
            vram_choice,
            steps,
            network_dim,
            num_repeats,
            learning_rate,
            save_every,
            sample_every,
            sample_prompt,
            base_model_choice,
            t5xxl_model_choice
        ):
            path = manual_path if manual_path else self._get_path_from_choice(dataset_dropdown)

            if not path or not os.path.exists(path):
                return "**Status:** No valid dataset", 0, "", None, "", self._get_training_job_status_md()

            if not character_name or not character_name.strip():
                return "**Status:** Charakter-Name fehlt", 0, "", None, "", self._get_training_job_status_md()

            if not trigger_word or not trigger_word.strip():
                return "**Status:** Trigger-Wort fehlt", 0, "", None, "", self._get_training_job_status_md()

            # Convert model type choice to enum
            model_type_value = "flux"
            for label, value in MODEL_TYPE_CHOICES:
                if label == model_type_choice:
                    model_type_value = value
                    break
            model_type_enum = KohyaModelType(model_type_value)

            # Convert VRAM choice to enum
            vram_choices = KOHYA_VRAM_CHOICES.get(model_type_value, KOHYA_VRAM_CHOICES["flux"])
            vram_value = "16gb"
            for label, value in vram_choices:
                if label == vram_choice:
                    vram_value = value
                    break
            vram_enum = KohyaVRAMPreset(vram_value)

            # Get model paths from selections
            base_model_path = self._get_model_path_from_choice(base_model_choice, model_type_value)
            t5xxl_model_path = self._get_model_path_from_choice(t5xxl_model_choice, "t5xxl")

            try:
                config_path = self.kohya_service.generate_training_config(
                    character_name=character_name.strip(),
                    images_dir=path,
                    trigger_word=trigger_word.strip(),
                    model_type=model_type_enum,
                    vram_preset=vram_enum,
                    base_model_path=base_model_path,
                    t5xxl_model_path=t5xxl_model_path,
                    max_train_steps=int(steps),
                    network_dim=int(network_dim),
                    num_repeats=int(num_repeats),
                    learning_rate=float(learning_rate),
                    save_every_n_steps=int(save_every),
                    sample_every_n_steps=int(sample_every),
                    sample_prompt=sample_prompt.strip() if sample_prompt else ""
                )

                log_lines = []

                def log_callback(line):
                    log_lines.append(line)

                success = self.kohya_service.start_training(
                    config_path,
                    model_type=model_type_enum,
                    log_callback=log_callback
                )

                if success:
                    self._job_store.set_status(
                        None,
                        "lora_training",
                        "running",
                        message=f"Training started ({model_type_value.upper()})",
                        metadata={
                            "dataset": path,
                            "character": character_name.strip(),
                            "trigger": trigger_word.strip(),
                            "model_type": model_type_value,
                        },
                    )
                    return (
                        f"**Status:** 🚀 {model_type_value.upper()} Training started...",
                        0,
                        "\n".join(log_lines[-50:]),
                        None,
                        "",
                        self._get_training_job_status_md()
                    )
                else:
                    progress = self.kohya_service.get_progress()
                    self._job_store.set_status(
                        None,
                        "lora_training",
                        "failed",
                        message=progress.error_message or "Training failed to start",
                    )
                    return (
                        f"**Status:** Error: {progress.error_message}",
                        0,
                        "",
                        None,
                        "",
                        self._get_training_job_status_md()
                    )
            except Exception as e:
                logger.error(f"Kohya training error: {e}", exc_info=True)
                self._job_store.set_status(
                    None,
                    "lora_training",
                    "failed",
                    message=str(e),
                )
                return f"**Status:** Error: {str(e)}", 0, "", None, "", self._get_training_job_status_md()

        def cancel_kohya_training():
            self.kohya_service.cancel_training()
            self._job_store.set_status(
                None,
                "lora_training",
                "cancelled",
                message="Training cancelled",
            )
            return "**Status:** ⏹️ Training cancelled", self._get_training_job_status_md()

        def get_kohya_status():
            progress = self.kohya_service.get_progress()
            logs = self.kohya_service.get_logs(last_n=50)

            status_icons = {
                KohyaTrainingStatus.IDLE: "Ready",
                KohyaTrainingStatus.PREPARING: "Preparing...",
                KohyaTrainingStatus.RUNNING: "Running...",
                KohyaTrainingStatus.COMPLETED: "Completed",
                KohyaTrainingStatus.CANCELLED: "Cancelled",
                KohyaTrainingStatus.ERROR: "Error",
            }

            status_text = status_icons.get(progress.status, "Unknown")
            progress_value = 0

            if progress.status == KohyaTrainingStatus.RUNNING:
                if progress.total_steps > 0:
                    pct = (progress.current_step / progress.total_steps) * 100
                    eta_min = progress.eta_seconds / 60 if progress.eta_seconds > 0 else 0
                    status_text = (
                        f"🚀 Step {progress.current_step}/{progress.total_steps} "
                        f"({pct:.1f}%) - Loss: {progress.current_loss:.4f} "
                        f"- ETA: {eta_min:.0f}m"
                    )
                    progress_value = pct
            elif progress.status == KohyaTrainingStatus.COMPLETED:
                status_text = "✅ Training abgeschlossen!"
                progress_value = 100
            elif progress.status == KohyaTrainingStatus.ERROR:
                status_text = f"❌ Error: {progress.error_message}"

            # Find latest sample image
            sample_image = None
            if progress.output_dir:
                sample_dir = os.path.join(progress.output_dir, "sample")
                if os.path.exists(sample_dir):
                    samples = sorted(
                        [f for f in os.listdir(sample_dir) if f.endswith(".png")],
                        key=lambda x: os.path.getmtime(os.path.join(sample_dir, x)),
                        reverse=True
                    )
                    if samples:
                        sample_image = os.path.join(sample_dir, samples[0])

            # Find LoRA path
            lora_path = ""
            if progress.status == KohyaTrainingStatus.COMPLETED and progress.output_dir:
                # Look for the final LoRA file in output_dir
                lora_dir = progress.output_dir
                if os.path.exists(lora_dir):
                    lora_files = sorted(
                        [f for f in os.listdir(lora_dir) if f.endswith(".safetensors")],
                        key=lambda x: os.path.getmtime(os.path.join(lora_dir, x)),
                        reverse=True
                    )
                    if lora_files:
                        lora_path = os.path.join(lora_dir, lora_files[0])

            job_status = self._update_training_job_status(progress, progress_value)
            return (
                f"**Status:** {status_text}",
                progress_value,
                "\n".join(logs),
                sample_image,
                lora_path,
                job_status
            )

        def open_kohya_lora_folder(lora_path):
            if lora_path:
                folder = os.path.dirname(lora_path) if os.path.isfile(lora_path) else lora_path
            else:
                folder = os.path.join(self.config.get_comfy_root() or "", "models", "loras")

            if folder and os.path.exists(folder):
                subprocess.run(["xdg-open", folder], check=False)
            return "**Status:** 📁 Folder opened"

        def refresh_models(model_type_label):
            model_type_value = "flux"
            for label, value in MODEL_TYPE_CHOICES:
                if label == model_type_label:
                    model_type_value = value
                    break
            base_choices = self._get_base_model_choices(model_type_value)
            t5xxl_choices = self._get_t5xxl_model_choices()
            return gr.Dropdown(choices=base_choices), gr.Dropdown(choices=t5xxl_choices)

        # Wire up events
        kohya_refresh_btn.click(
            fn=refresh_kohya_datasets,
            outputs=[kohya_dataset_dropdown]
        )

        kohya_dataset_dropdown.change(
            fn=on_kohya_dataset_select,
            inputs=[kohya_dataset_dropdown, kohya_dataset_manual],
            outputs=[kohya_dataset_info, kohya_character_name, kohya_trigger_word]
        )

        kohya_dataset_manual.change(
            fn=on_kohya_dataset_select,
            inputs=[kohya_dataset_dropdown, kohya_dataset_manual],
            outputs=[kohya_dataset_info, kohya_character_name, kohya_trigger_word]
        )

        kohya_model_type.change(
            fn=on_kohya_model_type_change,
            inputs=[kohya_model_type],
            outputs=[kohya_vram_preset, kohya_base_model, kohya_t5xxl_model]
        )

        kohya_vram_preset.change(
            fn=on_kohya_vram_change,
            inputs=[kohya_vram_preset, kohya_model_type],
            outputs=[kohya_steps, kohya_network_dim, kohya_num_repeats, kohya_learning_rate]
        )

        kohya_refresh_models_btn.click(
            fn=refresh_models,
            inputs=[kohya_model_type],
            outputs=[kohya_base_model, kohya_t5xxl_model]
        )

        kohya_start_btn.click(
            fn=start_kohya_training,
            inputs=[
                kohya_dataset_dropdown, kohya_dataset_manual,
                kohya_character_name, kohya_trigger_word,
                kohya_model_type, kohya_vram_preset, kohya_steps, kohya_network_dim,
                kohya_num_repeats, kohya_learning_rate, kohya_save_every,
                kohya_sample_every, kohya_sample_prompt,
                kohya_base_model, kohya_t5xxl_model
            ],
            outputs=[kohya_status, kohya_progress, kohya_log_output, kohya_sample_image, kohya_lora_path, job_status_md]
        )

        kohya_cancel_btn.click(
            fn=cancel_kohya_training,
            outputs=[kohya_status, job_status_md]
        )

        kohya_open_folder_btn.click(
            fn=open_kohya_lora_folder,
            inputs=[kohya_lora_path],
            outputs=[kohya_status]
        )

        # Timer for live updates during training
        kohya_timer = gr.Timer(value=2, active=False)

        kohya_start_btn.click(
            fn=lambda: gr.Timer(active=True),
            outputs=[kohya_timer]
        )

        kohya_timer.tick(
            fn=get_kohya_status,
            outputs=[kohya_status, kohya_progress, kohya_log_output, kohya_sample_image, kohya_lora_path, job_status_md]
        )

        kohya_timer.tick(
            fn=lambda: gr.Timer(active=self.kohya_service.is_training()),
            outputs=[kohya_timer]
        )

    # ==================== Helper Methods ====================

    def _get_training_job_status_md(self) -> str:
        """Return last training job status."""
        status = self._job_store.get_status(None, "lora_training")
        if not status:
            return ""
        updated = status.updated_at or "unknown time"
        message = status.message or "No details"
        return (
            f"**Last training job:** `{status.status}`\n\n"
            f"{message}\n\n"
            f"_Last updated: {updated}_"
        )

    def _update_training_job_status(self, progress: KohyaTrainingProgress, progress_value: float) -> str:
        """Persist current training status and return display text."""
        status_map = {
            KohyaTrainingStatus.IDLE: "idle",
            KohyaTrainingStatus.PREPARING: "running",
            KohyaTrainingStatus.RUNNING: "running",
            KohyaTrainingStatus.COMPLETED: "completed",
            KohyaTrainingStatus.CANCELLED: "cancelled",
            KohyaTrainingStatus.ERROR: "failed",
        }
        status_key = status_map.get(progress.status, "unknown")
        message = progress.error_message or ""
        if progress.status == KohyaTrainingStatus.RUNNING:
            message = f"Step {progress.current_step}/{progress.total_steps}"
        elif progress.status == KohyaTrainingStatus.COMPLETED:
            message = "Training completed"
        elif progress.status == KohyaTrainingStatus.CANCELLED:
            message = "Training cancelled"

        self._job_store.set_status(
            None,
            "lora_training",
            status_key,
            message=message,
            progress=progress_value,
        )
        return self._get_training_job_status_md()

    def _get_dataset_choices(self) -> List[str]:
        """Get available dataset choices for dropdown."""
        datasets = self.lora_service.list_available_datasets()
        choices = []
        for d in datasets:
            status = "✅" if d["valid"] else "❌"
            choices.append(f"{status} {d['name']} ({d['image_count']} Bilder)")
        return choices

    def _get_path_from_choice(self, choice: str) -> Optional[str]:
        """Extract path from dropdown choice."""
        if not choice:
            return None

        name = choice.split(" ", 1)[1] if " " in choice else choice
        name = name.rsplit(" (", 1)[0]

        datasets = self.lora_service.list_available_datasets()
        for d in datasets:
            if d["name"] == name:
                return d["path"]
        return None

    def _get_flux_model_choices(self) -> List[str]:
        """Get available FLUX model choices for dropdown."""
        models = self.kohya_service.scan_available_flux_models()
        if not models:
            return ["Keine FLUX Modele gefunden"]
        return [display for display, _ in models]

    def _get_sdxl_model_choices(self) -> List[str]:
        """Get available SDXL model choices for dropdown."""
        models = self.kohya_service.scan_available_sdxl_models()
        if not models:
            return ["Keine SDXL Modele gefunden"]
        return [display for display, _ in models]

    def _get_sd3_model_choices(self) -> List[str]:
        """Get available SD3 model choices for dropdown."""
        models = self.kohya_service.scan_available_sd3_models()
        if not models:
            return ["Keine SD3 Modele gefunden"]
        return [display for display, _ in models]

    def _get_base_model_choices(self, model_type_value: str) -> List[str]:
        """Get base model choices based on model type."""
        if model_type_value == "flux":
            return self._get_flux_model_choices()
        elif model_type_value == "sdxl":
            return self._get_sdxl_model_choices()
        elif model_type_value == "sd3":
            return self._get_sd3_model_choices()
        return ["No model type selected"]

    def _get_t5xxl_model_choices(self) -> List[str]:
        """Get available T5XXL model choices for dropdown."""
        models = self.kohya_service.scan_available_t5xxl_models()
        if not models:
            return ["Keine T5XXL Modele gefunden"]
        return [display for display, _ in models]

    def _get_model_path_from_choice(self, choice: str, model_type: str) -> Optional[str]:
        """Extract model path from dropdown choice."""
        if not choice or "not found" in choice.lower() or "not selected" in choice.lower():
            return None

        if model_type == "flux":
            models = self.kohya_service.scan_available_flux_models()
        elif model_type == "sdxl":
            models = self.kohya_service.scan_available_sdxl_models()
        elif model_type == "sd3":
            models = self.kohya_service.scan_available_sd3_models()
        elif model_type == "t5xxl":
            models = self.kohya_service.scan_available_t5xxl_models()
        else:
            return None

        for display, path in models:
            if display == choice:
                return path
        return None


__all__ = ["CharacterTrainerAddon"]
