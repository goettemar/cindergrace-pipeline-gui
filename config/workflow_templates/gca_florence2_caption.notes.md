# Florence-2 Image Captioning Workflow

## Purpose

Generates automatic captions/prompts from images using Microsoft's Florence-2 vision model.

## Required Custom Nodes

1. **ComfyUI-Florence2** - https://github.com/kijai/ComfyUI-Florence2
2. **ComfyUI-Custom-Scripts** - for `ShowText|pysssss` node

## Model

- **Name:** `microsoft/Florence-2-large-ft`
- **Size:** ~1.5 GB
- **Download:** Automatic on first run (from HuggingFace)
- **Precision:** FP16

## Outputs

| Node | Task | Output |
|------|------|--------|
| Node 4 | `caption` | Short description |
| Node 12 | `more_detailed_caption` | Detailed prompt for generation |

## Usage

Used by `ImageAnalyzerService` for:
- Image Importer AI analysis
- Automatic prompt generation from reference images

## Troubleshooting

- **Red node:** Install ComfyUI-Florence2 custom node pack
- **Model download fails:** Check HuggingFace access, may need `huggingface-cli login`
- **Out of memory:** Model requires ~4GB VRAM
