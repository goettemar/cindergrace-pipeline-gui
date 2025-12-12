# CINDERGRACE Test Suite

This directory contains the test suite for CINDERGRACE Pipeline GUI.

## Quick Start

```bash
# Install test dependencies
pip install -r requirements-dev.txt

# Run all tests
pytest

# Run with coverage
pytest --cov
```

## Structure

```
tests/
├── conftest.py              # Shared fixtures and pytest configuration
├── unit/                    # Unit tests (fast, isolated)
│   ├── test_storyboard_service.py
│   ├── test_config_manager.py
│   └── ...
├── integration/             # Integration tests (slower, mock HTTP)
│   ├── test_comfy_api.py
│   └── ...
└── fixtures/                # Test data files
    ├── storyboards/         # Sample storyboard JSON files
    └── workflows/           # Sample workflow JSON files
```

## Test Categories

### Unit Tests (`tests/unit/`)

- **Purpose:** Test individual functions/classes in isolation
- **Speed:** Fast (<1ms per test)
- **Dependencies:** None (use mocks and fixtures)
- **Marker:** `@pytest.mark.unit`

**Example:**
```python
@pytest.mark.unit
def test_load_storyboard(sample_storyboard_file):
    storyboard = StoryboardService.load_from_file(str(sample_storyboard_file))
    assert storyboard.project == "Test Project"
```

### Integration Tests (`tests/integration/`)

- **Purpose:** Test interaction between components
- **Speed:** Slower (10-100ms per test)
- **Dependencies:** Mocked HTTP/WebSocket
- **Marker:** `@pytest.mark.integration`

**Example:**
```python
@pytest.mark.integration
@responses.activate
def test_comfy_api(sample_flux_workflow):
    responses.add(responses.POST, "http://127.0.0.1:8188/prompt", ...)
    api = ComfyUIAPI("http://127.0.0.1:8188")
    result = api.queue_prompt(sample_flux_workflow)
    assert result is not None
```

## Available Fixtures

See `conftest.py` for complete list. Common fixtures:

- `sample_storyboard_file` - Valid storyboard JSON file
- `sample_storyboard_data` - Storyboard as Python dict
- `sample_selection_file` - Selection JSON file
- `sample_flux_workflow` - Flux workflow dict
- `sample_wan_workflow` - Wan workflow dict
- `mock_comfy_api` - Mocked ComfyUI API
- `mock_config_manager` - Mocked ConfigManager
- `temp_project_dir` - Temporary project directory
- `tmp_path` - pytest built-in temp directory

## Running Specific Tests

```bash
# Run only unit tests
pytest tests/unit -m unit

# Run only integration tests
pytest tests/integration -m integration

# Run specific file
pytest tests/unit/test_storyboard_service.py

# Run specific test
pytest tests/unit/test_storyboard_service.py::test_load_valid_storyboard

# Run tests matching pattern
pytest -k "storyboard"
```

## Coverage Reports

```bash
# Terminal report
pytest --cov --cov-report=term-missing

# HTML report (opens in browser)
pytest --cov --cov-report=html
open htmlcov/index.html

# XML report (for CI/CD)
pytest --cov --cov-report=xml
```

## Coverage Goals

| Module         | Target Coverage |
|----------------|-----------------|
| domain/        | 90%+            |
| infrastructure/| 70%+            |
| services/      | 80%+            |
| addons/        | 60%+            |

**Overall:** 75%+ coverage

## Writing New Tests

1. **Choose category:** Unit or Integration
2. **Create test file:** `test_<module_name>.py`
3. **Use fixtures:** Leverage existing fixtures from `conftest.py`
4. **Follow pattern:** Arrange-Act-Assert
5. **Add marker:** `@pytest.mark.unit` or `@pytest.mark.integration`

**Template:**

```python
import pytest
from module import function_to_test

class TestFunctionName:
    @pytest.mark.unit
    def test_success_case(self, fixture_name):
        """Should do X when Y"""
        # Arrange
        setup_data = ...

        # Act
        result = function_to_test(setup_data)

        # Assert
        assert result == expected_value

    @pytest.mark.unit
    def test_error_case(self):
        """Should raise Error when invalid input"""
        with pytest.raises(ExpectedError):
            function_to_test(invalid_input)
```

## CI/CD

Tests run automatically on:
- Push to `main` or `develop`
- Pull requests to `main` or `develop`

**Pipeline:**
1. Test on Python 3.10, 3.11, 3.12
2. Run unit tests with coverage
3. Run integration tests
4. Upload coverage to Codecov

## More Information

- **Full Testing Guide:** See `TESTING.md`
- **Contributing:** See `CONTRIBUTING.md`
- **Project Docs:** See `README.md`

Happy testing! 🧪
