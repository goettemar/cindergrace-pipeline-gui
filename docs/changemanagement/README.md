# Change Management Documents

**Purpose:** This directory contains detailed Change Request (CR) documents for tracking and implementing changes to CINDERGRACE.

---

## 📁 Directory Structure

```
changemanagement/
├── README.md                  # ← You are here (directory guide)
├── CR-001-cfg-scale.md       # Example: CFG Scale enhancement
├── CR-002-progress-bar.md    # Example: Progress bar feature
├── CR-XXX-short-name.md      # Individual CR documents
└── archive/                   # Completed/rejected CRs (optional)
    └── v0.5.1/
        └── CR-XXX-*.md
```

---

## 📝 Document Naming Convention

**Format:** `CR-XXX-short-descriptive-name.md`

**Examples:**
- `CR-001-cfg-scale.md` - Add CFG Scale to Keyframe Generator
- `CR-002-progress-bar.md` - Add Real-Time Progress Bar
- `CR-015-wan-motion.md` - Enhanced Wan Motion Control
- `CR-101-fix-refresh-bug.md` - Fix Refresh Bug (100-199 for critical bugs)

**Rules:**
- Zero-padded ID (CR-001, not CR-1)
- Lowercase short name
- Hyphens for spaces
- Max 3-4 words in short name

---

## 🎯 When to Create a CR Document

**Always create for:**
- ✅ New features (any size)
- ✅ Enhancements to existing features
- ✅ Architectural changes
- ✅ Breaking changes
- ✅ Performance optimizations
- ✅ Refactoring > 500 lines

**Optional for:**
- ⚠️ Small bugfixes (<50 lines, no tests needed)
- ⚠️ Documentation-only changes
- ⚠️ Typo fixes

**Never needed for:**
- ❌ Updating CHANGELOG.md
- ❌ Updating version numbers
- ❌ Formatting changes (pre-commit fixes)

---

## 📋 Creating a New CR Document

### Step 1: Copy Template
```bash
cp ../templates/CHANGE_TEMPLATE.md changemanagement/CR-XXX-short-name.md
```

### Step 2: Fill Out Template
Replace all placeholders:
- `[Short Descriptive Title]` → Actual title
- `[Your Name / AI Assistant]` → Author
- `YYYY-MM-DD` → Current date
- All sections with actual content

### Step 3: Register in CHANGEMANAGEMENT.md
Add entry to `../CHANGEMANAGEMENT.md`:
```markdown
### CR-XXX: [Title]

**Status:** 🟦 Proposed
**Type:** Enhancement
...
**Detailed CR Document:** `docs/changemanagement/CR-XXX-short-name.md`
```

### Step 4: Link from Main Table
Update the main CR registry table in `../CHANGEMANAGEMENT.md`

---

## 📊 CR Document Lifecycle

### 1. Draft (Proposed)
- CR document created from template
- Basic information filled
- Status: 🟦 Proposed
- Location: `changemanagement/CR-XXX-*.md`

### 2. Under Review (Approved)
- CR reviewed and approved
- Implementation plan refined
- Status: 🟨 Approved
- Location: `changemanagement/CR-XXX-*.md`

### 3. In Implementation (In Progress)
- Work in progress
- Document updated with implementation notes
- Status: 🟧 In Progress
- Location: `changemanagement/CR-XXX-*.md`

### 4. Completed
- Implementation done, tested, documented
- CHANGELOG.md updated
- Status: 🟩 Completed
- Location: **Move to** `changemanagement/archive/vX.X.X/CR-XXX-*.md` (optional)

### 5. Rejected
- Not approved for implementation
- Rejection reason documented
- Status: 🟥 Rejected
- Location: **Move to** `changemanagement/archive/rejected/CR-XXX-*.md` (optional)

---

## 🔍 Finding a CR Document

### By CR-ID
```bash
# Direct file access
cat changemanagement/CR-015-wan-motion.md

# Search in active CRs
ls changemanagement/CR-*.md

# Search in archive
ls changemanagement/archive/*/CR-*.md
```

### By Topic
```bash
# Search by title/content
grep -r "Progress Bar" changemanagement/
grep -r "Wan Motion" changemanagement/
```

