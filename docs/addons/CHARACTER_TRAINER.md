# 🎭 LoRA (Character Trainer)

**Tab Name:** 🎭 LoRA
**File:** `addons/character_trainer.py`
**Version:** v0.9.0
**Last Updated:** December 20, 2025

---

## Overview

Der Character Trainer ermöglicht das Training von Character LoRAs mit Kohya sd-scripts. Er unterstützt FLUX, SDXL und SD3 Modelle und bietet während des Trainings eine Live-Vorschau der generierten Testbilder.

**Hinweis:** Die Dataset-Generierung wurde in das separate Addon **📸 Dataset Generator** ausgelagert.

**Unterstützte Model-Typen:**
- **FLUX** - Diffusion Transformer (beste Qualität, 16GB+ VRAM)
- **SDXL** - Stable Diffusion XL (schneller, ab 8GB VRAM)
- **SD3** - Stable Diffusion 3 (hohe Qualität, ab 8GB VRAM)

**Training Backend:** Kohya sd-scripts (direkte Integration, kein ComfyUI-Training)

---

## Features

### Kohya LoRA Training
- **Multi-Model Support** - FLUX, SDXL und SD3 Training
- **Direkte sd-scripts Integration** - Stabiler als ComfyUI-basiertes Training
- **VRAM-Presets** - Optimiert für 8GB, 16GB und 24GB+ GPUs
- **FP8-Unterstützung** - Reduzierter VRAM-Verbrauch
- **Dynamische Model-Auswahl** - Zeigt verfügbare Modelle je nach Model-Typ
- **Echtzeit-Logging** - Training-Fortschritt live verfolgen

### NEU: Testbild-Generierung (v0.9.0)
- **Sample Every N Steps** - Generiert Testbilder während des Trainings
- **Custom Sample Prompt** - Eigener Prompt für Testbilder
- **Live-Vorschau** - Zeigt automatisch das neueste Testbild
- **Automatische LoRA-Erkennung** - Zeigt Pfad zum fertigen LoRA

---

## UI Structure

```
┌─────────────────────────────────────────────────────────────┐
│ 🎭 Kohya LoRA Training                                      │
├──────────────────────────┬──────────────────────────────────┤
│ 📂 Training Dataset      │ 🎬 Training                      │
│                          │                                  │
│ [✅ elena (16 Bilder)]   │ [▶️ Training starten] [⏹️ Stop]  │
│ [🔄]                     │                                  │
│                          │ Status: 🚀 Step 500/1500 (33%)   │
│ Oder manueller Pfad:     │ Loss: 0.0234 - ETA: 12m          │
│ [/pfad/zum/dataset___]   │                                  │
│                          │ Fortschritt: [████████──] 33%    │
├──────────────────────────┤                                  │
│ 🏷️ Charakter-Info        │ 📜 Training Log                  │
│                          │ ┌────────────────────────────┐   │
│ Charakter-Name:          │ │ Step 498/1500 - Loss: 0.024│   │
│ [elena_______________]   │ │ Step 499/1500 - Loss: 0.023│   │
│                          │ │ Step 500/1500 - Loss: 0.023│   │
│ Trigger-Wort:            │ │ Saving checkpoint...       │   │
│ [elena_______________]   │ └────────────────────────────┘   │
├──────────────────────────┤                                  │
│ 🎯 Model-Typ             │ 🖼️ Letztes Testbild             │
│                          │ ┌────────────────────────────┐   │
│ [🔥 FLUX ▼]              │ │                            │   │
│                          │ │  [Sample bei Step 500]     │   │
├──────────────────────────┤ │                            │   │
│ ⚙️ Training-Einstellungen │ └────────────────────────────┘   │
│                          │                                  │
│ GPU VRAM Preset:         │ 📊 Ergebnis                     │
│ [💾 16GB VRAM ▼]         │                                  │
│                          │ LoRA Datei:                      │
│ Training Steps: [1500]   │ [cg_elena.safetensors_______]    │
│                          │ [📁 LoRA Ordner öffnen]          │
│ ▼ 🔧 Erweiterte Settings │                                  │
│   Network Dim: [16]      │                                  │
│   Dataset Repeats: [10]  │                                  │
│   Save Every: [500]      │                                  │
│                          │                                  │
│   🖼️ Testbild-Generierung│                                  │
│   Sample Every: [250]    │  ← 0 = deaktiviert              │
│   Sample Prompt:         │                                  │
│   [elena, portrait___]   │  ← Optional                     │
│                          │                                  │
│   🎯 Model-Auswahl       │                                  │
│   Base Model:            │                                  │
│   [flux1-dev-fp8 ▼]      │                                  │
│   T5XXL Encoder:         │                                  │
│   [t5xxl_fp8_e4m3fn ▼]   │                                  │
│   [🔄 Models aktualisieren] │                               │
└──────────────────────────┴──────────────────────────────────┘
```

