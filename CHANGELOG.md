# CINDERGRACE GUI - Changelog

## [0.9.0] - December 21, 2025 - ✅ WORKING

### 🎬 LTX-Video Support & Model Selection

#### New Features:

**1. LTX-Video Integration (Low VRAM)**
- ✅ Native ComfyUI nodes (kein Custom Node Pack nötig)
- ✅ 6-8GB VRAM ausreichend (vs 12GB+ für Wan 2.2)
- ✅ Flexible Auflösungen (768x512, 512x768, 512x512)
- ✅ Workflow: `gcv_ltvx_i2v.json`

**2. Video Model Dropdown**
- ✅ Model-Auswahl im Video Generator
- ✅ Dynamisch basierend auf `.models` Datei
- ✅ Unterstützt UNETLoader, UnetLoaderGGUF, CheckpointLoaderSimple
- ✅ Nur installierte Modelle werden angezeigt

**3. Dataset Generator Workflow-Auswahl**
- ✅ Workflow-Dropdown für gcl_* Workflows
- ✅ Service unterstützt dynamische Workflow-Auswahl
- ✅ `gcl_qwen_image_edit_2509.models` Datei erstellt

**4. Resolution Guide Komponente**
- ✅ Collapsible Accordion im Project Tab
- ✅ Matrix für Wan 2.2 und LTX-Video Auflösungen
- ✅ VRAM-Empfehlungen pro Auflösung

**5. Neue LTX-Video Updaters**
- ✅ `LTXVLatentUpdater` - EmptyLTXVLatentVideo, LTXVImgToVideo
- ✅ `SamplerCustomUpdater` - SamplerCustom für LTX
- ✅ `SaveAnimatedWEBPUpdater` - WEBP Output

#### Files Changed:
- `addons/video_generator.py` - Model dropdown + Helper
- `addons/dataset_generator.py` - Workflow dropdown
- `addons/project_panel.py` - LTX resolution presets
- `addons/components/resolution_guide.py` - NEW: Resolution Guide
- `services/character_trainer_service.py` - Dynamic workflow
- `services/keyframe/workflow_utils.py` - Extended inject_model_override
- `infrastructure/comfy_api/updaters.py` - LTX-Video updaters
- `infrastructure/config_manager.py` - LTX resolution presets
- `config/workflow_templates/gcv_ltvx_i2v.json` - NEW
- `config/workflow_templates/gcv_ltvx_i2v.models` - NEW
- `config/workflow_templates/gcl_qwen_image_edit_2509.models` - NEW

#### Technical Details:

| Model | VRAM | Auflösungen | Qualität |
|-------|------|-------------|----------|
| Wan 2.2 14B | 12GB+ | 16:9 / 9:16 | ⭐⭐⭐ Beste |
| LTX-Video 2B | 6-8GB | Flexibel (÷32) | ⭐⭐ Gut |
| LTX-Video 13B-dev | 12GB+ | Flexibel (÷32) | ⭐⭐⭐ Sehr gut |

---

## [0.8.0] - December 20, 2025 - ✅ WORKING

### 🎨 Multi-Model LoRA Training (FLUX + SDXL + SD3)

#### New Features:

**1. Multi-Model Support**
- ✅ **FLUX** - Diffusion Transformer (beste Qualität, 16GB+ VRAM)
- ✅ **SDXL** - Stable Diffusion XL (schneller, ab 8GB VRAM)
- ✅ **SD3** - Stable Diffusion 3 (hohe Qualität, ab 8GB VRAM)

**2. Dynamische UI**
- ✅ Model-Typ Dropdown (FLUX/SDXL/SD3)
- ✅ VRAM-Presets aktualisieren sich automatisch je Model-Typ
- ✅ Base Model Dropdown zeigt nur passende Modelle
- ✅ T5XXL Encoder wird bei SDXL automatisch ausgeblendet

**3. VRAM-Presets erweitert**
- ✅ 8GB Preset für SDXL und SD3
- ✅ Model-spezifische Optimierungen (Resolution, Network Dim, Optimizer)

**4. Bugfixes**
- ✅ SDXL: `network_train_unet_only = true` hinzugefügt (behebt AssertionError)
- ✅ SD3: `network_train_unet_only = true` hinzugefügt
- ✅ Log-Parser: False Positives für "ar error" und "accelerator" behoben

