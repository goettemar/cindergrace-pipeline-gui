# CINDERGRACE Feature Roadmap

**Last Updated:** December 13, 2025
**Current Version:** v0.5.1
**Status:** Phase 3 Beta Complete → Production Hardening & Feature Enhancement

---

## 📋 Version Overview

| Version | Focus | Status | Target Date |
|---------|-------|--------|-------------|
| v0.5.1 | Code Refactoring & Test Coverage (75%) | ✅ Complete | Dec 13, 2025 |
| v0.6.0 | Storyboard Editor & Project Integration | 🔄 Planned | Q1 2026 |
| v0.7.0 | Timeline Toolkit & Motion Control | 📅 Planned | Q1 2026 |
| v0.8.0 | Performance & UX Enhancements | 📅 Planned | Q2 2026 |
| v0.9.0 | Advanced Editing & Collaboration | 📅 Planned | Q2 2026 |
| v1.0.0 | Production Release | 🎯 Goal | Q3 2026 |

---

## 🎯 v0.6.0 - Storyboard Editor & Project Integration

**Goal:** Enable manual storyboard creation and editing directly within the GUI, fully integrated with the project workflow.

### Core Feature: Storyboard Editor Addon

**Priority:** High
**Dependencies:** ProjectStore, StoryboardService, Domain Models
**Estimated Effort:** Medium (3-5 days)

#### Features

- **📝 CRUD Operations**
  - Create new storyboard within active project
  - Load existing storyboards from `<project>/storyboards/`
  - Edit shots (add, remove, reorder, duplicate)
  - Save changes to project-scoped JSON files
  - Delete storyboards with confirmation

- **🎬 Shot Management**
  - Add/Remove/Duplicate shots
  - Edit all shot properties:
    - shot_id, filename_base, description
    - prompt, negative_prompt
    - width, height, duration
    - camera_movement
    - wan_motion (type, strength, notes)
  - Drag-and-drop reordering
  - Shot validation with Pydantic models

- **📋 Timeline Preview**
  - Visual shot list with thumbnails (if keyframes exist)
  - Total duration calculation
  - Shot count and sequence overview
  - Color-coded status (new, has keyframes, has video)

- **🔗 Project Integration**
  - Auto-scoped to active project from ProjectStore
  - Saves storyboards to `<project>/storyboards/`
  - Updates `project.json` with storyboard references
  - Sets default storyboard for downstream pipeline
  - "No active project" guard with redirect to Project tab

- **✅ Validation**
  - Real-time field validation (min/max bounds)
  - Duplicate shot_id detection
  - Required field checks
  - Resolution/duration constraints
  - Filename_base uniqueness warnings

#### UI Layout

```
Tab: 📖 Storyboard Editor (positioned after "📁 Projekt")

┌─────────────────────────────────────────────────┐
│ 📦 Project Context                              │
│ Active Project: Demo Project (demo-slug)        │
│ Project Path: /path/to/ComfyUI/output/demo/    │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ 📖 Storyboard Management                        │
│ [Dropdown: Select Storyboard  ▼] [🔄 Refresh]  │
│ [➕ New Storyboard] [💾 Save] [🗑️ Delete]      │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ 🎬 Shot Editor                                  │
│ Shot List (Drag to Reorder):                    │
│ ┌─────────────────────────────────────────┐    │
│ │ Shot 001: cathedral-interior             │    │
│ │ 1024x576 | 4.0s | slow_push              │    │
│ │ [✏️ Edit] [📋 Duplicate] [🗑️ Delete]     │    │
│ ├─────────────────────────────────────────┤    │
│ │ Shot 002: character-closeup              │    │
│ │ 1024x576 | 3.0s | static                 │    │
│ │ [✏️ Edit] [📋 Duplicate] [🗑️ Delete]     │    │
│ └─────────────────────────────────────────┘    │
│ [➕ Add New Shot]                               │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ Shot Details (appears when editing)             │
│ Shot ID: [001_______]                           │
│ Filename Base: [cathedral-interior_______]      │
│ Description: [Opening shot of cathedral...]     │
│ Prompt: [gothic cathedral interior, cinematic]  │
│ Negative: [blurry, low quality]                 │
│ Width: [1024] Height: [576]                     │
│ Duration: [4.0] seconds                         │
│ Camera Movement: [slow_push ▼]                  │
│ Wan Motion Type: [macro_dolly ▼]               │
│ Wan Motion Strength: [0.6] (0.0-1.0)           │
│ Wan Motion Notes: [Small forward move...]       │
│ [✅ Save Shot] [❌ Cancel]                      │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ 📊 Timeline Summary                             │
│ Total Shots: 5                                  │
│ Total Duration: 17.5 seconds                    │
│ Average Shot Length: 3.5s                       │
│ Resolution(s): 1024x576                         │
└─────────────────────────────────────────────────┘
```

