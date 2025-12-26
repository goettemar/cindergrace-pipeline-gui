"""System Detector Service - Erkennt OS und Abhängigkeiten."""
import platform
import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional

from infrastructure.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DependencyStatus:
    """Status einer Abhängigkeit."""

    name: str
    installed: bool
    version: Optional[str] = None
    path: Optional[str] = None
    required: bool = True
    message: str = ""


class SystemDetector:
    """Service zur Erkennung von Betriebssystem und Abhängigkeiten."""

    def get_os(self) -> str:
        """Ermittelt das Betriebssystem.

        Returns:
            'windows', 'linux' oder 'macos'
        """
        system = platform.system().lower()
        if system == "darwin":
            return "macos"
        return system

    def get_os_version(self) -> str:
        """Ermittelt die OS-Version.

        Returns:
            Versionsstring (z.B. '10.15.7' für macOS, '10' für Windows)
        """
        return platform.version()

    def get_architecture(self) -> str:
        """Ermittelt die CPU-Architektur.

        Returns:
            Architektur (z.B. 'x86_64', 'arm64')
        """
        return platform.machine()

    def check_python(self) -> DependencyStatus:
        """Prüft Python-Installation.

        Returns:
            DependencyStatus für Python
        """
        version = platform.python_version()
        major, minor = map(int, version.split(".")[:2])

        status = DependencyStatus(
            name="Python",
            installed=True,
            version=version,
            path=shutil.which("python3") or shutil.which("python"),
            required=True,
        )

        if major < 3 or (major == 3 and minor < 10):
            status.message = f"Python 3.10+ empfohlen (aktuell: {version})"
        else:
            status.message = "OK"

        return status

    def check_nvidia(self) -> DependencyStatus:
        """Prüft NVIDIA-Treiber und CUDA.

        Returns:
            DependencyStatus für NVIDIA/CUDA
        """
        status = DependencyStatus(
            name="NVIDIA GPU",
            installed=False,
            required=True,
        )

        # Prüfe nvidia-smi
        nvidia_smi = shutil.which("nvidia-smi")
        if not nvidia_smi:
            status.message = "NVIDIA-Treiber nicht gefunden"
            return status

        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                output = result.stdout.strip()
                if output:
                    parts = output.split(",")
                    gpu_name = parts[0].strip() if parts else "Unbekannt"
                    driver_version = parts[1].strip() if len(parts) > 1 else ""

                    status.installed = True
                    status.version = driver_version
                    status.path = nvidia_smi
                    status.message = f"{gpu_name}"
                    return status

            status.message = "nvidia-smi Fehler"
        except subprocess.TimeoutExpired:
            status.message = "nvidia-smi Timeout"
        except Exception as e:
            status.message = f"Fehler: {e}"

        return status

    def check_cuda(self) -> DependencyStatus:
        """Prüft CUDA-Installation.

        Returns:
            DependencyStatus für CUDA
        """
        status = DependencyStatus(
            name="CUDA",
            installed=False,
            required=True,
        )

        # Prüfe nvcc (CUDA Compiler)
        nvcc = shutil.which("nvcc")
        if nvcc:
            try:
                result = subprocess.run(
                    ["nvcc", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    # Parse Version aus Output
                    for line in result.stdout.split("\n"):
                        if "release" in line.lower():
                            # z.B. "Cuda compilation tools, release 12.1, V12.1.66"
                            parts = line.split("release")
                            if len(parts) > 1:
                                version = parts[1].split(",")[0].strip()
                                status.installed = True
                                status.version = version
                                status.path = nvcc
                                status.message = "OK"
                                return status
            except Exception:
                pass

        # Alternativ: Prüfe über nvidia-smi
        try:
            result = subprocess.run(
                ["nvidia-smi"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                # CUDA Version aus nvidia-smi Header
                for line in result.stdout.split("\n"):
                    if "CUDA Version" in line:
                        # z.B. "| NVIDIA-SMI 535.129.03   Driver Version: 535.129.03   CUDA Version: 12.2     |"
                        parts = line.split("CUDA Version:")
                        if len(parts) > 1:
                            version = parts[1].strip().rstrip("|").strip()
                            status.installed = True
                            status.version = version
                            status.message = "OK (via nvidia-smi)"
                            return status
        except Exception:
            pass

        status.message = "CUDA nicht gefunden"
        return status

    def check_git(self) -> DependencyStatus:
        """Prüft Git-Installation.

        Returns:
            DependencyStatus für Git
        """
        status = DependencyStatus(
            name="Git",
            installed=False,
            required=False,  # Optional, aber empfohlen
        )

        git = shutil.which("git")
        if not git:
            status.message = "Git nicht installiert (optional)"
            return status

        try:
            result = subprocess.run(
                ["git", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                # z.B. "git version 2.34.1"
                version = result.stdout.strip().replace("git version ", "")
                status.installed = True
                status.version = version
                status.path = git
                status.message = "OK"
        except Exception as e:
            status.message = f"Fehler: {e}"

        return status

    def check_ffmpeg(self) -> DependencyStatus:
        """Prüft ffmpeg-Installation.

        Returns:
            DependencyStatus für ffmpeg
        """
        status = DependencyStatus(
            name="ffmpeg",
            installed=False,
            required=True,
        )

        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            status.message = "ffmpeg nicht installiert"
            return status

        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                # z.B. "ffmpeg version 4.4.2-0ubuntu0.22.04.1"
                first_line = result.stdout.split("\n")[0]
                version = first_line.replace("ffmpeg version ", "").split(" ")[0]
                status.installed = True
                status.version = version
                status.path = ffmpeg
                status.message = "OK"
        except Exception as e:
            status.message = f"Fehler: {e}"

        return status

    def check_comfyui_connection(self, url: str = "http://127.0.0.1:8188") -> DependencyStatus:
        """Prüft ComfyUI-Verbindung.

        Args:
            url: ComfyUI-Server URL

        Returns:
            DependencyStatus für ComfyUI
        """
        import urllib.request
        import urllib.error

        status = DependencyStatus(
            name="ComfyUI",
            installed=False,
            required=True,
        )

        try:
            req = urllib.request.Request(f"{url}/system_stats", method="GET")
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    status.installed = True
                    status.path = url
                    status.message = "Verbunden"
                    return status
        except urllib.error.URLError:
            status.message = f"Keine Verbindung zu {url}"
        except Exception as e:
            status.message = f"Fehler: {e}"

        return status

    def get_system_summary(self, comfyui_url: str = "http://127.0.0.1:8188") -> dict:
        """Erstellt eine Zusammenfassung aller System-Checks.

        Args:
            comfyui_url: ComfyUI-Server URL

        Returns:
            Dict mit allen Check-Ergebnissen
        """
        os_name = self.get_os()

        summary = {
            "os": {
                "name": os_name,
                "version": self.get_os_version(),
                "architecture": self.get_architecture(),
                "display_name": {
                    "windows": "Windows",
                    "linux": "Linux",
                    "macos": "macOS",
                }.get(os_name, os_name),
            },
            "dependencies": {
                "python": self.check_python(),
                "nvidia": self.check_nvidia(),
                "cuda": self.check_cuda(),
                "git": self.check_git(),
                "ffmpeg": self.check_ffmpeg(),
                "comfyui": self.check_comfyui_connection(comfyui_url),
            },
        }

        # Zähle installierte/fehlende
        deps = summary["dependencies"]
        summary["stats"] = {
            "total": len(deps),
            "installed": sum(1 for d in deps.values() if d.installed),
            "missing_required": sum(
                1 for d in deps.values() if not d.installed and d.required
            ),
            "missing_optional": sum(
                1 for d in deps.values() if not d.installed and not d.required
            ),
        }

        summary["ready"] = summary["stats"]["missing_required"] == 0

        logger.info(
            f"System-Check: {summary['os']['display_name']}, "
            f"{summary['stats']['installed']}/{summary['stats']['total']} Abhängigkeiten OK"
        )

        return summary

    def get_status_icon(self, dep: DependencyStatus) -> str:
        """Gibt ein Status-Icon für eine Abhängigkeit zurück.

        Args:
            dep: DependencyStatus

        Returns:
            Status-Icon als String
        """
        if dep.installed:
            return "OK"
        elif dep.required:
            return "FEHLT"
        else:
            return "Optional"

    def format_dependency_line(self, dep: DependencyStatus) -> str:
        """Formatiert eine Abhängigkeit als Text-Zeile.

        Args:
            dep: DependencyStatus

        Returns:
            Formatierte Zeile
        """
        icon = self.get_status_icon(dep)
        version = f" ({dep.version})" if dep.version else ""
        message = f" - {dep.message}" if dep.message and dep.message != "OK" else ""

        return f"[{icon}] {dep.name}{version}{message}"
