# 🎤 Lipsync (Lipsync Studio)

**Tab Name:** 🎤 Lipsync
**File:** `addons/lipsync_addon.py`
**Service:** `services/lipsync_service.py`
**Version:** v0.6.0
**Last Updated:** December 16, 2025

---

## Overview

Das Lipsync Studio erstellt lippensynchrone Videos aus einem Charakter-Bild und einer Audio-Datei. Es nutzt den Wan 2.2 Sound-to-Video (is2v) Workflow, um realistische Mundbewegungen zu generieren, die zum gesprochenen Audio passen.

**Ideal für:**
- Erklärvideos mit sprechenden Charakteren
- Voiceover-Animationen
- Content Creator Tools
- Prototyping von Animationen

---

## Features

- **Bild-Upload** - Charakter-Bild hochladen (Frontalansicht empfohlen)
- **Character LoRA Integration** - Vorbereitete LoRA-Unterstützung für konsistente Charaktere
- **Audio-Verarbeitung** - MP3/WAV Upload mit Trimming-Funktion
- **Flexible Auflösungen** - 480p, 720p, 1080p (Landscape & Portrait)
- **Konfigurierbare Parameter** - Steps, CFG, FPS anpassbar
- **Automatische Konvertierung** - Audio wird für wav2vec2 optimiert (16kHz, Mono)

---

## UI Structure

### Tab 1: Charakter-Bild

```
┌─────────────────────────────────────────────────────────────────┐
│ 🖼️ Charakter-Bild auswählen                                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Option A: Bild hochladen        │  Vorschau                    │
│  ┌─────────────────────────┐     │  ┌─────────────────────────┐ │
│  │                         │     │  │                         │ │
│  │   [Bild hierher ziehen] │     │  │   Aktuelles Bild        │ │
│  │                         │     │  │                         │ │
│  └─────────────────────────┘     │  └─────────────────────────┘ │
│                                  │                              │
│  Option B: Mit Flux generieren   │  Bild geladen: sprecher.png  │
│  Character LoRA: [Dropdown ▼]    │                              │
│  [🔄 LoRAs aktualisieren]        │                              │
│  Flux Prompt: [...] (coming soon)│                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Tab 2: Audio

```
┌─────────────────────────────────────────────────────────────────┐
│ 🎵 Audio vorbereiten                                            │
│ Max. Dauer: ~14 Sekunden (Hardware-abhängig, evtl. nur ~10s)    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Audio hochladen                 │  Vorschau                    │
│  ┌─────────────────────────┐     │                              │
│  │ 🎵 [Audio-Datei wählen] │     │  ▶️ [Zugeschnittenes Audio]   │
│  └─────────────────────────┘     │                              │
│                                  │  Dauer: 7.5s                 │
│  Datei: erklaerung.mp3           │  (bereit für Generierung)    │
│  Dauer: 45.2s | MP3 | 44100Hz    │                              │
│                                  │                              │
│  Zuschneiden                     │                              │
│  Start: [0.0    ] Sekunden       │                              │
│  Ende:  [10.0   ] Sekunden       │                              │
│  [✂️ Audio zuschneiden]          │                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Tab 3: Generierung

```
┌─────────────────────────────────────────────────────────────────┐
│ 🎬 Lipsync Video generieren                                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Einstellungen                   │  Vorschau                    │
│                                  │                              │
│  Prompt (Bewegung/Emotion):      │  📋 Input-Zusammenfassung    │
│  ┌─────────────────────────┐     │  Bild: sprecher.png          │
│  │ Person speaking warmly, │     │  Audio: 7.5s (zugeschnitten) │
│  │ looking at camera...    │     │                              │
│  └─────────────────────────┘     │  ┌─────────────────────────┐ │
│                                  │  │                         │ │
│  Auflösung: [720p (1280×720) ▼]  │  │   🎬 Generiertes Video  │ │
│  Steps: [====4====]              │  │                         │ │
│  CFG:   [===1.0===]              │  └─────────────────────────┘ │
│  FPS:   [====16===]              │                              │
│                                  │  Output: lipsync/output.mp4  │
│  Output Name: [lipsync_output]   │                              │
│                                  │                              │
│  [🎬 Lipsync Video generieren]   │                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Auflösungen

| Preset | Auflösung | Seitenverhältnis | Anwendung |
|--------|-----------|------------------|-----------|
| 480p | 854×480 | 16:9 | Schnelle Tests, wenig VRAM |
| 720p | 1280×720 | 16:9 | **Standard** (empfohlen) |
| 1080p | 1920×1080 | 16:9 | Hohe Qualität, mehr VRAM |
| 480p Portrait | 480×854 | 9:16 | Social Media (TikTok, Reels) |
| 720p Portrait | 720×1280 | 9:16 | Social Media HD |
| 640×640 | 640×640 | 1:1 | Quadratisch (Instagram) |

---

## Workflow

Der Workflow `gc_wan_2.2_is2v.json` wird verwendet:

```
┌─────────────┐     ┌─────────────┐
│ LoadImage   │     │ LoadAudio   │
│ (Charakter) │     │ (MP3/WAV)   │
└──────┬──────┘     └──────┬──────┘
       │                   │
       │    ┌──────────────┘
       │    │
       ▼    ▼
