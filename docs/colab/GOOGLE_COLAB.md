# Google Colab Integration Documentation

**Status:** Beta / Nicht funktional
**Files:** `colab/Cindergrace_ComfyUI.ipynb`, `colab/Comfy2.ipynb`
**Version:** v0.6.0 (Beta)
**Last Updated:** December 16, 2025
**Backlog Issue:** #029

---

## Overview

Die Google Colab Integration ermöglicht die Nutzung von ComfyUI als Cloud-Backend für CINDERGRACE. Die Notebooks im `colab/` Ordner automatisieren die Installation und Konfiguration von ComfyUI auf Google Colab mit GPU-Unterstützung.

> **Experimentell / Nicht vollständig funktional** - Siehe bekannte Einschränkungen unten.

---

## Notebooks

### Cindergrace_ComfyUI.ipynb

Hauptnotebook für das CINDERGRACE Cloud Backend:

1. **Konfiguration** - Workspace und Optionen festlegen
2. **Google Drive** - Persistente Speicherung mounten
3. **ComfyUI Installation** - Clone und Dependencies
4. **HuggingFace Login** - Für geschützte Modelle
5. **Modell-Downloads** - Flux, Wan, Text Encoders
6. **ComfyUI Start** - Mit Cloudflare Tunnel

### Comfy2.ipynb

Alternative Konfiguration (Details variieren).

---

## Setup Steps

### 1. Konfiguration

```python
USE_GOOGLE_DRIVE = True        # Persistente Speicherung
UPDATE_COMFY_UI = False        # ComfyUI aktualisieren
INSTALL_COMFYUI_MANAGER = True # Manager für Custom Nodes
INSTALL_NODE_DEPENDENCIES = True
INSTALL_FLUXTRAINER = False    # Optional: LoRA Training
```

### 2. Google Drive Mount

```python
from google.colab import drive
drive.mount('/content/drive')
```

Workspace: `/content/drive/MyDrive/ComfyUI`

### 3. ComfyUI Installation

```bash
git clone https://github.com/comfyanonymous/ComfyUI
pip install xformers -r requirements.txt
```

### 4. HuggingFace Token

Für geschützte Modelle (Flux, VAE):
- Token erstellen: https://huggingface.co/settings/tokens
- Im Notebook eingeben

### 5. Modell-Downloads

| Model | Size | Auth Required |
|-------|------|---------------|
| Flux Krea-Dev | ~23GB | Yes |
| Flux VAE | ~300MB | Yes |
| T5 XXL FP16 | ~9GB | No |
| CLIP L | ~250MB | No |
| Wan 2.2 14B | ~28GB | TBD |
| Wan 2.2 5B | ~10GB | TBD |

### 6. Cloudflare Tunnel

```bash
cloudflared tunnel --url http://127.0.0.1:8188
```

Generiert öffentliche URL für CINDERGRACE Settings.

---

## Bekannte Einschränkungen

### Kritisch

- **Wan 2.2 Modell-URLs nicht hinterlegt** - Download-Zellen unvollständig
- **Session-Timeout** - Google Colab Free: max ~12h
- **GPU-Verfügbarkeit** - Nicht garantiert bei Free Tier

### Instabil

- **Cloudflare Tunnel** - Kann nach einiger Zeit abbrechen
- **Keine Auto-Reconnect** - Manueller Neustart erforderlich
- **FluxTrainer Fork** - URL möglicherweise veraltet

### Einschränkungen

- **Speicherplatz** - Google Drive Limit beachten
- **VRAM** - Colab GPU: meist 15GB (T4) oder 40GB (A100)
- **Geschwindigkeit** - Langsamer als lokale RTX 4090

---

## Integration mit CINDERGRACE

### Verbindung herstellen

1. Colab Notebook ausführen bis zum Start-Schritt
2. Cloudflare URL kopieren (z.B. `https://xxx.trycloudflare.com`)
3. In CINDERGRACE: **Settings** → **ComfyUI URL** → URL einfügen
4. Verbindung testen

### Workflow

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ CINDERGRACE  │───▶│ Cloudflare   │───▶│ Colab        │
│ (lokal)      │    │ Tunnel       │    │ ComfyUI      │
└──────────────┘    └──────────────┘    └──────────────┘
                                               │
                                               ▼
                                        ┌──────────────┐
                                        │ Google Drive │
                                        │ (output)     │
                                        └──────────────┘
```

---

## Model Directory Structure

```
/content/drive/MyDrive/ComfyUI/
├── models/
│   ├── diffusion_models/
│   │   └── flux1-krea-dev.safetensors
│   ├── text_encoders/
│   │   ├── t5xxl_fp16.safetensors
│   │   └── clip_l.safetensors
│   ├── vae/
│   │   └── ae.safetensors
│   ├── loras/
│   └── checkpoints/
├── custom_nodes/
│   └── ComfyUI-Manager/
└── output/
```

---

## Troubleshooting

### "GPU not available"

- Colab Free Tier: GPU-Verfügbarkeit variiert
- Lösung: Später erneut versuchen oder Colab Pro

### "Out of memory"

- Modell zu groß für verfügbares VRAM
- Lösung: Kleineres Modell wählen (Wan 5B statt 14B)

### "Tunnel disconnected"

- Cloudflare Timeout oder Colab Idle
- Lösung: Notebook neu starten, neue URL generieren

### "HuggingFace access denied"

- Token fehlt oder ungültig
- Lösung: Neuen Token erstellen und eingeben

---

## Planned Improvements (v0.8.0)

1. **Wan 2.2 URLs vervollständigen**
   - HuggingFace Links für 14B und 5B Modelle

2. **Keep-Alive Mechanismus**
   - Verhindert Colab Session Timeout

3. **Auto-Reconnect**
   - Automatische Wiederverbindung bei Tunnel-Abbruch

4. **Health Check**
   - Integration mit CINDERGRACE Health System

5. **Dokumentation**
   - Video-Tutorial für Colab Setup

---

## Cost Considerations

### Google Colab Free

- **GPU:** T4 (15GB VRAM) - nicht garantiert
- **Session:** Max ~12h, dann Reset
- **Storage:** Nur Google Drive persistent
- **Empfohlen für:** Testing, kleine Projekte

### Google Colab Pro ($9.99/Monat)

- **GPU:** T4, P100, V100 - priorisiert
- **Session:** Längere Laufzeit
- **Storage:** Mehr Google Drive
- **Empfohlen für:** Regelmäßige Nutzung

### Google Colab Pro+ ($49.99/Monat)

- **GPU:** A100 (40GB VRAM) - priorisiert
- **Session:** Bis zu 24h
- **Background Execution:** Ja
- **Empfohlen für:** Produktionsnutzung

---

## Related Files

- `colab/Cindergrace_ComfyUI.ipynb` - Main notebook
- `colab/Comfy2.ipynb` - Alternative configuration
- `docs/BACKLOG.md` - Issue #029

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v0.6.0 | 2025-12-16 | Initial beta release |

---

**Status:** Beta / Nicht funktional
**Backlog:** #029
**Target:** v0.8.0
