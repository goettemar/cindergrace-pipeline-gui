# Storyboard JSON Format v2.0

Complete documentation for CINDERGRACE pipeline storyboard structure.

## File Location

Storyboards must be stored in: `<ComfyUI>/output/<project-slug>/storyboards/`

Example: `/home/ubuntuadmin/comfyui/output/my-project/storyboards/storyboard_main.json`

## File Naming

- **MUST** contain "storyboard" in the filename (case-insensitive)
- **MUST** end with `.json`
- Examples: `storyboard_main.json`, `my_storyboard_v2.json`, `Storyboard_Final.json`

## Complete Structure

```json
{
  "project": "string (required)",
  "version": "string (optional, e.g., '2.0')",
  "description": "string (optional)",
  "total_shots": number (optional, auto-calculated if missing),
  "shots": [...],
  "generation_settings": {...},
  "notes": "string (optional)"
}
```

**Note:** `video_settings` section has been removed. Video generation settings (workflow, model, FPS) are now configured in Tab 🎥 Video Generator.

## Shot Object Structure

### Required Fields

```json
{
  "shot_id": "001",              // Required: Unique identifier (001, 002, etc.)
  "filename_base": "my-shot",    // Required: Base name for generated files (no spaces)
  "description": "...",          // Required: Human-readable description
  "prompt": "..."               // Required: AI generation prompt
}
```

### Optional Fields with Defaults

```json
{
  "duration": 3.0,               // Default: 3.0 seconds
  "camera_movement": "static",   // Default: "static"
  "seed": -1,                    // Default: -1 (random)
  "cfg_scale": 7.0,             // Default: 7.0
  "steps": 20                    // Default: 20
}
```

**Note:** `width` and `height` should **NOT** be specified in individual shots. These values are inherited from the project settings in Tab Projekt → Globale Auflösung. If present in old storyboards, they will be ignored.

### Optional Metadata Fields

```json
{
  "scene": "Opening Scene",      // Scene name for organization
  "character": "Protagonist",    // Character(s) in shot
  "negative_prompt": "...",      // What to avoid in generation
  "wan_motion": {                // Wan 2.2 video motion settings
    "type": "macro_dolly",       // Motion type
    "strength": 0.5,             // Motion intensity (0.0 - 1.0)
    "notes": "..."               // Description of intended motion
  }
}
```

## Camera Movement Options

- `static` - No camera movement
- `slow_push` - Slow forward dolly
- `dolly` - Forward/backward dolly movement
- `pan` - Horizontal camera pan
- `tilt` - Vertical camera tilt
- `zoom` - Zoom in/out
- `crane` - Crane/jib movement

## Wan Motion Types (Per Shot)

These are defined in the `wan_motion` field of each shot:

- `none` - Minimal/atmospheric movement
- `macro_dolly` - Small dolly movement with parallax
- `macro_pan` - Horizontal pan
- `macro_tilt` - Vertical tilt
- `macro_zoom` - Zoom effect
- `macro_orbit` - Circular camera movement

**Motion strength** ranges from 0.0 (no motion) to 1.0 (maximum motion).

## Generation Settings (Optional)

```json
{
  "generation_settings": {
    "variants_per_shot": 4,           // Number of keyframe variants to generate
    "base_seed": 1000,                // Starting seed value
    "steps": 20,                      // Default steps (can be overridden per shot)
    "cfg_scale": 7.0,                 // Default CFG (can be overridden per shot)
    "workflow": "flux_test_simple.json",  // Flux workflow filename
    "output_dir": "keyframes",        // Output subdirectory
    "notes": "..."                    // Additional notes
  }
}
```

## Video Settings

**Video settings are NOT stored in the storyboard.** They are configured in the **Tab 🎥 Video Generator**:

- **Workflow & Model**: Selected in the Video Generator UI
- **FPS**: Global setting in Video Generator (default: 24)
- **Max Clip Seconds**: Global setting in Video Generator (default: 3)
- **Output Directory**: Automatically set to `<project>/video/`

Shot-specific motion settings are defined in the `wan_motion` field of each shot (see above).

## Validation Rules

1. **File must be valid JSON** - Will fail to load if malformed
2. **Must have `project` field** - Project name (string)
3. **Must have `shots` array** - Can be empty `[]`
4. **Each shot must have**:
   - `shot_id` (string)
   - `filename_base` (string, no spaces or special characters)
   - `prompt` (string)
   - `description` (string, can be stored in `raw` dict)

## Field Storage Notes

Some fields are stored in the `raw` dictionary of the Shot model:
- `description`
- `scene`
- `character`
- `negative_prompt`
- `camera_movement`
- `seed`
- `cfg_scale`
- `steps`

The Shot dataclass directly stores:
- `shot_id`
- `filename_base`
- `prompt`
- `width`
- `height`
- `duration`
- `wan_motion` (as MotionSettings object)

## Minimal Valid Storyboard

```json
{
  "project": "My Project",
  "shots": [
    {
      "shot_id": "001",
      "filename_base": "test-shot",
      "description": "Test shot",
      "prompt": "A beautiful landscape"
    }
  ]
}
```

## Full Example

See `storyboard_template.json` in this directory for a complete example with all fields.

## Tips

1. **Use descriptive `filename_base`** - This becomes the filename for generated images
2. **Keep prompts detailed** - More detail = better AI generation
3. **Use `scene` and `character`** - Helps organize shots in complex projects
4. **Set `duration` carefully** - Shots > 3s will be split into segments
5. **Use `negative_prompt`** - Helps avoid unwanted elements
6. **Test motion settings** - Start with strength 0.5, adjust based on results

## Integration with Storyboard Editor

When creating storyboards via the **Tab Storyboard** editor:
- Only required + enabled optional fields are saved
- Width/Height are omitted (inherited from project settings)
- The editor ensures proper structure automatically
- Files are saved to `<project>/storyboards/` with full path registration in `project.json`

## Troubleshooting

**Storyboard not appearing in Tab Projekt:**
- Ensure filename contains "storyboard" (case-insensitive)
- Check file is in `<project>/storyboards/` directory
- Verify JSON is valid (use a JSON validator)
- Click "↻" refresh button in Tab Projekt

**Storyboard loads but shots missing:**
- Check `shots` array is not empty
- Verify each shot has required fields: `shot_id`, `filename_base`, `description`, `prompt`
- Check for JSON syntax errors (missing commas, brackets)

**Width/Height not applied:**
- These are overridden by project settings in Tab Projekt
- Set global resolution in **Tab Projekt → Projekt-Defaults → Globale Auflösung**