#### Technical Implementation

**New Files:**
- `addons/storyboard_editor.py` - Main addon class
- `services/storyboard/storyboard_editor_service.py` - Business logic
- `tests/unit/test_storyboard_editor.py` - Addon tests
- `tests/unit/services/storyboard/test_storyboard_editor_service.py` - Service tests

**Modified Files:**
- `infrastructure/project_store.py` - Add methods:
  - `set_project_storyboard(project, storyboard_filename, set_as_default=True)`
  - `get_project_storyboard_dir(project)`
  - `ensure_storyboard_dir(project)`
  - `list_project_storyboards(project)`
- `addons/__init__.py` - Register StoryboardEditorAddon
- `domain/storyboard_service.py` - Add save/update methods if not present

**Event Handlers:**
```python
# In StoryboardEditorAddon
def on_new_storyboard(self, name: str) -> str:
    """Create new storyboard in active project"""

def on_load_storyboard(self, filename: str) -> Tuple[dict, str]:
    """Load storyboard from project directory"""

def on_save_storyboard(self, storyboard_data: dict) -> str:
    """Save storyboard and update project.json"""

def on_add_shot(self) -> dict:
    """Add new shot with defaults"""

def on_edit_shot(self, shot_id: str, shot_data: dict) -> str:
    """Update shot in storyboard"""

def on_delete_shot(self, shot_id: str) -> str:
    """Remove shot from storyboard"""

def on_duplicate_shot(self, shot_id: str) -> str:
    """Duplicate shot with incremented ID"""
```

**Validation:**
- Use existing `domain/validators/domain_validators.py`
- Extend with storyboard-specific rules if needed
- Real-time validation on field blur
- Bulk validation on save

**Testing:**
- Unit tests for service layer (CRUD operations)
- Integration tests for ProjectStore extensions
- UI smoke tests with monkeypatch
- Validation tests for edge cases
- Target: 85%+ coverage for new code

---

## 🔗 v0.6.0 - Pipeline Integration Improvements

**Goal:** Improve workflow between tabs with auto-sync and status indicators.

### Feature 1: Auto-Sync Project State

**Priority:** High
**Dependencies:** ProjectStore, StateStore
**Estimated Effort:** Small (1-2 days)

#### Implementation

- **Keyframe Generator** auto-loads storyboard from active project
  - On tab switch, check `project.json` for default storyboard
  - Auto-populate storyboard dropdown with project default
  - Show warning if no storyboard exists: "⚠️ No storyboard found. Create one in Storyboard Editor."

- **Video Generator** auto-loads selection from active project
  - Check `<project>/selected/` for selection JSON files
  - Auto-select most recent if multiple exist
  - Link to Keyframe Selector if none found

- **Event-driven refresh**
  - Use Gradio's `gr.State` to share project updates
  - Emit project change events when switching projects
  - Auto-refresh dependent dropdowns

**Files Modified:**
- `addons/keyframe_generator.py` - Add auto-load logic
- `addons/video_generator.py` - Add auto-load logic
- `infrastructure/project_store.py` - Add event callbacks

---

### Feature 2: Status Badges in Project Tab

**Priority:** Medium
**Dependencies:** ProjectStore, File System Checks
**Estimated Effort:** Small (1 day)

#### Implementation

- Add status section in Project tab showing:
  - 🟢 **Storyboard:** "storyboard_v1.json" (5 shots, 17.5s)
  - 🟡 **Keyframes:** 3/5 shots complete (60%)
  - 🔴 **Selection:** Not started
  - 🔴 **Videos:** Not started

