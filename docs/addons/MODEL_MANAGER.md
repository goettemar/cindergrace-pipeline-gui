# Model Manager - ComfyUI Model Organization Tool

**Category:** Tools
**Tab Location:** 🔧 Tools → 🗂️ Model Manager
**Status:** Phase 2 Complete

## Overview

The Model Manager is a comprehensive tool for analyzing, classifying, and managing ComfyUI model files. It scans your workflows to identify which models are actually being used, helps you identify unused models that can be archived to save disk space, and allows you to restore missing models from an archive directory.

## Purpose

Managing ComfyUI model files can become complex as your collection grows. This tool helps you:

- **Understand Usage**: See which models are referenced in your workflows
- **Save Disk Space**: Identify unused models that can be safely archived
- **Restore Missing Models**: Quickly restore models referenced in workflows but missing from disk
- **Organize Files**: Keep your ComfyUI models directory clean and efficient

## Features (Phase 2)

- 📊 **Storage Insights**: Pie + stacked bar charts, top 10 largest, size histogram
- 🔍 **Duplicate Detection**: Hash-based groups with keep-best recommendation
- 📝 **Workflow References**: Model → workflow/node mapping, most/least used lists
- 📄 **Exports**: CSV/JSON/HTML for full, filtered, or summary data
- 🧩 **Advanced Filters**: Size range, modified dates, workflow count, filename regex
- 🔄 **Batch Enhancements**: Archive/restore/delete with progress + operation log

### 1. Workflow Analysis
- Scans all ComfyUI workflow JSON files in a specified directory
- Extracts model references from workflow nodes
- Supports multiple node types:
  - CheckpointLoaderSimple, CheckpointLoader, CheckpointLoaderNF4 → checkpoints
  - LoraLoader, LoraLoaderModelOnly → loras
  - VAELoader → vae
  - ControlNetLoader → controlnet
  - UpscaleModelLoader → upscale_models
  - CLIPLoader, DualCLIPLoader → clip
  - UNETLoader → unet
  - StyleModelLoader → style_models

### 2. Model Classification
Classifies every model into one of three categories:

- **✅ Used**: Model exists on disk AND is referenced in at least one workflow
- **📦 Unused**: Model exists on disk but is NOT referenced in any workflow
- **❌ Missing**: Model is referenced in workflows but does NOT exist on disk

### 3. Statistics & Analysis
- Used vs Unused vs Missing pie chart
- Size by model type stacked bar chart
- Top 10 largest models table
- Size distribution histogram buckets
- Workflow statistics (total workflows, references)

### 4. Filtering & Search
- Filter by status/type and search by filename
- Advanced filters: size range (GB), modified before/after, workflow count range, filename regex
- Chainable filters via `ModelFilter`

### 5. Archive Management
- Move selected unused models to archive directory
- Restore selected missing models from archive
- Archive preserves model type directory structure
- Restore copies files (keeps archive as backup)
- Batch operations with progress callbacks and operation log

## User Interface

The Model Manager UI is organized into three collapsible accordions (all closed by default):

### ⚙️ Settings Accordion

Configure directory paths:

- **ComfyUI Installation Path**: Root directory of your ComfyUI installation
- **Workflows Directory**: Directory containing workflow JSON files
  Default: `/home/ubuntuadmin/comfyui/user/default/workflows`
- **Archive Directory**: Directory for archived (unused) models
  Default: `/home/ubuntuadmin/model-archive`

Click **💾 Save Settings** to apply changes.

### 📊 Analysis & Statistics Accordion

Click **🔍 Analyze Models** to scan workflows and models:

- **Analysis Results** (Markdown):
  - Total used models (count + disk space)
  - Total unused models (count + disk space)
  - Total missing models (count)
  - Potential savings by archiving unused
  - Breakdown by type (used/unused/missing counts per model type)

- **Workflow Statistics** (JSON):
  - Total workflows found
  - Workflows with model references
  - Total model references across all workflows

### 🗂️ Model Management Accordion

Filter and manage models:

- **Filter Controls**:
  - Status Filter dropdown (All, Used, Unused, Missing)
  - Type Filter dropdown (All, checkpoints, loras, vae, etc.)
  - Search box (filter by filename)
  - Advanced filters:
    - Size range sliders (GB)
    - Modified date after/before
    - Workflow count range
    - Filename regex
  - 🔄 Refresh List button

- **Models Dataframe**:
  Columns: Select | Filename | Type | Status | Size | Workflows | Path
  - Interactive checkboxes for batch selection
  - Shows all models matching current filters
  - Displays workflow count for each model

- **Batch Actions**:
  - **📦 Move Selected to Archive**: Move selected models to archive directory
  - **↩️ Restore Selected from Archive**: Restore selected missing models from archive

