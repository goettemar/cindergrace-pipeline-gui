# 🔧 Tools

**Tab Name:** 🔧 Tools
**Structure:** Sub-Tab System
**Category:** `tools` (grouped under main Tools tab)
**State:** Mixed (tool-dependent)

---

## Overview

The **Tools** tab is a special addon category that groups utility and debugging tools under a single tab with sub-tabs. This keeps the main navigation clean while providing access to specialized tools.

### Tab Architecture

```
🔧 Tools (Main Tab)
├── 🧪 Test ComfyUI (Sub-Tab)
└── 🗂️ Model Manager (Sub-Tab)  ← NEW
```

**Key Concept:** Tools are addons with `category="tools"` in their BaseAddon initialization. They automatically appear as sub-tabs under the Tools tab.

---

## Creating New Tool Addons

To create a new tool addon, simply set `category="tools"` in the `BaseAddon.__init__()`:

```python
class MyNewToolAddon(BaseAddon):
    def __init__(self):
        super().__init__(
            name="My Tool",
            description="Tool description",
            category="tools"  # ← This makes it a Tool
        )

    def get_tab_name(self) -> str:
        return "🛠️ My Tool"

    def render(self) -> gr.Blocks:
        with gr.Blocks() as interface:
            # Tool UI here
            pass
        return interface
```

The tool will automatically appear under the Tools tab!

---

## Available Tools

### 1. 🧪 Test ComfyUI

**Purpose:** Connection testing and keyframe image generation debugging

**Features:**
- ComfyUI connection test
- Keyframe test image generation
- System diagnostics
- Workflow validation

**Documentation:** [TEST_COMFY.md](TEST_COMFY.md)

**Use Cases:**
- Verify ComfyUI is running
- Test workflows before using in production
- Debug connection issues
- Quick image generation tests

---

### 2. 🗂️ Model Manager (Phase 2)

**Purpose:** Analyze, classify, and manage ComfyUI model files

**Status:** ✅ Phase 2 Complete

**Key Features:**
- Workflow scanner + file scanner + used/unused/missing classification
- Storage insights (charts, largest models, histograms)
- Hash-based duplicate detection with keep-best suggestion
- Workflow reference mapping (model ↔ workflow nodes)
- Advanced filters (size/date/workflow count/regex)
- Batch archive/restore/delete with operation log
- Exports to CSV/JSON/HTML (full, filtered, summary)

**Documentation:** [MODEL_MANAGER.md](MODEL_MANAGER.md)

**Use Cases:**
- Clean up unused models (free disk space)
- Find missing models referenced in workflows
- Identify duplicate models
- Archive old models for later use
- Understand which workflows need which models

---

## UI Design Pattern

All tools follow a consistent accordion-based layout:

```
Status: [Always visible progress/status line]

▶ Section 1 (Accordion, collapsed by default)
  [Configuration or input fields]

▶ Section 2 (Accordion, collapsed by default)
  [Main functionality]

▶ Section 3 (Accordion, collapsed by default)
  [Results or output]

▶ Settings (Accordion, collapsed by default)
  [Tool-specific configuration]
```

**Benefits:**
- Clean initial view (only status visible)
- Expand only what you need
- Consistent with Storyboard Editor design
- Mobile-friendly (less scrolling)

---

## Tool Development Guidelines

### 1. **Category Assignment**
```python
super().__init__(
    name="Tool Name",
    description="Brief description",
    category="tools"  # IMPORTANT: Makes it a Tool
)
```

### 2. **UI Structure**
- Start with a status line (always visible)
- Use Accordions for sections (default `open=False`)
- Group related functionality
- Add help text/info where needed

### 3. **State Management**
- Tools are typically **stateless** or use minimal state
- For persistent state, use JSON files in tool-specific subdirectories
- Example: `config/model_manager/settings.json`

### 4. **Error Handling**
- Use `@handle_errors` decorator for methods
- Provide clear, actionable error messages
- Never crash the entire GUI

### 5. **Testing**
- Add import tests to `tests/unit/test_addons_imports.py`
- Add functional tests for core logic
- Document manual testing procedures

---

## Technical Implementation

### BaseAddon Changes

The `BaseAddon` class now supports categorization:

```python
class BaseAddon(ABC):
    def __init__(self, name: str, description: str, category: str = "pipeline"):
        self.name = name
        self.description = description
        self.category = category  # "pipeline" or "tools"
        self.enabled = True
```

### Main.py Integration

The main GUI automatically groups tools:

