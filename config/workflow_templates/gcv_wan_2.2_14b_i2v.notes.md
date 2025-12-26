# Wan 2.2 14B Image-to-Video Workflow

## Purpose

Generates video clips from a start image using Wan 2.2 14B model. Used for the main video generation pipeline.

## Requirements

### VRAM
- **Minimum:** 12 GB
- **Recommended:** 16+ GB

### Models
| Model | Path | Size |
|-------|------|------|
| Wan 2.2 14B | `diffusion_models/wan2.2_14B_fp16.safetensors` | ~28 GB |
| T5 XXL | `clip/t5xxl_fp16.safetensors` | ~9 GB |
| Wan VAE | `vae/wan_2.2_vae.safetensors` | ~300 MB |

### Custom Nodes
- ComfyUI-WanVideoWrapper (or native Wan nodes)

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| Steps | 4 | Sampling steps (first pass) |
| CFG | 1 | Classifier-free guidance |
| Sampler | euler | Sampling method |
| Scheduler | simple | Noise schedule |

## Output

- Format: MP4/WEBM
- Duration: ~3 seconds per segment
- Resolution: Matches input image

## Usage

Used by Video Generator addon for:
- Shot-by-shot video generation
- LastFrame chaining for longer clips

## Troubleshooting

- **Out of memory:** Use GGUF variant (`gcv_wan_2.2_14B_i2v_gguf.json`)
- **Slow generation:** Enable SageAttention (`gcv_wan_2.2_14B_i2v_gguf_sage.json`)
- **Model not found:** Check `diffusion_models/` folder in ComfyUI
