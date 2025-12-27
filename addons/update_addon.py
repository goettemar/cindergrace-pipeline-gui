"""Update Addon - GUI for checking updates, backup and rollback.

Provides a user-friendly interface for:
- Checking for new versions
- Viewing changelogs
- Creating backups
- Updating to new versions
- Rolling back to previous versions
"""

import gradio as gr
from typing import Tuple, List, Optional
from datetime import datetime

from addons.base_addon import BaseAddon
from addons.components import format_project_status
from infrastructure.updater_service import (
    get_updater_service,
    UpdaterService,
    VersionInfo,
    BackupInfo,
)
from infrastructure.logger import get_logger

logger = get_logger(__name__)


class UpdateAddon(BaseAddon):
    """Addon for managing application updates."""

    def __init__(self):
        super().__init__(
            name="Update Manager",
            description="Check for updates, backup and rollback",
            category="system"
        )
        self.updater = get_updater_service()
        self._latest_version_info: Optional[VersionInfo] = None

    def get_tab_name(self) -> str:
        return "🔄 Updates"

    def _get_header_html(self) -> str:
        """Get header HTML with current version."""
        current = self.updater.get_current_version()
        return format_project_status(
            project_name=f"v{current}",
            project_slug=None,
            tab_name="🔄 Update Manager",
            no_project_relation=True,
            include_remote_warning=True,
        )

    def _format_backups_table(self, backups: List[BackupInfo]) -> List[List[str]]:
        """Format backups for dataframe display."""
        rows = []
        for b in backups:
            rows.append([
                f"v{b.version}",
                b.created_at.strftime("%Y-%m-%d %H:%M"),
                f"{b.size_mb:.1f} MB",
                str(b.path.name),
            ])
        return rows

    def _check_for_updates(self) -> Tuple[str, str, str, str]:
        """Check for updates and return UI updates.

        Returns:
            (status_md, changelog_md, update_btn_interactive, update_btn_label)
        """
        update_available, version_info, message = self.updater.check_for_updates()
        current = self.updater.get_current_version()
        verify_note = ""
        if version_info:
            verify_lines = []
            if version_info.minisig_url:
                verify_lines.append("✅ Minisign signature found")
            else:
                verify_lines.append("⚠️ No Minisign signature found in release")

            if version_info.sha256_url:
                verify_lines.append("✅ SHA256 asset found")
            else:
                verify_lines.append("ℹ️ No SHA256 asset found")

            verify_note = "\n**Verification:**\n" + "\n".join([f"- {line}" for line in verify_lines])

        if update_available and version_info:
            self._latest_version_info = version_info
            status_md = f"""### ✨ Update available!

**Current version:** v{current}
**New version:** v{version_info.version}

Published: {version_info.published_at[:10] if version_info.published_at else 'Unknown'}
{verify_note}
"""
            changelog_md = f"""### Changelog v{version_info.version}

{version_info.body}

---
[Open release on GitHub]({version_info.download_url})
"""
            return status_md, changelog_md, gr.update(interactive=True), f"📥 Update to v{version_info.version}"

        elif version_info:
            status_md = f"""### ✅ You're up to date

**Current version:** v{current}

{message}{verify_note}
"""
            changelog_md = f"""### Latest version: v{version_info.version}

{version_info.body}
"""
            return status_md, changelog_md, gr.update(interactive=False), "📥 No update available"

        else:
            status_md = f"""### ⚠️ Update check failed

**Current version:** v{current}

{message}
"""
            return status_md, "", gr.update(interactive=False), "📥 Update unavailable"

    def _create_backup(self) -> str:
        """Create a backup and return status message."""
        success, message = self.updater.create_backup()
        if success:
            return f"✅ {message}"
        else:
            return f"❌ {message}"

    def _refresh_backups(self) -> List[List[str]]:
        """Refresh backups list."""
        backups = self.updater.get_available_backups()
        return self._format_backups_table(backups)

    def _get_backup_choices(self) -> List[str]:
        """Get backup choices for dropdown."""
        backups = self.updater.get_available_backups()
        return [f"v{b.version} ({b.created_at.strftime('%Y-%m-%d %H:%M')})" for b in backups]

    def _perform_update(self, progress=gr.Progress()) -> str:
        """Perform the update process."""
        if not self._latest_version_info:
            return "❌ No update info available. Please check for updates first."

        version_info = self._latest_version_info

        # Step 1: Create backup
        progress(0.1, desc="Creating backup...")
        success, msg = self.updater.create_backup()
        if not success:
            return f"❌ Backup failed: {msg}"

        # Step 2: Download update
        progress(0.3, desc="Downloading update...")
        success, msg, download_path = self.updater.download_update(version_info)
        if not success or not download_path:
            return f"❌ Download failed: {msg}"

        # Step 3: Apply update
        progress(0.6, desc="Applying update...")
        success, msg = self.updater.apply_update(download_path, version_info.version)
        if not success:
            return f"❌ Update failed: {msg}"

        # Step 4: Update dependencies
        progress(0.9, desc="Updating dependencies...")
        success, dep_msg = self.updater.update_dependencies()

        progress(1.0, desc="Done!")

        if success:
            return f"""✅ **Update to v{version_info.version} successful!**

{msg}

**Dependencies:** {dep_msg}

## ⚠️ Restart Required

Please restart the **`cindergrace_gui` application** (not just the browser).
"""
        else:
            return f"""⚠️ **Update installed, but dependency issue:**

{msg}

**Dependencies:** {dep_msg}

Please run manually: `pip install -r requirements.txt`
"""

    def _perform_rollback(self, backup_selection: str) -> str:
        """Perform rollback to selected backup."""
        if not backup_selection:
            return "❌ Please select a backup to restore."

        backups = self.updater.get_available_backups()
        choices = self._get_backup_choices()

        try:
            idx = choices.index(backup_selection)
            backup = backups[idx]
        except (ValueError, IndexError):
            return "❌ Backup not found."

        success, msg = self.updater.rollback(backup)

        if success:
            return f"""✅ **Rollback successful!**

{msg}

## ⚠️ Restart Required

Please restart the **`cindergrace_gui` application** (not just the browser).
"""
        else:
            return f"❌ {msg}"

    def render(self) -> gr.Blocks:
        """Render the Update Manager UI."""
        current_version = self.updater.get_current_version()
        backups = self.updater.get_available_backups()

        with gr.Blocks() as interface:
            # Header
            header = gr.HTML(self._get_header_html())

            gr.Markdown("""
Manage updates, create backups, and restore previous versions.
            """)

            with gr.Row():
                # Left column: Update check
                with gr.Column(scale=1):
                    gr.Markdown("### 🔍 Update Check")

                    check_btn = gr.Button("🔍 Check for updates", variant="primary", size="lg")

                    status_md = gr.Markdown(f"""### Current version: v{current_version}

Click "Check for updates" to look for a new version.
""")

                    update_btn = gr.Button(
                        "📥 No update available",
                        variant="secondary",
                        size="lg",
                        interactive=False,
                    )

                    update_status = gr.Markdown("")

                # Right column: Changelog
                with gr.Column(scale=1):
                    gr.Markdown("### 📋 Changelog")

                    changelog_md = gr.Markdown("""
*Check for updates to view the changelog.*
""")

            gr.Markdown("---")

            with gr.Row():
                # Backup section
                with gr.Column(scale=1):
                    gr.Markdown("### 💾 Backups")

                    with gr.Row():
                        backup_btn = gr.Button("💾 Create backup", variant="secondary")
                        refresh_backups_btn = gr.Button("🔄", scale=0, min_width=50)

                    backup_status = gr.Markdown("")

                    backups_table = gr.Dataframe(
                        headers=["Version", "Created", "Size", "File"],
                        datatype=["str", "str", "str", "str"],
                        value=self._format_backups_table(backups),
                        interactive=False,
                        row_count=(3, "fixed"),
                    )

                # Rollback section
                with gr.Column(scale=1):
                    gr.Markdown("### ↩️ Rollback")

                    gr.Markdown("Restore a previous version from a backup:")

                    rollback_dropdown = gr.Dropdown(
                        choices=self._get_backup_choices(),
                        label="Select backup",
                        interactive=True,
                    )

                    rollback_btn = gr.Button(
                        "↩️ Perform rollback",
                        variant="stop",
                    )

                    rollback_status = gr.Markdown("")

            # Info section
            with gr.Accordion("ℹ️ Notes", open=False):
                gr.Markdown(f"""
### Backup Strategy

- Backups are stored under `~/.cindergrace/backups/`
- Only source code is saved (~5-10 MB per backup)
- `.venv`, `__pycache__`, `.git` are **not** included
- The last {self.updater._cleanup_old_backups.__defaults__} backups are kept

### Update Process

1. **Create backup** - Current version is saved automatically
2. **Download** - Fetch the new version from GitHub
3. **Install** - Files are updated (venv stays intact)
4. **Dependencies** - run `pip install -r requirements.txt`
5. **Restart** - Restart the `cindergrace_gui` application (not just the browser)

### Rollback

If a new version causes issues:
1. Choose a backup from the list
2. Click "Perform rollback"
3. Restart the `cindergrace_gui` application (not just the browser)

**Note:** A backup of the current version is created automatically before each rollback.
""")

            # Event handlers
            check_btn.click(
                fn=self._check_for_updates,
                outputs=[status_md, changelog_md, update_btn, update_btn],
            )

            update_btn.click(
                fn=self._perform_update,
                outputs=[update_status],
            )

            backup_btn.click(
                fn=self._create_backup,
                outputs=[backup_status],
            ).then(
                fn=self._refresh_backups,
                outputs=[backups_table],
            ).then(
                fn=self._get_backup_choices,
                outputs=[rollback_dropdown],
            )

            refresh_backups_btn.click(
                fn=self._refresh_backups,
                outputs=[backups_table],
            ).then(
                fn=self._get_backup_choices,
                outputs=[rollback_dropdown],
            )

            rollback_btn.click(
                fn=self._perform_rollback,
                inputs=[rollback_dropdown],
                outputs=[rollback_status],
            )

            # Refresh on tab load
            interface.load(
                fn=self._refresh_backups,
                outputs=[backups_table],
            )

        return interface
