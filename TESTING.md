# Testing Guide for CINDERGRACE

This document explains how to run tests, write new tests, and understand the test infrastructure.

## Quick Start

```bash
# Install test dependencies
pip install -r requirements-dev.txt

# Run all tests
pytest

# Run with coverage
pytest --cov

# Run specific test category
pytest tests/unit -m unit
pytest tests/integration -m integration
```

---

## Test Structure

```
tests/
├── conftest.py                     # Shared fixtures and configuration
├── unit/                           # Unit tests (fast, isolated)
│   ├── test_storyboard_service.py  # 40+ tests
│   ├── test_config_manager.py      # 30+ tests
│   └── ...
├── integration/                    # Integration tests (slower)
│   ├── test_comfy_api.py           # API integration tests
│   └── ...
└── fixtures/                       # Test data
    ├── storyboards/
    │   └── test_storyboard.json
    └── workflows/
```

---

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest

# Verbose output
pytest -v

# Run specific file
pytest tests/unit/test_storyboard_service.py

# Run specific test
pytest tests/unit/test_storyboard_service.py::TestStoryboardServiceLoadFromFile::test_load_valid_storyboard

# Run tests matching pattern
pytest -k "storyboard"

# Stop on first failure
pytest -x

# Show local variables on failure
pytest -l
```

### Test Markers

Tests are marked for filtering:

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run only slow tests
pytest -m slow

# Exclude slow tests
pytest -m "not slow"

# Tests requiring ComfyUI
pytest -m requires_comfyui
```

### Coverage Reports

```bash
# Terminal coverage report
pytest --cov=addons --cov=services --cov=infrastructure --cov=domain

# Generate HTML coverage report
pytest --cov --cov-report=html
# Open: htmlcov/index.html

# Generate XML coverage (for CI/CD)
pytest --cov --cov-report=xml

# Show missing lines
pytest --cov --cov-report=term-missing
```

---

## Writing Tests

### Test Structure

Follow the **Arrange-Act-Assert** pattern:

```python
import pytest
from domain.storyboard_service import StoryboardService

class TestStoryboardService:
    @pytest.mark.unit
    def test_load_valid_storyboard(self, sample_storyboard_file):
        """Should load valid storyboard file successfully"""
        # Arrange - Setup test data
        # (done by fixture in this case)

        # Act - Execute the function
        storyboard = StoryboardService.load_from_file(str(sample_storyboard_file))

        # Assert - Verify results
        assert storyboard.project == "Test Project"
        assert len(storyboard.shots) == 3
```

### Using Fixtures

Fixtures are defined in `tests/conftest.py`:

```python
def test_example(sample_storyboard_file, tmp_path, mock_comfy_api):
    """Fixtures are automatically injected"""
    # sample_storyboard_file: Path to test storyboard
    # tmp_path: Temporary directory (auto-cleanup)
    # mock_comfy_api: Mocked ComfyUI API
    pass
```

**Available Fixtures:**

- `sample_storyboard_file` - Valid storyboard JSON
- `sample_storyboard_data` - Storyboard as dict
- `sample_selection_file` - Selection JSON
- `sample_flux_workflow` - Flux workflow dict
- `sample_wan_workflow` - Wan workflow dict
- `mock_comfy_api` - Mocked ComfyUI API
- `mock_config_manager` - Mocked ConfigManager
- `mock_project_store` - Mocked ProjectStore
- `temp_project_dir` - Temporary project directory
- `tmp_path` - pytest built-in temp directory

### Test Categories

#### Unit Tests (`tests/unit/`)

Fast, isolated tests for individual functions/classes:

```python
@pytest.mark.unit
def test_calculate_resolution():
    """Unit test - no external dependencies"""
    result = calculate_resolution(1920, 1080)
    assert result == (1920, 1080)
```

**Characteristics:**
- No file I/O (use fixtures)
- No network calls (use mocks)
- No external dependencies
- Fast (<1ms each)

#### Integration Tests (`tests/integration/`)

Test interaction between components:

```python
@pytest.mark.integration
@responses.activate  # Mock HTTP responses
def test_comfy_api_workflow(sample_flux_workflow):
    """Integration test - tests ComfyUI API interaction"""
    responses.add(
        responses.POST,
        "http://127.0.0.1:8188/prompt",
        json={"prompt_id": "test-123"},
        status=200
    )

    api = ComfyUIAPI("http://127.0.0.1:8188")
    prompt_id = api.queue_prompt(sample_flux_workflow)

    assert prompt_id == "test-123"
```

**Characteristics:**
- May use file I/O
- Use mocked HTTP/WebSocket
- Test component interaction
- Slower (10-100ms each)

### Mocking

#### HTTP Mocking (with `responses`)

```python
import responses

@responses.activate
def test_api_call():
    responses.add(
        responses.GET,
        "http://127.0.0.1:8188/system_stats",
        json={"status": "ok"},
        status=200
    )

    # Make actual HTTP request (will be intercepted)
    result = requests.get("http://127.0.0.1:8188/system_stats")
    assert result.json()["status"] == "ok"
```

#### Object Mocking (with `unittest.mock`)

