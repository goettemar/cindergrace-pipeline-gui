# 📸 Dataset (Dataset Generator)

**Tab Name:** 📸 Dataset
**File:** `addons/dataset_generator.py`
**Version:** v1.0.0
**Last Updated:** December 20, 2025

---

## Overview

Der Dataset Generator erstellt automatisch Training-Datasets für LoRA Training. Aus einem einzelnen Basis-Bild werden 15 verschiedene Ansichten/Posen generiert, jeweils mit passenden Captions.

**Workflow:** Basis-Bild hochladen → 15 Ansichten generieren → Dataset für Character Trainer verwenden

**Backend:** Qwen Image Edit via ComfyUI

---

## Features

- **15 automatische Ansichten** - Verschiedene Posen und Perspektiven
- **Automatische Captions** - Passende Beschreibungen für jede Ansicht
- **Qwen Edit Integration** - Hochwertige Bildbearbeitung
- **Workflow-Auswahl** - Verschiedene gcl_* Workflows wählbar
- **Auflösungs-Guide** - Empfehlungen für verschiedene Trainings-Szenarien

---

## UI Structure

### Tab 1: Dataset erstellen

```
┌─────────────────────────────────────────────────────────────┐
│ 📸 Training Dataset generieren                              │
├──────────────────────────┬──────────────────────────────────┤
│ 📥 Eingabe               │ 🎬 Generierung                   │
│                          │                                  │
│ Charakter-Name:          │ [▶️ 15 Ansichten generieren]     │
│ [elena_warrior________]  │                                  │
│                          │ Status: ✅ 15/15 generiert       │
│ Basis-Bild:              │                                  │
│ ┌──────────────────┐     │ 🖼️ Generierte Ansichten         │
│ │                  │     │ ┌────┐┌────┐┌────┐┌────┐┌────┐  │
│ │  [Upload Image]  │     │ │Base││ 1  ││ 2  ││ 3  ││ 4  │  │
│ │                  │     │ └────┘└────┘└────┘└────┘└────┘  │
│ └──────────────────┘     │ ┌────┐┌────┐┌────┐┌────┐┌────┐  │
│                          │ │ 5  ││ 6  ││ 7  ││ 8  ││ 9  │  │
│ ⚙️ Workflow & Settings   │ └────┘└────┘└────┘└────┘└────┘  │
│ Workflow: [Qwen Edit ▼]  │ ┌────┐┌────┐┌────┐┌────┐┌────┐  │
│ Steps: [8] ────○─────    │ │10  ││11  ││12  ││13  ││14  │  │
│ CFG:   [1.0] ──○───      │ │10  ││11  ││12  ││13  ││14  │  │
│                          │ └────┘└────┘└────┘└────┘└────┘  │
│                          │                                  │
│                          │ Dataset-Pfad:                    │
│                          │ [/output/character_training/...] │
│                          │ [📁 Öffnen] [📋 Pfad kopieren]   │
└──────────────────────────┴──────────────────────────────────┘
```

### Tab 2: Ansichten-Referenz

Zeigt die 15 View Presets mit Namen, Qwen Edit Prompts und LoRA Captions.

### Tab 3: Auflösungs-Guide

```
┌─────────────────────────────────────────────────────────────┐
│ 💡 Auflösungs-Guide für LoRA Training                       │
├─────────────────────────────────────────────────────────────┤
│ 📊 Empfohlene Auflösungen nach Modell & VRAM               │
│                                                             │
│ | Modell | VRAM  | Basis-Bild    | Optimizer  | Hinweis    │
│ |--------|-------|---------------|------------|------------|│
│ | FLUX   | 16GB  | 512 x 512     | Prodigy    | Standard   │
│ | FLUX   | 24GB  | 768 x 768     | AdamW8bit  | Besser     │
│ | SDXL   | 8GB   | 512 x 512     | Prodigy    | Minimum    │
│ | SDXL   | 16GB  | 768 x 768     | AdamW8bit  | Kompromiss │
│ | SDXL   | 24GB  | 1024 x 1024   | AdamW8bit  | Optimal    │
│ | SD3    | 8GB   | 512 x 512     | Prodigy    | Minimum    │
│ | SD3    | 16GB  | 768 x 768     | AdamW8bit  | Kompromiss │
│ | SD3    | 24GB  | 1024 x 1024   | AdamW8bit  | Optimal    │
├─────────────────────────────────────────────────────────────┤
│ 🎬 Video-Generierung mit WAN                                │
│                                                             │
│ | Workflow | Auflösung   | Format    | Hinweis             │
│ |----------|-------------|-----------|---------------------|│
│ | WAN i2v  | 1280 x 720  | 16:9 Quer | 720p Standard       │
│ | WAN i2v  | 720 x 1280  | 9:16 Hoch | 720p Portrait       │
│ | WAN i2v  | 1920 x 1080 | 16:9 Quer | 1080p Beste         │
│ | WAN i2v  | 832 x 480   | 16:9 Quer | ⚠️ Nur Quick-Test   │
├─────────────────────────────────────────────────────────────┤
│ 🔄 Welches Modell für welchen Zweck?                       │
│                                                             │
│ | Ziel        | Modell    | Auflösung   | Anmerkung        │
│ |-------------|-----------|-------------|------------------|│
│ | Nur Bilder  | SDXL/SD3  | 1024 x 1024 | Quadratisch      │
│ | Nur Bilder  | FLUX      | 512 - 1024  | Flexibel         │
│ | Video (WAN) | FLUX      | 1280 x 720  | 16:9, passt WAN  │
│ | Video (WAN) | SDXL/SD3  | ❌          | Passt nicht!     │
└─────────────────────────────────────────────────────────────┘
```