### 📈 Storage Statistics Accordion

- Pie chart: Used vs Unused vs Missing counts
- Bar chart: Size by model type (stacked used/unused)
- Table: Top 10 largest models
- Table: Size distribution buckets for quick cleanup candidates

### 🔍 Duplicate Detection Accordion

- **Scan for Duplicates** button (hash-based detection with partial hashing for large files)
- Shows duplicate groups with filenames, sizes, and status
- **Keep Best** auto-selects unused duplicates (keeps used files)
- **Delete Selected Duplicates** moves selected duplicates to archive (confirmation required)

### 📄 Export Reports Accordion

- Choose CSV / JSON / HTML
- **Export Full Analysis**: All models and metadata
- **Export Filtered Models**: Current filtered list
- **Export Summary**: Statistics-only export
- Exports include timestamp and analysis parameters

### 📝 Workflow References Accordion

- Dropdown of analyzed model filenames
- Usage table: Workflow, model type, node id, node type
- Tables for most-used models, single-use models, workflow complexity (model count per workflow)

## Typical Workflow

### First-Time Setup

1. Open **🔧 Tools → 🗂️ Model Manager**
2. Expand **⚙️ Settings** accordion
3. Configure directory paths:
   - Set ComfyUI Installation Path (e.g., `/home/ubuntuadmin/comfyui`)
   - Set Workflows Directory (e.g., `/home/ubuntuadmin/comfyui/user/default/workflows`)
   - Set Archive Directory (e.g., `/home/ubuntuadmin/model-archive`)
4. Click **💾 Save Settings**

### Analyzing Models

1. Expand **📊 Analysis & Statistics** accordion
2. Click **🔍 Analyze Models**
3. Review analysis results:
   - Check how many models are used vs unused
   - See potential disk space savings
   - Review workflow statistics

### ⚠️ Important: ComfyUI Templates

**The Model Manager only scans your user workflows**, not the official ComfyUI templates installed in the system.

**Why?** To prevent marking template models as "Used" when you're not actually using them.

**Official templates location:**
- `/path/to/comfyui/.venv/lib/python3.12/site-packages/comfyui_workflow_templates_*/templates/`
- Categories: media_image (44), media_video (33), media_api (77), media_other (45)
- Total: ~199 official templates

**Recommended workflow:**
1. When you want to use an official template, **save a copy** to your workflows directory first
2. This ensures models needed by that template are marked as "Used"
3. Otherwise, template-required models may be incorrectly classified as "Unused" and archived

**Why templates are NOT scanned:**
- Prevents marking all template models as "Used" even if you never use them
- Gives you control over which templates you actually use
- Avoids cluttering your "Used" models list with unused template dependencies

### Archiving Unused Models

1. Expand **🗂️ Model Management** accordion
2. Set **Status Filter** to "Unused"
3. Optionally filter by **Type** (e.g., only checkpoints)
4. Use **Search** to find specific models
5. Select models to archive using checkboxes
6. Click **📦 Move Selected to Archive**
7. Review success/failure message
8. Models are moved to `<archive-dir>/<model-type>/filename`

### Restoring Missing Models

1. Expand **🗂️ Model Management** accordion
2. Set **Status Filter** to "Missing"
3. Select models to restore using checkboxes
4. Click **↩️ Restore Selected from Archive**
5. Review success/failure message
6. Models are copied from archive to ComfyUI models directory

## Architecture

### Service Layer

The Model Manager uses a modular service architecture:

```
services/model_manager/
├── __init__.py                 # Service exports
├── workflow_scanner.py         # Scan workflows for model references
├── model_scanner.py            # Scan filesystem for model files
├── model_classifier.py         # Classify models (used/unused/missing)
├── storage_analyzer.py         # Storage insights and distributions
├── duplicate_detector.py       # Hash-based duplicate detection
├── workflow_mapper.py          # Model ↔ workflow mapping helpers
├── report_exporter.py          # CSV/JSON/HTML exports
├── model_filter.py             # Chainable advanced filters
└── archive_manager.py          # Move/restore/delete/archive index
```

#### WorkflowScanner
- Scans JSON workflow files
- Extracts model references from node inputs
- Maps node types to model types
- Returns workflow → model references mapping

#### ModelScanner
- Scans ComfyUI models directory recursively
- Finds model files by extension
- Collects file metadata (path, size, type)
- Returns model type → file list mapping

#### ModelClassifier
- Combines workflow and filesystem data
- Classifies models into 3 categories (ModelStatus enum)
- Generates statistics (counts, sizes, breakdown by type)
- Provides filtering methods

#### ArchiveManager
- Moves models to archive preserving directory structure
- Restores models from archive to ComfyUI models directory
- Checks if models exist in archive
- Supports batch operations with dry-run mode

### UI Layer

