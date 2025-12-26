# Setup Wizard Addon Documentation

**Tab Name:** Setup
**File:** `addons/setup_wizard.py`
**Version:** v0.6.0
**Last Updated:** December 16, 2025

---

## Overview

Der Setup-Assistent führt neue Benutzer durch die Ersteinrichtung von CINDERGRACE. Er prüft Systemabhängigkeiten, bietet Installationsanleitungen für ComfyUI und konfiguriert die Verbindung zum Backend.

---

## Features

- **Systemprüfung** - Automatische Erkennung von Abhängigkeiten (Python, ffmpeg, etc.)
- **ComfyUI Installation** - Schritt-für-Schritt Anleitung für Windows und Linux
- **Konfiguration** - ComfyUI Pfad und URL einstellen
- **Verbindungstest** - Prüfe ComfyUI-Erreichbarkeit

---

## UI Structure

### Step 1: Systemprüfung

```
┌─────────────────────────────────────────────────────────────┐
│ ## Schritt 1: Systemprüfung                                 │
│                                                             │
│ [System erneut prüfen]                                      │
│                                                             │
│ **Betriebssystem:** Ubuntu 22.04 LTS (x86_64)              │
│                                                             │
│ ### Abhängigkeiten                                          │
│ - **Python:** [OK] v3.11.0                                  │
│ - **pip:** [OK] v23.0.1                                     │
│ - **ffmpeg:** [OK] v5.1.2                                   │
│ - **git:** [OK] v2.34.1                                     │
│ - **CUDA:** [OK] v12.1                                      │
│                                                             │
│ **System ist bereit für CINDERGRACE.**                      │
│                                                             │
│                                              [Weiter →]     │
└─────────────────────────────────────────────────────────────┘
```

### Step 2: ComfyUI Status

```
┌─────────────────────────────────────────────────────────────┐
│ ## Schritt 2: ComfyUI                                       │
│                                                             │
│ ComfyUI ist die KI-Backend-Software, die CINDERGRACE für    │
│ die Bild- und Videogenerierung verwendet.                   │
│                                                             │
│ Haben Sie ComfyUI bereits installiert?                      │
│                                                             │
│ ○ Ja, ComfyUI ist bereits installiert                      │
│ ○ Nein, ich muss ComfyUI noch installieren                 │
│                                                             │
│                              [← Zurück]    [Weiter →]       │
└─────────────────────────────────────────────────────────────┘
```

### Step 3: Installationsanleitung

```
┌─────────────────────────────────────────────────────────────┐
│ ## Schritt 3: ComfyUI Installation                          │
│                                                             │
│ ┌─────────┬─────────┐                                       │
│ │ Windows │  Linux  │                                       │
│ └─────────┴─────────┘                                       │
│                                                             │
│ ### Windows Installation                                    │
│                                                             │
│ #### Option 1: Portable Version (Empfohlen)                 │
│ 1. Download: ComfyUI_windows_portable_*.7z                 │
│ 2. Entpacken nach C:\ComfyUI_portable                      │
│ 3. run_nvidia_gpu.bat ausführen                            │
│                                                             │
│ #### Option 2: Git Installation                             │
│ ```                                                         │
│ git clone https://github.com/comfyanonymous/ComfyUI.git    │
│ cd ComfyUI                                                  │
│ python -m venv venv                                         │
│ ...                                                         │
│ ```                                                         │
│                                                             │
│ **Hinweis:** Nach der Installation müssen Sie ComfyUI       │
│ starten, bevor Sie fortfahren können.                       │
│                                                             │
│                 [← Zurück]  [ComfyUI ist installiert →]     │
└─────────────────────────────────────────────────────────────┘
```

### Step 4: Konfiguration

```
┌─────────────────────────────────────────────────────────────┐
│ ## Schritt 4: Konfiguration                                 │
│                                                             │
│ Geben Sie den Pfad zu Ihrer ComfyUI-Installation ein:       │
│                                                             │
│ ComfyUI-Installationspfad:                                  │
│ [/home/user/ComfyUI_____________________________]           │
│                                                             │
│ ComfyUI-Server URL:                                         │
│ [http://127.0.0.1:8188__________________________]           │
│                                                             │
│ **Verbindung erfolgreich!** ComfyUI ist erreichbar.         │
│                                                             │
│ [Verbindung testen]  [← Zurück]  [Setup abschließen ✓]     │
└─────────────────────────────────────────────────────────────┘
```

### Step 5: Abschluss

```
┌─────────────────────────────────────────────────────────────┐
│ ## Setup abgeschlossen!                                     │
│                                                             │
│ **CINDERGRACE ist jetzt eingerichtet!**                     │
│                                                             │
│ Sie können jetzt:                                           │
│ 1. Im **Projekt**-Tab ein neues Projekt erstellen          │
│ 2. Im **Keyframe-Generator** Bilder generieren             │
│ 3. Im **Video-Generator** Videos erstellen                 │
│                                                             │
│ Viel Erfolg mit Ihren Projekten!                            │
│                                                             │
│                                      [Zum Projekt-Tab →]    │
└─────────────────────────────────────────────────────────────┘
```

---

## Workflow

```
┌─────────────┐    ┌──────────────┐    ┌───────────────┐
│ System-     │───▶│ ComfyUI      │───▶│ Installation  │
│ prüfung     │    │ Status       │    │ (optional)    │
└─────────────┘    └──────────────┘    └───────────────┘
                          │                    │
                          │ (bereits installiert)
                          ▼                    ▼
                   ┌──────────────┐    ┌───────────────┐
                   │ Konfig-      │◀───│               │
                   │ uration      │    └───────────────┘
                   └──────────────┘
                          │
                          ▼
                   ┌──────────────┐
                   │ Abschluss    │
                   └──────────────┘
```

---

## Dependencies

### Services Used

- `SystemDetector` (`services/system_detector.py`)
- `ConfigManager` (`infrastructure/config_manager.py`)
- `HelpService` (`infrastructure/help_service.py`)
- `HelpContext` (`infrastructure/help_ui.py`)

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

Nach Abschluss des Setup werden folgende Werte in `config/settings.json` gespeichert:

```json
{
  "comfy_url": "http://127.0.0.1:8188",
  "comfy_root": "/path/to/ComfyUI",
  "setup_completed": true,
  "setup_completed_at": "2025-12-16T10:30:00"
}
```

---

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "Pfad ungültig" | ComfyUI Verzeichnis existiert nicht | Pfad korrigieren |
| "Verbindung fehlgeschlagen" | ComfyUI nicht erreichbar | ComfyUI starten |
| "X erforderliche Abhängigkeit(en) fehlen" | System incomplete | Abhängigkeiten installieren |

---

## Installation Guides

### Windows (Portable)

1. Download von GitHub Releases
2. 7z entpacken
3. `run_nvidia_gpu.bat` ausführen
4. Browser öffnet `http://127.0.0.1:8188`

### Windows (Git)

```powershell
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
python main.py
```

### Linux

```bash
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
python main.py --listen 127.0.0.1 --port 8188
```

---

## Related Files

- `addons/setup_wizard.py` - Main addon file
- `services/system_detector.py` - System detection service
- `infrastructure/help_service.py` - Help tooltips
- `infrastructure/help_ui.py` - Help context
- `config/settings.json` - Configuration storage

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v0.6.0 | 2025-12-16 | Initial implementation |

---

**Maintained By:** Architecture Team
