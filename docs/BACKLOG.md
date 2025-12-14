# CINDERGRACE Development Backlog - Deferred Issues

**Last Updated:** December 13, 2025
**Purpose:** Track issues, technical debt, and improvements that are deferred to future versions
**Related:** See [ROADMAP.md](ROADMAP.md) for planned features

---

## 📊 Issue Overview

| Category | Count | Priority Distribution |
|----------|-------|-----------------------|
| Known Issues | 6 | High: 2, Medium: 2, Low: 2 |
| Code Quality | 4 | Medium: 4 |
| Technical Debt - Architecture | 4 | Medium: 3, Low: 1 |
| Technical Debt - Infrastructure | 4 | Low: 4 |
| Technical Debt - Documentation | 4 | Medium: 2, Low: 2 |
| CI/CD Incomplete | 3 | Medium: 3 |
| Refactoring Carryover | 2 | Low: 2 |
| **Total** | **27** | **High: 2, Medium: 11, Low: 14** |

---

## 🐛 Known Issues & Limitations

### High Priority

#### #001: Stop/Abort Button Missing
**Status:** Open
**Priority:** High
**Impact:** User Experience
**Assigned Version:** v0.6.0 or v0.7.0

**Description:**
- No UI button to cancel running generation in Keyframe/Video Generator
- Users must use Ctrl+C in terminal to stop processes
- Impacts long-running operations (multi-shot generation, video segments)

**Current Workaround:**
- Ctrl+C in terminal
- Close browser tab (not recommended, may leave orphaned ComfyUI jobs)

**Proposed Solution:**
- Add "⏹️ Stop Generation" button in UI
- Implement graceful shutdown:
  - Set stop flag in service layer
  - Cancel pending ComfyUI jobs via API
  - Save checkpoint state before exit
- Update progress display to show "Stopping..."

**Technical Notes:**
- Requires thread-safe stop flag in services
- May need ComfyUI API enhancement to cancel queued prompts
- Should preserve partial results (completed shots)

**Related Files:**
- `addons/keyframe_generator.py`
- `addons/video_generator.py`
- `services/keyframe/keyframe_generation_service.py`
- `services/video/video_generation_service.py`

---

#### #002: Refresh-sicherer Start/Stop (Keyframe Generator)
**Status:** Open
**Priority:** High
**Impact:** Data Loss Risk
**Assigned Version:** v0.7.0

**Description:**
- UI state resets after browser refresh during generation
- Stop/Resume functionality experimental and may lose state
- Running jobs can be lost if user refreshes page

**Current Workaround:**
- Do not reload browser during generation
- Use Stop/Resume experimentally only
- Check terminal logs to verify job status

**Proposed Solution:**
- Persist generation state to `<project>/keyframes/_state.json`
- On page load, check for running jobs
- Show "Resume Generation" prompt if incomplete job detected
- Use StateStore pattern from Video Generator

**Technical Notes:**
- Video Generator already has this pattern (VideoGeneratorStateStore)
- Need to implement KeyframeGeneratorStateStore
- Should track:
  - Current shot being processed
  - Completed shots
  - Pending shots
  - Stop flag state

**Related Files:**
- `addons/keyframe_generator.py`
- `infrastructure/state_store.py` (add KeyframeGeneratorStateStore)

---

### Medium Priority

#### #003: Live Progress Updates
**Status:** Open
**Priority:** Medium
**Impact:** User Feedback
**Assigned Version:** v0.8.0

**Description:**
- Progress bar only updates at task completion
- No real-time percentage during image generation
- Users must check terminal for live updates

**Current Workaround:**
- Check terminal output for WebSocket progress logs
- Wait for task completion to see progress update

**Proposed Solution:**
- Use Gradio's `gr.Progress` with `tqdm` integration
- Update progress bar during ComfyUI WebSocket events
- Show sub-progress for multi-shot operations:
  - "Shot 3/10: Generating variant 2/3 (45%)"

