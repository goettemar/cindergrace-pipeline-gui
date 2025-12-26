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

        if update_available and version_info:
            self._latest_version_info = version_info
            status_md = f"""### ✨ Update verfügbar!

**Aktuelle Version:** v{current}
**Neue Version:** v{version_info.version}

Veröffentlicht: {version_info.published_at[:10] if version_info.published_at else 'Unbekannt'}
"""
            changelog_md = f"""### Changelog v{version_info.version}

{version_info.body}

---
[Release auf GitHub öffnen]({version_info.download_url})
"""
            return status_md, changelog_md, gr.update(interactive=True), f"📥 Update auf v{version_info.version}"

        elif version_info:
            status_md = f"""### ✅ Bereits aktuell

**Aktuelle Version:** v{current}

{message}
"""
            changelog_md = f"""### Letzte Version: v{version_info.version}

{version_info.body}
"""
            return status_md, changelog_md, gr.update(interactive=False), "📥 Kein Update verfügbar"

        else:
            status_md = f"""### ⚠️ Update-Check fehlgeschlagen

**Aktuelle Version:** v{current}

{message}
"""
            return status_md, "", gr.update(interactive=False), "📥 Update nicht möglich"

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
            return "❌ Kein Update-Info verfügbar. Bitte zuerst auf Updates prüfen."

        version_info = self._latest_version_info

        # Step 1: Create backup
        progress(0.1, desc="Erstelle Backup...")
        success, msg = self.updater.create_backup()
        if not success:
            return f"❌ Backup fehlgeschlagen: {msg}"

        # Step 2: Download update
        progress(0.3, desc="Lade Update herunter...")
        success, msg, download_path = self.updater.download_update(version_info)
        if not success or not download_path:
            return f"❌ Download fehlgeschlagen: {msg}"

        # Step 3: Apply update
        progress(0.6, desc="Wende Update an...")
        success, msg = self.updater.apply_update(download_path, version_info.version)
        if not success:
            return f"❌ Update fehlgeschlagen: {msg}"

        # Step 4: Update dependencies
        progress(0.9, desc="Aktualisiere Dependencies...")
        success, dep_msg = self.updater.update_dependencies()

        progress(1.0, desc="Fertig!")

        if success:
            return f"""✅ **Update auf v{version_info.version} erfolgreich!**

{msg}

**Dependencies:** {dep_msg}

⚠️ **Bitte starte die GUI neu, um die Änderungen zu aktivieren.**
"""
        else:
            return f"""⚠️ **Update installiert, aber Dependencies-Problem:**

{msg}

**Dependencies:** {dep_msg}

Bitte manuell ausführen: `pip install -r requirements.txt`
"""

    def _perform_rollback(self, backup_selection: str) -> str:
        """Perform rollback to selected backup."""
        if not backup_selection:
            return "❌ Bitte wähle ein Backup zum Wiederherstellen."

        backups = self.updater.get_available_backups()
        choices = self._get_backup_choices()

        try:
            idx = choices.index(backup_selection)
            backup = backups[idx]
        except (ValueError, IndexError):
            return "❌ Backup nicht gefunden."

        success, msg = self.updater.rollback(backup)

        if success:
            return f"""✅ **Rollback erfolgreich!**

{msg}

⚠️ **Bitte starte die GUI neu, um die Änderungen zu aktivieren.**
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
Verwalte Updates, erstelle Backups und stelle vorherige Versionen wieder her.
            """)

            with gr.Row():
                # Left column: Update check
                with gr.Column(scale=1):
                    gr.Markdown("### 🔍 Update-Check")

                    check_btn = gr.Button("🔍 Auf Updates prüfen", variant="primary", size="lg")

                    status_md = gr.Markdown(f"""### Aktuelle Version: v{current_version}

Klicke auf "Auf Updates prüfen" um nach neuen Versionen zu suchen.
""")

                    update_btn = gr.Button(
                        "📥 Kein Update verfügbar",
                        variant="secondary",
                        size="lg",
                        interactive=False,
                    )

                    update_status = gr.Markdown("")

                # Right column: Changelog
                with gr.Column(scale=1):
                    gr.Markdown("### 📋 Changelog")

                    changelog_md = gr.Markdown("""
*Prüfe auf Updates, um den Changelog anzuzeigen.*
""")

            gr.Markdown("---")

            with gr.Row():
                # Backup section
                with gr.Column(scale=1):
                    gr.Markdown("### 💾 Backups")

                    with gr.Row():
                        backup_btn = gr.Button("💾 Backup erstellen", variant="secondary")
                        refresh_backups_btn = gr.Button("🔄", scale=0, min_width=50)

                    backup_status = gr.Markdown("")

                    backups_table = gr.Dataframe(
                        headers=["Version", "Erstellt", "Größe", "Datei"],
                        datatype=["str", "str", "str", "str"],
                        value=self._format_backups_table(backups),
                        interactive=False,
                        row_count=(3, "fixed"),
                    )

                # Rollback section
                with gr.Column(scale=1):
                    gr.Markdown("### ↩️ Rollback")

                    gr.Markdown("Stelle eine frühere Version aus einem Backup wieder her:")

                    rollback_dropdown = gr.Dropdown(
                        choices=self._get_backup_choices(),
                        label="Backup auswählen",
                        interactive=True,
                    )

                    rollback_btn = gr.Button(
                        "↩️ Rollback durchführen",
                        variant="stop",
                    )

                    rollback_status = gr.Markdown("")

            # Info section
            with gr.Accordion("ℹ️ Hinweise", open=False):
                gr.Markdown(f"""
### Backup-Strategie

- Backups werden unter `~/.cindergrace/backups/` gespeichert
- Nur Source-Code wird gesichert (~5-10 MB pro Backup)
- `.venv`, `__pycache__`, `.git` werden **nicht** gesichert
- Die letzten {self.updater._cleanup_old_backups.__defaults__} Backups werden aufbewahrt

### Update-Prozess

1. **Backup erstellen** - Aktuelle Version wird automatisch gesichert
2. **Download** - Neue Version von GitHub herunterladen
3. **Installation** - Dateien aktualisieren (venv bleibt erhalten)
4. **Dependencies** - `pip install -r requirements.txt` ausführen
5. **Neustart** - GUI muss manuell neu gestartet werden

### Rollback

Bei Problemen mit einer neuen Version:
1. Backup aus der Liste wählen
2. "Rollback durchführen" klicken
3. GUI neu starten

**Hinweis:** Vor jedem Rollback wird automatisch ein Backup der aktuellen Version erstellt.
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
