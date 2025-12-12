# Contributing to CINDERGRACE Pipeline GUI

Thank you for your interest in contributing to CINDERGRACE! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Code Style](#code-style)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Project Structure](#project-structure)
- [Communication](#communication)

---

## Getting Started

### Prerequisites

- **Python 3.10+** (3.11 recommended)
- **ComfyUI** installed and running
- **Git** for version control
- Basic knowledge of Gradio and ComfyUI

### Fork and Clone

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/cindergrace_gui.git
   cd cindergrace_gui
   ```

3. Add upstream remote:
   ```bash
   git remote add upstream https://github.com/ORIGINAL_OWNER/cindergrace_gui.git
   ```

---

## Development Setup

### 1. Create Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate  # Windows
```

### 2. Install Dependencies

```bash
# Production dependencies
pip install -r requirements.txt

# Development dependencies (testing, linting)
pip install -r requirements-dev.txt
```

### 3. Install Pre-commit Hooks

```bash
pre-commit install
```

This will automatically run code formatting and linting before each commit.

### 4. Start ComfyUI

```bash
cd /path/to/ComfyUI
python main.py --listen 127.0.0.1 --port 8188
```

### 5. Run the GUI

```bash
./start.sh  # Auto-setup + launch
# or
python main.py
```

---

## Code Style

We follow **PEP 8** with some modifications:

### General Guidelines

- **Line length:** 100 characters (not 79)
- **Indentation:** 4 spaces (no tabs)
- **Quotes:** Double quotes for strings
- **Imports:** Sorted with `isort` (black profile)

### Tools

We use automated tools to enforce style:

```bash
# Format code
black .

# Sort imports
isort .

# Check style
flake8 .

# Type checking
mypy addons/ services/ infrastructure/ domain/
```

### Naming Conventions

- **Classes:** `PascalCase` (e.g., `StoryboardService`)
- **Functions/Methods:** `snake_case` (e.g., `load_storyboard`)
- **Constants:** `UPPER_SNAKE_CASE` (e.g., `DEFAULT_FPS`)
- **Private methods:** `_leading_underscore` (e.g., `_internal_method`)

### Documentation

- **Docstrings:** Google style for all public functions/classes
- **Type hints:** Required for function signatures
- **Comments:** Only when necessary to explain "why", not "what"

Example:

```python
def load_storyboard(file_path: str) -> Storyboard:
    """Load and validate storyboard from JSON file.

    Args:
        file_path: Absolute path to storyboard JSON file

    Returns:
        Validated Storyboard domain model

    Raises:
        FileNotFoundError: If storyboard file doesn't exist
        ValidationError: If JSON is invalid or schema mismatch
    """
    # Implementation
```

---

## Testing

We aim for **80%+ test coverage** on core modules.

### Running Tests

```bash
# Run all tests
pytest

# Run only unit tests
pytest tests/unit -m unit

# Run only integration tests
pytest tests/integration -m integration

# Run with coverage report
pytest --cov=addons --cov=services --cov=infrastructure --cov=domain

# Run specific test file
pytest tests/unit/test_storyboard_service.py

# Run specific test function
pytest tests/unit/test_storyboard_service.py::test_load_valid_storyboard
```

### Writing Tests

- **Unit tests:** Test individual functions/classes in isolation
- **Integration tests:** Test interaction between components
- **Fixtures:** Use pytest fixtures from `tests/conftest.py`

Example test:

```python
import pytest
from domain.storyboard_service import StoryboardService

class TestStoryboardService:
    @pytest.mark.unit
    def test_load_valid_storyboard(self, sample_storyboard_file):
        """Should load valid storyboard file successfully"""
        # Arrange
        # (setup done by fixture)

        # Act
        storyboard = StoryboardService.load_from_file(str(sample_storyboard_file))

        # Assert
        assert storyboard.project == "Test Project"
        assert len(storyboard.shots) == 3
```

### Test Structure

```
tests/
├── conftest.py           # Shared fixtures
├── unit/                 # Unit tests (fast, no external dependencies)
│   ├── test_storyboard_service.py
│   ├── test_config_manager.py
│   └── ...
├── integration/          # Integration tests (may be slower)
│   ├── test_comfy_api.py
│   └── ...
└── fixtures/             # Test data files
    ├── storyboards/
    └── workflows/
```

---

## Submitting Changes

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/bug-description
```

Branch naming:
- `feature/` - New features
- `fix/` - Bug fixes
- `refactor/` - Code refactoring
- `docs/` - Documentation updates
- `test/` - Test additions/improvements

### 2. Make Changes

- Write clean, readable code
- Follow the style guide
- Add tests for new functionality
- Update documentation if needed

### 3. Commit Changes

```bash
git add .
git commit -m "feat: add keyframe caching feature"
```

**Commit message format:**

```
<type>: <short description>

<optional detailed description>

<optional footer>
```

**Types:**
- `feat:` - New feature
- `fix:` - Bug fix
- `refactor:` - Code refactoring
- `test:` - Adding tests
- `docs:` - Documentation changes
- `style:` - Code style changes (formatting)
- `perf:` - Performance improvements
- `chore:` - Maintenance tasks

**Examples:**

```
feat: add video segmentation for clips >3 seconds

Implements LastFrame chaining to extend video generation
beyond the 3-second limit by splitting into segments.

Closes #42
```

```
fix: resolve keyframe selector crash on missing files

The selector now handles missing keyframe files gracefully
and displays a warning instead of crashing.

Fixes #15
```

### 4. Run Tests

```bash
# Run all tests
pytest

# Check code style
black --check .
flake8 .
```

### 5. Push to Your Fork

```bash
git push origin feature/your-feature-name
```

### 6. Create Pull Request

1. Go to GitHub and create a Pull Request
2. Fill out the PR template:
   - **Description:** What does this PR do?
   - **Motivation:** Why is this change needed?
   - **Testing:** How was it tested?
   - **Screenshots:** (if UI changes)
3. Link related issues (e.g., "Closes #42")
4. Request review from maintainers

---

## Project Structure

Understanding the codebase:

```
cindergrace_gui/
├── addons/              # UI modules (tabs)
│   ├── project_panel.py
│   ├── keyframe_generator.py
│   ├── keyframe_selector.py
│   ├── video_generator.py
│   ├── test_comfy_flux.py
│   └── settings_panel.py
├── infrastructure/      # Core services
│   ├── comfy_api.py
│   ├── config_manager.py
│   ├── project_store.py
│   ├── logger.py
│   └── error_handler.py
├── domain/              # Domain logic
│   ├── models.py
│   ├── storyboard_service.py
│   ├── validators.py
│   └── exceptions.py
├── services/            # Business logic
│   ├── keyframe_service.py
│   ├── selection_service.py
│   └── video_service.py
├── tests/               # Test suite
│   ├── unit/
│   ├── integration/
│   └── fixtures/
└── config/              # Configuration files
```

### Key Concepts

- **Addons:** Self-contained UI modules that implement `BaseAddon`
- **Services:** Business logic separated from UI
- **Infrastructure:** Reusable components (API, logging, config)
- **Domain:** Core models and validation logic

---

## Communication

### Questions?

- **Issues:** Open an issue for bug reports or feature requests
- **Discussions:** Use GitHub Discussions for questions
- **Pull Requests:** Comment on PRs for code review discussions

### Getting Help

If you're stuck:

1. Check the documentation (`README.md`, `GUI_FRAMEWORK_README.md`)
2. Search existing issues
3. Ask in GitHub Discussions
4. Open a new issue with the `question` label

---

## Code Review Process

All submissions require review:

1. **Automated checks:** CI/CD pipeline runs tests and linting
2. **Manual review:** Maintainer reviews code quality and design
3. **Feedback:** Address review comments
4. **Approval:** Once approved, PR will be merged

**What reviewers look for:**

- Code quality and readability
- Test coverage
- Documentation
- No breaking changes
- Follows project conventions

---

## Development Tips

### Debugging

```python
# Use the logger
from infrastructure.logger import get_logger

logger = get_logger(__name__)
logger.debug("Debugging info")
logger.info("Normal operation")
logger.error("Error occurred", exc_info=True)
```

### Testing ComfyUI Connection

```bash
# Quick test
curl http://127.0.0.1:8188/system_stats

# Or use the GUI test tab
# Tab: 🧪 Test ComfyUI → Click "Test Connection"
```

### Hot Reload

Gradio supports hot reload during development:

```bash
python main.py --reload
```

---

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.

---

## Thank You!

Your contributions make CINDERGRACE better for everyone. We appreciate your time and effort!

For more information, see:
- [README.md](README.md) - Getting started guide
- [CHANGELOG.md](CHANGELOG.md) - Version history
- [GUI_FRAMEWORK_README.md](../GUI_FRAMEWORK_README.md) - Technical documentation