### By Status
Check `../CHANGEMANAGEMENT.md` for current status of all CRs

---

## 📂 Archive Strategy (Optional)

### When to Archive
- After version release, move completed CRs to archive
- Helps keep active directory clean
- Preserves history for reference

### Archive Structure
```
changemanagement/archive/
├── v0.5.1/
│   ├── CR-001-*.md
│   └── CR-002-*.md
├── v0.6.0/
│   └── CR-015-*.md
└── rejected/
    └── CR-099-*.md
```

### Archive Commands
```bash
# Archive completed CRs for v0.6.0
mkdir -p changemanagement/archive/v0.6.0
mv changemanagement/CR-015-*.md changemanagement/archive/v0.6.0/

# Archive rejected CR
mkdir -p changemanagement/archive/rejected
mv changemanagement/CR-099-*.md changemanagement/archive/rejected/
```

---

## ✅ Best Practices

### Document Quality
- ✅ Use CHANGE_TEMPLATE.md as base
- ✅ Fill all sections completely
- ✅ Include code examples where helpful
- ✅ Add sequence diagrams for complex flows
- ✅ Link to relevant documentation

### Version Control
- ✅ Commit CR documents to git
- ✅ Update CR when implementation changes
- ✅ Track status history in document
- ✅ Link commits to CR-ID in commit messages

### Collaboration
- ✅ CR-ID in all related commits: `git commit -m "CR-015: Add Wan motion parameters"`
- ✅ CR-ID in PR titles: `[CR-015] Add Wan motion parameters`
- ✅ Link CR in code comments: `// See CR-015 for implementation details`

---

## 📚 Related Documentation

- **../CHANGEMANAGEMENT.md** - Central CR registry and tracking
- **../templates/CHANGE_TEMPLATE.md** - Template for new CR documents
- **../ROADMAP.md** - Feature planning and version roadmap
- **../BACKLOG.md** - Known issues and technical debt
- **../CHANGELOG.md** - Completed changes per version

---

## 🎓 Example Workflow

### Creating CR-015 (Enhanced Wan Motion Control)

**1. Create CR document:**
```bash
cd /home/ubuntuadmin/projekte/comfy_ui_api/cindergrace_gui/docs
cp templates/CHANGE_TEMPLATE.md changemanagement/CR-015-wan-motion.md
```

**2. Edit CR-015-wan-motion.md:**
```markdown
# Change Request: Enhanced Wan Motion Control

**Date:** 2025-12-13
**Author:** Architecture Team
**Type:** Enhancement
**Priority:** High
**Status:** Proposed

## Summary
Implement reading wan_motion parameters from storyboard and applying them to HunyuanVideoSampler node.

## Affected Components
- Video Generator Addon
- VideoGenerationService
- HunyuanVideoSamplerUpdater
- Storyboard model

## Required Reading
- docs/addons/VIDEO_GENERATOR.md
- docs/services/VIDEO_SERVICE.md
- docs/README.md - ComfyAPI section
- ROADMAP.md - v0.7.0 Enhanced Wan Motion Control

## Implementation Plan
### Step 1: Extend HunyuanVideoSamplerUpdater
...
```

**3. Register in CHANGEMANAGEMENT.md:**
```markdown
### CR-015: Enhanced Wan Motion Control

**Status:** 🟦 Proposed
**Type:** Enhancement
**Priority:** High
**Created:** 2025-12-13
**Target Version:** v0.7.0

**Summary:**
Read wan_motion parameters from storyboard and apply to video generation

**Detailed CR Document:** `docs/changemanagement/CR-015-wan-motion.md`
```

**4. Implement:**
```bash
# Work on implementation
# Update CR-015-wan-motion.md with progress notes
# Commit with CR reference
git commit -m "CR-015: Add wan_motion parameter reading from storyboard"
```

**5. Complete:**
```bash
# Update status in CR-015-wan-motion.md
# Update CHANGEMANAGEMENT.md status to Completed
# Update CHANGELOG.md
# Archive (optional)
mv changemanagement/CR-015-wan-motion.md changemanagement/archive/v0.7.0/
```

---

**Directory Created:** December 13, 2025
**Maintained By:** Architecture Team & Development Team