```python
from unittest.mock import Mock, patch

def test_with_mock():
    mock_service = Mock()
    mock_service.load.return_value = "mocked data"

    result = mock_service.load("test.json")
    assert result == "mocked data"
    mock_service.load.assert_called_once_with("test.json")
```

#### Patching

```python
@patch('infrastructure.comfy_api.requests.post')
def test_with_patch(mock_post):
    mock_post.return_value.json.return_value = {"id": "123"}

    # Code that calls requests.post will use mock
    result = some_function_that_posts()
    assert result == "123"
```

---

## Test Data

### Creating Test Storyboards

```python
def test_with_custom_storyboard(tmp_path):
    # Create custom storyboard
    storyboard_data = {
        "project": "Custom Test",
        "shots": [
            {
                "shot_id": "001",
                "filename_base": "custom-shot",
                "prompt": "test prompt",
                "width": 1024,
                "height": 576,
                "duration": 3.0
            }
        ]
    }

    # Save to temporary file
    storyboard_file = tmp_path / "custom.json"
    with open(storyboard_file, "w") as f:
        json.dump(storyboard_data, f)

    # Test with it
    storyboard = load_storyboard(str(storyboard_file))
    assert storyboard.project == "Custom Test"
```

### Creating Test Images

```python
def test_with_test_image(tmp_path):
    from PIL import Image
    import numpy as np

    # Create test image
    img_array = np.random.randint(0, 255, (576, 1024, 3), dtype=np.uint8)
    img = Image.fromarray(img_array)

    # Save to temp file
    img_path = tmp_path / "test.png"
    img.save(img_path)

    # Use in test
    assert img_path.exists()
```

---

## Continuous Integration

Tests run automatically on GitHub Actions:

- **On push** to `main` or `develop`
- **On pull request** to `main` or `develop`

### CI Pipeline

1. **Test Matrix:** Python 3.10, 3.11, 3.12
2. **Unit Tests:** Run with coverage
3. **Integration Tests:** Run separately
4. **Code Quality:** Linting, type checking
5. **Coverage Upload:** To Codecov

### Viewing CI Results

- Check the **Actions** tab on GitHub
- Green checkmark = all tests passed
- Red X = tests failed (click for details)

---

## Coverage Goals

| Module         | Target | Current |
|----------------|--------|---------|
| domain/        | 90%+   | TBD     |
| infrastructure/| 70%+   | TBD     |
| services/      | 80%+   | TBD     |
| addons/        | 60%+   | TBD     |

**Overall target:** 75%+ coverage

---

## Common Issues

### Import Errors

```python
# Add project root to path
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
```

Or run from project root:
```bash
cd cindergrace_gui
pytest
```

### Fixture Not Found

Make sure fixture is defined in `conftest.py` or imported:

```python
# In test file
from conftest import my_custom_fixture
```

### Tests Fail Locally but Pass in CI

- Check Python version (`python --version`)
- Ensure dependencies are up to date (`pip install -r requirements-dev.txt`)
- Clear pytest cache (`pytest --cache-clear`)

### Slow Tests

Mark slow tests:

```python
@pytest.mark.slow
def test_heavy_operation():
    # Long-running test
    pass
```

Run fast tests only:
```bash
pytest -m "not slow"
```

---

## Best Practices

### Do's

✅ Write tests before fixing bugs (TDD)  
✅ Test edge cases (empty input, null, errors)  
✅ Use descriptive test names  
✅ Keep tests independent (no shared state)  
✅ Mock external dependencies  
✅ Use fixtures for reusable setup  

### Don'ts

❌ Don't test implementation details  
❌ Don't make tests depend on each other  
❌ Don't use sleep() (use mocks instead)  
❌ Don't commit commented-out tests  
❌ Don't skip tests without reason  

---

## Examples

### Testing Error Handling

```python
def test_handles_invalid_input():
    """Should raise ValidationError for invalid input"""
    with pytest.raises(ValidationError) as exc_info:
        load_storyboard("/invalid/path.json")

    assert "nicht gefunden" in str(exc_info.value)
```

### Parametrized Tests

```python
@pytest.mark.parametrize("preset,expected", [
    ("1080p_landscape", (1920, 1080)),
    ("720p_portrait", (720, 1280)),
])
def test_resolution_presets(preset, expected):
    """Test multiple resolution presets"""
    config = ConfigManager()
    config.set("global_resolution", preset)

    width, height = config.get_resolution_tuple()
    assert (width, height) == expected
```

### Testing with Files

```python
def test_file_operations(tmp_path):
    """Test file creation and reading"""
    # Create file
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")

    # Verify
    assert test_file.exists()
    assert test_file.read_text() == "test content"

    # File auto-deleted after test (tmp_path cleanup)
```

---

## Resources

- [pytest Documentation](https://docs.pytest.org/)
- [unittest.mock Guide](https://docs.python.org/3/library/unittest.mock.html)
- [responses Documentation](https://github.com/getsentry/responses)
- [Coverage.py Guide](https://coverage.readthedocs.io/)

---

## Getting Help

- Check `CONTRIBUTING.md` for general development guidelines
- See `conftest.py` for available fixtures
- Look at existing tests for examples
- Ask in GitHub Discussions

Happy testing! 🧪