**Technical Notes:**
- Gradio 4.x supports real-time progress via `gr.Progress()`
- Need to pass progress callback to service layer
- WebSocket monitor already emits progress events
- May require threading adjustments for UI updates

**Related Files:**
- `infrastructure/comfy_api/comfy_api_client.py` (monitor_progress)
- `services/keyframe/keyframe_generation_service.py`
- `services/video/video_generation_service.py`

---

#### #004: Shots >3s Extended (Video Padding)
**Status:** Open
**Priority:** Medium
**Impact:** Workflow Efficiency
**Assigned Version:** v0.7.0

**Description:**
- Videos padded to multiples of 3 seconds due to segmentation
- Example: 5s storyboard → 6s output (2 segments of 3s each)
- Results in longer videos than specified in storyboard

**Current Workaround:**
- Trim excess duration in post-production (Premiere, DaVinci Resolve)
- Plan storyboard durations in 3-second increments

**Proposed Solution:**
**Option A:** Precise trimming
- Use ffmpeg to trim last segment to exact duration
- Example: 5s shot → Segment 1 (3s) + Segment 2 (2s trimmed from 3s)

**Option B:** Variable segment size
- Allow final segment to be shorter than 3s
- Update Wan workflow to support 1-3s durations

**Option C:** Smart segmentation
- Calculate optimal segment sizes to minimize padding
- Example: 5s → 2.5s + 2.5s (requires 2.5s support in Wan)

**Technical Notes:**
- Current implementation uses fixed 3s segments (Wan limitation?)
- Need to verify Wan 2.2 min/max duration constraints
- ffmpeg trim command: `ffmpeg -i input.mp4 -t 2.0 -c copy output.mp4`

**Related Files:**
- `services/video/video_plan_builder.py` (split_into_segments)
- `services/video/video_generation_service.py`

---

### Low Priority

#### #005: Windows File Locking
**Status:** Open
**Priority:** Low
**Impact:** Race Conditions (Rare)
**Assigned Version:** v0.9.0

**Description:**
- No fcntl support on Windows
- File locking falls back to atomic file operations
- Potential race conditions in multi-process scenarios

**Current Workaround:**
- Atomic file writes using temp file + rename
- Rare occurrence in single-user scenarios

**Proposed Solution:**
- Implement Windows-specific locking using `msvcrt.locking()`
- Add cross-platform lock manager:
  ```python
  class FileLock:
      def __init__(self, path):
          self.path = path
          self.lock_file = None

      def __enter__(self):
          if sys.platform == 'win32':
              # Use msvcrt.locking
              pass
          else:
              # Use fcntl
              pass

      def __exit__(self, *args):
          # Release lock
          pass
  ```

**Technical Notes:**
- Current locking in `infrastructure/project_store.py`
- Only affects concurrent writes to project.json, settings.json
- Windows testing required

**Related Files:**
- `infrastructure/project_store.py`
- `infrastructure/config_manager.py`

---

#### #006: Resume Doesn't Preview
**Status:** Open
**Priority:** Low
**Impact:** Minor UX Issue
**Assigned Version:** v0.7.0

**Description:**
- Resume button works functionally
- No image preview of last generated keyframe on resume
- User doesn't see visual confirmation of where generation left off

**Current Workaround:**
- Check `<project>/keyframes/` directory manually
- Trust checkpoint data is correct

**Proposed Solution:**
- Load last generated image from checkpoint data
- Display in gallery with "▶️ Resume from here" indicator
- Show shot summary: "Last completed: Shot 003, Variant 2/3"

**Technical Notes:**
- Checkpoint already stores last processed shot info
- Need to load image file and display in Gradio gallery
- Simple enhancement, low effort

**Related Files:**
- `addons/keyframe_generator.py` (resume button handler)
- `services/keyframe/keyframe_service.py` (prepare_checkpoint)

---

## 🧹 Code Quality Issues

### #007: Large Addon Files
**Status:** Open
**Priority:** Medium
**Impact:** Maintainability
**Assigned Version:** v0.8.0

