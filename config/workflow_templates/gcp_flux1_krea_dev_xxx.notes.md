# Flux Krea Dev Keyframe Generation Workflow

## Purpose

Generates high-quality keyframe images using Flux model. Primary workflow for Phase 1 (Keyframe Generation).

## Requirements

### VRAM
- **Minimum:** 16 GB
- **Recommended:** 24 GB

### Models
| Model | Path | Size |
|-------|------|------|
| Flux Krea Dev | `unet/flux1-krea-dev.safetensors` | ~12 GB |
| T5 XXL | `clip/t5xxl_fp16.safetensors` | ~9 GB |
| CLIP L | `clip/clip_l.safetensors` | ~250 MB |
| Flux VAE | `vae/ae.safetensors` | ~300 MB |

### Custom Nodes
- None required (native ComfyUI nodes)

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| Steps | 20 | Sampling steps |
| CFG | 1 | Classifier-free guidance |
| Sampler | euler | Sampling method |
| Resolution | 1024x1024 | Output size |

## Output

- Format: PNG
- Resolution: As specified in storyboard
- Naming: `{filename_base}_v{N}_00001_.png`

## Usage

Used by Keyframe Generator addon for:
- Storyboard-based image generation
- Multiple variants per shot
- Checkpoint/resume support

## Variants

| Workflow | VRAM | Use Case |
|----------|------|----------|
| `gcp_flux1_krea_dev_xxx.json` | 24 GB | Full quality |
| `gcp_flux1_krea_dev_fp8.json` | 16 GB | Reduced precision |
| `gcp_flux1_krea_dev_lora.json` | 24 GB | With character LoRA |

## Troubleshooting

- **Out of memory:** Use FP8 variant
- **LoRA needed:** Use `_lora` variant
- **Model not found:** Check `unet/` folder
