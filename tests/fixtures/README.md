# Test Fixtures

This directory contains test fixtures for the CINDERGRACE test suite.

## Structure

- `storyboards/` - Sample storyboard JSON files
- `workflows/` - Sample ComfyUI workflow JSON files

## Usage

These fixtures are automatically loaded by pytest through `conftest.py`.

Example:
```python
def test_storyboard_loading(sample_storyboard_file):
    storyboard = load_storyboard(sample_storyboard_file)
    assert storyboard.project == "Test Project"
```
