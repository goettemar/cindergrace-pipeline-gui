# Wan 2.2 14B GGUF + SageAttention Workflow

## Purpose

Optimized version combining GGUF quantization with SageAttention for maximum performance.

## Requirements

### VRAM
- **Minimum:** 10 GB
- **Recommended:** 12 GB

### Models
| Model | Path | Size |
|-------|------|------|
| Wan 2.2 14B GGUF | `diffusion_models/wan2.2_14B_Q4_K_M.gguf` | ~8 GB |
| T5 XXL | `clip/t5xxl_fp16.safetensors` | ~9 GB |
| Wan VAE | `vae/wan_2.2_vae.safetensors` | ~300 MB |

### Custom Nodes
- ComfyUI-GGUF
- ComfyUI-WanVideoWrapper
- SageAttention node

### Hardware
- **GPU:** NVIDIA RTX 30xx or newer (Ampere+)
- SageAttention requires specific CUDA capabilities

## Performance

| Variant | Speed | VRAM |
|---------|-------|------|
| FP16 | 1x | 16 GB |
| GGUF | 1.2x | 10 GB |
| GGUF + Sage | 1.5-2x | 10 GB |

## Output

- Format: MP4/WEBM
- Duration: ~3 seconds per segment
- Quality: Same as GGUF

## Usage

**Best choice for:**
- RTX 30xx/40xx GPUs
- Fastest generation times
- Production workflows

## Troubleshooting

- **SageAttention error:** Check GPU compatibility (RTX 30xx+)
- **Fallback:** Use `gcv_wan_2.2_14B_i2v_gguf.json` without Sage
