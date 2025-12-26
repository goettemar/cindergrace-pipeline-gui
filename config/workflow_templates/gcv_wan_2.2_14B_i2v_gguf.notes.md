# Wan 2.2 14B GGUF Image-to-Video Workflow

## Purpose

Quantized version of Wan 2.2 14B using GGUF format. Reduced VRAM with minimal quality loss.

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
- ComfyUI-GGUF (for UnetLoaderGGUF node)
- ComfyUI-WanVideoWrapper

## GGUF Quantization Levels

| Variant | Size | Quality | VRAM |
|---------|------|---------|------|
| Q8_0 | ~14 GB | Best | 12 GB |
| Q5_K_M | ~10 GB | Good | 10 GB |
| Q4_K_M | ~8 GB | Acceptable | 8 GB |

## Output

- Format: MP4/WEBM
- Duration: ~3 seconds per segment
- Quality: ~95% of FP16

## Usage

Recommended for:
- 12-16 GB VRAM GPUs
- Production use with good quality
- When FP16 causes OOM

## See Also

- `gcv_wan_2.2_14B_i2v_gguf_sage.json` - With SageAttention acceleration
