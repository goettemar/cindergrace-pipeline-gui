# CINDERGRACE Pipeline GUI

[![CI](https://github.com/goettemar/cindergrace-pipeline-gui/workflows/CI%20Pipeline/badge.svg)](https://github.com/goettemar/cindergrace-pipeline-gui/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-76+-brightgreen.svg)](tests/)

**AI-powered video production pipeline** - Professional Gradio GUI for ComfyUI with Flux Dev and Wan 2.2 integration.

🔗 **[GitHub Repository](https://github.com/goettemar/cindergrace-pipeline-gui)** | 📖 **[Documentation](CONTRIBUTING.md)** | 🧪 **[Testing Guide](TESTING.md)**

---

## 🎯 Features at a Glance

### 🧪 Production-Ready Quality
- **76+ Tests** - Unit & integration tests with comprehensive fixtures
- **CI/CD Pipeline** - GitHub Actions with Python 3.10, 3.11, 3.12
- **Code Quality** - Automated linting, formatting, type checking
- **Pre-commit Hooks** - Automatic code formatting before commits
- **80%+ Target Coverage** - Robust test suite for core modules

### 🛡️ Enterprise-Grade Infrastructure
- **Input Validation** - Pydantic validators for all user inputs
- **Structured Logging** - Centralized logging with rotation (10MB, 5 backups)
- **Error Handling** - Custom exception hierarchy with decorators
- **State Persistence** - UI state survives browser refreshes
- **File Locking** - Prevents race conditions on concurrent access

### 🎬 Video Production Pipeline
- **Modular Architecture** - 6 self-contained addon tabs
- **Project-Centric Storage** - All artifacts organized by project
- **Keyframe Generation** - Flux Dev integration with variants
- **Video Synthesis** - Wan 2.2 with LastFrame chaining for long clips
- **Interactive Selection** - Gallery-based variant comparison

### 🔧 Developer Experience
- **Clean Architecture** - Domain/Infrastructure/Services separation
- **Type Safety** - Full type hints with mypy validation
- **Hot Reload** - Gradio supports live development
- **Comprehensive Docs** - CONTRIBUTING.md, TESTING.md, API docs

---

## ✨ System Features (v0.5.1)

### 🛡️ Input Validation mit Pydantic
- **Automatische Validierung** aller User-Eingaben (Projektnamen, FPS, Seeds, URLs)
- **Deutsche Fehlermeldungen** für bessere User Experience
- **Type Safety** garantiert korrekte Datentypen
- **Frühe Fehlerkennung** verhindert ungültige Operationen

### 📊 Strukturiertes Logging & Error Handling
- **Zentrale Logging-Infrastruktur** (`logs/pipeline.log`)
- **Log-Rotation** (10MB, 5 Backups)
- **Custom Exception Hierarchy** für präzise Fehlerbehandlung
- **Automatische Error Formatting** für UI-Ausgaben
- Siehe `LOGGING_ERROR_HANDLING.md` für Details

### 🔄 Intelligente Dependency-Verwaltung
- **start.sh** aktualisiert automatisch alle Dependencies
- **Kein manuelles pip install** mehr nötig
- **Virtual Environment** wird automatisch erstellt und aktiviert

### 🎨 Gradio 4.x Kompatibilität
- Vollständig kompatibel mit Gradio 4.0+
- Optimierte Gallery-Performance
- Moderne UI-Components

## 🚀 Quick Start

### 1. Setup

**Keine manuelle Installation nötig!** Das `start.sh` Script installiert automatisch alle Dependencies.

```bash
# (Optional) Manuell installieren:
pip install -r requirements.txt

# Add your ComfyUI workflow files
# Place your Flux/Wan workflow JSON files in:
# config/workflow_templates/
# Ein Wan 2.2 Beispiel-Workflow liegt bereits hier:
# config/workflow_templates/Wan 2.2 14B i2v.json
```

**Dependencies (automatisch installiert):**
- gradio >= 4.0.0
- pydantic >= 2.0.0 (Input-Validierung)
- websocket-client >= 1.6.0
- pillow >= 10.0.0
- numpy >= 1.24.0

### 2. Start ComfyUI

Make sure ComfyUI is running before launching the GUI:

```bash
cd /path/to/ComfyUI
python main.py --listen 127.0.0.1 --port 8188
```

## ⚙️ Settings & Workflow-Presets

- Tab **⚙️ Settings** (neu) erlaubt dir, `config/settings.json` direkt aus dem UI anzupassen (ComfyUI-URL & Installationspfad).
- In `config/workflow_presets.json` definierst du, welche Workflows in den einzelnen Tabs angezeigt werden (z.B. Kategorien `flux`, `wan`).
- Der ComfyUI-Installationspfad wird genutzt, um fehlende Modelle im Video Generator zu erkennen. Passe ihn auf dein Setup an, falls nötig.
- Storyboard-Auswahl **und** globale Auflösung (720p/1080p, Hoch/Quer) stellst du zentral im Tab **📁 Projekt** ein; alle Tabs übernehmen diese Werte.

### 3. Launch GUI

```bash
# Linux/Mac (empfohlen - installiert automatisch Dependencies)
./start.sh

# Or manually
python3 main.py
```

**Das start.sh Script:**
- ✅ Erstellt automatisch Virtual Environment (.venv)
- ✅ Aktiviert die venv
- ✅ Installiert/aktualisiert alle Dependencies
- ✅ Prüft ComfyUI-Verbindung
- ✅ Startet die GUI

The GUI will open at: **http://127.0.0.1:7860**

### 4. Projekt anlegen

- Öffne das Tab **📁 Projekt**.
- Lege einen neuen Projektnamen an oder wähle ein bestehendes Projekt aus der Liste.
- Der Ordner wird automatisch unter `<ComfyUI>/output/<projekt-slug>/` erstellt (inkl. `project.json`).
- Alle Pipeline-Tabs (Keyframes, Auswahl, Video) arbeiten ausschließlich innerhalb dieses Projektordners.

## 📁 Projektbasierter Workflow

1. **Projekt wählen** – Tab 📁 Projekt öffnen, neues Projekt erstellen oder bestehendes `project.json` auswählen. Das Dropdown zeigt automatisch alle Ordner unter `<ComfyUI>/output/`, die bereits eine Projektdatei besitzen.
2. **Storyboard & Workflow vorbereiten** – Storyboards bleiben wie bisher unter `config/`, alle Flux/Wan-Workflows liegen in `config/workflow_templates/`.
3. **Phase 1 (🎬 Keyframe Generator)** – Generierte PNGs landen direkt in `<ComfyUI>/output/<projekt>/keyframes/`, Checkpoints unter `.../checkpoints/`.
4. **Phase 2 (✅ Keyframe Selector)** – Lädt dieselben Keyframes aus dem Projektordner, exportiert JSON + Kopien nach `.../selected/selected_keyframes.json`.
5. **Phase 3 (🎥 Video Generator)** – Nutzt die Auswahl und schreibt Clips nach `.../video/`, inklusive `_startframes/`-Cache und per-Projekt `_state.json`.
6. **Tests / Debug (🧪 Test ComfyUI)** – Bleibt weiterhin vom Projekt entkoppelt und speichert nach `cindergrace_gui/output/test/`.

Damit bleiben alle produktionsrelevanten Artefakte direkt bei ComfyUI, während die GUI selbst weitgehend stateless bleibt.

## 📋 First Test

1. **Test Connection Tab:**
   - Click "🔌 Test Connection"
   - Verify you see ✅ Connected

2. **Generate Test Images:**
   - Enter a prompt (or use default)
   - Select workflow from dropdown
   - Set number of images: 4
   - Set starting seed: 1001
   - Click "🎨 Generate Test Images"

3. **Monitor Progress:**
   - Watch the progress bar
   - Images will appear in the gallery when complete

4. **Check Results:**
   - Images saved to `cindergrace_gui/output/test/`
   - Gallery shows all generated images with seeds

## 📁 Project Structure

```
cindergrace_gui/
├── main.py                      # Launch this file
├── start.sh                     # Convenience launcher (auto-install dependencies)
├── requirements.txt             # Python dependencies (auto-installed)
├── addons/                      # Addon modules (UI tabs)
├── domain/                      # Domain models & validators
│   ├── exceptions.py            # Custom exception hierarchy
│   ├── validators.py            # Pydantic validation models (NEW!)
│   └── models.py                # Domain data models
├── infrastructure/              # Core infrastructure
│   ├── logger.py                # Structured logging system (NEW!)
│   ├── error_handler.py         # Error handling decorators (NEW!)
│   ├── comfy_api.py             # ComfyUI API client
│   └── project_store.py         # Project management
├── services/                    # Business logic services
├── config/
│   ├── settings.json
│   ├── workflow_presets.json   # ← Workflow-Kategorien (flux/wan)
│   └── workflow_templates/     # ← PUT YOUR WORKFLOWS HERE
├── logs/                        # Log files (NEW!)
│   └── pipeline.log             # Rotating log file (10MB, 5 backups)
└── output/
    └── test/                    # Nur das Test-Tab schreibt hier hinein
```

### Projektordner unter ComfyUI

Alles, was zu deinem Projekt gehört, landet jetzt direkt bei ComfyUI:

```
<ComfyUI>/output/<projekt-slug>/
├── project.json          # Metadaten (Name, created_at, last_opened, …)
├── keyframes/            # Phase 1 Ergebnisse
├── checkpoints/          # Keyframe-Resume-Dateien
├── selected/             # Phase 2 Exporte (JSON + PNGs)
├── video/
│   ├── *.mp4/.webm       # Phase 3 Clips
│   └── _startframes/     # LastFrame-Cache für Segment-Chaining
└── misc …                # Weitere Artefakte folgen später
```

## 🔁 State-Persistenz

Der Video Generator speichert wichtige UI-Daten automatisch in `<ComfyUI>/output/<projekt>/video/_state.json`:
- zuletzt geladenes Storyboard + Auswahl + Workflow
- aktueller Generation-Plan inkl. Status, ausgewähltem Shot und Fortschritts-Text
- Pfad zum zuletzt erzeugten Clip

Beim Browser-Refresh oder Neustart bleiben diese Werte erhalten – du kannst direkt weitermachen, ohne alles neu auszuwählen.

## ⚙️ Configuration

Edit `config/settings.json` to change defaults:

```json
{
  "comfy_url": "http://127.0.0.1:8188",
  "workflow_dir": "config/workflow_templates",
  "output_dir": "output"
}
```

## 🐛 Troubleshooting

### Connection Failed

**Problem:** 🔴 Connection failed

**Solution:**
```bash
# Check if ComfyUI is running
curl http://127.0.0.1:8188/system_stats

# If not, start it:
cd /path/to/ComfyUI
python main.py --listen 127.0.0.1 --port 8188
```

### No Workflows Found

**Problem:** Dropdown shows "No workflows found"

**Solution:**
- Add your ComfyUI workflow JSON files to `config/workflow_templates/`
- Click "🔄 Refresh Workflows" button
- Make sure files are in API format (not UI format)

### Generation Fails

**Problem:** Images not generating

**Solution:**
- Check ComfyUI console for errors
- Verify Flux model is loaded in ComfyUI
- Ensure sufficient VRAM (16GB for Flux)
- Check workflow JSON is valid

### Smoke Check (CLI)

**Problem:** Setup unklar (Workflows/Projekt/ComfyUI)

**Solution:**
```bash
cd cindergrace_gui
python scripts/smoke_test.py --ping  # ohne --ping wird ComfyUI nicht angefragt
```

## 📚 Documentation

For detailed documentation, see:
- **Technical docs:** `../GUI_FRAMEWORK_README.md`
- **Pipeline docs:** `../CINDERGRACE_PIPELINE_README.md`
- **Logging & Error Handling:** `LOGGING_ERROR_HANDLING.md` (NEW!)
- **AI Context:** `CLAUDE.md`

## 🎯 Next Steps

After testing successfully:
1. Verify workflows work with your models
2. Test with different prompts and resolutions
3. Check output quality
4. Nutze den Keyframe Selector, um pro Shot die beste Variante zu markieren
5. Erzeuge die ersten Wan-Clips über Tab 3 (Video Generator – 3s-Segmente + LastFrame-Chaining sind aktiv)
6. Teste Shots > 3 Sekunden und prüfe, ob die automatisch verlängerten Segmente für deinen Schnitt passen

---

## ✅ What Works Right Now

### Tab 0: 📁 Projekt (v0.5.0) - NEW!
**Projektverwaltung direkt im ComfyUI/output Ordner**

Successfully Implemented:
- ✅ **Projekt anlegen** – Legt `<ComfyUI>/output/<slug>/project.json` inkl. Metadaten an
- ✅ **Projekt auswählen** – Dropdown listet alle vorhandenen Projektordner mit `project.json`
- ✅ **Statusanzeige** – Aktiver Projektpfad + Timestamps auf einen Blick
- ✅ **Nahtlose Integration** – Keyframe-, Selector- und Video-Tabs nutzen automatisch den aktiven Ordner

---

### Tab 1: 🎬 Keyframe Generator (v0.2.0)
**Phase 1: Multi-shot keyframe generation**

Successfully Implemented:
- ✅ **Storyboard Loading** - Load JSON storyboard files with multiple shots
- ✅ **Content-Based Filenames** - Use descriptive names (e.g., "hand-book_v1.png")
- ✅ **Resolution Control** - Set width/height per shot in storyboard
- ✅ **Batch Variants** - Generate 1-10 variants per shot
- ✅ **Checkpoint/Resume** - Save progress, resume interrupted generations
- ✅ **Progress Tracking** - Detailed status in terminal and UI
- ✅ **Image Gallery** - View all generated keyframes

Example Workflow:
1. Load `storyboard_example.json` (5 shots)
2. Configure variants per shot (default: 4)
3. Set base seed (default: 2000)
4. Click "▶️ Start Generation"
5. Result: 20 keyframes unter `<ComfyUI>/output/<projekt>/keyframes/`

Storyboard Format:
```json
{
  "shot_id": "003",
  "filename_base": "hand-book",
  "prompt": "close-up of pale hand with silver rings...",
  "width": 1024,
  "height": 576,
  "duration": 2.5,
  "camera_movement": "slow_dolly",
  "wan_motion": {
    "type": "macro_dolly",
    "strength": 0.6,
    "notes": "Small forward move with slight handheld sway"
  }
}
```

`wan_motion` ist optional und wird aktuell nur vom Video Generator ausgewertet. Die Flux-Keyframe-Generierung nutzt weiterhin ausschließlich Prompt, Auflösung, Seeds usw., daher bleiben bestehende Workflows kompatibel. Zusätzlich definiert `video_settings` im Storyboard globale Defaultwerte (z.B. Workflow, FPS, Dauer-Limit) für Wan – diese Felder dienen als Orientierung, auch wenn sie momentan noch nicht automatisch übernommen werden.

Output:
- Keyframes saved to: `<ComfyUI>/output/<projekt>/keyframes/`
- Filenames: `{filename_base}_v{N}_00001_.png`
- Checkpoints: `<ComfyUI>/output/<projekt>/checkpoints/{storyboard}_checkpoint.json`
- Gallery: All variants displayed in browser

**Key Feature:** Content-based filenames make it easy to reference keyframes in later pipeline phases (video generation).

---

### Tab 2: ✅ Keyframe Selector (v0.3.1)
**Phase 2: Beste Varianten auswählen & exportieren**

Successfully Implemented:
- ✅ **Storyboard-gekoppelter Browser** – Shots + Metadaten werden aus derselben JSON gelesen
- ✅ **Multi-Location Search** – Findet Storyboards in config/, Projekt-Root und projekt/storyboards/ (NEW!)
- ✅ **Automatische Gruppierung** – Alle PNGs aus `<ComfyUI>/output/<projekt>/keyframes/` werden pro `filename_base` gefunden
- ✅ **Variantenvergleich** – Galerie zeigt alle Treffer inkl. Variantennummer und Dateiname
- ✅ **Shot-bezogene Auswahl** – Radio-Auswahl speichert Variante pro Shot
- ✅ **Exportformat** – `selected_keyframes.json` enthält Projektinfos + Auswahlliste für Phase 3
- ✅ **Dateikopie** – Ausgewählte PNGs landen zusätzlich in `<ComfyUI>/output/<projekt>/selected/`
- ✅ **Gradio 4.x Optimierung** – Verbesserte Gallery-Performance (NEW!)

Workflow:
1. Lade dein Storyboard.
2. Wähle einen Shot im Dropdown und prüfe die Galerie.
3. Markiere die gewünschte Variante und speichere sie.
4. Wiederhole das für alle Shots (Statusliste zeigt Fortschritt).
5. Exportiere – JSON + PNGs werden nach `<ComfyUI>/output/<projekt>/selected/` kopiert.

Export-Beispiel (`<ComfyUI>/output/<projekt>/selected/selected_keyframes.json`):
```json
{
  "project": "CINDERGRACE Test",
  "total_shots": 5,
  "exported_at": "2024-12-12T10:15:01",
  "selections": [
    {
      "shot_id": "001",
      "filename_base": "cathedral-interior",
      "selected_variant": 2,
      "selected_file": "cathedral-interior_v2_00001_.png",
      "source_path": ".../ComfyUI/output/<projekt>/keyframes/cathedral-interior_v2_00001_.png",
      "export_path": ".../ComfyUI/output/<projekt>/selected/cathedral-interior_v2_00001_.png"
    }
  ]
}
```

---

### Tab 3: 🎥 Video Generator (v0.5.0)
**Phase 3: Wan 2.2 Clips aus Startframes bauen**

Successfully Implemented:
- ✅ **Planer** – Kombiniert Storyboard + `selected_keyframes.json`
- ✅ **3-Sekunden-Segmente** – Jeder Clip wird mit 3s Länge an Wan gesendet (sicheres Default)
- ✅ **LastFrame-Chaining** – Shots > 3s werden automatisch in 3s-Segmente aufgeteilt; der letzte Frame dient als Startframe des nächsten Segments
- ✅ **Wan-Workflow Steuerung** – Startframe + Prompt + Auflösung werden ins Workflow-JSON injiziert
- ✅ **Motion-Metadaten** – Optionale `wan_motion`-Felder aus dem Storyboard werden mit angezeigt (für kommende Steuerung)
- ✅ **FPS-Kontrolle** – Wähle 12–30 fps (Standard 24 fps)
- ✅ **Output-Organisation** – Clips landen unter `<ComfyUI>/output/<projekt>/video/`
- ✅ **Sprechende Dateinamen** – Exportierte Videos heißen z.B. `cathedral-interior.mp4`
- ✅ **Model-Check** – Fehlende Wan-Modelle werden vor Start erkannt (Pfad in ⚙️ Settings konfigurierbar)
- ✅ **Status + Preview** – Fortschritt in Markdown, letzter Clip direkt als Video abspielbar
- ✅ **State-Persistenz** – Nach Refresh bleiben Storyboard/Selection/Plan sowie letzter Clip sichtbar
- ✅ **Startframe-Cache** – Unter `<ComfyUI>/output/<projekt>/video/_startframes/` werden die extrahierten LastFrames abgelegt (erfordert `ffmpeg`)

Workflow:
1. Lade Storyboard und deine `selected_keyframes.json` in Tab 3.
2. Prüfe den automatisch erzeugten Plan (Shots ohne Startframe werden markiert).
3. Wähle den gewünschten Wan-Workflow (z.B. `Wan 2.2 14B i2v.json`, bereits unter `config/workflow_templates/` vorhanden).
4. Starte die Generierung – jeder Shot nutzt seinen Keyframe als erstes Bild.
5. Clips erscheinen nach Abschluss im Video-Ordner und im UI-Player.

ℹ️ **Hinweis:** Shots mit 4–5 Sekunden werden aktuell auf Vielfache von 3 Sekunden verlängert (z.B. Storyboard 5s → zwei Segmente = 6s Output). Über den Schnitt kannst du das Übermaß nachträglich kürzen.

---

### Tab 4: 🧪 Test ComfyUI (v0.1.0)
**Quick image generation testing**

Successfully Implemented:
- ✅ **ComfyUI Connection Test** - Tests connection and shows system info
- ✅ **Batch Image Generation** - Generate 1-10 images with different seeds
- ✅ **Workflow Management** - Load workflows from dropdown, refresh on demand
- ✅ **Parameter Control** - Prompt, seed, steps all updateable
- ✅ **Image Gallery** - View all generated images with seeds
- ✅ **Auto venv** - start.sh handles everything automatically
- ✅ **Error Handling** - Clear error messages from ComfyUI

Output:
- Images saved to: `cindergrace_gui/output/test/`
- Format: PNG with seed in filename
- Gallery view in browser

---

### Tab 5: ⚙️ Settings (v0.4.0)
**Global Config + Workflow-Presets**

Successfully Implemented:
- ✅ **ComfyUI URL & Root** – Anpassbar direkt aus dem UI, inklusive Persistenz in `config/settings.json`
- ✅ **Workflow-Presets Editor** – Bearbeite `workflow_presets.json`, um Flux/Wan-Workflows zu kuratieren
- ✅ **Live-Reload** – Änderungen können während einer Session neu geladen werden

### Verified Working With:
- **Model:** flux1-krea-dev.safetensors (Flux variant)
- **Workflow:** flux_test_simple.json (included example)
- **ComfyUI:** Local instance at http://127.0.0.1:8188
- **Gradio:** Version 6.0+
- **Resolution:** 1024x576 (16:9), configurable per shot
- **Video:** Wan 2.2 Workflow (`Wan 2.2 14B i2v.json` unter `config/workflow_templates/`)

---

## 🔮 Next Phase: Timeline Toolkit (v0.6.0)

**Status:** In Planung – Segmentierung & LastFrame-Chaining sind live, jetzt folgt Feinschliff

### Roadmap-Ideen:
- Export eines `timeline.json`, das alle Segmente inkl. Dauer & Motion-Angaben für den Schnitt auflistet
- Feinjustage der Wan-Motion (Strength/Easing) direkt aus dem Storyboard
- Verbesserte Fortschrittsanzeige + Wiederaufnahme pro Segment
- Fehlerbehandlung für fehlende Modelle/Nodes inkl. konkreter Hinweise
- Vorbereitung auf spätere Add-ons (z.B. Lipsync-Modul nach v1.0)

---

---

## 🔧 Developer Notes

### Recent Updates (v0.5.1)

**Input Validation & Error Handling:**
- Pydantic validators für alle User-Eingaben
- Structured logging system mit Rotation
- Custom exception hierarchy
- Automatic error formatting für UI

**Bug Fixes:**
- Keyframe Selector sucht jetzt in mehreren Locations
- Gradio 4.x Gallery-Kompatibilität behoben
- start.sh installiert Dependencies automatisch

**Code Quality:**
- Alle print() durch logger ersetzt
- @handle_errors Decorator für konsistentes Error Handling
- Type hints und Validierung

Siehe `LOGGING_ERROR_HANDLING.md` für Migration Guide.

---

**Status:** ✅ Phase 3 Beta – Keyframe Generator + Selector + Video Generator funktionsfähig (v0.5.1)
**Last Updated:** December 10, 2025
**Next:** Phase 4 – Timeline-/Motion-Tools & Qualitäts-Monitoring
