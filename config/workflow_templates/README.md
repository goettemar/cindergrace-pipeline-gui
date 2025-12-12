# Workflow Templates

Place your ComfyUI workflow JSON files here.

## Required Workflows:

1. **flux_keyframe_1.json** - Your first Flux keyframe generation workflow
2. **flux_keyframe_2.json** - Your second Flux keyframe generation workflow
3. **flux_keyframe_3.json** - Your third Flux keyframe generation workflow

## Workflow Format:

Your workflow files must be in **ComfyUI API format** (JSON). You can export these from ComfyUI:

1. Create your workflow in ComfyUI
2. Enable "Dev mode" in ComfyUI settings
3. Click "Save (API Format)" button
4. Save the JSON file to this directory

## Example Structure:

```json
{
  "3": {
    "inputs": {
      "seed": 1001,
      "steps": 20,
      "cfg": 7.0
    },
    "class_type": "KSampler"
  },
  "6": {
    "inputs": {
      "text": "your prompt here"
    },
    "class_type": "CLIPTextEncode"
  },
  "9": {
    "inputs": {
      "filename_prefix": "output"
    },
    "class_type": "SaveImage"
  }
}
```

The GUI will automatically update the following parameters:
- **Prompt** (CLIPTextEncode node)
- **Seed** (KSampler node)
- **Filename prefix** (SaveImage node)

Make sure your workflows have these nodes!
