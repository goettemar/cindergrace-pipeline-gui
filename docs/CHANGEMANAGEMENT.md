# Change Management - CINDERGRACE

**Last Updated:** December 13, 2025
**Version:** v0.5.1
**Purpose:** Central registry for all Change Requests (CRs)

---

## 📋 Change Request Overview

| CR-ID | Title | Type | Priority | Status | Assigned To | Target Version | Created | Completed |
|-------|-------|------|----------|--------|-------------|----------------|---------|-----------|
| CR-001 | Example: Add CFG Scale to Keyframe Generator | Enhancement | Medium | Proposed | - | v0.6.0 | 2025-12-13 | - |

**Status Legend:**
- 🟦 **Proposed** - Awaiting review and approval
- 🟨 **Approved** - Approved, awaiting implementation
- 🟧 **In Progress** - Currently being implemented
- 🟩 **Completed** - Implementation complete and verified
- 🟥 **Rejected** - Not approved for implementation
- ⏸️ **On Hold** - Temporarily paused

**Type Legend:**
- **Feature** - New functionality
- **Enhancement** - Improvement to existing functionality
- **Bugfix** - Fix for a bug
- **Refactoring** - Code quality improvement
- **Documentation** - Documentation changes only

**Priority Legend:**
- **Critical** - Blocker, must be fixed immediately
- **High** - Important, should be addressed soon
- **Medium** - Normal priority
- **Low** - Nice to have

---

## 🔍 Quick Filters

### By Status
- **Proposed:** CR-001
- **In Progress:** None
- **Completed:** None
- **Rejected:** None

### By Priority
- **Critical:** None
- **High:** None
- **Medium:** CR-001
- **Low:** None

### By Version
- **v0.6.0:** CR-001
- **v0.7.0:** None
- **v0.8.0:** None

### By Type
- **Feature:** None
- **Enhancement:** CR-001
- **Bugfix:** None
- **Refactoring:** None

---

## 📝 Change Request Details

### CR-001: Example - Add CFG Scale to Keyframe Generator

**Status:** 🟦 Proposed
**Type:** Enhancement
**Priority:** Medium
**Created:** 2025-12-13
**Target Version:** v0.6.0

**Summary:**
Add CFG (Classifier Free Guidance) scale control to Keyframe Generator to allow fine-tuning of image generation quality.

**Affected Components:**
- Keyframe Generator Addon
- KeyframeService
- ComfyAPI KSampler Updater

**Required Reading:**
- `docs/addons/KEYFRAME_GENERATOR.md`
- `docs/services/KEYFRAME_SERVICE.md`
- `docs/README.md` - ComfyAPI section

**Estimated Effort:** Small (1-2 days)

**Implementation Notes:**
- Add slider UI component (1.0-20.0, default 7.0)
- Update workflow params to include cfg_scale
- Pass to KSamplerUpdater
- Add validation

**Testing Requirements:**
- Unit tests for validation
- Integration test with ComfyUI
- Manual testing with different CFG values

**Dependencies:** None

**Detailed CR Document:** `docs/changemanagement/CR-001-cfg-scale.md` (to be created using CHANGE_TEMPLATE.md)

**Status History:**
- 2025-12-13: Created (Proposed)

---

## 📊 Statistics

### Overall
- **Total CRs:** 1
- **Active CRs:** 1 (Proposed: 1, In Progress: 0)
- **Completed CRs:** 0
- **Rejected CRs:** 0

### By Version
- **v0.6.0:** 1 CR
- **v0.7.0:** 0 CRs
- **v0.8.0:** 0 CRs
- **Backlog:** 0 CRs

### By Type
- **Feature:** 0
- **Enhancement:** 1
- **Bugfix:** 0
- **Refactoring:** 0
- **Documentation:** 0

---

## 🔄 Change Request Workflow

### 1. Proposal
1. Create entry in this CHANGEMANAGEMENT.md
2. Assign CR-ID (next available number)
3. Fill in basic metadata (Title, Type, Priority, Summary)
4. Set Status to 🟦 Proposed

### 2. Review & Approval
1. Review proposal (architecture, feasibility, impact)
2. Estimate effort and assign version
3. Decision:
   - **Approve** → Status: 🟨 Approved
   - **Reject** → Status: 🟥 Rejected (add reason)
   - **Hold** → Status: ⏸️ On Hold (add reason)

### 3. Implementation
1. Create detailed CR document using `templates/CHANGE_TEMPLATE.md`
2. Save as `docs/changes/CR-XXX-short-name.md`
3. Link in this document
4. Set Status to 🟧 In Progress
5. Assign to developer/AI
6. Implement following the detailed CR document
7. Update documentation as needed
8. Write/update tests

### 4. Completion
1. All acceptance criteria met
2. Tests passing (maintain ≥75% coverage)
3. Documentation updated
4. Code reviewed (if applicable)
5. Set Status to 🟩 Completed
6. Update Completed date
7. Update CHANGELOG.md