**File:** `addons/model_manager.py`

- Inherits from `BaseAddon` with `category="tools"`
- Accordion-based UI (Settings, Analysis, Management)
- Event handlers for:
  - Save settings
  - Analyze models
  - Filter models (status, type, search)
  - Move to archive
  - Restore from archive
- State management:
  - Cached classification results (`last_classification`)
  - Service instances (initialized on demand)

## File Locations

### Code
- **Addon UI**: `addons/model_manager.py`
- **Services**: `services/model_manager/`
  - `workflow_scanner.py`
  - `model_scanner.py`
  - `model_classifier.py`
  - `archive_manager.py`

### Documentation
- **This file**: `docs/addons/MODEL_MANAGER.md`
- **Tools overview**: `docs/addons/TOOLS.md`

### Data Directories
- **Workflows**: Configured in Settings (default: `/home/ubuntuadmin/comfyui/user/default/workflows`)
- **Models**: `<ComfyUI>/models/` (checkpoints, loras, vae, etc.)
- **Archive**: Configured in Settings (default: `/home/ubuntuadmin/model-archive`)

## Archive Directory Structure

The archive preserves model type organization:

```
<archive-root>/
├── checkpoints/
│   ├── unused-checkpoint-1.safetensors
│   └── unused-checkpoint-2.ckpt
├── loras/
│   └── old-lora.safetensors
├── vae/
│   └── unused-vae.pt
└── controlnet/
    └── old-controlnet.pth
```

This structure matches the ComfyUI models directory, making it easy to understand what each archived file is.

## Important Notes

### Model Detection
- Only scans workflow JSON files in API format
- Requires workflows to use standard node types (CheckpointLoader, LoraLoader, etc.)
- Custom nodes with non-standard model loading may not be detected

### File Operations
- **Move to Archive**: Uses `shutil.move()` - files are MOVED, not copied
- **Restore from Archive**: Uses `shutil.copy2()` - files are COPIED, archive keeps backup
- Both operations preserve file metadata (timestamps, permissions)

### Safety
- Models marked as "Used" cannot be moved to archive from the UI
- Only "Used" or "Unused" models can be moved (not "Missing" since they don't exist)
- Only "Missing" models can be restored (only if they exist in archive)
- Each operation reports success/failure for each file

### Performance
- Workflow scanning is I/O intensive (reads all JSON files)
- Model scanning is I/O intensive (recursively scans model directories)
- Classification caches results until next "Analyze" click
- Large model collections may take time to scan

## Planned Features (Phase 2)

Future enhancements planned but not yet implemented:

### Advanced Filtering
- Filter by file size range
- Filter by last modified date
- Filter by workflow usage count
- Multiple simultaneous filters with AND/OR logic

### Duplicate Detection
- Find models with identical content (hash-based)
- Compare models with similar names
- Suggest which duplicates to keep

### Usage Analytics
- Most frequently used models
- Least used models
- Models not used in recent workflows
- Time-based usage trends

### Bulk Operations
- Archive all unused models of a type
- Restore all missing models
- Delete archived models permanently (with confirmation)
- Export/import archive index

### Integration
- Load workflows directly from Model Manager
- Jump to workflow editor from model row
- Preview model details (metadata, size, creation date)
- Generate usage reports (CSV, JSON, HTML)

## Troubleshooting

### No Workflows Found
- Check that workflows directory exists
- Verify workflows are in JSON format (not PNG or other formats)
- Ensure workflows are in API format (dict of nodes)
- Check file permissions on workflows directory

### No Models Found
- Verify ComfyUI installation path is correct
- Check that models directory exists at `<ComfyUI>/models/`
- Ensure model files have correct extensions (.safetensors, .ckpt, .pt, .pth, .bin)
- Verify file permissions on models directory

### Archive Operations Fail
- Check that archive directory exists or can be created
- Verify write permissions on archive directory
- Ensure sufficient disk space for archive operations
- Check that source files exist and are accessible

### Incorrect Classification
- Re-run **Analyze Models** to refresh data
- Verify workflows are up-to-date
- Check that workflow JSON contains correct model references
- Ensure model filenames match exactly (case-sensitive)

### Performance Issues
- For large collections, analysis may take several minutes
- Close unnecessary accordions to reduce UI updates
- Use filters to reduce table size
- Consider splitting workflows into subdirectories

## Version History

- **v1.0.0 (Phase 1 MVP)** - Initial release (Dec 2024)
  - Workflow scanning
  - Model classification (used/unused/missing)
  - Basic filtering and search
  - Archive/restore functionality
  - Statistics and analysis

## See Also

- [Tools Tab Overview](TOOLS.md) - All tools in the Tools tab
- [Test ComfyUI](TEST_COMFY.md) - Connection testing and keyframe generation
