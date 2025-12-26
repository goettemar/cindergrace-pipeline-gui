# 🎞️ Transition (First/Last Frame Video)

**Tab Name:** 🎞️ Transition
**File:** `addons/firstlast_video.py`
**Version:** v0.6.0
**Last Updated:** December 16, 2025

---

## Overview

Der First/Last Frame Video Generator erstellt flüssige Übergangsvideos (Morphing) zwischen Bildern. Im Gegensatz zum regulären Video Generator, der ein Storyboard verwendet, arbeitet dieses Addon direkt mit hochgeladenen Bildern und generiert Transitions zwischen ihnen.

---

## Features

- **Multi-Bild Upload** - Mehrere Bilder hochladen und sortieren
- **Clip-Gruppierung** - Bilder in separate Clips aufteilen (Trenner einfügen)
- **Wan 2.2 Morphing** - Flüssige Übergänge zwischen Bildern generieren
- **Flexible Einstellungen** - Auflösung, Frames, FPS, Steps konfigurierbar
- **Reihenfolge ändern** - Bilder per Button nach oben/unten verschieben

---

## UI Structure

### Left Column: Image Management

```
┌─────────────────────────────────────────────┐
│ 📤 Bilder hochladen                         │
│ [Bilder auswählen (drag & drop)]            │
│ [📥 Bilder hinzufügen]                      │
├─────────────────────────────────────────────┤
│ 🖼️ Bilder-Reihenfolge                       │
│ ┌────┐ ┌────┐ ┌────┐ ┌────┐                │
│ │ 1  │ │ 2  │ │ 3  │ │ 4  │                │
│ └────┘ └────┘ └────┘ └────┘                │
│                                             │
│ [⬆️] [⬇️] [➖ Trenner] [🗑️ Entfernen]       │
│ [🗑️ Alle Bilder löschen]                   │
└─────────────────────────────────────────────┘
```

### Right Column: Clip Preview & Settings

```
┌─────────────────────────────────────────────┐
│ 📋 Clip-Struktur                            │
│                                             │
│ **Clip 1** (2 Transitions)                  │
│   img1.png → img2.png → img3.png            │
│                                             │
│ **Clip 2** (1 Transition)                   │
│   img4.png → img5.png                       │
│                                             │
│ Gesamt: 2 Clips, 3 Transitions              │
├─────────────────────────────────────────────┤
│ ⚙️ Einstellungen                            │
│                                             │
│ Prompt: [smooth cinematic transition...]    │
│                                             │
│ Auflösung: [1280×720 (Querformat) ▼]       │
│ Frames:    [81] ─────○─────── (≈5s @ 16fps)│
│ FPS:       [16] ───○───────                │
│ Steps:     [20] ───────○───                │
└─────────────────────────────────────────────┘
```

### Generation Section

```
┌─────────────────────────────────────────────┐
│ 🎬 Generierung                              │
│                                             │
│ [▶️ Videos generieren] [📁 Ausgabeordner]   │
│                                             │
│ Status: ✅ 2/2 Clips generiert (3 Trans.)   │
│         Dauer: 45.2s                        │
│                                             │
│ ┌─────────────────────────────────────┐    │
│ │ ▶️ Letztes generiertes Video        │    │
│ │    [Video Player]                   │    │
│ └─────────────────────────────────────┘    │
└─────────────────────────────────────────────┘
```

---

## Workflow

```
┌─────────────┐    ┌──────────────┐    ┌───────────────┐
│ Bilder      │───▶│ Reihenfolge  │───▶│ Clips         │
│ hochladen   │    │ sortieren    │    │ gruppieren    │
└─────────────┘    └──────────────┘    └───────────────┘
                                              │
                                              ▼
┌─────────────┐    ┌──────────────┐    ┌───────────────┐
│ Video       │◀───│ Wan 2.2      │◀───│ Transitions   │
│ Player      │    │ Generierung  │    │ definieren    │
└─────────────┘    └──────────────┘    └───────────────┘
```

---

## Clip-Gruppierung

Bilder können in separate Clips aufgeteilt werden:

**Ohne Trenner:**
```
img1 → img2 → img3 → img4 → img5
         \       /
          Clip 1 (4 Transitions)
```

**Mit Trenner nach img3:**
```
img1 → img2 → img3  |  img4 → img5
         \          |       /
       Clip 1       |    Clip 2
   (2 Transitions)  | (1 Transition)
```

---

## Resolution Options

| Label | Resolution | Aspect Ratio |
|-------|------------|--------------|
| 1280×720 (Querformat) | 1280×720 | 16:9 |
| 720×1280 (Hochformat) | 720×1280 | 9:16 |
| 854×480 (Querformat) | 854×480 | 16:9 |
| 480×854 (Hochformat) | 480×854 | 9:16 |
| 640×640 (Quadrat) | 640×640 | 1:1 |

---

## Dependencies

### Services Used

- `FirstLastVideoService` (`services/firstlast_video_service.py`)
- `ComfyUIAPI` (`infrastructure/comfy_api/client.py`)
- `ConfigManager` (`infrastructure/config_manager.py`)

### External Dependencies

- **Wan 2.2** - Video generation model
- **ComfyUI** - Backend for video generation
- **Workflow** - First/Last frame capable workflow (z.B. `video_wan2_2_14B_flf2v.json`)

---

## Data Flow

### Input

- **Bilder** - PNG, JPG (beliebige Quelle)
- **Settings** - Resolution, Frames, FPS, Steps, Prompt

### Output

- **Videos** - MP4 files in output directory
- **Location** - `<ComfyUI>/output/firstlast_video/` oder projekt-spezifisch

---

## Generation Logic

Für jeden Clip mit N Bildern werden N-1 Transitions generiert:

```python
for clip in clips:
    for i in range(len(clip) - 1):
        first_frame = clip[i]
        last_frame = clip[i + 1]
        generate_transition(first_frame, last_frame)
```

### Workflow Injection

Der Service injiziert in den Wan Workflow:
- `first_frame` - Startbild der Transition
- `last_frame` - Endbild der Transition
- `prompt` - Bewegungsbeschreibung
- `num_frames` - Anzahl der Frames
- `width`, `height` - Auflösung

---

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "Keine Bilder vorhanden" | Leere Liste | Bilder hochladen |
| "Keine gültigen Clips" | <2 Bilder pro Clip | Mehr Bilder hinzufügen |
| ComfyUI Fehler | Workflow oder Model | ComfyUI Console prüfen |

---

## State Management

Das Addon verwendet Gradio State für:
- `images_state` - Liste der Bilder `[{"path": str, "name": str}, ...]`
- `clips_state` - Clip-Indizes `[[0, 1, 2], [3, 4]]`
- `selected_index` - Aktuell ausgewähltes Bild

---

## Related Files

- `addons/firstlast_video.py` - Main addon file
- `services/firstlast_video_service.py` - Generation business logic
- `config/workflow_templates/video_wan2_2_14B_flf2v.json` - First/Last workflow

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v0.6.0 | 2025-12-16 | Initial implementation |

---

**Maintained By:** Architecture Team
