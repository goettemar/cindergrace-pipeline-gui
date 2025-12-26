# SDXL LoRA Keyframe Generation Workflow

## Purpose

Generates keyframe images using SDXL with LoRA support. Alternative to Flux for lower VRAM systems.

## Requirements

### VRAM
- **Minimum:** 8 GB
- **Recommended:** 12 GB

### Models
| Model | Path | Size |
|-------|------|------|
| SDXL Base | `checkpoints/sd_xl_base_1.0.safetensors` | ~6.5 GB |
| SDXL VAE | `vae/sdxl_vae.safetensors` | ~300 MB |
| LoRA (optional) | `loras/cg_*.safetensors` | varies |

### Custom Nodes
- None required (native ComfyUI nodes)

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| Steps | 25 | Sampling steps |
| CFG | 7 | Classifier-free guidance |
| Sampler | euler | Sampling method |
| Resolution | 1024x1024 | Output size (SDXL native) |

## Comparison to Flux

| Aspect | SDXL | Flux |
|--------|------|------|
| VRAM | 8-12 GB | 16-24 GB |
| Quality | Very Good | Excellent |
| Speed | Fast | Medium |
| LoRA Training | Easier | More complex |

## Output

- Format: PNG
- Resolution: 1024x1024 (native), other sizes supported
- Best at 1024x1024 or 768x1024

## Usage

**Best for:**
- GPUs with 8-12 GB VRAM
- When Flux causes OOM
- Quick LoRA iterations
- SDXL-trained character LoRAs

## Troubleshooting

- **Quality lower than Flux:** Expected, SDXL is older model
- **LoRA not loading:** Check `loras/` folder and `cg_` prefix