**Description:**
- After Sprint 2 refactoring:
  - `keyframe_generator.py`: 444 lines (down from 919)
  - `video_generator.py`: 373 lines (down from 960)
- Target: <300 lines per addon (UI-only logic)

**Current Status:**
- Already improved significantly (-52% and -61%)
- Remaining bloat mostly UI layout code

**Proposed Solution:**
- Extract UI component builders to separate helpers:
  - `addons/helpers/keyframe_ui_builder.py`
  - `addons/helpers/video_ui_builder.py`
- Move validation logic to validators in `domain/`
- Keep only event handlers and Gradio component wiring in addon

**Related Files:**
- `addons/keyframe_generator.py` (444 lines → target 250)
- `addons/video_generator.py` (373 lines → target 250)

---

### #008: Long Methods
**Status:** Open
**Priority:** Medium
**Impact:** Complexity
**Assigned Version:** v0.8.0

**Description:**
- Methods exceeding 50 lines (current threshold):
  - `KeyframeGenerationService._run_generation()` (~60 lines)
  - `VideoGenerationService.run_generation()` (~70 lines)
  - `VideoGeneratorAddon.render()` (~80 lines UI layout)

**Proposed Solution:**
- Split orchestration methods into sub-methods:
  - `_run_generation()` → `_setup_generation()`, `_process_shots()`, `_finalize_generation()`
- Extract UI sections into component builders
- Aim for max 40 lines per method

**Related Files:**
- `services/keyframe/keyframe_generation_service.py`
- `services/video/video_generation_service.py`
- `addons/video_generator.py`

---

### #009: Deep Nesting (>3 levels)
**Status:** Open
**Priority:** Medium
**Impact:** Readability
**Assigned Version:** v0.8.0

**Description:**
- Multiple locations with nesting depth >3
- Typical pattern:
  ```python
  for shot in shots:                    # Level 1
      for variant in range(variants):   # Level 2
          if condition:                 # Level 3
              try:                      # Level 4
                  # Logic here
  ```

**Proposed Solution:**
- Early returns to reduce nesting
- Extract inner loops to separate methods
- Use guard clauses
- Example refactor:
  ```python
  def process_shots(shots):
      for shot in shots:
          self._process_shot(shot)  # Extract to method

  def _process_shot(self, shot):
      if not self._is_valid(shot):
          return
      # Logic at reduced nesting level
  ```

**Related Files:**
- `services/keyframe/keyframe_generation_service.py`
- `services/video/video_generation_service.py`

---

### #010: Duplicated Workflow Update Logic
**Status:** Open
**Priority:** Medium
**Impact:** Maintainability
**Assigned Version:** v0.7.0

**Description:**
- Workflow parameter updates duplicated across services
- Each service manually calls node updaters
- No centralized workflow update orchestration

**Proposed Solution:**
- Create `WorkflowUpdateOrchestrator` in `infrastructure/comfy_api/`:
  ```python
  class WorkflowUpdateOrchestrator:
      def __init__(self, workflow):
          self.workflow = workflow
          self.updaters = [
              CLIPTextEncodeUpdater(),
              EmptyLatentImageUpdater(),
              HunyuanVideoSamplerUpdater(),
              # ...
          ]

      def apply_updates(self, params: dict):
          for updater in self.updaters:
              updater.update(self.workflow, params)
          return self.workflow
  ```

**Related Files:**
- `infrastructure/comfy_api/node_updaters/` (all updaters)
- `services/keyframe/keyframe_generation_service.py`
- `services/video/video_generation_service.py`

---

## 🏗️ Technical Debt - Architecture

### #011: Separate UI from Business Logic
**Status:** Partial
**Priority:** Medium
**Impact:** Architecture
**Assigned Version:** v0.8.0

**Description:**
- Sprint 2 extracted services, but addons still contain some business logic
- Examples:
  - File path construction in addons
  - Validation mixed with UI code
  - Status markdown generation in addons