- Status calculation logic:
  ```python
  def get_project_status(project):
      status = {
          "storyboard": check_storyboard_exists(project),
          "keyframes": count_keyframe_shots(project),
          "selection": check_selection_json(project),
          "videos": count_video_files(project),
      }
      return status
  ```

- Color coding:
  - 🟢 Green: Complete/Ready
  - 🟡 Yellow: In Progress
  - 🔴 Red: Not Started

**Files Modified:**
- `addons/project_panel.py` - Add status display
- `infrastructure/project_store.py` - Add status helper methods

---

### Feature 3: Quick Navigation Buttons

**Priority:** Medium
**Dependencies:** Gradio Tab API
**Estimated Effort:** Small (1 day)

#### Implementation

- Add contextual navigation buttons after key actions:
  - **Storyboard Editor** → After save: "→ Generate Keyframes"
  - **Keyframe Generator** → After completion: "→ Select Keyframes"
  - **Keyframe Selector** → After export: "→ Generate Videos"
  - **Video Generator** → After completion: "→ View in Project"

- Use Gradio's `gr.Button` with `link` parameter to switch tabs
- Disable buttons if prerequisites not met (e.g., no storyboard, no selection)

**Files Modified:**
- All addon files - Add navigation buttons to UI

---

## 🎨 v0.7.0 - Timeline Toolkit & Motion Control

**Goal:** Enhanced timeline visualization and motion parameter control from storyboard.

### Feature 1: Timeline Export to JSON

**Priority:** High
**Dependencies:** StoryboardService, SelectionService
**Estimated Effort:** Medium (2-3 days)

#### Implementation

- Export `timeline.json` combining:
  - Storyboard metadata (prompts, duration, camera movement)
  - Selected keyframe references
  - Generated video file paths
  - Timing information (start_time, end_time per shot)

- Format:
  ```json
  {
    "project": "Demo Project",
    "total_duration": 17.5,
    "timeline": [
      {
        "shot_id": "001",
        "start_time": 0.0,
        "end_time": 4.0,
        "duration": 4.0,
        "keyframe": "cathedral-interior_v2_00001_.png",
        "video_segments": [
          "shot_001_seg_0.mp4",
          "shot_001_seg_1.mp4"
        ],
        "prompt": "gothic cathedral interior...",
        "camera_movement": "slow_push",
        "wan_motion": {
          "type": "macro_dolly",
          "strength": 0.6
        }
      }
    ]
  }
  ```

- Use case: Import into video editing software (Premiere, DaVinci Resolve)

**Files:**
- `services/timeline/timeline_export_service.py`
- `addons/timeline_exporter.py` (new tab or button in Video Generator)

---

### Feature 2: Enhanced Wan Motion Control

**Priority:** Medium
**Dependencies:** ComfyAPI Workflow Updaters
**Estimated Effort:** Medium (2-3 days)

#### Implementation

- Read `wan_motion` parameters from storyboard
- Update `HunyuanVideoSampler` nodes with:
  - `embedded_guidance_scale` (from `strength`)
  - Motion type presets (map to node parameters)
  - Easing curves (if supported by Wan 2.2)

- Add motion preview in Storyboard Editor:
  - Visual indicator of motion type (dolly, pan, tilt)
  - Strength slider with live preview

**Files Modified:**
- `infrastructure/comfy_api/node_updaters/hunyuan_updater.py`
- `addons/storyboard_editor.py` - Add motion preview
- `addons/video_generator.py` - Use storyboard motion params

---

### Feature 3: Visual Timeline Editor (Phase 2)

**Priority:** Low
**Dependencies:** Gradio Advanced Components or Custom JS
**Estimated Effort:** Large (1-2 weeks)

#### Implementation

- Interactive timeline with:
  - Draggable shot blocks
  - Visual duration bars
  - Thumbnail preview on hover
  - Click to jump to shot details

- Requires custom Gradio component or HTML/JS integration
- Defer to v0.8.0 or later if complexity too high

---

## ⚡ v0.8.0 - Performance & UX Enhancements

**Goal:** Optimize performance for large storyboards and improve user experience.

### Feature 1: Parallel File Operations

**Priority:** High
**Dependencies:** ThreadPoolExecutor
**Estimated Effort:** Medium (2-3 days)

#### Implementation

