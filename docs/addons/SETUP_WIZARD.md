# Setup Wizard Addon Documentation

**Tab Name:** Setup
**File:** `addons/setup_wizard.py`
**Version:** v0.6.1
**Last Updated:** December 26, 2025

---

## Overview

Der Setup-Assistent führt neue Benutzer durch die Ersteinrichtung von CINDERGRACE. Er beginnt mit dem Disclaimer/Nutzungsbedingungen, prüft Systemabhängigkeiten, bietet Installationsanleitungen für ComfyUI, konfiguriert die Verbindung zum Backend und ermöglicht die Eingabe von API-Keys.

---

## Features

- **Disclaimer & Nutzungsbedingungen** - Rechtliche Hinweise vor der Nutzung
- **Systemprüfung** - Automatische Erkennung von Abhängigkeiten (Python, ffmpeg, etc.)
- **ComfyUI Installation** - Schritt-für-Schritt Anleitung für Windows und Linux
- **Konfiguration** - ComfyUI Pfad und URL einstellen
- **API Keys** - Civitai, Huggingface, Google TTS (verschlüsselt gespeichert)
- **Verbindungstest** - Prüfe ComfyUI-Erreichbarkeit
- **Example Project** - Optional ein Beispielprojekt erstellen
- **Setup-Reset** - Möglichkeit den Wizard erneut zu durchlaufen

---

## UI Structure

### Setup bereits abgeschlossen (Nach Ersteinrichtung)

Nach erfolgreicher Ersteinrichtung zeigt der Setup-Tab eine Zusammenfassung:

```
┌─────────────────────────────────────────────────────────────┐
│ ## ✅ Setup bereits abgeschlossen                           │
│                                                             │
│ **CINDERGRACE ist bereits eingerichtet!**                   │
│                                                             │
│ ▼ 📜 Nutzungsbedingungen & Disclaimer (aufklappbar)        │
│ ┌─────────────────────────────────────────────────────────┐│
│ │ ✓ Akzeptiert am: 26.12.2025 um 21:29 Uhr               ││
│ │                                                         ││
│ │ ### 1. Disclaimer of Warranty                           ││
│ │ This software is provided "AS IS"...                    ││
│ │ ...                                                     ││
│ └─────────────────────────────────────────────────────────┘│
│                                                             │
│ **Möchtest du Einstellungen ändern?**                       │
│ Alle Konfigurationen findest du im ⚙️ Settings Tab          │
│                                                             │
│ ☐ Setup Wizard erneut durchlaufen (setzt Einrichtung zurück)│
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Step 0: Disclaimer & Nutzungsbedingungen

```
┌─────────────────────────────────────────────────────────────┐
│ ## Terms of Use & Disclaimer                                │
│                                                             │
│ Please read and accept the following terms:                 │
│                                                             │
│ ### 1. Disclaimer of Warranty                               │
│ This software is provided "AS IS" without warranty...       │
│                                                             │
│ ### 2. License - Private Use Only                           │
│ ❌ Commercial use, resale, distribution                     │
│ ✅ Private use on your own systems                          │
│                                                             │
│ ### 3. Responsibility for AI-Generated Content              │
│ You bear sole responsibility for all content...             │
│                                                             │
│ ### 4. Third-Party Models                                   │
│ Comply with respective license terms...                     │
│                                                             │
│ ### 5. Alpha/Beta Status                                    │
│ Errors, crashes, data loss may occur...                     │
│                                                             │
│ ### 6. Indemnification                                      │
│ You agree to indemnify and hold harmless...                 │
│                                                             │
│ ☐ I have read, understood, and accept the Terms of Use      │
│                                                             │
│                                              [Continue →]   │
└─────────────────────────────────────────────────────────────┘
```

### Step 1: Systemprüfung

```
┌─────────────────────────────────────────────────────────────┐
│ ## Step 1: System Check                                     │
│                                                             │
│ [Check system again]                                        │
│                                                             │
│ **Operating System:** Ubuntu 22.04 LTS (x86_64)            │
│                                                             │
│ ### Dependencies                                            │
│ - **Python:** [OK] v3.11.0                                  │
│ - **pip:** [OK] v23.0.1                                     │
│ - **ffmpeg:** [OK] v5.1.2                                   │
│ - **git:** [OK] v2.34.1                                     │
│ - **CUDA:** [OK] v12.1                                      │
│                                                             │
│ **System is ready for CINDERGRACE.**                        │
│                                                             │
│                                              [Next →]       │
└─────────────────────────────────────────────────────────────┘
```

### Step 2: ComfyUI Status

```
┌─────────────────────────────────────────────────────────────┐
│ ## Step 2: ComfyUI                                          │
│                                                             │
│ ComfyUI is the AI backend software that CINDERGRACE uses    │
│ for image and video generation.                             │
│                                                             │
│ Do you have ComfyUI installed?                              │
│                                                             │
│ ○ Yes, ComfyUI is already installed                        │
│ ○ No, I still need to install ComfyUI                      │
│                                                             │
│                              [← Back]    [Next →]           │
└─────────────────────────────────────────────────────────────┘
```

### Step 3: Installationsanleitung (falls "No" gewählt)

```
┌─────────────────────────────────────────────────────────────┐
│ ## Step 3: ComfyUI Installation                             │
│                                                             │
│ ┌─────────┬─────────┐                                       │
│ │ Windows │  Linux  │                                       │
│ └─────────┴─────────┘                                       │
│                                                             │
│ ### Windows Installation                                    │
│                                                             │
│ #### Option 1: Portable Version (Recommended)               │
│ 1. Download: ComfyUI_windows_portable_*.7z                 │
│ 2. Extract to C:\ComfyUI_portable                          │
│ 3. Run run_nvidia_gpu.bat                                  │
│                                                             │
│ #### Option 2: Git Installation                             │
│ ```                                                         │
│ git clone https://github.com/comfyanonymous/ComfyUI.git    │
│ ...                                                         │
│ ```                                                         │
│                                                             │
│ **Note:** After installation, you must start ComfyUI        │
│ before you can continue.                                    │
│                                                             │
│        [← Back]  [ComfyUI is installed and running →]       │
└─────────────────────────────────────────────────────────────┘
```

### Step 4: Konfiguration

```
┌─────────────────────────────────────────────────────────────┐
│ ## Step 4: Configuration                                    │
│                                                             │
│ ### ComfyUI Settings                                        │
│ Enter the path to your ComfyUI installation:                │
│                                                             │
│ ComfyUI Installation Path:                                  │
│ [/home/user/ComfyUI_____________________________]           │
│                                                             │
│ ComfyUI Server URL:                                         │
│ [http://127.0.0.1:8188__________________________]           │
│                                                             │
│ **Connection successful!** ComfyUI is reachable.            │
│                                                             │
│ [Test Connection]                                           │
│                                                             │
│ ---                                                         │
│ ### API Keys (Optional)                                     │
│ These keys enable additional features.                      │
│ They are stored **encrypted** in the local database.        │
│                                                             │
│ Civitai API Key:      [********************************]    │
│ Huggingface Token:    [________________________________]    │
│ Google TTS API Key:   [________________________________]    │
│                                                             │
│ ---                                                         │
│ ### Quick Start                                             │
│ ☑ Create example project with sample storyboard             │
│                                                             │
│               [← Back]              [Finish Setup ✓]        │
└─────────────────────────────────────────────────────────────┘
```

### Step 5: Abschluss (Neustart erforderlich)

```
┌─────────────────────────────────────────────────────────────┐
│ ## ✅ Setup Complete!                                       │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐│
│ │           🎉 CINDERGRACE ist jetzt eingerichtet!        ││
│ │                                                         ││
│ │   Die Konfiguration wurde gespeichert.                  ││
│ │                                                         ││
│ │   🔄 Bitte starte die App jetzt neu!                    ││
│ │   Drücke Ctrl+C im Terminal und starte mit              ││
│ │   ./start.sh neu.                                       ││
│ └─────────────────────────────────────────────────────────┘│
│                                                             │
│ **Nach dem Neustart:**                                      │
│ 1. Alle Tabs sind freigeschaltet                            │
│ 2. Dein Example-Projekt ist geladen (falls erstellt)        │
│ 3. Du kannst direkt mit der Arbeit beginnen!                │
│                                                             │
│ 💡 Einstellungen können jederzeit im ⚙️ Settings Tab        │
│    geändert werden.                                         │
└─────────────────────────────────────────────────────────────┘
```

---

## Workflow

```
┌───────────────┐
│ Disclaimer    │
│ akzeptieren   │
└───────┬───────┘
        │
        ▼
┌───────────────┐    ┌──────────────┐    ┌───────────────┐
│ System-       │───▶│ ComfyUI      │───▶│ Installation  │
│ prüfung       │    │ Status       │    │ (optional)    │
└───────────────┘    └──────────────┘    └───────────────┘
                            │                    │
                            │ (bereits installiert)
                            ▼                    ▼
                     ┌──────────────┐    ┌───────────────┐
                     │ Konfig-      │◀───│               │
                     │ uration      │    └───────────────┘
                     │ + API Keys   │
                     └──────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │ Abschluss    │
                     │ (Neustart)   │
                     └──────────────┘
```

---

## Dependencies

### Services Used

- `SystemDetector` (`services/system_detector.py`)
- `ConfigManager` (`infrastructure/config_manager.py`)
- `SettingsStore` (`infrastructure/settings_store.py`)
- `HelpService` (`infrastructure/help_service.py`)
- `HelpContext` (`infrastructure/help_ui.py`)
- `ProjectStore` (`infrastructure/project_store.py`)

---

## System Checks

Der SystemDetector prüft folgende Abhängigkeiten:

| Dependency | Required | Check Method |
|------------|----------|--------------|
| Python | Yes | `python --version` |
| pip | Yes | `pip --version` |
| ffmpeg | Yes | `ffmpeg -version` |
| git | No | `git --version` |
| CUDA | No | `nvidia-smi` |
| ComfyUI | No | HTTP GET to URL |

---

## Configuration Saved

Nach Abschluss des Setup werden folgende Werte gespeichert:

### In SettingsStore (SQLite, verschlüsselt)
```
setup_completed: true
disclaimer_accepted_date: "26.12.2025 um 21:29 Uhr"
civitai_api_key: (encrypted)
huggingface_token: (encrypted)
google_tts_api_key: (encrypted)
```

### In config/settings.json
```json
{
  "comfy_url": "http://127.0.0.1:8188",
  "comfy_root": "/path/to/ComfyUI"
}
```

---

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "Invalid path" | ComfyUI directory doesn't exist | Correct the path |
| "Connection failed" | ComfyUI not reachable | Start ComfyUI |
| "X required dependency(ies) missing" | System incomplete | Install dependencies |

---

## Disclaimer Contents

The disclaimer covers:

1. **Disclaimer of Warranty** - Software provided "AS IS"
2. **License - Private Use Only** - Non-commercial use only
3. **Responsibility for AI-Generated Content** - User bears sole responsibility
4. **Third-Party Models** - Comply with model license terms
5. **Alpha/Beta Status** - Errors and data loss may occur
6. **Indemnification** - User agrees to indemnify developers

---

## Reset Setup

Users can reset the setup wizard by:

1. Opening the Setup tab (after setup is complete)
2. Checking "Setup Wizard erneut durchlaufen"
3. Clicking "Setup Wizard neu starten"

This will:
- Delete `setup_completed` flag
- Delete `disclaimer_accepted_date`
- Reload the page to show the wizard again

---

## Related Files

- `addons/setup_wizard.py` - Main addon file
- `services/system_detector.py` - System detection service
- `infrastructure/settings_store.py` - Encrypted settings storage
- `infrastructure/config_manager.py` - Configuration manager
- `infrastructure/help_service.py` - Help tooltips
- `infrastructure/help_ui.py` - Help context
- `infrastructure/project_store.py` - Project creation

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v0.6.1 | 2025-12-26 | Added collapsible disclaimer in "Setup completed" view |
| v0.6.0 | 2025-12-16 | Added Disclaimer step, API keys, Example project creation |
| v0.5.0 | 2025-12-16 | Initial implementation |

---

**Maintained By:** Architecture Team
