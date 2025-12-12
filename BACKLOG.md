# CINDERGRACE Development Backlog

**Last Updated:** December 12, 2025  
**Current Version:** v0.5.1  
**Status:** Phase 3 Beta → Production Hardening

---

## 🎯 Sprint Priorities

### Sprint 2: Code Refactoring (Current) ⏳

**Goal:** Improve code quality and maintainability

#### High Priority
- [ ] **Refactor Video Generator** (976 lines → ~300 lines)
  - [ ] Extract `VideoGenerationService` orchestrator
  - [ ] Create `SegmentManager` for segmentation logic
  - [ ] Create `LastFrameExtractor` for ffmpeg operations
  - [ ] Create `VideoPlanBuilder` (move from addon)
  - **Files:** `addons/video_generator.py`, `services/video_service.py`
  - **Impact:** ⭐⭐⭐⭐⭐ Massive maintainability improvement

- [ ] **Refactor Keyframe Generator** (886 lines)
  - [ ] Break down `_run_generation()` (200+ lines)
  - [ ] Extract `_generate_shot()` method
  - [ ] Extract `_generate_variant()` method
  - [ ] Reduce nesting from 4 to 2 levels
  - **Files:** `addons/keyframe_generator.py`
  - **Impact:** ⭐⭐⭐⭐ Better readability and testability

#### Medium Priority
- [ ] **Refactor ComfyAPI** (Strategy Pattern)
  - [ ] Create `NodeUpdater` base class
  - [ ] Create updaters: `CLIPTextEncodeUpdater`, `SaveImageUpdater`, etc.
  - [ ] Implement `WorkflowUpdater` orchestrator
  - **Files:** `infrastructure/comfy_api.py`, new `infrastructure/comfy_api/` directory
  - **Impact:** ⭐⭐⭐⭐ Easier to extend with new node types

### Sprint 3: Test Coverage (Next) 📊

**Goal:** Reach 80%+ overall test coverage

#### Missing Tests
- [ ] **SelectionService Tests** (Priority: High)
  - [ ] `test_collect_keyframes()` - Variant collection
  - [ ] `test_export_selections()` - JSON + file export
  - [ ] `test_selection_validation()` - Error cases
  - **Target:** 80%+ coverage

- [ ] **VideoService Tests** (Priority: High)
  - [ ] `test_split_into_segments()` - Segmentation logic
  - [ ] `test_extract_last_frame()` - ffmpeg extraction
  - [ ] `test_segment_chaining()` - LastFrame workflow
  - **Target:** 80%+ coverage

- [ ] **ProjectStore Tests** (Priority: Medium)
  - [ ] `test_create_project()` - Project creation
  - [ ] `test_get_active_project()` - Project retrieval
  - [ ] `test_file_locking()` - Concurrent safety
  - **Target:** 70%+ coverage

- [ ] **WorkflowRegistry Tests** (Priority: Low)
  - [ ] `test_load_presets()` - Preset loading
  - [ ] `test_get_workflows_by_category()` - Filtering
  - **Target:** 70%+ coverage

#### Coverage Goals
| Module         | Current | Target | Priority |
|----------------|---------|--------|----------|
| StoryboardService | ✅ 90%+ | 90%+ | Done |
| ConfigManager    | ✅ 80%+ | 80%+ | Done |
| ComfyAPI         | ✅ 70%+ | 70%+ | Done |
| SelectionService | ❌ 0%   | 80%+ | High |
| VideoService     | ❌ 0%   | 80%+ | High |
| ProjectStore     | ❌ 0%   | 70%+ | Medium |
| WorkflowRegistry | ❌ 0%   | 70%+ | Low |
| **Overall**      | ~40%    | 75%+ | Goal |

### Sprint 4: CI/CD & DevOps 🔧

**Goal:** Automate quality assurance

- [ ] **Verify GitHub Actions**
  - [ ] Check first CI run status
  - [ ] Fix any failing tests
  - [ ] Verify Python 3.10, 3.11, 3.12 matrix
  - [ ] Check coverage upload to Codecov

- [ ] **Codecov Integration**
  - [ ] Create Codecov account
  - [ ] Connect repository
  - [ ] Add Codecov badge to README.md
  - [ ] Set coverage thresholds

- [ ] **Pre-commit Hooks (Local)**
  - [ ] Install: `pip install pre-commit && pre-commit install`
  - [ ] Test hooks: `pre-commit run --all-files`
  - [ ] Document in CONTRIBUTING.md

- [ ] **Branch Protection**
  - [ ] Enable for `main` branch
  - [ ] Require PR reviews
  - [ ] Require status checks to pass
  - [ ] Require up-to-date branches