```python
# Separate addons by category
pipeline_addons = [a for a in addons if a.category == "pipeline"]
tool_addons = [a for a in addons if a.category == "tools"]

with gr.Tabs():
    # Pipeline addons as top-level tabs
    for addon in pipeline_addons:
        with gr.Tab(addon.get_tab_name()):
            addon.render()

    # Tool addons grouped under Tools tab
    if tool_addons:
        with gr.Tab("🔧 Tools"):
            gr.Markdown("## ComfyUI Tools & Utilities")
            with gr.Tabs():
                for addon in tool_addons:
                    with gr.Tab(addon.get_tab_name()):
                        addon.render()
```

No manual registration needed - just set the category!

---

## Future Tools (Ideas)

### Potential Tool Addons

1. **🎨 Prompt Library**
   - Save/organize prompts
   - Tag and search
   - Quick insert into workflows

2. **📊 Pipeline Analytics**
   - Track generation times
   - Model performance metrics
   - Resource usage graphs

3. **🔄 Workflow Converter**
   - Convert UI workflows to API format
   - Batch update workflows
   - Version migration

4. **🖼️ Image Comparison**
   - Compare keyframe variants side-by-side
   - A/B testing for prompts
   - Metadata viewer

5. **📦 Batch Processor**
   - Queue multiple generations
   - CSV input support
   - Automated testing

6. **🗄️ Project Archiver**
   - Archive old projects
   - Compress and export
   - Import from archive

7. **🔍 Node Inspector**
   - Browse available ComfyUI nodes
   - Show node inputs/outputs
   - Generate workflow snippets

---

## Migration from Test-Only Tab

**Old Structure:** Test ComfyUI was a top-level tab

**New Structure:** Test ComfyUI is under Tools → Test ComfyUI

**Changes Required:**
1. Added `category="tools"` to TestComfyFluxAddon
2. Updated tab name from "🧪 Test ComfyUI" (kept same)
3. No functional changes to the addon itself

**Benefits:**
- Cleaner main navigation
- Room for more tools without cluttering tabs
- Logical grouping of utilities
- Better scalability

---

## Adding a Tool (Step-by-Step)

### Example: Adding a "Prompt Generator" Tool

**Step 1:** Create the addon file
```bash
touch addons/prompt_generator.py
```

**Step 2:** Implement the addon
```python
from addons.base_addon import BaseAddon
import gradio as gr

class PromptGeneratorAddon(BaseAddon):
    def __init__(self):
        super().__init__(
            name="Prompt Generator",
            description="AI-powered prompt generation and enhancement",
            category="tools"  # Tool category
        )

    def get_tab_name(self) -> str:
        return "✨ Prompt Generator"

    def render(self) -> gr.Blocks:
        with gr.Blocks() as interface:
            gr.Markdown("# ✨ AI Prompt Generator")

            # Your UI here
            with gr.Accordion("Generate Prompt", open=False):
                theme = gr.Textbox(label="Theme/Subject")
                style = gr.Dropdown(["Cinematic", "Artistic", "Realistic"], label="Style")
                generate_btn = gr.Button("Generate")
                output = gr.Textbox(label="Generated Prompt")

            # Event handlers
            generate_btn.click(
                fn=self.generate_prompt,
                inputs=[theme, style],
                outputs=[output]
            )

        return interface

    def generate_prompt(self, theme, style):
        # Your logic here
        return f"A {style.lower()} scene of {theme}..."
```

**Step 3:** Register in `addons/__init__.py`
```python
from addons.prompt_generator import PromptGeneratorAddon

AVAILABLE_ADDONS = [
    # ... existing addons ...
    PromptGeneratorAddon(),  # ← Add here
]
```

**Step 4:** Restart GUI
```bash
./start.sh
```

The new tool automatically appears under Tools → ✨ Prompt Generator!

---

## Performance Considerations

### Load Time
- Tools are loaded on GUI startup (like all addons)
- Heavy operations should be lazy-loaded (only when tab opened)
- Use `interface.load()` event for initialization

### Resource Usage
- Tools should be lightweight (< 100 MB memory)
- Long operations should use `progress=gr.Progress()`
- Consider background processing for heavy tasks

### Scalability
- Max recommended: 10-15 tools per Tools tab
- Beyond that, consider sub-categories or separate apps
- Keep tool count manageable for UX

---

## Related Documentation

- **Test ComfyUI:** [TEST_COMFY.md](TEST_COMFY.md)
- **Model Manager:** [MODEL_MANAGER.md](MODEL_MANAGER.md)
- **BaseAddon:** `addons/base_addon.py`
- **Main GUI:** `main.py` (line 67-85, tab grouping logic)

---

**Last Updated:** December 13, 2025
**Version:** v0.6.0
**Status:** ✅ Stable (Test ComfyUI) + ⏳ In Development (Model Manager)