### 5. Rejection
1. Document rejection reason
2. Set Status to 🟥 Rejected
3. Archive or remove from active tracking

---

## 📁 Directory Structure

```
docs/
├── CHANGEMANAGEMENT.md           # ← You are here (CR registry)
├── templates/
│   └── CHANGE_TEMPLATE.md        # Template for detailed CR docs
└── changemanagement/              # Detailed CR documents
    ├── README.md                 # Directory guide
    ├── CR-001-cfg-scale.md       # (to be created when approved)
    ├── CR-002-*.md
    └── archive/                  # Completed/rejected CRs (optional)
        └── vX.X.X/
```

**Note:** Directory `docs/changemanagement/` is ready for CR documents.

---

## 🎯 Active Change Requests (Detailed)

### 🟦 Proposed (1)

#### CR-001: Add CFG Scale to Keyframe Generator
- **Priority:** Medium
- **Effort:** Small (1-2 days)
- **Target:** v0.6.0
- **Blocking:** None
- **Blocked By:** None

---

### 🟨 Approved (0)

No approved CRs pending implementation.

---

### 🟧 In Progress (0)

No CRs currently in progress.

---

### ⏸️ On Hold (0)

No CRs currently on hold.

---

## 📅 Version Planning

### v0.6.0 - Storyboard Editor & Enhancements
**Target Date:** Q1 2026
**Planned CRs:** 1
- CR-001: Add CFG Scale to Keyframe Generator (Proposed)

**From ROADMAP.md:**
- Storyboard Editor implementation
- Auto-Sync Project State
- Status Badges
- Quick Navigation

---

### v0.7.0 - Timeline Toolkit
**Target Date:** Q1 2026
**Planned CRs:** 0

**From ROADMAP.md:**
- Timeline Export
- Enhanced Wan Motion Control
- Resume/Checkpoint improvements

---

### v0.8.0 - Performance & UX
**Target Date:** Q2 2026
**Planned CRs:** 0

**From ROADMAP.md:**
- Parallel File Operations
- Workflow Caching
- Live Progress Updates

---

## 🔗 Related Documentation

- **ROADMAP.md** - Feature planning and version roadmap
- **BACKLOG.md** - Known issues and technical debt (27 issues)
- **templates/CHANGE_TEMPLATE.md** - Template for detailed CR documents
- **CHANGELOG.md** - Version history (completed changes)

---

## 📝 How to Use This Document

### For Planning
1. Review ROADMAP.md and BACKLOG.md
2. Identify changes needed
3. Create CR entry in this document
4. Discuss and prioritize
5. Approve and assign to version

### For Implementation
1. Find CR in this document
2. Read "Required Reading" docs
3. Create detailed CR doc using CHANGE_TEMPLATE.md
4. Implement following the detailed CR
5. Update CR status as you progress

### For Tracking
1. Check "Active Change Requests" section
2. Review statistics for progress
3. Update status as CRs progress
4. Archive completed CRs (move to CHANGELOG.md)

---

## 🎨 CR ID Numbering

**Format:** CR-XXX (zero-padded to 3 digits)

**Current Range:**
- CR-001 to CR-099: General changes
- CR-100 to CR-199: Reserved for critical bugfixes
- CR-200 to CR-299: Reserved for major features
- CR-300 to CR-399: Reserved for refactoring

**Next Available ID:** CR-002

---

## 📋 CR Template (Quick Add)

```markdown
### CR-XXX: [Title]

**Status:** 🟦 Proposed
**Type:** [Feature|Enhancement|Bugfix|Refactoring|Documentation]
**Priority:** [Critical|High|Medium|Low]
**Created:** YYYY-MM-DD
**Target Version:** vX.X.X

**Summary:**
[One paragraph summary]

**Affected Components:**
- [Component 1]
- [Component 2]

**Required Reading:**
- `docs/[relevant-doc].md`

**Estimated Effort:** [Small|Medium|Large] ([days])

**Implementation Notes:**
- [Key point 1]
- [Key point 2]

**Testing Requirements:**
- [Test 1]
- [Test 2]

**Dependencies:** [CR-IDs or "None"]

**Detailed CR Document:** `docs/changemanagement/CR-XXX-short-name.md` (to be created)

**Status History:**
- YYYY-MM-DD: Created (Proposed)
```

---

## 🔄 Maintenance

### Weekly
- Review Proposed CRs → Approve or Reject
- Update In Progress CRs status
- Check for blocked CRs

### Sprint End
- Move Completed CRs to CHANGELOG.md
- Update statistics
- Plan next sprint CRs

### Version Release
- Archive all Completed CRs for that version
- Review Rejected CRs (reconsider?)
- Plan next version CRs

---

**Maintained By:** Architecture Team & Development Team
**Review Frequency:** Weekly
**Last Review:** December 13, 2025
**Next Review:** December 20, 2025
