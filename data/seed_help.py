#!/usr/bin/env python3
"""Seed-Script zum Befüllen der Help-Datenbank mit initialen deutschen Texten."""
import sys
from pathlib import Path

# Projekt-Root zum Pfad hinzufügen
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from infrastructure.help_service import HelpService


def seed_database():
    """Befüllt die Help-Datenbank mit initialen Texten."""
    service = HelpService(language="de")

    # ===== TAB INFORMATIONEN =====

    service.add_tab_info(
        tab="setup_wizard",
        title="Setup-Assistent",
        description="Willkommen bei CINDERGRACE! Dieser Assistent hilft Ihnen bei der Ersteinrichtung.",
    )

    service.add_tab_info(
        tab="project",
        title="Projektverwaltung",
        description="Erstellen und verwalten Sie Ihre Videoprojekte. Jedes Projekt speichert alle zugehörigen Dateien an einem Ort.",
    )

    service.add_tab_info(
        tab="keyframe_generator",
        title="Keyframe-Generator",
        description="Generieren Sie Keyframes (Standbilder) für jeden Shot Ihres Storyboards mit Flux Dev.",
    )

    service.add_tab_info(
        tab="keyframe_selector",
        title="Keyframe-Auswahl",
        description="Wählen Sie die besten Keyframe-Varianten für jeden Shot aus.",
    )

    service.add_tab_info(
        tab="video_generator",
        title="Video-Generator",
        description="Generieren Sie Videos aus Ihren ausgewählten Keyframes mit Wan 2.2.",
    )

    service.add_tab_info(
        tab="settings",
        title="Einstellungen",
        description="Konfigurieren Sie ComfyUI-Verbindung, Pfade und Workflow-Presets.",
    )

    # ===== GEMEINSAME FELDER (common) =====

    service.add_help_text(
        tab="common",
        field="comfyui_url",
        text_type="tooltip",
        content="URL zum laufenden ComfyUI-Server (Standard: http://127.0.0.1:8188)",
    )

    service.add_help_text(
        tab="common",
        field="comfyui_url",
        text_type="modal",
        content="""## ComfyUI-Server URL

ComfyUI muss gestartet sein, bevor Sie CINDERGRACE verwenden können.

**Standard-URL:** `http://127.0.0.1:8188`

### ComfyUI starten:
```bash
cd /pfad/zu/ComfyUI
python main.py --listen 127.0.0.1 --port 8188
```

### Verbindung testen:
Nutzen Sie den Tab "Test ComfyUI" um die Verbindung zu überprüfen.
""",
    )

    service.add_help_text(
        tab="common",
        field="comfyui_root",
        text_type="tooltip",
        content="Installationsverzeichnis von ComfyUI (z.B. /home/user/ComfyUI)",
    )

    service.add_help_text(
        tab="common",
        field="comfyui_root",
        text_type="modal",
        content="""## ComfyUI-Installationsverzeichnis

Geben Sie hier den Pfad an, in dem ComfyUI installiert ist.

**Beispiele:**
- Linux: `/home/benutzer/ComfyUI`
- Windows: `C:\\Users\\Benutzer\\ComfyUI`
- Windows Portable: `D:\\ComfyUI_portable`

Dieser Pfad wird benötigt um:
- Modelle zu validieren
- Output-Verzeichnisse zu finden
- Workflow-Templates zu laden
""",
    )

    service.add_help_text(
        tab="common",
        field="storyboard",
        text_type="tooltip",
        content="JSON-Datei mit Shot-Definitionen (Prompts, Auflösung, Dauer)",
    )

    service.add_help_text(
        tab="common",
        field="storyboard",
        text_type="modal",
        content="""## Storyboard-Datei

Das Storyboard ist eine JSON-Datei, die alle Shots Ihres Videos definiert.

**Jeder Shot enthält:**
- `shot_id`: Eindeutige Nummer (z.B. "001")
- `filename_base`: Name für Dateien (z.B. "cathedral-interior")
- `prompt`: Beschreibung für die KI
- `width`, `height`: Auflösung in Pixeln
- `duration`: Dauer in Sekunden
- `camera_movement`: Kamerabewegung (optional)

**Beispiel:**
```json
{
  "shot_id": "001",
  "filename_base": "opening-scene",
  "prompt": "Eine gotische Kathedrale im Morgenlicht...",
  "width": 1024,
  "height": 576,
  "duration": 4.0
}
```
""",
    )

    # ===== SETUP WIZARD =====

    service.add_help_text(
        tab="setup_wizard",
        field="welcome",
        text_type="modal",
        content="""## Willkommen bei CINDERGRACE!

CINDERGRACE ist eine Benutzeroberfläche für die automatisierte Videoproduktion mit KI.

**Was Sie benötigen:**
1. **ComfyUI** - Die KI-Backend-Software
2. **Python 3.10+** - Programmiersprache
3. **NVIDIA GPU** - Mit CUDA-Unterstützung (empfohlen: 16GB VRAM)
4. **Git** - Für Updates (optional)
5. **ffmpeg** - Für Videobearbeitung

Dieser Assistent führt Sie durch die Einrichtung.
""",
    )

    service.add_help_text(
        tab="setup_wizard",
        field="python",
        text_type="tooltip",
        content="Python 3.10 oder höher wird benötigt",
    )

    service.add_help_text(
        tab="setup_wizard",
        field="nvidia",
        text_type="tooltip",
        content="NVIDIA-Grafikkarte mit CUDA-Unterstützung",
    )

    service.add_help_text(
        tab="setup_wizard",
        field="git",
        text_type="tooltip",
        content="Git für Updates (optional, aber empfohlen)",
    )

    service.add_help_text(
        tab="setup_wizard",
        field="ffmpeg",
        text_type="tooltip",
        content="ffmpeg für Video-Extraktion und -Bearbeitung",
    )

    service.add_help_text(
        tab="setup_wizard",
        field="comfyui_install",
        text_type="modal",
        content="""## ComfyUI Installation

### Windows (Portable)
1. Laden Sie die Portable-Version herunter:
   https://github.com/comfyanonymous/ComfyUI/releases
2. Entpacken Sie das Archiv
3. Starten Sie `run_nvidia_gpu.bat`

### Windows (Git)
```powershell
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI
python -m venv venv
venv\\Scripts\\activate
pip install -r requirements.txt
python main.py
```

### Linux
```bash
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py --listen 127.0.0.1
```

**Wichtig:** Nach der Installation müssen Sie noch die KI-Modelle herunterladen.
Siehe: https://github.com/comfyanonymous/ComfyUI#installing-models
""",
    )

    # ===== PROJECT TAB =====

    service.add_help_text(
        tab="project",
        field="project_name",
        text_type="tooltip",
        content="Eindeutiger Name für Ihr Projekt (wird als Ordnername verwendet)",
    )

    service.add_help_text(
        tab="project",
        field="project_name",
        text_type="modal",
        content="""## Projektname

Der Projektname wird als Ordnername verwendet und sollte:
- Keine Sonderzeichen enthalten
- Eindeutig sein
- Beschreibend sein

**Beispiele:**
- `musikvideo-winter`
- `kurzfilm-szene1`
- `test-animation`

Der Projektordner wird unter `<ComfyUI>/output/<projektname>/` erstellt.
""",
    )

    # ===== KEYFRAME GENERATOR =====

    service.add_help_text(
        tab="keyframe_generator",
        field="workflow",
        text_type="tooltip",
        content="ComfyUI-Workflow für die Bildgenerierung",
    )

    service.add_help_text(
        tab="keyframe_generator",
        field="variants",
        text_type="tooltip",
        content="Anzahl der Varianten pro Shot (mehr = mehr Auswahl, aber längere Generierung)",
    )

    service.add_help_text(
        tab="keyframe_generator",
        field="seed",
        text_type="tooltip",
        content="Zufallsseed für reproduzierbare Ergebnisse (-1 = zufällig)",
    )

    # ===== KEYFRAME SELECTOR =====

    service.add_help_text(
        tab="keyframe_selector",
        field="selection",
        text_type="tooltip",
        content="Klicken Sie auf eine Variante um sie auszuwählen",
    )

    service.add_help_text(
        tab="keyframe_selector",
        field="export",
        text_type="tooltip",
        content="Exportiert alle Auswahlen in den 'selected'-Ordner",
    )

    # ===== VIDEO GENERATOR =====

    service.add_help_text(
        tab="video_generator",
        field="workflow",
        text_type="tooltip",
        content="ComfyUI-Workflow für die Videogenerierung (Wan 2.2)",
    )

    service.add_help_text(
        tab="video_generator",
        field="fps",
        text_type="tooltip",
        content="Bilder pro Sekunde (Standard: 24)",
    )

    service.add_help_text(
        tab="video_generator",
        field="segment_duration",
        text_type="tooltip",
        content="Maximale Länge eines Video-Segments (längere Shots werden aufgeteilt)",
    )

    service.add_help_text(
        tab="video_generator",
        field="segment_duration",
        text_type="modal",
        content="""## Video-Segmentierung

Wan 2.2 kann Videos bis zu einer bestimmten Länge generieren.
Längere Shots werden automatisch in Segmente aufgeteilt.

**Wie funktioniert es:**
1. Shot ist länger als max. Segment-Dauer
2. Erstes Segment wird generiert
3. Letztes Frame wird extrahiert
4. Nächstes Segment startet mit diesem Frame
5. Ergebnis: Nahtlose Übergänge

**Standard:** 3 Sekunden pro Segment
""",
    )

    # ===== SETTINGS =====

    service.add_help_text(
        tab="settings",
        field="timeout",
        text_type="tooltip",
        content="Maximale Wartezeit für ComfyUI-Jobs in Sekunden",
    )

    service.add_help_text(
        tab="settings",
        field="retry",
        text_type="tooltip",
        content="Anzahl der Wiederholungsversuche bei Fehlern",
    )

    # ===== PROJECT TAB - RESOLUTION =====

    service.add_help_text(
        tab="project",
        field="global_resolution",
        text_type="tooltip",
        content="Globale Auflösung für alle Shots. Wan unterstützt 480p, 720p, 1080p.",
    )

    service.add_help_text(
        tab="project",
        field="global_resolution",
        text_type="modal",
        content="""## Auflösungs-Matrix

### Für Wan 2.2 Video-Workflows (gcv_*)

| Auflösung | Format | VRAM | Empfehlung |
|-----------|--------|------|------------|
| **1280×720** | 16:9 Landscape | 12GB+ | ⭐ **Standard** (YouTube, TV) |
| **720×1280** | 9:16 Portrait | 12GB+ | TikTok, Reels, Shorts |
| **832×480** | 16:9 Landscape | 8GB+ | Schnelle Tests, niedriger VRAM |
| **480×832** | 9:16 Portrait | 8GB+ | Portrait-Tests |
| **1920×1080** | 16:9 Landscape | 24GB+ | Beste Qualität, hoher VRAM |
| **1080×1920** | 9:16 Portrait | 24GB+ | Portrait HD |

### Für SDXL Keyframe-Workflows (gcp_sdxl_*)

| Auflösung | Format | VRAM | Empfehlung |
|-----------|--------|------|------------|
| **1024×1024** | 1:1 Quadrat | 6GB+ | ⭐ **Native SDXL** (beste Qualität) |
| **512×512** | 1:1 Quadrat | 4GB+ | Schnelle Tests |

⚠️ **Wichtig:** SDXL wurde für 1024×1024 trainiert. Andere Auflösungen können zu Artefakten führen!

### Für Flux Keyframe-Workflows (gcp_flux_*)

| Auflösung | Format | VRAM | Empfehlung |
|-----------|--------|------|------------|
| **1280×720** | 16:9 Landscape | 16GB+ | ⭐ **Video-optimiert** (passt zu Wan) |
| **720×1280** | 9:16 Portrait | 16GB+ | Portrait-Videos |
| **1024×1024** | 1:1 Quadrat | 16GB+ | Bilder ohne Video |

### Empfehlungen nach GPU

| GPU VRAM | Keyframes | Videos |
|----------|-----------|--------|
| **6-8GB** | SDXL 1024×1024 | Wan 480p |
| **12-16GB** | Flux 720p | Wan 720p |
| **24GB+** | Flux 1080p | Wan 1080p |

### Tipp
Wählen Sie die Auflösung **vor** der Keyframe-Generierung. Die Keyframes und Videos sollten dieselbe Auflösung haben für beste Ergebnisse.
""",
    )

    print("Help-Texte erfolgreich in Datenbank geschrieben!")
    print(f"Datenbank: {service.db_path}")

    # Zeige Statistik
    import sqlite3

    conn = sqlite3.connect(service.db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM help_texts")
    text_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM tab_info")
    tab_count = cursor.fetchone()[0]
    conn.close()

    print(f"Einträge: {text_count} Hilfetexte, {tab_count} Tab-Infos")


if __name__ == "__main__":
    seed_database()