---

## Testbild-Generierung

### Konfiguration

| Parameter | Wert | Beschreibung |
|-----------|------|--------------|
| Sample Every N Steps | 0-1000 | 0 = deaktiviert, 250-500 empfohlen |
| Sample Prompt | Text | Optional, Standard: `{trigger_word}, portrait, high quality` |
| Sample Sampler | euler | Intern verwendet |

### Sample Output

Die Testbilder werden im Unterordner `sample/` des Output-Verzeichnisses gespeichert:

```
<ComfyUI>/models/loras/
├── cg_elena.safetensors           # Finales LoRA
├── cg_elena-step00500.safetensors # Checkpoint
└── sample/
    ├── sample_0000250.png         # Testbild bei Step 250
    ├── sample_0000500.png         # Testbild bei Step 500
    └── sample_0000750.png         # usw.
```

### Live-Vorschau

Die UI zeigt automatisch das neueste Testbild an:
- Aktualisierung alle 2 Sekunden während des Trainings
- Ermöglicht visuelle Beurteilung des Training-Fortschritts
- Hilft bei der Entscheidung, ob Training fortgesetzt werden soll

---

## Unterstützte Model-Typen

### FLUX (Diffusion Transformer)

| Eigenschaft | Wert |
|-------------|------|
| Training Script | `flux_train_network.py` |
| Network Module | `networks.lora_flux` |
| Min VRAM | 16GB |
| Text Encoder | CLIP-L + T5XXL (separat) |
| VAE Parameter | `--ae` |
| Besonderheit | `blocks_to_swap` für VRAM-Optimierung |

### SDXL (Stable Diffusion XL)

| Eigenschaft | Wert |
|-------------|------|
| Training Script | `sdxl_train_network.py` |
| Network Module | `networks.lora` |
| Min VRAM | 8GB |
| Text Encoder | 2x CLIP (im Checkpoint eingebettet) |
| VAE Parameter | `--vae` (optional) |
| Besonderheit | Kein T5XXL benötigt, schneller |

### SD3 (Stable Diffusion 3)

| Eigenschaft | Wert |
|-------------|------|
| Training Script | `sd3_train_network.py` |
| Network Module | `networks.lora_sd3` |
| Min VRAM | 8GB |
| Text Encoder | CLIP-L + CLIP-G + T5XXL |
| VAE Parameter | `--vae` |
| Besonderheit | `blocks_to_swap` für VRAM-Optimierung |

---

## VRAM Presets

### FLUX Presets

| Preset | Resolution | Batch | Network Dim | Optimizer | Steps |
|--------|------------|-------|-------------|-----------|-------|
| 16GB | 512px | 1 | 16 | Prodigy | 1500 |
| 24GB+ | 768px | 2 | 32 | AdamW8bit | 2000 |

### SDXL Presets

| Preset | Resolution | Batch | Network Dim | Optimizer | Steps |
|--------|------------|-------|-------------|-----------|-------|
| 8GB | 512px | 1 | 8 | Prodigy | 1000 |
| 16GB | 768px | 1 | 16 | AdamW8bit | 1500 |
| 24GB+ | 1024px | 2 | 32 | AdamW8bit | 2000 |

### SD3 Presets

