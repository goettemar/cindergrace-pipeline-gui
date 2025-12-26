"""Updater Service - Check for updates, backup, update and rollback.

This service handles:
- Version checking against GitHub releases
- Creating backups before updates
- Downloading and applying updates
- Rolling back to previous versions
"""

import os
import json
import shutil
import tarfile
import tempfile
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, List, NamedTuple
from dataclasses import dataclass
import urllib.request
import urllib.error

from infrastructure.logger import get_logger

logger = get_logger(__name__)

# GitHub repository info
GITHUB_OWNER = "goettemar"
GITHUB_REPO = "cindergrace-pipeline-gui"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases"

# Backup settings
BACKUP_DIR = Path.home() / ".cindergrace" / "backups"
MAX_BACKUPS = 3  # Keep last N backups

# Files/dirs to exclude from backup
BACKUP_EXCLUDES = [
    ".venv",
    "__pycache__",
    ".git",
    "*.pyc",
    ".pytest_cache",
    "logs/*.log",
    "htmlcov",
    ".coverage",
    "coverage.xml",
    "data/*.db",  # Keep databases separate
]


@dataclass
class VersionInfo:
    """Version information."""
    version: str
    tag_name: str
    name: str
    body: str  # Release notes / changelog
    published_at: str
    download_url: str
    tarball_url: str


@dataclass
class BackupInfo:
    """Backup information."""
    version: str
    path: Path
    created_at: datetime
    size_mb: float