┌─────────────────────────────────┐
│ WanSoundImageToVideo            │
│ - Audio-Encoding (wav2vec2)     │
│ - Lipsync-Generation            │
└──────────────┬──────────────────┘
               │
               ▼
       ┌───────────────┐
       │ KSampler (×3) │  ← 3 Chunks für ~14s
       └───────┬───────┘
               │
               ▼
       ┌───────────────┐
       │ SaveVideo     │
       └───────────────┘
```

---

## Benötigte Modelle

| Modell | Größe | Pfad in ComfyUI |
|--------|-------|-----------------|
| `wan2.2_s2v_14B_fp8_scaled.safetensors` | ~15GB | `models/diffusion_models/` |
| `wav2vec2_large_english_fp16.safetensors` | ~1.2GB | `models/audio_encoders/` |
| `umt5_xxl_fp8_e4m3fn_scaled.safetensors` | ~9GB | `models/clip/` |
| `wan_2.1_vae.safetensors` | ~335MB | `models/vae/` |

---

## Parameter-Referenz

| Parameter | Default | Bereich | Beschreibung |
|-----------|---------|---------|--------------|
| Steps | 4 | 2-20 | Sampling Steps (4 mit LoRA-Speedup empfohlen) |
| CFG | 1.0 | 0.5-5.0 | Classifier-Free Guidance |
| FPS | 16 | 12-24 | Frames pro Sekunde |
| Max Duration | ~14s | - | Hardware-abhängig (evtl. nur ~10s) |

---

## Tipps für beste Ergebnisse

### Bild-Auswahl
- **Frontalansicht** - Gesicht sollte direkt in die Kamera schauen
- **Neutraler Ausdruck** - Leicht geöffneter Mund oder neutrales Lächeln
- **Gute Beleuchtung** - Gleichmäßig ausgeleuchtet, keine harten Schatten
- **Hohe Auflösung** - Mindestens 512×512, besser 1024×1024

### Audio-Vorbereitung
- **Klare Sprache** - Deutliche Aussprache ohne Hintergrundgeräusche
- **Optimale Länge** - 7-10 Sekunden für beste Qualität
- **Mono bevorzugt** - Wird automatisch konvertiert

### Prompt-Gestaltung
```
# Gute Prompts:
"Person speaking warmly, looking at camera, natural lip movements, gentle expression"
"Professional presenter talking, confident, maintaining eye contact"
"Character singing emotionally, expressive face, looking at viewer"

# Vermeiden:
"Person walking" (zu viel Bewegung)
"Multiple people" (nur ein Gesicht)
"Looking away" (erschwert Lipsync)
```

---

## Troubleshooting

### Problem: Lipsync nicht synchron
- **Lösung:** Audio auf 16kHz Mono konvertieren (wird automatisch gemacht)
- **Lösung:** Kürzere Clips (7-10s statt 14s)

### Problem: VRAM-Fehler bei 1080p
- **Lösung:** Auf 720p oder 480p reduzieren
- **Lösung:** Andere Programme schließen

### Problem: Verzerrtes Gesicht
- **Lösung:** Besseres Referenzbild (frontal, neutral)
- **Lösung:** Steps erhöhen (6-8 statt 4)

### Problem: Audio wird nicht geladen
- **Lösung:** MP3 oder WAV verwenden (kein OGG, FLAC)
- **Lösung:** Datei in ComfyUI/input/ manuell prüfen

---

## Geplante Features

- [ ] Flux-Integration für Bild-Generierung direkt im Addon
- [ ] Long-Lipsync mit automatischer Segmentierung (>14s)
- [ ] Deutsches wav2vec2-Modell für bessere deutsche Lipsync
- [ ] Batch-Verarbeitung mehrerer Audio-Clips
- [ ] Character LoRA automatisch in Prompt einbauen

---

## Verwandte Dokumentation

- [Video Generator](../README.md) - Standard Video-Generierung
- [First/Last Frame](FIRSTLAST_VIDEO.md) - Übergangsvideos
- [Character Trainer](CHARACTER_TRAINER.md) - LoRA Training für Charaktere
