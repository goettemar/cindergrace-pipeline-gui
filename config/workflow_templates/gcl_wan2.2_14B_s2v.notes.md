# Wan 2.2 14B Sound-to-Video Workflow

## Purpose

Generates lipsync videos from audio input using Wan 2.2 s2v (sound-to-video) model.

## Requirements

### VRAM
- **Minimum:** 16 GB
- **Recommended:** 24 GB

### Models
| Model | Path | Size |
|-------|------|------|
| Wan 2.2 s2v 14B | `diffusion_models/wan2.2_s2v_14B_fp8_scaled.safetensors` | ~15 GB |
| Wav2Vec2 | `clip/wav2vec2_large_english_fp16.safetensors` | ~1.2 GB |
| T5 XXL | `clip/t5xxl_fp16.safetensors` | ~9 GB |
| Wan VAE | `vae/wan_2.2_vae.safetensors` | ~300 MB |

### Custom Nodes
- ComfyUI-WanVideoWrapper

## Audio Requirements

- Format: WAV or MP3
- Duration: Max ~14 seconds (hardware dependent)
- Sample Rate: 16kHz recommended

## Output

- Format: MP4
- Duration: Matches audio length
- Features: Lip-synced character animation

## Usage

Used by Lipsync Studio addon for:
- Character talking head videos
- Audio-driven lip synchronization
- Emotion/expression matching

## Limitations

- Max duration: ~10-14 seconds per clip
- Best with frontal face images
- English audio works best (wav2vec2 model)

## Troubleshooting

- **No lip movement:** Check audio is loud enough
- **Duration too long:** Split audio into segments
- **German audio:** Consider german wav2vec2 model (future)
