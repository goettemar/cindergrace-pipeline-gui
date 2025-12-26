# LTX-Video Image-to-Video Workflow

## Purpose

Lightweight video generation using LTX-Video model. Ideal for low-VRAM GPUs.

## Requirements

### VRAM
- **Minimum:** 6 GB
- **Recommended:** 8 GB

### Models
| Model | Path | Size |
|-------|------|------|
| LTX-Video 2B | `diffusion_models/ltx-video-2b-v0.9.safetensors` | ~5 GB |
| T5 XXL | `clip/t5xxl_fp16.safetensors` | ~9 GB |
| LTX VAE | (built into model) | - |

### Custom Nodes
- None required (native ComfyUI nodes)

## Comparison

| Model | VRAM | Quality | Speed |
|-------|------|---------|-------|
| LTX-Video 2B | 6-8 GB | ⭐⭐ Good | Fast |
| LTX-Video 13B | 12 GB | ⭐⭐⭐ Very Good | Medium |
| Wan 2.2 14B | 12+ GB | ⭐⭐⭐ Best | Slow |

## Resolution

LTX-Video supports flexible resolutions (must be divisible by 32):
- 768x512 (Landscape)
- 512x768 (Portrait)
- 512x512 (Square)

## Output

- Format: WEBP (animated) or MP4
- Duration: Configurable
- FPS: 24 default

## Usage

**Best for:**
- GPUs with 6-8 GB VRAM (RTX 3060, 4060)
- Quick previews and iterations
- When Wan 2.2 causes OOM

## Troubleshooting

- **Resolution error:** Ensure dimensions are divisible by 32
- **Quality issues:** Try LTX-Video 13B if VRAM allows