---

## 🔮 Future Enhancements

### v0.6.0 - Timeline Toolkit

- [ ] Export `timeline.json` for video editing
- [ ] Wan motion fine-tuning (strength/easing from storyboard)
- [ ] Segment-level resume functionality
- [ ] Progress tracking improvements
- [ ] Enhanced error messages with model/node hints

### v0.7.0 - Performance Optimizations

- [ ] Parallel file copy with ThreadPoolExecutor
- [ ] Caching layer for workflow updates
- [ ] Batch operations for multi-shot generation
- [ ] Memory optimization for large storyboards

### v1.0.0 - Production Release

- [ ] Complete test suite (85%+ coverage)
- [ ] Performance benchmarks
- [ ] User documentation site
- [ ] Video tutorials
- [ ] Example projects gallery

---

## 🐛 Known Issues & Limitations

### High Priority
- [ ] **Stop/Abort Button** - No UI button to cancel running generation
  - Workaround: Ctrl+C in terminal
  - Impact: User experience

- [ ] **Live Progress Updates** - Progress only updates at task completion
  - Workaround: Check terminal for live updates
  - Impact: User feedback

### Medium Priority
- [ ] **Shots >3s Extended** - Videos padded to multiples of 3 seconds
  - Example: 5s storyboard → 6s output (2 segments)
  - Workaround: Trim in post-production
  - Impact: Workflow efficiency

- [ ] **Windows File Locking** - No fcntl support on Windows
  - Fallback: Atomic file operations
  - Impact: Race conditions possible (rare)

### Low Priority
- [ ] **Resume Doesn't Preview** - Resume button works but no image preview
  - Impact: Minor UX issue

---

## 📊 Code Quality Metrics

### Current Status
| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| Test Coverage | ~40% | 75%+ | ⏳ |
| Longest File | 976 lines | <500 lines | ⏳ |
| Max Nesting | 4 levels | 2 levels | ⏳ |
| Cyclomatic Complexity | High | Medium | ⏳ |
| Type Hints | 80%+ | 95%+ | ⏳ |
| Documentation | 90%+ | 95%+ | ✅ |

### Code Smells to Address
- [ ] Large classes (>500 lines): VideoGenerator, KeyframeGenerator
- [ ] Long methods (>50 lines): `_run_generation()`, `generate_videos()`
- [ ] Deep nesting (>3 levels): Multiple locations
- [ ] Duplicated logic: Workflow parameter updates

---

## 🎓 Technical Debt

### Architecture
- [ ] Separate UI logic from business logic in addons
- [ ] Introduce service layer for all addons
- [ ] Implement repository pattern for data access
- [ ] Add caching layer for configuration

### Infrastructure
- [ ] Add health check endpoint
- [ ] Implement metrics collection (Prometheus)
- [ ] Add distributed tracing (OpenTelemetry)
- [ ] Container support (Docker)

### Documentation
- [ ] Add API documentation (Sphinx)
- [ ] Create architecture diagrams
- [ ] Write migration guides
- [ ] Add troubleshooting flowcharts

---

## 🚀 Release Planning

### v0.5.2 (Hotfix) - Next Release
**Focus:** Bug fixes and small improvements
- Fix any critical bugs found
- Improve error messages
- Update documentation

### v0.6.0 (Feature) - Q1 2026
**Focus:** Timeline toolkit and motion control
- Timeline export
- Motion parameters from storyboard
- Enhanced video generation

### v0.7.0 (Feature) - Q2 2026
**Focus:** Performance and polish
- Parallel processing
- Caching improvements
- UI/UX enhancements

### v1.0.0 (Major) - Q3 2026
**Focus:** Production release
- Complete test coverage
- Full documentation
- Performance benchmarks
- Stability guarantees

---

## 📝 Notes

### Development Workflow
1. **Refactor** → Improve code structure (Sprint 2)
2. **Test** → Write comprehensive tests (Sprint 3)
3. **CI/CD** → Verify automation works (Sprint 4)
4. **Release** → Ship improvements

### Contributing
See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on:
- Code style
- Testing requirements
- PR process
- Development setup

### Resources
- **Testing Guide:** [TESTING.md](TESTING.md)
- **Architecture Docs:** [GUI_FRAMEWORK_README.md](../GUI_FRAMEWORK_README.md)
- **Pipeline Overview:** [CINDERGRACE_PIPELINE_README.md](../CINDERGRACE_PIPELINE_README.md)
- **Refactoring Plan:** [REFACTORING_PLAN.md](../REFACTORING_PLAN.md)

---

**Last Review:** December 12, 2025  
**Next Review:** After Sprint 2 completion  
**Status:** Active Development 🚀