**Current Progress:**
- ✅ Services extracted (Keyframe, Video, Selection)
- ✅ Domain models in place
- ⏳ Addons still have helper methods that could be services

**Proposed Solution:**
- Move all helper methods to services or domain
- Addons should only:
  - Define UI components
  - Wire event handlers
  - Call service methods
  - Display results
- Example: Move `_project_status_md()` to ProjectStore

**Related Files:**
- All addon files in `addons/`
- Extract to corresponding services in `services/`

---

### #012: Repository Pattern for Data Access
**Status:** Open
**Priority:** Medium
**Impact:** Architecture
**Assigned Version:** v0.9.0

**Description:**
- Direct file I/O scattered across services
- No abstraction layer for persistence
- Hard to mock in tests, hard to swap storage backend

**Proposed Solution:**
- Implement repository pattern:
  ```python
  class StoryboardRepository:
      def get(self, project, filename) -> Storyboard:
          pass

      def save(self, project, storyboard) -> None:
          pass

      def list(self, project) -> List[str]:
          pass

      def delete(self, project, filename) -> None:
          pass
  ```
- Repositories for:
  - Storyboards
  - Projects
  - Selections
  - Checkpoints

**Benefits:**
- Easier testing (mock repository)
- Potential future backends (database, S3, etc.)
- Centralized file I/O logic

**Related Files:**
- New: `infrastructure/repositories/` directory
- Refactor: All services to use repositories

---

### #013: Service Layer for All Addons
**Status:** Partial
**Priority:** Medium
**Impact:** Architecture
**Assigned Version:** v0.7.0

**Description:**
- Not all addons have corresponding services:
  - ✅ Keyframe Generator → KeyframeGenerationService
  - ✅ Video Generator → VideoGenerationService
  - ✅ Keyframe Selector → SelectionService
  - ❌ Project Panel → No ProjectService
  - ❌ Settings Panel → No SettingsService
  - ❌ Test ComfyUI → No TestService

**Proposed Solution:**
- Create missing services:
  - `ProjectService` - Project CRUD, validation, status calculation
  - `SettingsService` - Settings validation, persistence, migration
  - `TestService` - Connection testing, health checks, diagnostics

**Related Files:**
- New: `services/project_service.py`
- New: `services/settings_service.py`
- New: `services/test_service.py`
- Refactor: Corresponding addons to use services

---

### #014: Caching Layer for Configuration
**Status:** Open
**Priority:** Low
**Impact:** Performance
**Assigned Version:** v0.8.0

**Description:**
- Configuration files loaded on every access
- Workflow templates loaded repeatedly
- No invalidation strategy for file changes

**Proposed Solution:**
- Implement caching with TTL or file modification time check:
  ```python
  class CachedConfigManager:
      def __init__(self):
          self._cache = {}
          self._mtime = {}

      def get_config(self, key):
          if self._is_stale(key):
              self._reload(key)
          return self._cache[key]
  ```
- Use `functools.lru_cache` for workflow templates
- Cache invalidation on file write

**Related Files:**
- `infrastructure/config_manager.py`
- `infrastructure/workflow_registry.py`

---

## 🔧 Technical Debt - Infrastructure

### #015: Health Check Endpoint
**Status:** Open
**Priority:** Low
**Impact:** Operations
**Assigned Version:** v1.0.0

**Description:**
- No programmatic way to check if GUI is healthy
- Useful for:
  - Systemd service monitoring
  - Docker health checks
  - Load balancer probes

**Proposed Solution:**
- Add `/health` endpoint to Gradio app
- Check:
  - ComfyUI connection status
  - Active project existence
  - Disk space availability
  - Config file validity
- Return JSON:
  ```json
  {
    "status": "healthy",
    "checks": {
      "comfy_api": "ok",
      "active_project": "ok",
      "disk_space": "ok"
    },
    "timestamp": "2025-12-13T15:30:00Z"
  }
  ```

**Related Files:**
- `main.py` - Add health endpoint
- New: `infrastructure/health_check.py`