- Use `concurrent.futures.ThreadPoolExecutor` for:
  - Copying keyframe variants (currently sequential)
  - Downloading images from ComfyUI
  - Extracting LastFrames from multiple segments

- Example:
  ```python
  with ThreadPoolExecutor(max_workers=4) as executor:
      futures = [executor.submit(copy_file, src, dst) for src, dst in file_pairs]
      for future in as_completed(futures):
          result = future.result()
  ```

- Expected speedup: 2-4x for 10+ keyframe variants

**Files Modified:**
- `services/keyframe/keyframe_generation_service.py`
- `services/video/video_generation_service.py`

---

### Feature 2: Workflow Update Caching

**Priority:** Medium
**Dependencies:** ConfigManager
**Estimated Effort:** Small (1-2 days)

#### Implementation

- Cache workflow JSON after first load
- Only reload if file modified timestamp changes
- Use `functools.lru_cache` or custom cache

**Files Modified:**
- `infrastructure/workflow_registry.py`
- `infrastructure/comfy_api/comfy_api_client.py`

---

### Feature 3: Batch Shot Generation

**Priority:** Medium
**Dependencies:** ComfyAPI Queue Management
**Estimated Effort:** Medium (3-4 days)

#### Implementation

- Queue multiple shots to ComfyUI at once
- Monitor all jobs in parallel via WebSocket
- Update progress per-shot in UI
- Requires redesign of progress tracking

**Files Modified:**
- `services/keyframe/keyframe_generation_service.py`
- `infrastructure/comfy_api/comfy_api_client.py`

---

### Feature 4: Memory Optimization

**Priority:** Low
**Dependencies:** Profiling
**Estimated Effort:** Medium (2-3 days)

#### Implementation

- Profile memory usage with `memory_profiler`
- Optimize large storyboard handling (avoid loading entire JSON multiple times)
- Stream large file operations instead of loading into memory

---

## 🤝 v0.9.0 - Advanced Editing & Collaboration

**Goal:** Advanced editing features and multi-user support.

### Feature 1: Undo/Redo for Shot Editing

**Priority:** Medium
**Dependencies:** State Management
**Estimated Effort:** Medium (3-4 days)

#### Implementation

- Maintain edit history stack in StoryboardEditorService
- Implement command pattern for all edit operations
- Add Undo/Redo buttons in Storyboard Editor UI
- Limit history to last 50 operations

**Files:**
- `services/storyboard/edit_history.py` (new)
- `addons/storyboard_editor.py` - Add Undo/Redo UI

---

### Feature 2: Import/Export from Other Projects

**Priority:** Medium
**Dependencies:** ProjectStore, FileSystem
**Estimated Effort:** Small (2 days)

#### Implementation

- **Import Storyboard:**
  - Browse other projects in `<ComfyUI>/output/`
  - Copy storyboard JSON to current project
  - Option to import with or without keyframes

- **Export Storyboard:**
  - Save storyboard to external location
  - Package with keyframes/videos (zip archive)

**Files:**
- `addons/storyboard_editor.py` - Add import/export buttons
- `services/storyboard/import_export_service.py` (new)

---

### Feature 3: Template Library

**Priority:** Low
**Dependencies:** Storyboard Presets
**Estimated Effort:** Medium (3 days)

#### Implementation

- Pre-defined storyboard templates:
  - Music Video Template (10 shots, 30s)
  - Short Film Template (20 shots, 60s)
  - Product Showcase (5 shots, 15s)

- Store in `config/storyboard_templates/`
- One-click apply to new project

**Files:**
- `config/storyboard_templates/*.json` (new)
- `addons/storyboard_editor.py` - Add template selector

---

### Feature 4: Multi-User File Locking

**Priority:** Low
**Dependencies:** Enhanced File Locking
**Estimated Effort:** Medium (3-4 days)

#### Implementation

- Extend current fcntl locking to storyboard files
- Show "locked by user X" message if storyboard in use
- Auto-refresh when lock released

**Files Modified:**
- `infrastructure/project_store.py` - Add storyboard locking
- `addons/storyboard_editor.py` - Show lock status

---

## 🎯 v1.0.0 - Production Release

**Goal:** Stable, documented, production-ready release.

### Requirements

