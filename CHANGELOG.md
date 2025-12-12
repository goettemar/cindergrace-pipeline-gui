# CINDERGRACE GUI - Changelog

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

### [0.5.0] - Next Release (Planned)
- 🔮 **LastFrame Extension** - Phase 3b der Pipeline
  - Mehr als 3 Sek. via Segment-Chaining
  - Automatischer Import der Endframes als Startframes für Segment 2+
  - Segment-Status + Resume
  - Erweiterte Video-Metadaten (`timeline.json`)

### [0.6.0] - Future Release (Planned)
- 🔮 **Timeline/Video Enhancements**
  - Bulk review UX improvements
  - Placeholder thumbnails for missing shots
  - Integration mit Postproduktion / Export

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

**Current Version:** 0.4.0 (WORKING)
**Status:** ✅ Phase 3 Beta - Keyframe Generator + Selector + Video Generator
**Ready for:** Phase 3b development (LastFrame Extension)