#### Files Changed:
- `services/kohya/models.py` - KohyaModelType Enum, erweiterte Presets
- `services/kohya/config_builder.py` - TOML-Generierung für SDXL/SD3
- `services/kohya/training_runner.py` - Script-Auswahl basierend auf Model-Typ
- `services/kohya/model_scanner.py` - Neue Scan-Methoden für SDXL/SD3
- `services/kohya_trainer_service.py` - model_type Parameter
- `addons/character_trainer.py` - Dynamische UI für Multi-Model
- `docs/addons/CHARACTER_TRAINER.md` - Dokumentation erweitert

#### Technical Details:

| Model | Training Script | Network Module | Min VRAM |
|-------|-----------------|----------------|----------|
| FLUX | `flux_train_network.py` | `networks.lora_flux` | 16GB |
| SDXL | `sdxl_train_network.py` | `networks.lora` | 8GB |
| SD3 | `sd3_train_network.py` | `networks.lora_sd3` | 8GB |

---

## [0.7.0] - December 17, 2025 - ✅ WORKING

### 🔥 Kohya Training Only - ComfyUI Training Removed

#### Breaking Changes:

**1. ComfyUI LoRA Training Tab entfernt**
- ❌ Tab "Phase 3: LoRA Training (ComfyUI)" wurde vollständig entfernt
- ❌ FluxTrainer-basiertes Training nicht mehr unterstützt
- ✅ Nur noch Kohya sd-scripts für LoRA Training

**2. Kohya Training Verbesserungen**
- ✅ Konfigurierbare Model-Auswahl (FLUX + T5XXL)
- ✅ Automatisches Scannen verfügbarer Modelle
- ✅ FP8-Modelle werden bevorzugt für 16GB VRAM
- ✅ Korrigiertes TOML-Format (separate Dataset-Config)
- ✅ Bilder müssen direkt im Ordner liegen (keine Unterordner)

**3. Neue UI-Elemente im Kohya Tab**
- ✅ FLUX Base Model Dropdown
- ✅ T5XXL Text Encoder Dropdown
- ✅ Models Refresh Button

#### Migration:

Wenn Sie vorher ComfyUI-basiertes Training verwendet haben:
1. Nutzen Sie nun den "Kohya Training" Tab
2. Wählen Sie Ihre bevorzugten Modelle in den Erweiterten Einstellungen
3. FP8-Modelle empfohlen für 16GB VRAM

#### Files Changed:
- `addons/character_trainer.py` - ComfyUI Tab entfernt, Kohya erweitert
- `services/kohya_trainer_service.py` - Model scanning, configurable paths
- `docs/addons/CHARACTER_TRAINER.md` - Dokumentation aktualisiert

---

## [0.6.1] - December 16, 2025 - ✅ WORKING

### 🌐 Google Colab Integration & Multi-Backend Support

#### New Features:

**1. Multi-Backend System**
- ✅ Unterstützung für mehrere ComfyUI-Backends (lokal + Cloud)
- ✅ Einfaches Wechseln zwischen Backends im Settings-Tab
- ✅ Backend-Indikator im Header zeigt aktives Backend
- **ConfigManager:** Neue Methoden `get_backends()`, `add_backend()`, `set_active_backend()`

**2. Google Colab Support**
- ✅ Optimiertes Colab-Notebook für CINDERGRACE
- ✅ Cloudflare Tunnel für Fernzugriff (keine ngrok-Registrierung nötig)
- ✅ Google Drive Integration für persistente Modelle
- ✅ Optional: FluxTrainer-Fork Installation
- **Location:** `colab/Cindergrace_ComfyUI.ipynb`

**3. Settings Panel Überarbeitung**
- ✅ Backend-Auswahl Dropdown mit Wechsel-Button
- ✅ Verbindungstest für aktives Backend
- ✅ "Backend hinzufügen" Dialog für Colab-URLs
- ✅ Lokales Backend separat konfigurierbar

**4. FluxTrainer Fork**
- ✅ Fork erstellt für Cindergrace-spezifische Fixes
- ✅ PyTorch 2.8 Kompatibilität geplant
- ✅ 16GB VRAM Optimierungen dokumentiert
- **Repository:** `github.com/goettemar/ComfyUI-FluxTrainer-Cindergrace`

#### Usage:

1. **Colab starten:**
   - `colab/Cindergrace_ComfyUI.ipynb` in Google Colab öffnen
   - GPU auswählen (T4 kostenlos, H100 für Training)
   - Alle Zellen ausführen
   - Cloudflare-URL kopieren