- **Test Coverage:** 85%+ overall
- **Performance Benchmarks:**
  - 10-shot storyboard → keyframes: < 5 minutes (hardware dependent)
  - 5-shot video generation: < 15 minutes (hardware dependent)
  - UI response time: < 200ms for all interactions

- **Documentation:**
  - Complete user guide with screenshots
  - API documentation (Sphinx)
  - Video tutorials (YouTube)
  - Troubleshooting guide

- **Example Projects:**
  - Gallery of 5+ completed projects
  - Sample storyboards for different genres
  - Workflow presets for common use cases

- **Stability:**
  - No known critical bugs
  - Error handling for all edge cases
  - Graceful degradation on missing dependencies

- **Deployment:**
  - Docker container support
  - One-click installer for Windows/Mac/Linux
  - Systemd service file for background operation

---

## 📊 Priority Matrix

| Feature | Version | Priority | Effort | Dependencies | Impact |
|---------|---------|----------|--------|--------------|--------|
| Storyboard Editor | v0.6.0 | High | Medium | ProjectStore | High |
| Auto-Sync Project State | v0.6.0 | High | Small | StateStore | High |
| Status Badges | v0.6.0 | Medium | Small | ProjectStore | Medium |
| Quick Navigation | v0.6.0 | Medium | Small | Gradio | Medium |
| Timeline Export | v0.7.0 | High | Medium | Services | High |
| Wan Motion Control | v0.7.0 | Medium | Medium | ComfyAPI | Medium |
| Visual Timeline Editor | v0.7.0 | Low | Large | Custom JS | Low |
| Parallel File Ops | v0.8.0 | High | Medium | Threading | High |
| Workflow Caching | v0.8.0 | Medium | Small | Cache | Medium |
| Batch Generation | v0.8.0 | Medium | Medium | ComfyAPI | Medium |
| Undo/Redo | v0.9.0 | Medium | Medium | State Mgmt | Medium |
| Import/Export | v0.9.0 | Medium | Small | FileSystem | Medium |
| Template Library | v0.9.0 | Low | Medium | Config | Low |
| Multi-User Locking | v0.9.0 | Low | Medium | Locking | Low |

---

## 🚀 Implementation Strategy

### Phase 1: Foundation (v0.6.0)
1. Implement Storyboard Editor (core feature)
2. Add project integration improvements
3. Update documentation
4. Release beta for testing

### Phase 2: Enhancement (v0.7.0)
1. Timeline toolkit implementation
2. Motion control enhancements
3. User feedback incorporation
4. Performance testing

### Phase 3: Optimization (v0.8.0)
1. Performance improvements
2. UX polish
3. Bug fixes from v0.6/v0.7
4. Stability testing

### Phase 4: Advanced Features (v0.9.0)
1. Advanced editing capabilities
2. Collaboration features
3. Template library
4. Beta testing with external users

### Phase 5: Release (v1.0.0)
1. Final bug fixes
2. Complete documentation
3. Video tutorials
4. Production deployment guide
5. Official release announcement

---

## 📝 Notes

### Success Metrics

**v0.6.0:**
- Storyboard Editor functional with CRUD operations
- Auto-sync reduces manual dropdown changes by 80%
- Status badges visible in Project tab
- Zero regressions in existing features

**v0.7.0:**
- Timeline export works with 3+ video editing tools
- Wan motion parameters correctly applied from storyboard
- User feedback positive on motion control

**v0.8.0:**
- 2x speedup in keyframe copying for 10+ variants
- Workflow loading time reduced by 50%
- UI remains responsive during long operations

**v0.9.0:**
- Undo/Redo tested with 50+ operations
- Import/Export works across different projects
- Template library used in 50%+ of new projects

**v1.0.0:**
- 85%+ test coverage achieved
- Documentation complete and reviewed
- 5+ example projects in gallery
- Zero critical bugs in production

---

## 🔗 Related Documents

- **BACKLOG.md** - Sprint planning and technical debt
- **STATUS.md** - Current project status
- **CHANGELOG.md** - Version history
- **TESTING.md** - Test coverage reports
- **CLAUDE.md** - Development guidelines

---

**Last Review:** December 13, 2025
**Next Review:** After v0.6.0 release
**Maintained By:** Architecture Team
