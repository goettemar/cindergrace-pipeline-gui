# CINDERGRACE auf RunPod

Anleitung zum Betrieb von CINDERGRACE mit RunPod GPU-Pods.

## Voraussetzungen

- RunPod Account mit Credits ($10-25 empfohlen zum Testen)
- Network Volume (min. 100 GB, empfohlen 150 GB)

---

## 1. Network Volume erstellen

1. **Storage** → **Network Volumes** → **+ New Network Volume**
2. Einstellungen:
   - Name: `cindergrace-models`
   - Region: **Gleiche Region wie GPU-Pod!** (z.B. EU-RO-1)
   - Size: **150 GB**
3. **Create** klicken

---

## 2. CPU Pod starten (für Model-Downloads)

1. **Pods** → **+ Deploy**
2. Günstigen CPU Pod wählen (z.B. 2 vCPU, 4 GB RAM)
3. **Network Volume** anhängen: `cindergrace-models`
4. Template: Standard Ubuntu/Debian
5. **Deploy**

---

## 3. Modelle herunterladen

### Verbindung zum Pod

Web Terminal öffnen oder SSH verwenden.

### aria2 installieren (schnellere Downloads)

```bash
apt-get update && apt-get install -y aria2
```

### Verzeichnisse erstellen

```bash
mkdir -p /workspace/models/{clip,vae,diffusion_models,unet,loras,audio_encoders}
```

---

## Modell-Downloads

### Wan 2.2 I2V (Image-to-Video) - FP8 für 32GB VRAM

```bash
# UMT5-XXL Text Encoder (6.7 GB)
aria2c -x 16 -d /workspace/models/clip -o umt5_xxl_fp8_e4m3fn_scaled.safetensors \
  "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors"

# Wan 2.1 VAE (254 MB)
aria2c -x 16 -d /workspace/models/vae -o wan_2.1_vae.safetensors \
  "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors"

# I2V HighNoise FP8 (14.3 GB)
aria2c -x 16 -d /workspace/models/diffusion_models -o wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors \
  "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors"

# I2V LowNoise FP8 (14.3 GB)
aria2c -x 16 -d /workspace/models/diffusion_models -o wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors \
  "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors"
```

### Wan 2.2 S2V (Subject-to-Video)

```bash
# S2V Diffusion Model (16.4 GB)
aria2c -x 16 -d /workspace/models/diffusion_models -o wan2.2_s2v_14B_fp8_scaled.safetensors \
  "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_s2v_14B_fp8_scaled.safetensors"

# Audio Encoder für S2V (631 MB)
aria2c -x 16 -d /workspace/models/audio_encoders -o wav2vec2_large_english_fp16.safetensors \
  "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/audio_encoders/wav2vec2_large_english_fp16.safetensors"

# LightX2V LoRA für schnellere Generation (1.2 GB)
aria2c -x 16 -d /workspace/models/loras -o wan2.2_t2v_lightx2v_4steps_lora_v1.1_low_noise.safetensors \
  "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/loras/wan2.2_t2v_lightx2v_4steps_lora_v1.1_low_noise.safetensors"
```

### Flux (Keyframe-Generierung)

```bash
# CLIP-L (235 MB)
aria2c -x 16 -d /workspace/models/clip -o clip_l.safetensors \
  "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors"

# T5-XXL FP16 (9.2 GB)
aria2c -x 16 -d /workspace/models/clip -o t5xxl_fp16.safetensors \
  "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp16.safetensors"

# Flux VAE (335 MB)
aria2c -x 16 -d /workspace/models/vae -o ae.safetensors \
  "https://huggingface.co/ffxvs/vae-flux/resolve/main/ae.safetensors"

# Flux Dev FP8 (11.9 GB)
aria2c -x 16 -d /workspace/models/unet -o flux1-dev-fp8-e4m3fn.safetensors \
  "https://huggingface.co/Kijai/flux-fp8/resolve/main/flux1-dev-fp8-e4m3fn.safetensors"
```

---

## Speicherübersicht

| Modell-Set | Größe | VRAM Empfehlung |
|------------|-------|-----------------|
| Wan I2V FP8 | ~36 GB | 24-32 GB |
| + S2V | +18 GB | 32 GB |
| + Flux | +22 GB | 24-32 GB |
| **Gesamt** | **~76 GB** | 32 GB |

### Modell-Formate Vergleich

| Format | Größe (2 Modelle) | Speed | Qualität | VRAM |
|--------|-------------------|-------|----------|------|
| **FP8 Scaled** | 28.6 GB | Schnell | 95%+ | ~28 GB |
| GGUF Q4_K_M | 19.3 GB | Langsam | ~85-90% | ~20 GB |
| FP16/BF16 | 57.2 GB | Schnell | 100% | >32 GB |