---

### #016: Metrics Collection (Prometheus)
**Status:** Open
**Priority:** Low
**Impact:** Operations
**Assigned Version:** v1.0.0

**Description:**
- No metrics for monitoring performance
- Useful metrics:
  - Generation time per shot
  - ComfyUI API latency
  - Error rates
  - Active users (if multi-user)

**Proposed Solution:**
- Use `prometheus_client` library
- Export metrics at `/metrics` endpoint
- Track:
  - `generation_duration_seconds` (histogram)
  - `comfy_api_requests_total` (counter)
  - `errors_total` (counter by type)

**Related Files:**
- `main.py` - Add metrics endpoint
- New: `infrastructure/metrics.py`
- All services - Add metrics instrumentation

---

### #017: Distributed Tracing (OpenTelemetry)
**Status:** Open
**Priority:** Low
**Impact:** Debugging
**Assigned Version:** v1.0.0

**Description:**
- No tracing for debugging long-running operations
- Difficult to diagnose where time is spent in pipeline

**Proposed Solution:**
- Integrate OpenTelemetry
- Trace spans for:
  - Full generation pipeline (storyboard → video)
  - Individual shot generation
  - ComfyUI API calls
  - File operations
- Export to Jaeger or Zipkin for visualization

**Related Files:**
- All services - Add tracing decorators
- New: `infrastructure/tracing.py`

---

### #018: Container Support (Docker)
**Status:** Open
**Priority:** Low
**Impact:** Deployment
**Assigned Version:** v1.0.0

**Description:**
- No Docker containerization
- Manual setup required (venv, dependencies, ComfyUI connection)

**Proposed Solution:**
- Create `Dockerfile`:
  - Base image: `python:3.11-slim`
  - Install dependencies from `requirements.txt`
  - Expose port 7860
  - Mount volumes for config, output, logs
- Docker Compose for GUI + ComfyUI together
- Document environment variables for configuration

**Related Files:**
- New: `Dockerfile`
- New: `docker-compose.yml`
- New: `docs/DOCKER.md`

---

## 📚 Technical Debt - Documentation

### #019: API Documentation (Sphinx)
**Status:** Open
**Priority:** Medium
**Impact:** Developer Experience
**Assigned Version:** v0.9.0

**Description:**
- No auto-generated API documentation
- Docstrings exist but not published
- Hard for contributors to understand internal APIs

**Proposed Solution:**
- Setup Sphinx with autodoc extension
- Generate HTML docs from docstrings
- Host on Read the Docs or GitHub Pages
- Document:
  - All services (public methods)
  - Infrastructure (ComfyAPI, ProjectStore, etc.)
  - Domain models
  - Addon base class

**Related Files:**
- New: `docs/conf.py` (Sphinx config)
- New: `docs/api/` (API reference RST files)
- Update: All modules with complete docstrings

---

### #020: Architecture Diagrams
**Status:** Open
**Priority:** Medium
**Impact:** Onboarding
**Assigned Version:** v0.9.0

**Description:**
- No visual architecture documentation
- Text descriptions only in README files

**Proposed Solution:**
- Create diagrams using Mermaid or draw.io:
  - System architecture (GUI → ComfyUI → Models)
  - Addon lifecycle (render → event → service → infrastructure)
  - Data flow (Storyboard → Keyframes → Selection → Video)
  - Service layer architecture
- Embed in documentation as images or live Mermaid

**Related Files:**
- New: `docs/diagrams/` directory
- Update: `docs/ARCHITECTURE.md` with diagrams

---

### #021: Migration Guides
**Status:** Open
**Priority:** Low
**Impact:** User Experience
**Assigned Version:** v1.0.0

**Description:**
- No migration guides for version upgrades
- Users may face breaking changes without guidance

**Proposed Solution:**
- Create migration guides for major versions:
  - v0.5.x → v0.6.x (new storyboard editor)
  - v0.6.x → v0.7.x (timeline format changes?)
  - Breaking changes highlighted
  - Step-by-step upgrade instructions
  - Config file migration scripts if needed