2. **Backend in CINDERGRACE hinzufügen:**
   - Settings → Backend hinzufügen
   - Name: "Colab T4" / "Colab H100"
   - URL: Cloudflare-URL einfügen
   - Typ: Remote/Colab
   - Wechseln & Testen

---

## [0.6.0] - December 14, 2025 - ✅ WORKING

### 🏗️ Architecture Refactoring - SQLite Migration & Preset System

#### Major Changes:

**1. SQLite für ProjectStore**
- ✅ Projekt-Metadaten in SQLite-Datenbank statt JSON-Dateien
- ✅ Bessere Concurrency und Datenkonsistenz
- ✅ Automatische Migration bestehender Projekte
- **Location:** `data/projects.db`

**2. PresetService mit SQLite**
- ✅ 64 Presets in 8 Kategorien (style, lighting, mood, time_of_day, composition, color_grade, camera, motion)
- ✅ Auto-Seeding der Datenbank beim ersten Start
- ✅ Prompt-Expansion mit kombinierten Preset-Texten
- **Location:** `data/presets.db`
- **Service:** `infrastructure/preset_service.py`

**3. Storyboard Format v2.0**
- ✅ Neue Struktur mit `presets`, `flux`, `wan` Objekten
- ✅ Legacy-Felder entfernt (camera_movement, wan_motion, seed, cfg_scale, steps)
- ✅ Render-Settings pro Shot (flux/wan Seeds, CFG, Steps)
- **Beispiel:**
```json
{
  "shot_id": "001",
  "presets": {
    "style": "cinematic",
    "lighting": "golden_hour",
    "mood": "epic"
  },
  "flux": {"seed": -1, "cfg": 7.0, "steps": 20},
  "wan": {"seed": -1, "cfg": 7.0, "steps": 20, "motion_strength": 0.4}
}
```

**4. Storyboard Editor 3-Tab Struktur**
- ✅ Tab 1: Shot-Liste mit Übersicht
- ✅ Tab 2: Shot-Details (Prompt, Description, Presets)
- ✅ Tab 3: Render-Settings (Flux/Wan Parameter)
- ✅ Preset-Dropdowns für alle 8 Kategorien
- ✅ Full Prompt Preview mit expandierten Presets

**5. Workflow Templates Umbenannt**
- `flux_preview_fast.json` → `flux_test_schnell.json` (🧪 Test)
- `flux_test_simple.json` → `flux_keyframe_hq.json` (🎬 HQ)
- Klarere Unterscheidung: Test (schnell, niedrige Qualität) vs. Production (HQ)

**6. Keyframe Selector UI Refactoring**
- ✅ "Auswahl Speichern" → "💾 Shot Variante speichern"
- ✅ Neu: "🗑️ Shot Variante entfernen" mit Bestätigungsdialog
- ✅ "📤 Shot Auswahl speichern" für Video Generator Export
- ✅ Radio-Element "Beste Variante auswählen" nach links in Sidebar verschoben
- ✅ Captions unter Gallery-Bildern (v1, v2, v3...)
- ✅ Warnung bei unvollständiger Auswahl (X/Y Shots fehlen)
- ✅ X/Y Format in Auswahlübersicht

#### New Files:
```
data/
├── projects.db                      ✅ SQLite für Projekte
├── presets.db                       ✅ SQLite für Presets
└── templates/
    └── storyboard_beispiel.json     ✅ Beispiel-Storyboard v2.0

infrastructure/
└── preset_service.py                ✅ Preset-Management Service

services/
└── storyboard_editor_service.py     ✅ Storyboard CRUD Service

addons/
└── storyboard_editor.py             ✅ 3-Tab Storyboard Editor

config/workflow_templates/
├── flux_test_schnell.json           ✅ Umbenannt (vorher flux_preview_fast)
└── flux_keyframe_hq.json            ✅ Umbenannt (vorher flux_test_simple)
```

#### Updated Files:
```
infrastructure/project_store.py      ✅ SQLite Backend
config/workflow_presets.json         ✅ Neue Namen mit Emojis
addons/keyframe_selector.py          ✅ UI Refactoring
data/templates/storyboard_beispiel.json ✅ v2.0 Format
docs/BACKLOG.md                      ✅ #028 Gallery Caption Position
```