---

## 15 View Presets

| # | Name | Qwen Edit Prompt | LoRA Caption |
|---|------|------------------|--------------|
| 1 | front_neutral | show the character from the front... | front view, facing camera, neutral expression |
| 2 | front_smile | show the character from the front... | front view, facing camera, gentle smile |
| 3 | three_quarter_left | turn the character slightly to face left... | three-quarter view, facing left |
| 4 | three_quarter_right | turn the character slightly to face right... | three-quarter view, facing right |
| 5 | profile_left | show the character's left profile... | left profile, side view |
| 6 | profile_right | show the character's right profile... | right profile, side view |
| 7 | back_view | show the character from behind... | back view, from behind |
| 8 | looking_up | show the character looking upward... | looking up, chin raised |
| 9 | looking_down | show the character looking downward... | looking down, chin lowered |
| 10 | closeup_face | close-up shot of the character's face... | close-up portrait, face detail |
| 11 | full_body | show the full body of the character... | full body shot, head to toe |
| 12 | upper_body | show the upper body of the character... | upper body, bust shot |
| 13 | head_tilt_left | show the character with head tilted... | head tilted left |
| 14 | head_tilt_right | show the character with head tilted... | head tilted right |
| 15 | dynamic_pose | show the character in a dynamic action pose | dynamic pose, action shot |

---

## Auflösungs-Empfehlungen

### Für Bild-LoRAs (quadratisch)

| Ziel-Modell | VRAM | Empfohlene Basis-Auflösung |
|-------------|------|---------------------------|
| FLUX | 16GB | 512 x 512 |
| FLUX | 24GB | 768 x 768 |
| SDXL | 8GB | 512 x 512 |
| SDXL | 16GB | 768 x 768 |
| SDXL | 24GB | 1024 x 1024 (nativ) |
| SD3 | 8GB | 512 x 512 |
| SD3 | 16GB | 768 x 768 |
| SD3 | 24GB | 1024 x 1024 (nativ) |

### Für Video-LoRAs (WAN kompatibel)

| Workflow | Format | Auflösung | Hinweis |
|----------|--------|-----------|---------|
| WAN i2v | 16:9 Quer | 1280 x 720 | Standard 720p |
| WAN i2v | 9:16 Hoch | 720 x 1280 | Portrait 720p |
| WAN i2v | 16:9 Quer | 1920 x 1080 | 1080p (beste) |
| WAN i2v | 16:9 Quer | 832 x 480 | Nur Quick-Test! |

**Wichtig:** Für Video-LoRAs nur **FLUX** verwenden! SDXL/SD3 sind quadratisch und passen nicht zu WAN.

---

## Output Structure

```
<ComfyUI>/output/character_training/<name>/
├── 00_base_image.png        # Original hochgeladenes Bild
├── 00_base_image.txt        # Caption
├── 01_front_neutral.png     # Generierte Ansicht
├── 01_front_neutral.txt     # Caption
├── 02_front_smile.png
├── 02_front_smile.txt
├── ...
├── 15_dynamic_pose.png
├── 15_dynamic_pose.txt
└── metadata.json            # Generierungs-Metadaten
```

---

## Dependencies

### Services Used

- `CharacterTrainerService` (`services/character_trainer_service.py`)
- `ConfigManager` (`infrastructure/config_manager.py`)

### External Dependencies

- **ComfyUI** - Für Qwen Image Edit Workflow
- **Qwen Image Edit Workflow** - `config/workflow_templates/gcl_qwen_image_edit_2509.json`
- **Custom Nodes** - FluxKontextImageScale, TextEncodeQwenImageEditPlus, CFGNorm, ModelSamplingAuraFlow

---

## Best Practices

### Basis-Bild Auswahl
- **Klarer, neutraler Hintergrund** - Bessere Ergebnisse bei Posen-Änderungen
- **Gute Beleuchtung** - Konsistente Beleuchtung in allen Ansichten
- **Charakter gut sichtbar** - Keine Verdeckungen
- **Richtige Auflösung** - Siehe Auflösungs-Guide!

### Auflösung wählen
1. Entscheide: Bilder oder Video?
2. Wähle Modell und VRAM-Preset
3. Generiere Basis-Bild in passender Auflösung
4. Nutze dieses für den Dataset Generator

### Nach der Generierung
- Dataset-Pfad kopieren
- Im Character Trainer für Training verwenden
- Optional: Schlechte Bilder manuell entfernen/ersetzen

---

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "Charakter-Namen eingeben" | Leeres Namensfeld | Namen eingeben |
| "Basis-Bild hochladen" | Kein Bild hochgeladen | Bild hochladen |
| "ComfyUI nicht erreichbar" | ComfyUI nicht gestartet | ComfyUI starten |
| "Qwen Workflow nicht gefunden" | Workflow fehlt | Workflow in config/workflow_templates/ platzieren |

---

## Related Files

- `addons/dataset_generator.py` - Main addon file
- `addons/character_trainer.py` - Training (verwendet generierte Datasets)
- `services/character_trainer_service.py` - Dataset generation logic
- `config/workflow_templates/qwen_image_edit_2509.json` - Qwen Edit Workflow

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v1.1.0 | 2025-12-21 | Workflow-Dropdown hinzugefügt, dynamische Workflow-Auswahl |
| v1.0.0 | 2025-12-20 | Initial release (ausgelagert aus Character Trainer) |

---

**Maintained By:** Architecture Team
**Last Updated:** December 21, 2025