class UpdaterService:
    """Service for managing application updates."""

    def __init__(self, app_dir: Optional[Path] = None):
        """Initialize updater service.

        Args:
            app_dir: Application directory (default: current working directory)
        """
        self.app_dir = Path(app_dir) if app_dir else Path.cwd()
        self.version_file = self.app_dir / "VERSION"
        self.backup_dir = BACKUP_DIR
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def get_current_version(self) -> str:
        """Get current installed version from VERSION file.

        Returns:
            Version string (e.g., "0.6.0")
        """
        try:
            if self.version_file.exists():
                return self.version_file.read_text().strip()
            return "0.0.0"
        except Exception as e:
            logger.error(f"Failed to read version file: {e}")
            return "0.0.0"

    def check_for_updates(self) -> Tuple[bool, Optional[VersionInfo], str]:
        """Check GitHub releases for available updates.

        Returns:
            Tuple of (update_available, version_info, message)
        """
        current = self.get_current_version()
        logger.info(f"Checking for updates... Current version: {current}")

        try:
            # Fetch latest release from GitHub
            req = urllib.request.Request(
                f"{GITHUB_API_URL}/latest",
                headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "CINDERGRACE-Updater"}
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())

            latest_tag = data.get("tag_name", "").lstrip("v")

            if not latest_tag:
                return False, None, "Konnte Version nicht ermitteln"

            version_info = VersionInfo(
                version=latest_tag,
                tag_name=data.get("tag_name", ""),
                name=data.get("name", f"Version {latest_tag}"),
                body=data.get("body", "Keine Release Notes verfügbar"),
                published_at=data.get("published_at", ""),
                download_url=data.get("html_url", ""),
                tarball_url=data.get("tarball_url", ""),
            )

            # Compare versions
            if self._version_compare(latest_tag, current) > 0:
                logger.info(f"Update available: {current} -> {latest_tag}")
                return True, version_info, f"Update verfügbar: v{latest_tag}"
            else:
                logger.info(f"Already up to date: {current}")
                return False, version_info, f"Bereits aktuell (v{current})"

        except urllib.error.URLError as e:
            msg = f"Netzwerkfehler: {e.reason}"
            logger.error(msg)
            return False, None, msg
        except Exception as e:
            msg = f"Fehler beim Update-Check: {str(e)}"
            logger.error(msg, exc_info=True)
            return False, None, msg

    def _version_compare(self, v1: str, v2: str) -> int:
        """Compare two version strings.

        Returns:
            1 if v1 > v2, -1 if v1 < v2, 0 if equal
        """
        def parse_version(v: str) -> List[int]:
            return [int(x) for x in v.split(".")]

        try:
            parts1 = parse_version(v1)
            parts2 = parse_version(v2)

            # Pad shorter version with zeros
            max_len = max(len(parts1), len(parts2))
            parts1.extend([0] * (max_len - len(parts1)))
            parts2.extend([0] * (max_len - len(parts2)))

            for p1, p2 in zip(parts1, parts2):
                if p1 > p2:
                    return 1
                if p1 < p2:
                    return -1
            return 0
        except ValueError:
            return 0

    def create_backup(self, version: Optional[str] = None) -> Tuple[bool, str]:
        """Create backup of current installation.

        Args:
            version: Version label for backup (default: current version)

        Returns:
            Tuple of (success, message)
        """
        version = version or self.get_current_version()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"v{version}_{timestamp}_source.tar.gz"
        backup_path = self.backup_dir / backup_name

        logger.info(f"Creating backup: {backup_path}")

        try:
            # Create tar.gz excluding large/unnecessary files
            with tarfile.open(backup_path, "w:gz") as tar:
                for item in self.app_dir.iterdir():
                    # Check exclusions
                    if self._should_exclude(item):
                        continue
                    tar.add(item, arcname=item.name)

            size_mb = backup_path.stat().st_size / (1024 * 1024)
            logger.info(f"Backup created: {backup_path} ({size_mb:.1f} MB)")

            # Cleanup old backups
            self._cleanup_old_backups()

            return True, f"Backup erstellt: {backup_name} ({size_mb:.1f} MB)"

        except Exception as e:
            msg = f"Backup fehlgeschlagen: {str(e)}"
            logger.error(msg, exc_info=True)
            return False, msg

    def _should_exclude(self, path: Path) -> bool:
        """Check if path should be excluded from backup."""
        name = path.name

        # Direct name matches - large/unnecessary directories
        exclude_names = {
            ".venv",
            "__pycache__",
            ".git",
            ".pytest_cache",
            "htmlcov",
            ".coverage",
            "coverage.xml",
            "tools",           # sd-scripts and other large tools (~500MB)
            "data",            # databases and generated data
            "temp",            # temporary files
            "logs",            # log files
            "node_modules",    # npm (if any)
            ".mypy_cache",
            ".ruff_cache",
            "runpod",          # runpod scripts
            "colab",           # colab notebooks
            "output",          # test output images
        }
        if name in exclude_names:
            return True

        # Pattern matches
        if name.endswith(".pyc"):
            return True
        if name.endswith(".log"):
            return True
        if name.endswith(".db"):
            return True

        return False

    def _cleanup_old_backups(self):
        """Remove old backups, keeping only MAX_BACKUPS most recent."""
        backups = sorted(self.backup_dir.glob("*.tar.gz"), key=lambda p: p.stat().st_mtime, reverse=True)

        for old_backup in backups[MAX_BACKUPS:]:
            try:
                old_backup.unlink()
                logger.info(f"Removed old backup: {old_backup.name}")
            except Exception as e:
                logger.warning(f"Failed to remove old backup {old_backup}: {e}")

    def get_available_backups(self) -> List[BackupInfo]:
        """Get list of available backups for rollback.

        Returns:
            List of BackupInfo sorted by date (newest first)
        """
        backups = []

        for backup_file in self.backup_dir.glob("*.tar.gz"):
            try:
                # Parse version from filename: v0.6.0_20251226_180932_source.tar.gz
                name = backup_file.stem.replace("_source", "")
                parts = name.split("_")
                version = parts[0].lstrip("v") if parts else "unknown"

                stat = backup_file.stat()
                created = datetime.fromtimestamp(stat.st_mtime)
                size_mb = stat.st_size / (1024 * 1024)

                backups.append(BackupInfo(
                    version=version,
                    path=backup_file,
                    created_at=created,
                    size_mb=size_mb,
                ))
            except Exception as e:
                logger.warning(f"Failed to parse backup info for {backup_file}: {e}")

        return sorted(backups, key=lambda b: b.created_at, reverse=True)

    def rollback(self, backup: BackupInfo) -> Tuple[bool, str]:
        """Rollback to a previous backup.

        Args:
            backup: BackupInfo to restore

        Returns:
            Tuple of (success, message)
        """
        logger.info(f"Rolling back to backup: {backup.path}")

        if not backup.path.exists():
            return False, f"Backup nicht gefunden: {backup.path}"

        try:
            # First, create a backup of current state
            self.create_backup()

            # Extract backup to temp directory first
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                with tarfile.open(backup.path, "r:gz") as tar:
                    tar.extractall(temp_path)

                # Remove current files (except excluded)
                for item in self.app_dir.iterdir():
                    if self._should_exclude(item):
                        continue
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()

                # Copy extracted files
                for item in temp_path.iterdir():
                    dest = self.app_dir / item.name
                    if item.is_dir():
                        shutil.copytree(item, dest)
                    else:
                        shutil.copy2(item, dest)

            logger.info(f"Rollback complete to version {backup.version}")
            return True, f"Rollback auf v{backup.version} erfolgreich"

        except Exception as e:
            msg = f"Rollback fehlgeschlagen: {str(e)}"
            logger.error(msg, exc_info=True)
            return False, msg

    def download_update(self, version_info: VersionInfo) -> Tuple[bool, str, Optional[Path]]:
        """Download update from GitHub.

        Args:
            version_info: Version information with download URL

        Returns:
            Tuple of (success, message, download_path)
        """
        logger.info(f"Downloading update: {version_info.version}")

        try:
            # Download tarball
            download_dir = self.backup_dir / "downloads"
            download_dir.mkdir(exist_ok=True)

            download_path = download_dir / f"update_{version_info.version}.tar.gz"

            req = urllib.request.Request(
                version_info.tarball_url,
                headers={"User-Agent": "CINDERGRACE-Updater"}
            )

            with urllib.request.urlopen(req, timeout=60) as response:
                with open(download_path, "wb") as f:
                    f.write(response.read())

            size_mb = download_path.stat().st_size / (1024 * 1024)
            logger.info(f"Download complete: {download_path} ({size_mb:.1f} MB)")

            return True, f"Download abgeschlossen ({size_mb:.1f} MB)", download_path

        except Exception as e:
            msg = f"Download fehlgeschlagen: {str(e)}"
            logger.error(msg, exc_info=True)
            return False, msg, None

    def apply_update(self, download_path: Path, version: str) -> Tuple[bool, str]:
        """Apply downloaded update.

        Args:
            download_path: Path to downloaded tarball
            version: New version string

        Returns:
            Tuple of (success, message)
        """
        logger.info(f"Applying update from: {download_path}")

        try:
            # Create backup first
            success, msg = self.create_backup()
            if not success:
                return False, f"Backup vor Update fehlgeschlagen: {msg}"

            # Extract to temp directory
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                with tarfile.open(download_path, "r:gz") as tar:
                    tar.extractall(temp_path)

                # GitHub tarballs have a root folder like "repo-name-version/"
                extracted_dirs = list(temp_path.iterdir())
                if len(extracted_dirs) == 1 and extracted_dirs[0].is_dir():
                    source_dir = extracted_dirs[0]
                else:
                    source_dir = temp_path

                # Copy new files (preserving excluded directories)
                for item in source_dir.iterdir():
                    dest = self.app_dir / item.name

                    # Skip if excluded
                    if self._should_exclude(item):
                        continue

                    # Remove old version
                    if dest.exists():
                        if dest.is_dir():
                            shutil.rmtree(dest)
                        else:
                            dest.unlink()

                    # Copy new version
                    if item.is_dir():
                        shutil.copytree(item, dest)
                    else:
                        shutil.copy2(item, dest)

            # Update VERSION file
            self.version_file.write_text(version + "\n")

            # Cleanup download
            download_path.unlink()

            logger.info(f"Update applied successfully: v{version}")
            return True, f"Update auf v{version} erfolgreich! Bitte GUI neu starten."

        except Exception as e:
            msg = f"Update fehlgeschlagen: {str(e)}"
            logger.error(msg, exc_info=True)
            return False, msg

    def update_dependencies(self) -> Tuple[bool, str]:
        """Run pip install to update dependencies after update.

        Returns:
            Tuple of (success, message)
        """
        requirements_file = self.app_dir / "requirements.txt"

        if not requirements_file.exists():
            return True, "Keine requirements.txt gefunden"

        try:
            logger.info("Updating dependencies...")

            # Use the venv python if available
            venv_pip = self.app_dir / ".venv" / "bin" / "pip"
            pip_cmd = str(venv_pip) if venv_pip.exists() else "pip"

            result = subprocess.run(
                [pip_cmd, "install", "-r", str(requirements_file), "--quiet"],
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode == 0:
                logger.info("Dependencies updated successfully")
                return True, "Dependencies aktualisiert"
            else:
                msg = f"pip install fehlgeschlagen: {result.stderr}"
                logger.error(msg)
                return False, msg

        except subprocess.TimeoutExpired:
            return False, "Timeout beim Aktualisieren der Dependencies"
        except Exception as e:
            msg = f"Fehler beim Aktualisieren der Dependencies: {str(e)}"
            logger.error(msg, exc_info=True)
            return False, msg


# Singleton instance
_updater_service: Optional[UpdaterService] = None


def get_updater_service() -> UpdaterService:
    """Get or create the updater service singleton."""
    global _updater_service
    if _updater_service is None:
        _updater_service = UpdaterService()
    return _updater_service
