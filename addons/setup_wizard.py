"""Setup Wizard Addon - Initial setup for new users."""
import gradio as gr

from addons.base_addon import BaseAddon
from addons.components import format_project_status
from infrastructure.config_manager import ConfigManager
from infrastructure.help_service import get_help_service
from infrastructure.help_ui import HelpContext
from infrastructure.logger import get_logger
from services.system_detector import SystemDetector

logger = get_logger(__name__)


class SetupWizardAddon(BaseAddon):
    """Setup assistant for initial CINDERGRACE configuration."""

    def __init__(self):
        super().__init__(
            name="Setup Wizard",
            description="Initial setup and system check",
            category="tools"
        )
        self.config = ConfigManager()
        self.detector = SystemDetector()
        self.help = HelpContext("setup_wizard", get_help_service())

    def get_tab_name(self) -> str:
        return "Setup"

    def render(self) -> gr.Blocks:
        with gr.Blocks() as interface:
            # Unified header: Tab name left, no project relation
            gr.HTML(format_project_status(
                tab_name="🛠️ Setup Wizard",
                no_project_relation=True,
                include_remote_warning=True,
            ))

            # Check if setup is already completed (static check at render time)
            from infrastructure.settings_store import get_settings_store
            store = get_settings_store()
            setup_already_done = not self.config.is_first_run()
            acceptance_date = store.get("disclaimer_accepted_date") or "unbekannt"

            # === SETUP ALREADY COMPLETED VIEW ===
            with gr.Column(visible=setup_already_done) as setup_done_view:
                gr.Markdown(
                    f"""
                    ## ✅ Setup bereits abgeschlossen

                    **CINDERGRACE ist bereits eingerichtet!**
                    """
                )

                # Disclaimer in collapsible accordion
                with gr.Accordion("📜 Nutzungsbedingungen & Disclaimer", open=False):
                    gr.Markdown(f"✓ **Akzeptiert am:** {acceptance_date}")
                    gr.Markdown(self._get_disclaimer_text())

                gr.Markdown(
                    """
                    ---

                    **Möchtest du Einstellungen ändern?**

                    Alle Konfigurationen findest du im **⚙️ Settings** Tab:
                    - ComfyUI Verbindung und Backend
                    - API Keys (Civitai, Huggingface, etc.)
                    - Auflösung und andere Optionen

                    ---
                    """
                )

                rerun_setup = gr.Checkbox(
                    label="Setup Wizard erneut durchlaufen (setzt Einrichtung zurück)",
                    value=False,
                    info="Nur verwenden, wenn du die komplette Ersteinrichtung wiederholen möchtest."
                )

                rerun_btn = gr.Button("Setup Wizard neu starten", variant="secondary", visible=False)

                def toggle_rerun_btn(checked):
                    return gr.Button(visible=checked)

                def reset_and_reload():
                    """Reset setup_completed flag and trigger page reload."""
                    store.delete("setup_completed")
                    store.delete("disclaimer_accepted_date")
                    return None

                rerun_setup.change(
                    fn=toggle_rerun_btn,
                    inputs=[rerun_setup],
                    outputs=[rerun_btn]
                )

                rerun_btn.click(
                    fn=reset_and_reload,
                    js="() => { setTimeout(() => window.location.reload(), 100); }"
                )

            # === SETUP WIZARD VIEW ===
            with gr.Column(visible=not setup_already_done) as setup_wizard_view:
                gr.Markdown(
                    "Welcome to **CINDERGRACE**! "
                    "This wizard will help you with the initial setup."
                )

            # State for current step
            current_step = gr.State(value=0)

            # === STEP 0: Disclaimer ===
            with gr.Column(visible=not setup_already_done) as step0:
                gr.Markdown("## Terms of Use & Disclaimer")
                gr.Markdown("Please read and accept the following terms before continuing:")

                gr.Markdown(self._get_disclaimer_text())

                accept_checkbox = gr.Checkbox(
                    label="I have read, understood, and accept the Terms of Use and Disclaimer",
                    value=False,
                )

                with gr.Row():
                    step0_next = gr.Button("Continue", variant="primary", interactive=False)

            # === STEP 1: System Detection ===
            with gr.Column(visible=False) as step1:
                gr.Markdown("## Step 1: System Check")
                gr.Markdown("Checking your system for required dependencies...")

                with gr.Row():
                    refresh_btn = gr.Button("Check system again", variant="secondary")

                system_info = gr.Markdown("")
                deps_info = gr.Markdown("")
                step1_status = gr.Markdown("")

                with gr.Row():
                    step1_next = gr.Button("Next", variant="primary")

            # === STEP 2: ComfyUI Status ===
            with gr.Column(visible=False) as step2:
                gr.Markdown("## Step 2: ComfyUI")

                gr.Markdown(
                    "ComfyUI is the AI backend software that CINDERGRACE uses for "
                    "image and video generation."
                )

                comfyui_question = gr.Radio(
                    choices=[
                        ("Yes, ComfyUI is already installed", "installed"),
                        ("No, I still need to install ComfyUI", "not_installed"),
                    ],
                    label="Do you have ComfyUI installed?",
                    value=None,
                )

                with gr.Row():
                    step2_back = gr.Button("Back", variant="secondary")
                    step2_next = gr.Button("Next", variant="primary", interactive=False)

            # === STEP 3: Installation Guide ===
            with gr.Column(visible=False) as step3:
                gr.Markdown("## Step 3: ComfyUI Installation")

                os_tabs = gr.Tabs()
                with os_tabs:
                    with gr.Tab("Windows"):
                        gr.Markdown(self._get_windows_guide())
                    with gr.Tab("Linux"):
                        gr.Markdown(self._get_linux_guide())

                gr.Markdown(
                    "**Note:** After installation, you must start ComfyUI "
                    "before you can continue."
                )

                with gr.Row():
                    step3_back = gr.Button("Back", variant="secondary")
                    step3_next = gr.Button(
                        "ComfyUI is installed and running", variant="primary"
                    )

            # === STEP 4: Configuration ===
            with gr.Column(visible=False) as step4:
                gr.Markdown("## Step 4: Configuration")

                gr.Markdown("### ComfyUI Settings")
                gr.Markdown("Enter the path to your ComfyUI installation:")

                comfyui_path = gr.Textbox(
                    label="ComfyUI Installation Path",
                    placeholder="/path/to/ComfyUI or C:\\Users\\...\\ComfyUI",
                    info=self.help.tooltip("comfyui_root"),
                )

                comfyui_url = gr.Textbox(
                    label="ComfyUI Server URL",
                    value="http://127.0.0.1:8188",
                    info=self.help.tooltip("comfyui_url"),
                )

                test_result = gr.Markdown("")

                with gr.Row():
                    test_btn = gr.Button("Test Connection", variant="secondary")

                gr.Markdown("---")
                gr.Markdown("### API Keys (Optional)")
                gr.Markdown(
                    "These keys enable additional features. "
                    "They are stored **encrypted** in the local database."
                )

                civitai_key = gr.Textbox(
                    label="Civitai API Key",
                    type="password",
                    placeholder="Enter your Civitai API key (optional)",
                    info="Required for downloading models from Civitai. Get yours at civitai.com/user/account",
                )

                huggingface_token = gr.Textbox(
                    label="Huggingface Token",
                    type="password",
                    placeholder="Enter your Huggingface token (optional)",
                    info="Required for some model downloads. Get yours at huggingface.co/settings/tokens",
                )

                google_tts_key = gr.Textbox(
                    label="Google TTS API Key",
                    type="password",
                    placeholder="Enter your Google Cloud TTS API key (optional)",
                    info="Required for text-to-speech features. Optional for basic usage.",
                )

                gr.Markdown("---")
                gr.Markdown("### Quick Start")

                create_example = gr.Checkbox(
                    label="Create example project with sample storyboard",
                    value=True,
                    info="Creates an 'Example' project with a demo storyboard so you can start right away.",
                )

                with gr.Row():
                    step4_back = gr.Button("Back", variant="secondary")
                    step4_finish = gr.Button(
                        "Finish Setup", variant="primary", interactive=False
                    )

            # === STEP 5: Complete - RESTART REQUIRED ===
            with gr.Column(visible=False) as step5:
                gr.Markdown("## ✅ Setup Complete!")

                gr.HTML(
                    """
                    <div style="
                        background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
                        color: white;
                        padding: 30px;
                        border-radius: 12px;
                        text-align: center;
                        margin: 20px 0;
                        box-shadow: 0 4px 12px rgba(76, 175, 80, 0.3);
                    ">
                        <div style="font-size: 3em; margin-bottom: 15px;">🎉</div>
                        <h2 style="margin: 0 0 15px 0;">CINDERGRACE ist jetzt eingerichtet!</h2>
                        <p style="margin: 0 0 20px 0; opacity: 0.95; font-size: 1.1em;">
                            Die Konfiguration wurde gespeichert.
                        </p>
                        <div style="
                            background: rgba(255,255,255,0.2);
                            padding: 15px 20px;
                            border-radius: 8px;
                            margin-top: 15px;
                        ">
                            <p style="margin: 0; font-size: 1.2em; font-weight: bold;">
                                🔄 Bitte starte die App jetzt neu!
                            </p>
                            <p style="margin: 10px 0 0 0; opacity: 0.9; font-size: 0.95em;">
                                Drücke <strong>Ctrl+C</strong> im Terminal und starte mit <strong>./start.sh</strong> neu.
                            </p>
                        </div>
                    </div>
                    """
                )

                gr.Markdown(
                    """
                **Nach dem Neustart:**
                1. Alle Tabs sind freigeschaltet
                2. Dein Example-Projekt ist geladen (falls erstellt)
                3. Du kannst direkt mit der Arbeit beginnen!

                ---

                💡 **Tipp:** Einstellungen können jederzeit im **⚙️ Settings** Tab geändert werden.
                """
                )

            # === EVENT HANDLERS ===

            def check_system():
                """Performs system check."""
                summary = self.detector.get_system_summary()

                os_info = summary["os"]
                system_text = (
                    f"**Operating System:** {os_info['display_name']} "
                    f"({os_info['architecture']})"
                )

                deps = summary["dependencies"]
                deps_lines = []
                for key, dep in deps.items():
                    if key == "comfyui":
                        continue  # Handle separately
                    icon = "OK" if dep.installed else ("MISSING" if dep.required else "Optional")
                    version = f" v{dep.version}" if dep.version else ""
                    msg = f" - {dep.message}" if dep.message and dep.message != "OK" else ""
                    deps_lines.append(f"- **{dep.name}:** [{icon}]{version}{msg}")

                deps_text = "### Dependencies\n" + "\n".join(deps_lines)

                if summary["ready"]:
                    status = "**System is ready for CINDERGRACE.**"
                else:
                    missing = summary["stats"]["missing_required"]
                    status = f"**{missing} required dependency(ies) missing.**"

                return system_text, deps_text, status

            def enable_step2_next(choice):
                """Enables Next button in step 2."""
                return gr.Button(interactive=choice is not None)

            def enable_disclaimer_next(accepted):
                """Enables Continue button when disclaimer is accepted."""
                return gr.Button(interactive=accepted)

            def go_to_step(step_num, comfyui_choice=None):
                """Navigation between steps."""
                # If "installed" was chosen in step 2, skip step 3
                if step_num == 3 and comfyui_choice == "installed":
                    step_num = 4

                return (
                    gr.Column(visible=(step_num == 0)),  # step0 (disclaimer)
                    gr.Column(visible=(step_num == 1)),  # step1
                    gr.Column(visible=(step_num == 2)),  # step2
                    gr.Column(visible=(step_num == 3)),  # step3
                    gr.Column(visible=(step_num == 4)),  # step4
                    gr.Column(visible=(step_num == 5)),  # step5
                    step_num,  # current_step state
                )

            def test_connection(url, path):
                """Tests ComfyUI connection."""
                import os

                # Check path
                if path and not os.path.isdir(path):
                    return (
                        "**Invalid path:** The directory does not exist.",
                        gr.Button(interactive=False),
                    )

                # Check connection
                status = self.detector.check_comfyui_connection(url)

                if status.installed:
                    return (
                        "**Connection successful!** ComfyUI is reachable.",
                        gr.Button(interactive=True),
                    )
                else:
                    return (
                        f"**Connection failed:** {status.message}\n\n"
                        "Make sure ComfyUI is running.",
                        gr.Button(interactive=False),
                    )

            def finish_setup(url, path, civitai, huggingface, google_tts, create_example_project):
                """Saves configuration and completes setup."""
                from datetime import datetime
                from infrastructure.settings_store import get_settings_store

                self.config.set("comfy_url", url)
                if path:
                    self.config.set("comfy_root", path)

                # Save API keys (encrypted automatically via SettingsStore)
                if civitai:
                    self.config.set_civitai_api_key(civitai)
                if huggingface:
                    self.config.set_huggingface_token(huggingface)
                if google_tts:
                    self.config.set_google_tts_api_key(google_tts)

                # Create example project if requested
                if create_example_project:
                    try:
                        from infrastructure.project_store import ProjectStore
                        project_store = ProjectStore(self.config)
                        project_store.create_project("Example")
                        logger.info("Example project created during setup")
                    except Exception as e:
                        logger.warning(f"Could not create example project: {e}")

                # Store disclaimer acceptance date
                acceptance_date = datetime.now().strftime("%d.%m.%Y um %H:%M Uhr")
                store = get_settings_store()
                store.set("disclaimer_accepted_date", acceptance_date)

                self.config.mark_setup_completed()

                return go_to_step(5)

            # Event Bindings

            # Step 0: Disclaimer
            accept_checkbox.change(
                fn=enable_disclaimer_next,
                inputs=[accept_checkbox],
                outputs=[step0_next],
            )

            step0_next.click(
                fn=lambda: go_to_step(1),
                outputs=[step0, step1, step2, step3, step4, step5, current_step],
            )

            # Step 1: System Check
            interface.load(
                fn=check_system,
                outputs=[system_info, deps_info, step1_status],
            )

            refresh_btn.click(
                fn=check_system,
                outputs=[system_info, deps_info, step1_status],
            )

            step1_next.click(
                fn=lambda: go_to_step(2),
                outputs=[step0, step1, step2, step3, step4, step5, current_step],
            )

            # Step 2: ComfyUI Question
            comfyui_question.change(
                fn=enable_step2_next,
                inputs=[comfyui_question],
                outputs=[step2_next],
            )

            step2_back.click(
                fn=lambda: go_to_step(1),
                outputs=[step0, step1, step2, step3, step4, step5, current_step],
            )

            step2_next.click(
                fn=lambda choice: go_to_step(3, choice),
                inputs=[comfyui_question],
                outputs=[step0, step1, step2, step3, step4, step5, current_step],
            )

            # Step 3: Installation Guide
            step3_back.click(
                fn=lambda: go_to_step(2),
                outputs=[step0, step1, step2, step3, step4, step5, current_step],
            )

            step3_next.click(
                fn=lambda: go_to_step(4),
                outputs=[step0, step1, step2, step3, step4, step5, current_step],
            )

            # Step 4: Configuration
            step4_back.click(
                fn=lambda: go_to_step(2),
                outputs=[step0, step1, step2, step3, step4, step5, current_step],
            )

            test_btn.click(
                fn=test_connection,
                inputs=[comfyui_url, comfyui_path],
                outputs=[test_result, step4_finish],
            )

            step4_finish.click(
                fn=finish_setup,
                inputs=[comfyui_url, comfyui_path, civitai_key, huggingface_token, google_tts_key, create_example],
                outputs=[step0, step1, step2, step3, step4, step5, current_step],
            )

        return interface

    def _get_windows_guide(self) -> str:
        """Returns installation guide for Windows."""
        return """
### Windows Installation

#### Option 1: Portable Version (Recommended for beginners)

1. **Download:** Go to
   [ComfyUI Releases](https://github.com/comfyanonymous/ComfyUI/releases)

2. **Extract:** Download the latest `ComfyUI_windows_portable_*.7z`
   and extract it (e.g. to `C:\\ComfyUI_portable`)

3. **Start:** Run `run_nvidia_gpu.bat`

4. **Browser:** ComfyUI opens at `http://127.0.0.1:8188`

---

#### Option 2: Git Installation

```powershell
# In PowerShell or CMD:
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI
python -m venv venv
venv\\Scripts\\activate
pip install -r requirements.txt
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
python main.py
```

---

### Important Links

- [ComfyUI GitHub](https://github.com/comfyanonymous/ComfyUI)
- [Download Models](https://github.com/comfyanonymous/ComfyUI#installing-models)
- [ComfyUI Manager](https://github.com/ltdrdata/ComfyUI-Manager) (recommended)
"""

    def _get_linux_guide(self) -> str:
        """Returns installation guide for Linux."""
        return """
### Linux Installation

#### Prerequisites

- Python 3.10 or higher
- NVIDIA driver with CUDA
- Git

#### Installation

```bash
# Clone repository
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# PyTorch with CUDA (if not automatic)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Start
python main.py --listen 127.0.0.1 --port 8188
```

#### Autostart (optional)

Create a systemd service or use a start script:

```bash
#!/bin/bash
cd /path/to/ComfyUI
source venv/bin/activate
python main.py --listen 127.0.0.1 --port 8188
```

---

### Important Links

- [ComfyUI GitHub](https://github.com/comfyanonymous/ComfyUI)
- [Download Models](https://github.com/comfyanonymous/ComfyUI#installing-models)
- [ComfyUI Manager](https://github.com/ltdrdata/ComfyUI-Manager) (recommended)
"""

    def _get_disclaimer_text(self) -> str:
        """Returns the disclaimer and terms of use text."""
        return """
---

### 1. Disclaimer of Warranty

This software is provided **"AS IS"** without warranty of any kind, express or implied, including but not limited to:

- No warranty of merchantability or fitness for a particular purpose
- No warranty of error-free or uninterrupted operation
- No warranty regarding the quality of generated content
- No warranty that the software will meet your requirements

**THE DEVELOPERS AND RIGHTS HOLDERS SHALL NOT BE LIABLE FOR ANY CLAIMS, DAMAGES, OR OTHER LIABILITIES**, whether in contract, tort, or otherwise, arising from the use of the software or the content created with it.

---

### 2. License - Private Use Only

This software is licensed exclusively for **private, non-commercial use**.

**NOT PERMITTED:**
- ❌ Commercial use of any kind
- ❌ Resale or rental
- ❌ Distribution to third parties
- ❌ Publication of source code
- ❌ Creation of derivative works
- ❌ Reverse engineering

**PERMITTED:**
- ✅ Private use on your own systems
- ✅ Creation of content for private purposes

---

### 3. Responsibility for AI-Generated Content

You bear **sole responsibility** for all content created with this software.

**You agree to:**
- Not create deepfakes/lipsync videos of individuals without their explicit consent
- Not create content that defames, harasses, or deceives individuals
- Not use content for disinformation, fraud, or illegal purposes
- Label AI-generated content as such when published
- Comply with all local laws regarding AI-generated content

---

### 4. Third-Party Models

This software uses AI models from third parties (e.g., Wan 2.2, Flux, LTX-Video, SDXL). You are required to comply with the **respective license terms of these models**. The developers of CINDERGRACE assume no responsibility for license violations by users.

---

### 5. Alpha/Beta Status

This software is in **Alpha/Beta stage**. You accept that:
- Errors, crashes, and data loss may occur
- Changes may be made without notice
- Development may be discontinued without notice
- There is no entitlement to support or updates

---

### 6. Indemnification

You agree to indemnify and hold harmless the developers and rights holders from any claims, damages, losses, or expenses (including legal fees) arising from:
- Your use of the software
- Content you create with the software
- Your violation of these terms
- Your violation of any third-party rights

---

**By using this software, you confirm that you have read, understood, and accepted these terms.**
"""


__all__ = ["SetupWizardAddon"]
