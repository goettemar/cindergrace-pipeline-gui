# Wan 2.2 5B Image-to-Video Workflow

## Purpose

Lighter version of Wan 2.2 for video generation. Lower VRAM requirements but reduced quality.

## Requirements

### VRAM
- **Minimum:** 8 GB
- **Recommended:** 12 GB

### Models
| Model | Path | Size |
|-------|------|------|
| Wan 2.2 5B | `diffusion_models/wan2.2_5B_fp16.safetensors` | ~10 GB |
| T5 XXL | `clip/t5xxl_fp16.safetensors` | ~9 GB |
| Wan VAE | `vae/wan_2.2_vae.safetensors` | ~300 MB |

### Custom Nodes
- ComfyUI-WanVideoWrapper (or native Wan nodes)

## Comparison to 14B

| Aspect | 5B | 14B |
|--------|----|----|
| VRAM | 8 GB | 12+ GB |
| Quality | Good | Best |
| Speed | Faster | Slower |
| Motion | Simpler | More complex |

## Output

- Format: MP4/WEBM
- Duration: ~3 seconds per segment
- Resolution: Matches input image

## Usage

Use this workflow when:
- Limited VRAM (8-12 GB GPUs)
- Faster iteration needed
- Quality is less critical

## Troubleshooting

- **Still OOM:** Try LTX-Video (`gcv_ltvx_i2v.json`) for 6-8 GB VRAM
- **Quality issues:** Upgrade to 14B variant if VRAM allows