#### Breaking Changes:
- ⚠️ Storyboard-Format v2.0 nicht abwärtskompatibel
- ⚠️ Alte Storyboards müssen auf neues Format migriert werden
- ⚠️ Legacy-Felder (camera_movement, wan_motion) werden nicht mehr unterstützt

#### Tests:
- 417 Unit Tests bestanden
- Test-Coverage: 52%

---

## [0.5.0] - December 13, 2025 - ✅ WORKING

### 🎬 Phase 3b - LastFrame Extension & Project Management

#### Implemented Features:
- ✅ **LastFrame Chaining** - Shots >3s werden in Segmente aufgeteilt
- ✅ **Project Management Tab** - Projekte erstellen/auswählen
- ✅ **Settings Tab** - ComfyUI URL, Pfade, Workflow-Presets
- ✅ **State Persistence** - UI-State überlebt Browser-Refresh
- ✅ **Model Validation** - Prüft fehlende Wan-Modelle vor Generation

---

## [0.4.0] - December 13, 2024 - ✅ WORKING

### 🎥 Phase 3 Beta - Wan Video Generator Addon

#### Implemented Features:
- ✅ **VideoGeneratorAddon** – Steuert Wan 2.2 direkt aus dem GUI
- ✅ **Storyboard + Selection Merge** – Liest `selected_keyframes.json` und erstellt einen Generierungsplan
- ✅ **3-Sekunden-Segmente** – Clips werden auf 3 Sek. begrenzt, längere Shots werden markiert
- ✅ **Workflow Injection** – Prompt, Auflösung, FPS und Startframe landen automatisch im Workflow
- ✅ **Output Management** – Kopiert fertige Videos nach `output/video/{projekt}/`
- ✅ **Status & Preview** – Fortschritt als Markdown-Log, letzter Clip als Video in der UI
- ✅ **Workflow-Presets + Settings Tab** – ⚙️ Tab erlaubt Pflege von `workflow_presets.json` und Comfy-URL/-Pfad
- ✅ **Sprechende Clip-Namen** – Video-Exports heißen z.B. `cathedral-interior.mp4`
- ✅ **Model-Validierung** – Fehlende Wan-Modelle werden vor Start erkannt (Pfad aus Settings)
- ✅ **Storyboard Video Settings** – Beispiel-Storyboard liefert Wan-Motion + Defaultwerte fürs Mapping

#### New Files:
```
cindergrace_gui/
├── addons/
│   ├── settings_panel.py             ✅ NEW: UI-Settings/Workflow-Konfiguration
│   └── video_generator.py            ✅ NEW: Wan 2.2 video generator addon
└── output/
    └── video/                        ✅ NEW: Zielordner für generierte Clips
config/workflow_presets.json          ✅ NEW: Kategorie-Definition für Flux/Wan Workflows
utils/workflow_registry.py            ✅ NEW: Preset-Lader
utils/model_validator.py              ✅ NEW: Model-Check basierend auf Comfy-Root
config/workflow_templates/
    └── Wan 2.2 14B i2v.json          ✅ NEW: Beispiel-Workflow für Wan 2.2 I2V Remix
```

#### Updated Files:
```
addons/__init__.py                    ✅ Registriert Settings + Video Generator
addons/test_comfy_flux.py             ✅ Nutzt Workflow-Presets (Flux)
addons/keyframe_generator.py          ✅ Nutzt Workflow-Presets (Flux)
addons/video_generator.py             ✅ Benennung, Model-Check, Workflow-Filter
README.md                             ✅ Dokumentiert Settings-Tab & neue Features
CHANGELOG.md                          ✅ Release Notes für 0.4.0
config/storyboard_example.json        ✅ Ergänzt um `wan_motion`-Metadaten (Flux bleibt kompatibel)
output/keyframes/*.png                ✅ Demo-Startframes für Tests ohne Flux
output/selected/selected_keyframes_example.json ✅ Beispiel-Auswahl für Tab 3/4
```

#### Workflow:
1. Storyboard laden
2. `selected_keyframes.json` laden (aus Phase 2)
3. Video-Workflow wählen
4. Plan prüfen und Clips generieren

#### Known Limitations:
- ⚠️ Shots > 3 Sek. werden gekürzt (LastFrame-Funktion folgt in 0.5.0)
- ⚠️ Stop/Resume für lange Wan-Jobs noch nicht verfügbar

---

## [0.3.0] - December 12, 2024 - ✅ WORKING

### 🎯 Phase 2 Complete - Keyframe Selector Addon