**Empfehlung:** FP8 Scaled für 24-32 GB VRAM Pods.

---

## 4. GPU Pod starten

1. CPU Pod stoppen (Network Volume bleibt erhalten!)
2. **Pods** → **+ Deploy**
3. GPU auswählen:
   - **RTX 4090** (24 GB) - ~$0.40/h
   - **A100 40GB** - ~$1.50/h
   - **A100 80GB** - ~$2.00/h (für FP16)
4. Template: **RunPod PyTorch 2.x** oder ComfyUI Template
5. **Network Volume** anhängen: `cindergrace-models`
6. **Deploy**

---

## 5. ComfyUI starten

### Wenn ComfyUI nicht vorinstalliert ist:

```bash
cd /workspace
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI
pip install -r requirements.txt

# Custom Nodes installieren
cd custom_nodes
git clone https://github.com/kijai/ComfyUI-WanVideoWrapper
git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite
git clone https://github.com/city96/ComfyUI-GGUF
git clone https://github.com/ltdrdata/ComfyUI-Manager
```

### Modelle verlinken

```bash
# Symlinks erstellen
ln -sf /workspace/models/clip/* /workspace/ComfyUI/models/clip/
ln -sf /workspace/models/vae/* /workspace/ComfyUI/models/vae/
ln -sf /workspace/models/diffusion_models/* /workspace/ComfyUI/models/diffusion_models/
ln -sf /workspace/models/unet/* /workspace/ComfyUI/models/unet/
ln -sf /workspace/models/loras/* /workspace/ComfyUI/models/loras/
ln -sf /workspace/models/audio_encoders/* /workspace/ComfyUI/models/audio_encoders/
```

### ComfyUI starten

```bash
cd /workspace/ComfyUI
python main.py --listen 0.0.0.0 --port 8188 --enable-cors-header
```

---

## 6. CINDERGRACE verbinden

1. Pod URL kopieren: `https://<POD_ID>-8188.proxy.runpod.net`
2. In CINDERGRACE → **Settings**:
   - **ComfyUI URL**: Die kopierte URL eintragen
   - **ComfyUI Root**: Leer lassen (nicht benötigt für Remote)
3. **Test Connection** klicken

---

## Troubleshooting

### "Model not found"
- Prüfen ob Network Volume gemountet ist: `df -h`
- Symlinks prüfen: `ls -la /workspace/ComfyUI/models/`

### "Connection refused"
- ComfyUI läuft nicht? `ps aux | grep python`
- Port 8188 nicht exposed? Pod Einstellungen prüfen

### "Out of memory"
- Kleinere Modelle verwenden (GGUF statt FP8)
- Resolution reduzieren
- Größeren GPU Pod wählen

### Langsame Downloads
- aria2 mit parallelen Verbindungen nutzen: `aria2c -x 16 -s 16`

---

## Kosten-Übersicht

| Task | GPU | Zeit | Kosten |
|------|-----|------|--------|
| 1 Keyframe (Flux) | RTX 4090 | ~30s | ~$0.01 |
| 1 Video Clip (Wan 14B) | RTX 4090 | ~3min | ~$0.02 |
| 10 Shot Storyboard | RTX 4090 | ~30min | ~$0.20 |

**Tipps zum Sparen:**
- Pod stoppen wenn nicht in Benutzung
- FP8 statt FP16 (gleiche Qualität, weniger VRAM)
- Spot Instances für Batch-Jobs (50% günstiger)

---

## Nützliche Befehle

```bash
# Speicherplatz prüfen
du -sh /workspace/models/*

# Alle Modelle auflisten
ls -lh /workspace/models/**/*

# ComfyUI Logs
tail -f /workspace/ComfyUI/comfyui.log

# GPU Status
nvidia-smi
```

---

---

## CINDERGRACE Public Template

Ein fertiges Docker Template steht unter `runpod/` bereit:

```
runpod/
├── Dockerfile          # Docker Image mit ComfyUI + Custom Nodes
├── start.sh            # Startup Script
├── link_models.sh      # Model Linking Script
├── template.json       # RunPod Template Konfiguration
└── download_models.sh  # Model Download Helper
```

### Docker Image bauen und pushen

```bash
cd runpod/
docker build -t ghcr.io/cindergrace/comfyui-runpod:latest .
docker push ghcr.io/cindergrace/comfyui-runpod:latest
```

### Template auf RunPod veröffentlichen

1. **My Templates** → **New Template**
2. Einstellungen aus `template.json` übernehmen
3. **Public template** aktivieren (optional)
4. **Save Template**

---

*Letzte Aktualisierung: 2025-12-25*
