# RunPod Integration - TODOs

Stand: 2025-12-25

## Erledigt heute

- [x] Network Volume erstellt auf RunPod
- [x] Modelle heruntergeladen (FP8 für 32GB VRAM)
  - [x] Wan 2.2 I2V HighNoise/LowNoise FP8
  - [x] UMT5-XXL FP8
  - [x] Wan 2.1 VAE
  - [x] Flux Dev FP8
  - [x] CLIP-L, T5-XXL
  - [x] S2V Model + Audio Encoder + LoRA
- [x] GPU Pod gestartet (RTX 5090)
- [x] ComfyUI + Custom Nodes installiert
- [x] CINDERGRACE erfolgreich verbunden!
- [x] Bug fix: User-Agent Header für RunPod Proxy
- [x] Bug fix: Settings Panel test_connection() Status Check
- [x] RunPod Template Dateien erstellt:
  - [x] Dockerfile (CUDA 12.8)
  - [x] start.sh
  - [x] link_models.sh
  - [x] download_models.sh
  - [x] template.json
  - [x] README.md
- [x] Dokumentation aktualisiert (docs/Runpod_HowTo.md)

## TODOs für morgen

### 1. Docker Image bauen & testen
```bash
cd runpod/
docker build -t ghcr.io/cindergrace/comfyui-runpod:latest .
```
- [ ] Image lokal testen
- [ ] Zu GitHub Container Registry pushen

### 2. RunPod Template veröffentlichen
- [ ] Template auf RunPod erstellen (My Templates)
- [ ] Mit Network Volume testen
- [ ] Optional: Public Template aktivieren

### 3. CINDERGRACE Video-Generation testen
- [ ] Wan I2V Workflow testen
- [ ] Flux Keyframe Generation testen
- [ ] S2V Workflow testen
- [ ] Performance messen (Generierungszeit)

### 4. Fehlende Modelle prüfen
Auf dem Pod checken:
```bash
ls -lh /workspace/models/clip/
ls -lh /workspace/models/vae/
ls -lh /workspace/models/diffusion_models/
ls -lh /workspace/models/unet/
ls -lh /workspace/models/loras/
ls -lh /workspace/models/audio_encoders/
```

Noch fehlend?
- [ ] Flux VAE (ae.safetensors) prüfen
- [ ] wan_2.1_vae.safetensors prüfen (vs wan2.2_vae)

### 5. Workflow Templates anpassen
Die Workflows müssen die korrekten Model-Namen verwenden:
- [ ] gcv_wan_2.2_14b_i2v.json - Model-Namen prüfen
- [ ] gcp_flux1_krea_dev_xxx.json - Model-Namen prüfen

### 6. Cleanup auf Network Volume
```bash
# Leere/kaputte Dateien löschen
rm -f /workspace/models/diffusion_models/wan2.1_14B_Q4_K_S.gguf
rm -f /workspace/models/vae/wan_2.2_vae.safetensors
rm -f /workspace/models/clip/t5xxl_fp16.1.safetensors
```

### 7. Optional: Colab Integration
- [ ] Colab Notebook für CINDERGRACE erstellen
- [ ] Vergleich RunPod vs Colab dokumentieren

## Notizen

### Funktionierende Model-URLs (getestet)
```
# Wan 2.2 FP8
https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors
https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors
https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors
https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors

# Flux
https://huggingface.co/Kijai/flux-fp8/resolve/main/flux1-dev-fp8-e4m3fn.safetensors
https://huggingface.co/ffxvs/vae-flux/resolve/main/ae.safetensors
https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors
https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp16.safetensors

# S2V
https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_s2v_14B_fp8_scaled.safetensors
https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/audio_encoders/wav2vec2_large_english_fp16.safetensors
https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/loras/wan2.2_t2v_lightx2v_4steps_lora_v1.1_low_noise.safetensors
```

### RunPod Pod Info
- Pod ID: `khi0bvn456hpte` (oder aktuell)
- URL: `https://<POD_ID>-8188.proxy.runpod.net`
- GPU: RTX 5090 (32 GB VRAM)
- Network Volume: `cindergrace-models`

### Code-Änderungen heute
1. `infrastructure/comfy_api/client.py` - User-Agent Header hinzugefügt
2. `addons/settings_panel.py` - Bug fix: `result.get("status")` → `result.get("connected")`