#### Implemented Features:
- ✅ **Keyframe Selector Addon** – Review all variants per shot directly inside the GUI
- ✅ **Storyboard-aware UI** – Dropdown + metadata auto-sync with the loaded storyboard JSON
- ✅ **Variant Gallery** – All PNGs from `output/keyframes/` grouped by `filename_base`
- ✅ **Selection Tracking** – Saves the chosen variant per shot with status overview
- ✅ **Export Pipeline** – Writes `output/selected/selected_keyframes.json` including metadata + timestamps
- ✅ **Asset Copy** – Copies the winning PNGs into `output/selected/` for the next pipeline stage

#### New Files:
```
cindergrace_gui/
├── addons/
│   └── keyframe_selector.py          ✅ NEW: Keyframe selection addon
└── output/
    └── selected/                     ✅ NEW: Stores exported PNGs + JSON
```

#### Updated Files:
```
addons/__init__.py                    ✅ Registers KeyframeSelectorAddon
README.md                             ✅ Documents Tab 3 workflow + export steps
```

#### Workflow:
1. Load the storyboard in Tab 3
2. Pick a shot → gallery shows all variants
3. Store the preferred variant per shot
4. Export → JSON + PNGs copied to `output/selected/`
5. Result feeds Phase 3 (Video Generator)

#### Known Limitations:
- Shots with zero keyframes simply show a warning; no placeholder image yet
- Selections are session-based (export before closing the GUI)

---

## [0.2.0] - December 10, 2024 - ✅ WORKING

### 🎬 Phase 1 Complete - Keyframe Generator Addon

