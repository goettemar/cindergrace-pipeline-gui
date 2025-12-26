"""Help & Workflow Overview Addon for CINDERGRACE Pipeline"""
import gradio as gr

from addons.base_addon import BaseAddon
from addons.components import format_project_status
from infrastructure.logger import get_logger

logger = get_logger(__name__)


class HelpAddon(BaseAddon):
    """Provides help, workflow overview and addon documentation."""

    def __init__(self):
        super().__init__(
            name="Help & Workflows",
            description="Help, workflow overview and documentation",
            category="tools"
        )

    def get_tab_name(self) -> str:
        return "❓ Help"

    def render(self) -> gr.Blocks:
        with gr.Blocks() as interface:
            # Unified header: Tab name left, no project relation
            gr.HTML(format_project_status(tab_name="❓ Help & Workflows", no_project_relation=True))

            with gr.Tabs():
                with gr.Tab("Workflow Overview"):
                    self._render_workflow_overview()

                with gr.Tab("ComfyUI Workflows"):
                    self._render_comfyui_workflows()

                with gr.Tab("Tab Reference"):
                    self._render_tab_reference()

                with gr.Tab("Quick Start"):
                    self._render_quickstart()

                with gr.Tab("Shortcuts"):
                    self._render_shortcuts()

        return interface

    def _render_workflow_overview(self):
        """Render visual workflow diagram."""
        gr.Markdown("""
## Main Workflows

CINDERGRACE supports various workflows for video production:

---

### Workflow A: Complete AI Pipeline (Text → Video)

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   📁 Project  │───▶│ 📖 Storyboard │───▶│ 🎬 Keyframe  │───▶│ ✅ Keyframe  │
│    create    │    │    create    │    │  Generator   │    │   Selector   │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
                                               │                    │
                           Flux Dev generates  │                    │ Choose best
                           multiple variants   │                    │ variant per shot
                                               ▼                    ▼
                                        ┌──────────────┐    ┌──────────────┐
                                        │   keyframes/ │    │   selected/  │
                                        │  shot_v1.png │───▶│  shot_v2.png │
                                        │  shot_v2.png │    │    .json     │
                                        └──────────────┘    └──────────────┘
                                                                   │
                                                                   ▼
                                                            ┌──────────────┐
                                                            │ 🎥 Video     │
                                                            │  Generator   │
                                                            └──────────────┘
                                                                   │
                                                    Wan 2.2 animates│
                                                    the keyframes   │
                                                                   ▼
                                                            ┌──────────────┐
                                                            │   video/     │
                                                            │  shot_001.mp4│
                                                            └──────────────┘
```

**When to use:** You want to generate everything from scratch with AI.

---

### Workflow B: Animate Your Own Images (Image → Video)

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   📁 Project  │───▶│ 📖 Storyboard │───▶│ 📥 Image     │
│    create    │    │    create    │    │   Importer   │
└──────────────┘    └──────────────┘    └──────────────┘
                                               │
                           Upload your own     │ Assign images
                           images              │ to shots
                                               ▼
                                        ┌──────────────┐
                                        │   selected/  │
                                        │  shot_001.png│
                                        └──────────────┘
                                               │
                                               ▼
                                        ┌──────────────┐
                                        │ 🎥 Video     │
                                        │  Generator   │
                                        └──────────────┘
                                               │
                                Wan 2.2 animates│
                                the images      │
                                               ▼
                                        ┌──────────────┐
                                        │   video/     │
                                        │  shot_001.mp4│
                                        └──────────────┘
```

**When to use:** You already have images (photos, drawings, other AI images) that you want to animate.

---

### Workflow C: First/Last Frame Video

```
┌──────────────┐    ┌──────────────┐
│   📁 Project  │───▶│ 🎞️ First/Last │
│    create    │    │    Video     │
└──────────────┘    └──────────────┘
                           │
          Start image +    │ Direct video
          End image +      │ generation
          Prompt           │
                           ▼
                    ┌──────────────┐
                    │   video/     │
                    │  output.mp4  │
                    └──────────────┘
```

**When to use:** You want a seamless transition between two specific images.

---

### Workflow D: Lipsync Video (Audio → Video)

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   📁 Project  │───▶│ 🎤 Lipsync   │───▶│ Audio        │
│    create    │    │   Studio     │    │ Segmentation │
└──────────────┘    └──────────────┘    └──────────────┘
                           │                    │
          Portrait image + │                    │ Smart cuts at
          Audio file +     │                    │ silences/beats
          Prompt           │                    │
                           ▼                    ▼
                    ┌──────────────┐    ┌──────────────┐
                    │ Wan 2.2 s2v  │    │ Segment 1-n  │
                    │ (Sound2Video)│    │ with overlap │
                    └──────────────┘    └──────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │   video/     │
                    │  lipsync.mp4 │
                    └──────────────┘
```

**When to use:** You want a character to lip-sync to audio (music, speech, voiceover).

---

### Workflow E: Character LoRA Training

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ 👤 Character  │───▶│ Training     │───▶│ Use LoRA in  │
│   Trainer    │    │ Dataset      │    │ Storyboard   │
└──────────────┘    └──────────────┘    └──────────────┘
       │
       │ Upload images,
       │ create captions
       ▼
┌──────────────┐
│ External     │
│ LoRA Training│
│ (Kohya etc.) │
└──────────────┘
```

**When to use:** You want a consistent character across multiple shots.
""")

    def _render_comfyui_workflows(self):
        """Render detailed ComfyUI workflow reference."""
        gr.Markdown("""
## ComfyUI Workflow Reference

### Workflow Naming Convention

All workflows follow a prefix convention indicating their purpose:

| Prefix | Purpose | Used in Tab |
|--------|---------|-------------|
| `gcp_` | **G**enerate **C**indergrace **P**icture | 🎬 Keyframe Generator |
| `gcv_` | **G**enerate **C**indergrace **V**ideo | 🎥 Video Generator |
| `gcl_` | **G**enerate **C**indergrace **L**ipsync | 🎤 Lipsync Studio |

---

## 🎨 Image Generation Workflows (gcp_)

### gcp_flux1_krea_dev_xxx.json
**Purpose:** Generate keyframe images from text prompts

| Property | Value |
|----------|-------|
| **Model** | Flux.1 Krea Dev |
| **VRAM** | ~16-20 GB |
| **Output** | 1024x576 or custom |
| **Speed** | ~10-20s per image |
| **Quality** | High detail, good prompt following |

**Required Models:**
- `diffusion_models/flux1-krea-dev.safetensors`

**Best for:** High-quality keyframes, detailed scenes, character portraits

---

### gcp_sdxl_lora.json
**Purpose:** Generate images with SDXL + custom LoRAs

| Property | Value |
|----------|-------|
| **Model** | SDXL 1.0 |
| **VRAM** | ~10-12 GB |
| **Output** | 1024x1024 or custom |
| **Speed** | ~5-15s per image |
| **Quality** | Good with proper LoRAs |

**Best for:** Character consistency with trained LoRAs

---

## 🎬 Video Generation Workflows (gcv_)

### gcv_wan_2.2_14b_i2v.json
**Purpose:** Image-to-Video with Wan 2.2 14B (Full Precision)

| Property | Value |
|----------|-------|
| **Model** | Wan 2.2 14B FP16 |
| **VRAM** | ~24+ GB |
| **Max Duration** | ~3s per segment |
| **FPS** | 16 |
| **Quality** | Highest quality motion |

**Required Models:**
- `diffusion_models/wan2.2_ti2v_14B_fp16.safetensors`

**Best for:** Maximum quality when VRAM is available

---

### gcv_wan_2.2_14B_i2v_gguf.json
**Purpose:** Image-to-Video with Wan 2.2 14B (Quantized)

| Property | Value |
|----------|-------|
| **Model** | Wan 2.2 14B GGUF Q5 |
| **VRAM** | ~16-18 GB |
| **Max Duration** | ~3s per segment |
| **FPS** | 16 |
| **Quality** | Very good (95% of FP16) |

**Best for:** 16GB GPUs, good quality/VRAM balance

---

### gcv_wan_2.2_14B_i2v_gguf_sage.json
**Purpose:** Image-to-Video with Wan 2.2 14B + SageAttention

| Property | Value |
|----------|-------|
| **Model** | Wan 2.2 14B GGUF + Sage |
| **VRAM** | ~14-16 GB |
| **Max Duration** | ~3s per segment |
| **FPS** | 16 |
| **Speed** | 30-40% faster |

**Best for:** Speed optimization with minimal quality loss

---

### gcv_wan_2.2_5b_i2v.json
**Purpose:** Image-to-Video with Wan 2.2 5B (Lightweight)

| Property | Value |
|----------|-------|
| **Model** | Wan 2.2 5B FP16 |
| **VRAM** | ~10-12 GB |
| **Max Duration** | ~3s per segment |
| **FPS** | 16 |
| **Quality** | Good for simple scenes |

**Required Models:**
- `diffusion_models/wan2.2_ti2v_5B_fp16.safetensors`

**Best for:** Lower VRAM GPUs, faster generation, simpler motions

---

### gcv_ltvx_i2v.json
**Purpose:** Image-to-Video with LTX-Video

| Property | Value |
|----------|-------|
| **Model** | LTX-Video 2B/13B |
| **VRAM** | ~12-20 GB |
| **Max Duration** | ~5s per segment |
| **FPS** | 24 |
| **Quality** | Good temporal consistency |

**Required Models:**
- `checkpoints/ltx-video-2b-v0.9.5.safetensors`
- `checkpoints/ltxv-13b-0.9.7-dev-fp8.safetensors`

**Best for:** Longer clips, smooth motion, 24fps output

---

## 🎤 Lipsync Workflows (gcl_)

### gcl_wan2.2_14B_s2v.json
**Purpose:** Sound-to-Video Lipsync with Wan 2.2

| Property | Value |
|----------|-------|
| **Model** | Wan 2.2 14B is2v |
| **VRAM** | ~20-24 GB |
| **Max Duration** | ~14s per segment |
| **FPS** | 16 |
| **Input** | Image + Audio |

**Best for:** Lip-synced talking head videos, music videos

---

### gcl_qwen_image_edit_2509.json
**Purpose:** AI Image Editing with Qwen

| Property | Value |
|----------|-------|
| **Model** | Qwen VL 2509 |
| **VRAM** | ~12-16 GB |
| **Input** | Image + Text instruction |
| **Output** | Edited image |

**Best for:** Inpainting, style transfer, image modifications

---

## 📊 VRAM Quick Reference

| VRAM | Recommended Workflows |
|------|----------------------|
| **8-10 GB** | gcp_sdxl_lora, gcv_wan_2.2_5b_i2v |
| **12-16 GB** | gcp_flux1_krea_dev, gcv_wan_2.2_14B_i2v_gguf_sage, gcv_ltvx_i2v |
| **16-20 GB** | gcv_wan_2.2_14B_i2v_gguf, gcl_wan2.2_14B_s2v |
| **24+ GB** | gcv_wan_2.2_14b_i2v (Full FP16) |

---

## 🔧 Model Configuration

Each workflow can have a `.models` sidecar file listing required models:
- Located in `config/workflow_templates/`
- Same name as workflow + `.models` extension
- Use **Model Manager** → **Workflow Model Requirements** to edit

**Example:** `gcv_wan_2.2_5b_i2v.models`
```
# Pfade relativ zu ComfyUI/models/
diffusion_models/wan2.2_ti2v_5B_fp16.safetensors
```
""")

    def _render_tab_reference(self):
        """Render reference for all tabs."""
        gr.Markdown("""
## Tab Reference

### Project & Setup

| Tab | Function | Dependencies |
|-----|----------|--------------|
| **📁 Project** | Create/select project | First step for all workflows |
| **📖 Storyboard** | Define shots with prompts, presets, characters | Requires active project |
| **⚙️ Settings** | ComfyUI path, resolution, backend | Configure once |
| **🧙 Setup Wizard** | Initial setup | On first start |

---

### Keyframe Production

| Tab | Function | Input | Output |
|-----|----------|-------|--------|
| **🎬 Keyframe Generator** | AI generates images from prompts | Storyboard | `keyframes/*.png` |
| **📥 Image Importer** | Import your own images | Your images | `selected/*.png` |
| **✅ Keyframe Selector** | Choose best variant per shot | `keyframes/` | `selected/*.png` + `.json` |

---

### Video Production

| Tab | Function | Input | Output |
|-----|----------|-------|--------|
| **🎥 Video Generator** | Animate keyframes to video | `selected/` | `video/*.mp4` |
| **🎞️ First/Last Video** | Video between two images | 2 images + prompt | `video/*.mp4` |
| **🎤 Lipsync Studio** | Audio-driven talking head | Image + Audio | `lipsync/*.mp4` |

---

### Tools & Training

| Tab | Function | Description |
|-----|----------|-------------|
| **👤 Character Trainer** | Prepare LoRA training data | Images + captions for Kohya |
| **🧪 Test ComfyUI** | Test connection | Debug and workflow test |
| **📦 Model Manager** | Manage models | Archive, categorize |

---

### Cross-References

```
📥 Image Importer ─────────────┐
                               │
                               ▼
🎬 Keyframe Generator ───▶ ✅ Selector ───▶ 🎥 Video Generator
                               ▲
                               │
👤 Character Trainer ─────────┘
(LoRAs for consistent characters)


🎤 Lipsync Studio (standalone)
       │
       │ Portrait + Audio
       ▼
┌──────────────────┐
│ Wan 2.2 is2v     │───▶ lipsync/*.mp4
│ (Sound-to-Video) │
└──────────────────┘
```

**Image Importer** is an alternative to **Keyframe Generator** - both feed the **Selector**.

**Character Trainer** creates LoRAs that are assigned to shots in the **Storyboard** and then used in the **Keyframe Generator**.

**Lipsync Studio** is a standalone workflow - upload an image + audio to generate lip-synced video.
""")

    def _render_quickstart(self):
        """Render quickstart guide."""
        gr.Markdown("""
## Quick Start: First Video in 5 Steps

### 1. Create Project
- Open **📁 Project**
- Enter a name and click "Create"
- The project will be automatically activated

### 2. Create Storyboard
- Switch to **📖 Storyboard**
- Click "New Shot" for each desired video clip
- Fill in:
  - **Prompt**: What should be visible in the image?
  - **Duration**: How long should the clip be? (max 3s per segment)
  - **Presets**: Style, Lighting, Mood etc.
- Click "Save"

### 3. Generate Keyframes
- Switch to **🎬 Keyframe Generator**
- Choose workflow (24GB or 16GB depending on VRAM)
- Select variants per shot (2-4 recommended)
- Click "Start Generation"
- Wait until all shots are generated

### 4. Select Best Variants
- Switch to **✅ Keyframe Selector**
- For each shot:
  - View the variants in the gallery
  - Select the best variant
  - Click "Save Shot Variant"
- Click "Save Shot Selection" (Export)

### 5. Generate Videos
- Switch to **🎥 Video Generator**
- Storyboard and selection are automatically loaded
- Choose workflow and quality
- Click "Generate Clips"
- Finished videos are in `<project>/video/`

---

## Tips

- **ComfyUI must be running** before starting the GUI
- **GPU with 16GB+ VRAM** recommended for best results
- **Shots > 3 seconds** are automatically split into segments
- **Character LoRAs** for consistent characters: train first, then assign in Storyboard
""")

    def _render_shortcuts(self):
        """Render keyboard shortcuts."""
        gr.Markdown("""
## Shortcuts & Tips

### General

| Action | Shortcut |
|--------|----------|
| Switch tab | Click on tab header |
| Open/close accordion | Click on header |
| Open dropdown | Click or Enter |

### Storyboard Editor

| Action | Tip |
|--------|-----|
| Quick navigation | Use shot dropdown |
| Apply presets | Use category dropdowns |
| Assign character | Multi-select dropdown |

### Keyframe Generator

| Action | Tip |
|--------|-----|
| Fix seed | Set seed value in Storyboard (-1 = random) |
| More variants | Increase "Variants per shot" |
| Open output | Button "Open Output Folder" |

### Video Generator

| Action | Tip |
|--------|-----|
| Long videos | Choose "Long Video GGUF" workflow |
| Save VRAM | Use Q4 or Q5 quality |
| See progress | Log file or ComfyUI terminal |

---

## Common Problems

### "Connection failed"
→ ComfyUI is not running. Start it with `python main.py`

### "Models missing"
→ Click "Re-verify models" or install missing models

### "No keyframes found"
→ First generate keyframes or use Image Importer

### "Generation hangs"
→ Check ComfyUI terminal for errors, possibly VRAM full
""")


__all__ = ["HelpAddon"]