| Preset | Resolution | Batch | Network Dim | Optimizer | Steps |
|--------|------------|-------|-------------|-----------|-------|
| 8GB | 512px | 1 | 12 | Prodigy | 1000 |
| 16GB | 768px | 1 | 24 | AdamW8bit | 1500 |
| 24GB+ | 1024px | 2 | 32 | AdamW8bit | 2000 |

---

## Dependencies

### Services Used

- `KohyaTrainerService` (`services/kohya_trainer_service.py`)
- `LoraTrainerService` (`services/lora_trainer_service.py`) - Dataset validation
- `ConfigManager` (`infrastructure/config_manager.py`)

### Kohya Submodules

- `services/kohya/models.py` - Enums, Presets, Progress-Tracking
- `services/kohya/config_builder.py` - TOML-Generierung inkl. Sample-Config
- `services/kohya/training_runner.py` - Subprocess-Management
- `services/kohya/model_scanner.py` - Model-Erkennung

### External Dependencies

- **Kohya sd-scripts** (sd3 branch) - `tools/sd-scripts/`

---

## Output Structure

### Kohya Training Output

```
<ComfyUI>/models/loras/
├── cg_<name>.safetensors           # Trained LoRA
├── cg_<name>-step00500.safetensors # Checkpoint
├── cg_<name>-step01000.safetensors # Checkpoint
└── sample/                         # Testbilder (wenn aktiviert)
    ├── sample_0000250.png
    ├── sample_0000500.png
    └── ...
```

### Config Files

```
<cindergrace_gui>/config/training_configs/
├── <name>_kohya_training.toml  # Training config
├── <name>_dataset.toml         # Dataset config
└── <name>_sample_prompts.txt   # Sample prompts (wenn aktiviert)
```

---

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "Charakter-Name fehlt" | Leeres Feld | Namen eingeben |
| "Trigger-Wort fehlt" | Leeres Feld | Trigger-Wort eingeben |
| "Kein gültiges Dataset" | Dataset nicht gefunden | Dataset im Dataset Generator erstellen |
| "CUDA out of memory" | Zu wenig VRAM | ComfyUI beenden, kleineres Preset wählen |
| "Kohya sd-scripts nicht gefunden" | sd-scripts nicht installiert | Installation in `tools/sd-scripts/` |

---

## Best Practices

### Trigger-Wort
- Einzigartiges Wort wählen (z.B. "elena")
- Nicht generische Begriffe (nicht "girl", "man")
- Wird automatisch als `cg_<name>` prefix gespeichert

### Model-Typ Auswahl
- **FLUX**: Beste Qualität, aber 16GB+ VRAM nötig
- **SDXL**: Guter Kompromiss, ab 8GB VRAM, schneller
- **SD3**: Hohe Qualität, ab 8GB VRAM, braucht SD3-Modelle

### Testbild-Generierung
- **250-500 Steps** empfohlen für regelmäßige Vorschau
- **Sample Prompt** sollte Trigger-Wort enthalten
- Beobachte den Fortschritt und stoppe bei Übertraining

### VRAM-Optimierung
- ComfyUI vor Training beenden
- FP8 Modelle bevorzugen
- Kleineres VRAM-Preset bei Problemen
- `nvidia-smi` zum Prüfen der GPU-Auslastung

---

## Related Files

- `addons/character_trainer.py` - Main addon file
- `addons/dataset_generator.py` - Dataset Generation (ausgelagert)
- `services/kohya_trainer_service.py` - Kohya training orchestration
- `services/kohya/` - Kohya submodules
- `tools/sd-scripts/` - Kohya sd-scripts installation
- `config/training_configs/` - Generated TOML configs

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v0.9.0 | 2025-12-20 | Testbild-Generierung, Sample-Vorschau, LoRA-Pfad-Fix, Dataset Generator ausgelagert |
| v0.8.0 | 2025-12-20 | Multi-Model Support (FLUX/SDXL/SD3), dynamische Model-Auswahl, 8GB VRAM Preset |
| v0.7.0 | 2025-12-17 | Removed ComfyUI training, Kohya-only, configurable models |
| v0.6.0 | 2025-12-16 | Initial implementation |

---

**Maintained By:** Architecture Team