#### Implemented Features:
- ✅ **Keyframe Generator Addon** - Generate multiple keyframe variants per shot
- ✅ **Storyboard Loading** - Load and validate JSON storyboard files
- ✅ **Content-Based Filenames** - Use `filename_base` per shot (e.g., "hand-book_v1.png")
- ✅ **Resolution Control** - Set `width` and `height` per shot in storyboard
- ✅ **Batch Generation** - Generate N variants per shot with auto-incrementing seeds
- ✅ **Checkpoint/Resume System** - Save progress, resume interrupted generations
- ✅ **Direct Image Copy** - Reliable copying from ComfyUI output to GUI output
- ✅ **Progress Tracking** - Detailed terminal output and checkpoint status display
- ✅ **Collapsible UI** - Storyboard info in accordion (doesn't clutter interface)
- ✅ **API Enhancement** - width/height support in ComfyUI API wrapper

#### New Files:
```
cindergrace_gui/
├── addons/
│   └── keyframe_generator.py         ✅ NEW: Keyframe generator addon
├── config/
│   └── storyboard_example.json       ✅ NEW: Example storyboard (5 shots)
└── output/
    ├── keyframes/                    ✅ NEW: Generated keyframes
    └── checkpoints/                  ✅ NEW: Generation checkpoints
```

#### Updated Files:
```
utils/comfy_api.py                    ✅ Added width/height support (EmptyLatentImage node)
utils/config_manager.py               ✅ Added config_dir property
addons/__init__.py                    ✅ Registered KeyframeGeneratorAddon
```

#### Storyboard Format (v2.0):
New fields added to shot definition:
```json
{
  "shot_id": "003",
  "filename_base": "hand-book",       // NEW: Content-based naming
  "width": 1024,                       // NEW: Resolution control
  "height": 576,                       // NEW: Resolution control (16:9)
  "prompt": "...",
  "duration": 2.5,
  "camera_movement": "slow_dolly"
}
```

#### Tested & Verified:
- ✅ Loads storyboard.json with multiple shots
- ✅ Generates 4 variants per shot (configurable 1-10)
- ✅ Uses content-based filenames (e.g., "cathedral-interior_v1.png")
- ✅ Respects resolution settings from storyboard (1024x576)
- ✅ Copies images to `output/keyframes/` directory
- ✅ Checkpoint system saves progress every shot
- ✅ Resume button loads checkpoint and continues generation
- ✅ Gallery displays all generated keyframes
- ✅ Works with flux1-krea-dev.safetensors

#### Example Workflow:
1. Start GUI: `./start.sh`
2. Tab: **🎬 Keyframe Generator**
3. Load: `storyboard_example.json` (5 shots, 20 images total)
4. Configure: 4 variants per shot, base seed 2000
5. Click: **▶️ Start Generation**
6. Result: 20 keyframes in `output/keyframes/`

#### Known Issues & Limitations:
- ⚠️ Progress Details only update at end (not live during generation)
  - Workaround: Terminal shows live progress
  - See Backlog: "Live Progress Updates"
- ⚠️ Stop button not implemented
  - Workaround: Ctrl+C in terminal to stop
  - See Backlog: "Stop Button"
- ℹ️ Resume button works but doesn't preview existing images first

#### Breaking Changes:
- Storyboard format updated to v2.0 (new fields: `filename_base`, `width`, `height`)
- Old storyboards without these fields will use defaults (shot_id for filename, 1024x576 for resolution)

---

## [0.1.0] - December 2024 - ✅ WORKING

### 🎉 Initial Release - Test Addon Functional

#### Implemented Features:
- ✅ **Modular Addon System** - Base architecture for pipeline addons
- ✅ **Test ComfyUI Addon** - Connection test + batch image generation
- ✅ **ComfyUI API Wrapper** - Full REST + WebSocket support
- ✅ **Gradio 6.0 GUI** - Modern web interface
- ✅ **Auto venv Management** - Automatic virtual environment setup
- ✅ **Workflow System** - Load and manage ComfyUI workflows
- ✅ **Batch Generation** - Generate 1-10 images with auto-incrementing seeds
- ✅ **Error Handling** - Detailed error messages from ComfyUI

#### Files Created:
```
cindergrace_gui/
├── main.py                           ✅ Main GUI application
├── start.sh                          ✅ Auto venv launcher
├── requirements.txt                  ✅ Dependencies
├── addons/
│   ├── base_addon.py                 ✅ Base class for all addons
│   ├── test_comfy_flux.py            ✅ Test addon (WORKING)
│   └── __init__.py                   ✅ Addon registry
├── utils/
│   ├── comfy_api.py                  ✅ ComfyUI API client
│   ├── config_manager.py             ✅ Config management
│   └── progress_tracker.py           ✅ Progress tracking
├── config/
│   ├── settings.json                 ✅ Default settings
│   └── workflow_templates/
│       └── flux_test_simple.json     ✅ Example Flux workflow
└── README.md                         ✅ Quick start guide
```

#### Tested & Verified:
- ✅ Connection to ComfyUI at http://127.0.0.1:8188
- ✅ System info retrieval
- ✅ Workflow loading (flux_test_simple.json)
- ✅ Parameter updates (prompt, seed, steps)
- ✅ Batch generation of 4 images (seeds 1001-1004)
- ✅ Image saving to output/test/
- ✅ Gallery display in browser
- ✅ Works with flux1-krea-dev.safetensors

#### Known Issues & Limitations:
- ⚠️ No visual progress bar (Gradio 6.0 limitation)
- ℹ️ Progress shown in terminal only
- ℹ️ Single workflow execution at a time
- ℹ️ Requires ComfyUI to be started manually

#### Breaking Changes:
- None (initial release)

#### Dependencies:
```
gradio>=4.0.0 (tested with 6.0)
websocket-client>=1.6.0
pillow>=10.0.0
numpy>=1.24.0
```

---

## Roadmap

### [0.7.0] - Next Release (Planned)
- 🔮 **Stop/Abort Button** - Generation abbrechen
- 🔮 **Refresh Safety** - State-Persistence für Keyframe Generator
- 🔮 **Help System** - Tooltips + Modals für alle Tabs
- 🔮 **Setup Wizard** - Erstnutzer-Konfiguration

### [0.8.0] - Future Release (Planned)
- 🔮 **Live Progress Updates** - Echtzeit-Fortschritt im UI
- 🔮 **Code Quality** - Addon-Refactoring, Method-Extraktion
- 🔮 **Timeline/Video Enhancements** - Bulk review, Placeholder thumbnails

---

## Usage

```bash
cd cindergrace_gui
./start.sh
# Browser opens at http://127.0.0.1:7860
```

## Testing

1. Start ComfyUI: `cd /path/to/ComfyUI && python main.py`
2. Start GUI: `cd cindergrace_gui && ./start.sh`
3. Test Connection: Click "🔌 Test Connection"
4. Generate Images: Select workflow, enter prompt, click "🎨 Generate"
5. View Results: Gallery shows images, saved to `output/test/`

---

**Current Version:** 0.9.0 (WORKING)
**Status:** ✅ LTX-Video Support + Model Selection + Workflow Dropdown
**Ready for:** v1.0.0 - Production Release, ECHO NULL Demo Video
