# 📥 Import (Image Importer)

**Tab Name:** 📥 Import
**File:** `addons/image_importer.py`
**Version:** v0.6.0
**Last Updated:** December 16, 2025

---

## Overview

Der Image Importer ermöglicht das Importieren vorhandener Bilder als Alternative zum Keyframe Generator. Er analysiert Bilder optional mit Florence-2 für automatische Prompt-Generierung und erstellt automatisch ein Storyboard sowie die `selected_keyframes.json` für den direkten Einsatz im Video Generator.

---

## Features

- **Ordner-Scan** - Scanne beliebige Ordner nach Bildern (PNG, JPG, WEBP)
- **File Upload** - Bilder direkt hochladen als Alternative
- **Florence-2 AI-Analyse** - Automatische Prompt-Generierung via ComfyUI
- **Storyboard-Erstellung** - Automatisch Storyboard aus importierten Bildern
- **Workflow-Integration** - Direkt zum Video Generator, Keyframe Selector überspringen

---

## UI Structure

### Step 1: Bilder auswählen

```
┌─────────────────────────────────────────────┐
│ 📂 Ordner-Pfad                              │
│ [/pfad/zu/deinen/bildern___________] [🔍]   │
│                                             │
│ ▼ Oder: Bilder hochladen                    │
│   [📤 Bilder hochladen]                     │
└─────────────────────────────────────────────┘
```

### Step 2: Vorschau & Reihenfolge

```
┌─────────────────────────────────────────────┐
│ 🖼️ Bilder-Galerie                           │
│ ┌────┐ ┌────┐ ┌────┐ ┌────┐                │
│ │ 1  │ │ 2  │ │ 3  │ │ 4  │                │
│ └────┘ └────┘ └────┘ └────┘                │
│                                             │
│ # | Dateiname    | Auflösung | Name         │
│ 1 | image_01.png | 1024x576  | image-01     │
│ 2 | image_02.png | 1024x576  | image-02     │
│                                             │
│ [🗑️ Bild entfernen: ▼ image_01.png]        │
└─────────────────────────────────────────────┘
```

### Step 3: Import-Einstellungen

```
┌─────────────────────────────────────────────┐
│ Projekt-Name: [Imported Project__________]  │
│ Storyboard:   [imported_storyboard_______]  │
│ Dauer/Shot:   [3.0 Sek.] ─────────○─────── │
│                                             │
│ ☑️ Dateien umbenennen (empfohlen)           │
│ ☐ Bild-Auflösung übernehmen                │
│                                             │
│ ▼ 🤖 KI-Analyse (Florence-2)               │
│   [🔍 Bilder analysieren mit Florence-2]    │
└─────────────────────────────────────────────┘
```

### Step 4: Import starten

```
┌─────────────────────────────────────────────┐
│ [📥 Bilder importieren & Storyboard erst.]  │
│                                             │
│ ✅ Import erfolgreich!                      │
│ 5 Bilder wurden importiert.                 │
│                                             │
│ Nächste Schritte:                           │
│ 1. 📖 Storyboard Tab - Prompts anpassen    │
│ 2. 🎥 Video Generator - Videos generieren   │
└─────────────────────────────────────────────┘
```

---

## Workflow

```
┌─────────────┐    ┌──────────────┐    ┌───────────────┐
│ Ordner/     │───▶│ Florence-2   │───▶│ Storyboard    │
│ Upload      │    │ Analyse      │    │ erstellen     │
└─────────────┘    │ (optional)   │    └───────────────┘
                   └──────────────┘           │
                                              ▼
┌─────────────┐    ┌──────────────┐    ┌───────────────┐
│ Video       │◀───│ selected_    │◀───│ Keyframes     │
│ Generator   │    │ keyframes    │    │ kopieren      │
└─────────────┘    └──────────────┘    └───────────────┘
```

---

## Dependencies

### Services Used

- `ImageImportService` (`services/image_import_service.py`)
- `ImageAnalyzerService` (`services/image_analyzer_service.py`)
- `ProjectStore` (`infrastructure/project_store.py`)
- `ConfigManager` (`infrastructure/config_manager.py`)

### External Dependencies

- **Florence-2** - AI Model für Bildanalyse (via ComfyUI)
- **ComfyUI Workflow** - `config/workflow_templates/florence2_caption.json`

---

## Data Flow

### Input

- **Bilder** - PNG, JPG, WEBP aus Ordner oder Upload
- **Projekt** - Aktives Projekt aus ProjectStore

### Output

- **Keyframes** - `<project>/keyframes/<filename_base>_v1_00001_.png`
- **Selected** - `<project>/selected/<filename_base>_v1_00001_.png`
- **Storyboard** - `<project>/storyboards/<name>.json`
- **Selection** - `<project>/selected/selected_keyframes.json`

---

## Florence-2 Analysis

Die Florence-2 Analyse generiert automatisch Prompts für jedes Bild:

```json
{
  "caption": "A detailed description of the image...",
  "description": "A short caption..."
}
```

Diese werden in das Storyboard übernommen:

```json
{
  "shots": [
    {
      "shot_id": "001",
      "filename_base": "image-01",
      "prompt": "A detailed description...",
      "description": "A short caption..."
    }
  ]
}
```

---

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "Kein aktives Projekt" | Kein Projekt ausgewählt | Tab 📁 Projekt öffnen |
| "Ordner nicht gefunden" | Ungültiger Pfad | Pfad überprüfen |
| "ComfyUI nicht erreichbar" | Florence-2 nicht verfügbar | ComfyUI starten |
| "Keine gültigen Bilder" | Keine PNG/JPG/WEBP | Bildformat prüfen |

---

## Configuration

### Settings

Keine zusätzlichen Settings erforderlich. Verwendet:
- `comfy_url` - ComfyUI Server für Florence-2
- `active_project_slug` - Ziel-Projekt

### Workflow

Florence-2 Workflow muss vorhanden sein:
- `config/workflow_templates/florence2_caption.json`

---

## Related Files

- `addons/image_importer.py` - Main addon file
- `services/image_import_service.py` - Import business logic
- `services/image_analyzer_service.py` - Florence-2 integration
- `config/workflow_templates/florence2_caption.json` - AI workflow

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v0.6.0 | 2025-12-16 | Initial implementation |

---

**Maintained By:** Architecture Team
