# Qwen Image Edit Workflow

## Purpose

AI-powered image editing using Qwen model. Used for dataset generation with automatic pose/view changes.

## Requirements

### VRAM
- **Minimum:** 12 GB
- **Recommended:** 16 GB

### Models
| Model | Path | Size |
|-------|------|------|
| Qwen Image Edit | `unet/qwen_image_edit_2509_fp8_e4m3fn.safetensors` | ~8 GB |
| Flux VAE | `vae/ae.safetensors` | ~300 MB |

### Custom Nodes
- FluxKontextImageScale
- TextEncodeQwenImageEditPlus
- CFGNorm
- ModelSamplingAuraFlow

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| Steps | 20 | Sampling steps |
| CFG | 2.5 | Classifier-free guidance |
| Sampler | euler | Sampling method |

## Edit Capabilities

- Pose changes (front, side, back views)
- Expression changes
- Lighting adjustments
- Background modifications
- Outfit changes

## Output

- Format: PNG
- Resolution: Matches input image

## Usage

Used by Dataset Generator addon for:
- Generating 15 training views from single image
- Automatic caption generation
- Character LoRA training preparation

## Troubleshooting

- **Custom node error:** Install required custom nodes
- **Edit not working:** Check prompt format matches Qwen expectations
- **Quality issues:** Increase steps to 30-40