**Related Files:**
- New: `docs/migrations/` directory
- New: `docs/migrations/v0.5-to-v0.6.md`

---

### #022: Troubleshooting Flowcharts
**Status:** Open
**Priority:** Low
**Impact:** Support
**Assigned Version:** v1.0.0

**Description:**
- No structured troubleshooting guide
- Users struggle with common errors

**Proposed Solution:**
- Create flowcharts for common issues:
  - "ComfyUI Connection Failed" flowchart
  - "No Images Generated" flowchart
  - "Video Generation Stuck" flowchart
- Use Mermaid for interactive diagrams
- Include in main documentation

**Related Files:**
- New: `docs/TROUBLESHOOTING.md` with flowcharts

---

## 🔄 CI/CD Incomplete Items

### #023: Codecov Integration
**Status:** Open
**Priority:** Medium
**Impact:** Quality Visibility
**Assigned Version:** v0.7.0

**Description:**
- GitHub Actions uploads coverage to Codecov
- But Codecov account not configured
- No coverage badge in README

**Tasks:**
- [ ] Create Codecov account (free for open source)
- [ ] Connect GitHub repository to Codecov
- [ ] Add Codecov badge to README.md
- [ ] Set coverage thresholds in `.codecov.yml`:
  ```yaml
  coverage:
    status:
      project:
        default:
          target: 75%
          threshold: 2%
  ```

**Related Files:**
- New: `.codecov.yml`
- Update: `README.md` (add badge)

---

### #024: Pre-commit Hooks (Local)
**Status:** Open
**Priority:** Medium
**Impact:** Code Quality
**Assigned Version:** v0.7.0

**Description:**
- `.pre-commit-config.yaml` exists but not documented
- Developers may not install hooks locally
- Inconsistent code formatting

**Tasks:**
- [ ] Document hook installation in CONTRIBUTING.md:
  ```bash
  pip install pre-commit
  pre-commit install
  pre-commit run --all-files
  ```
- [ ] Test hooks on fresh clone
- [ ] Add pre-commit CI check (already in GitHub Actions)

**Related Files:**
- `.pre-commit-config.yaml` (already exists)
- New: `docs/CONTRIBUTING.md`

---

### #025: Branch Protection
**Status:** Open
**Priority:** Medium
**Impact:** Code Quality
**Assigned Version:** v0.7.0

**Description:**
- No branch protection rules on GitHub
- Direct pushes to `main` possible
- No required reviews or CI checks before merge

**Tasks:**
- [ ] Enable branch protection for `main`:
  - Require pull request reviews (1+ approvers)
  - Require status checks to pass (CI tests)
  - Require branches to be up-to-date
  - No force pushes
  - No deletions
- [ ] Document PR process in CONTRIBUTING.md

**Related Files:**
- GitHub repository settings (no files)
- New: `docs/CONTRIBUTING.md`

---

## 🔧 Refactoring Carryover from Sprint 2

### #026: SegmentManager Extraction (Optional)
**Status:** Deferred
**Priority:** Low
**Impact:** Code Organization
**Assigned Version:** v0.9.0

**Description:**
- Segment management logic in `VideoService`
- Could be extracted to separate class if more segment features needed
- Currently no urgent need (YAGNI principle)

**Proposed Solution:**
- Only extract if:
  - New segment features added (e.g., transitions, effects)
  - Segment logic grows >200 lines
  - Reused in multiple services

**Related Files:**
- `services/video/video_service.py` (current location)
- Potential: `services/video/segment_manager.py`

---

### #027: ComfyAPI Strategy Pattern Refinement
**Status:** Partial
**Priority:** Low
**Impact:** Extensibility
**Assigned Version:** v0.8.0

**Description:**
- NodeUpdater base class exists
- Specific updaters implemented (CLIP, KSampler, etc.)
- But no auto-discovery or registration system
- Updaters manually instantiated in services

**Proposed Solution:**
- Add updater registry:
  ```python
  class UpdaterRegistry:
      _updaters = {}

      @classmethod
      def register(cls, node_type):
          def decorator(updater_class):
              cls._updaters[node_type] = updater_class
              return updater_class
          return decorator

      @classmethod
      def get_updater(cls, node_type):
          return cls._updaters.get(node_type)
  ```
- Use decorator to register updaters:
  ```python
  @UpdaterRegistry.register("CLIPTextEncode")
  class CLIPTextEncodeUpdater(NodeUpdater):
      ...
  ```
- Auto-discover and apply all updaters

**Related Files:**
- `infrastructure/comfy_api/node_updaters/base.py`
- All updater classes

---

## 📊 Priority Summary

### Immediate Action Required (High Priority)
1. #001: Stop/Abort Button (v0.6.0)
2. #002: Refresh-sicherer Start/Stop (v0.7.0)

### Short-term (Medium Priority)
3. #003: Live Progress Updates (v0.8.0)
4. #004: Video Padding Issue (v0.7.0)
5. #007-#010: Code Quality Issues (v0.8.0)
6. #011-#013: Architecture Debt (v0.7.0-v0.9.0)
7. #019-#020: Documentation (v0.9.0)
8. #023-#025: CI/CD Completion (v0.7.0)

### Long-term (Low Priority)
9. #005: Windows File Locking (v0.9.0)
10. #006: Resume Preview (v0.7.0)
11. #014-#018: Infrastructure Improvements (v0.8.0-v1.0.0)
12. #021-#022: Additional Documentation (v1.0.0)
13. #026-#027: Refactoring Polish (v0.8.0-v0.9.0)

---

## 🔗 Cross-References

### Issues by Version Assignment

**v0.6.0:**
- #001: Stop/Abort Button

**v0.7.0:**
- #002: Refresh-sicherer Start/Stop
- #004: Video Padding
- #006: Resume Preview
- #010: Duplicated Workflow Logic
- #013: Service Layer Completion
- #023: Codecov Integration
- #024: Pre-commit Hooks
- #025: Branch Protection

**v0.8.0:**
- #003: Live Progress Updates
- #007: Large Addon Files
- #008: Long Methods
- #009: Deep Nesting
- #011: UI/Business Logic Separation
- #014: Caching Layer
- #027: ComfyAPI Strategy Refinement

**v0.9.0:**
- #005: Windows File Locking
- #012: Repository Pattern
- #019: API Documentation
- #020: Architecture Diagrams
- #026: SegmentManager Extraction

**v1.0.0:**
- #015: Health Check Endpoint
- #016: Metrics Collection
- #017: Distributed Tracing
- #018: Container Support
- #021: Migration Guides
- #022: Troubleshooting Flowcharts

---

## 📝 Notes

### Issue Lifecycle

**States:**
- **Open** - Identified but not started
- **Partial** - Some work done, needs completion
- **Deferred** - Explicitly postponed to future version
- **Closed** - Resolved and verified

### Adding New Issues

When adding issues to this backlog:
1. Assign unique ID (#XXX)
2. Set priority (High/Medium/Low)
3. Assign target version
4. Describe current workaround if available
5. Propose concrete solution
6. List affected files
7. Update summary tables

### Reviewing Backlog

Review schedule:
- **Weekly:** Check high-priority issues
- **After each sprint:** Update statuses
- **Before version planning:** Assign issues to versions

---

## 🔗 Related Documents

- **[ROADMAP.md](ROADMAP.md)** - Feature planning and version roadmap
- **[../BACKLOG.md](../BACKLOG.md)** - Main project backlog (sprint planning)
- **[../STATUS.md](../STATUS.md)** - Current project status
- **[../TESTING.md](../TESTING.md)** - Test coverage and strategy
- **[../CHANGELOG.md](../CHANGELOG.md)** - Version history

---

**Last Review:** December 13, 2025
**Next Review:** After v0.6.0 Release
**Maintained By:** Architecture Team
