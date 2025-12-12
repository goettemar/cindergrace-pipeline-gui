"""Unit tests for VideoGeneratorStateStore"""
import pytest
import os
import json
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

from infrastructure.state_store import VideoGeneratorStateStore


class TestVideoGeneratorStateStoreInit:
    """Test VideoGeneratorStateStore initialization"""

    @pytest.mark.unit
    def test_init_without_path(self):
        """Should initialize with None state_path"""
        # Act
        store = VideoGeneratorStateStore()

        # Assert
        assert store.state_path is None

    @pytest.mark.unit
    def test_init_with_path(self):
        """Should initialize with provided state_path"""
        # Act
        store = VideoGeneratorStateStore(state_path="/tmp/state.json")

        # Assert
        assert store.state_path == "/tmp/state.json"


class TestVideoGeneratorStateStoreConfigure:
    """Test VideoGeneratorStateStore.configure()"""

    @pytest.mark.unit
    def test_configure_updates_path(self):
        """Should update state_path"""
        # Arrange
        store = VideoGeneratorStateStore()
        assert store.state_path is None

        # Act
        store.configure("/new/path/state.json")

        # Assert
        assert store.state_path == "/new/path/state.json"

    @pytest.mark.unit
    def test_configure_can_set_to_none(self):
        """Should allow setting state_path to None"""
        # Arrange
        store = VideoGeneratorStateStore(state_path="/tmp/state.json")

        # Act
        store.configure(None)

        # Assert
        assert store.state_path is None


class TestVideoGeneratorStateStoreLoad:
    """Test VideoGeneratorStateStore.load()"""

    @pytest.mark.unit
    def test_load_existing_file(self, tmp_path):
        """Should load state from existing file"""
        # Arrange
        state_file = tmp_path / "state.json"
        state_data = {
            "selected_file": "test.mp4",
            "plan_id": "001A",
            "status": "completed"
        }

        with open(state_file, "w") as f:
            json.dump(state_data, f)

        store = VideoGeneratorStateStore(state_path=str(state_file))

        # Act
        result = store.load()

        # Assert
        assert result == state_data
        assert result["selected_file"] == "test.mp4"
        assert result["plan_id"] == "001A"

    @pytest.mark.unit
    def test_load_file_not_exists(self, tmp_path):
        """Should return empty dict when file doesn't exist"""
        # Arrange
        state_file = tmp_path / "nonexistent.json"
        store = VideoGeneratorStateStore(state_path=str(state_file))

        # Act
        result = store.load()

        # Assert
        assert result == {}

    @pytest.mark.unit
    def test_load_no_state_path(self):
        """Should return empty dict when state_path is None"""
        # Arrange
        store = VideoGeneratorStateStore()

        # Act
        result = store.load()

        # Assert
        assert result == {}

    @pytest.mark.unit
    def test_load_invalid_json(self, tmp_path, capsys):
        """Should return empty dict and print warning for invalid JSON"""
        # Arrange
        state_file = tmp_path / "invalid.json"
        with open(state_file, "w") as f:
            f.write("{ invalid json }")

        store = VideoGeneratorStateStore(state_path=str(state_file))

        # Act
        result = store.load()

        # Assert
        assert result == {}

        # Verify warning was printed
        captured = capsys.readouterr()
        assert "⚠️" in captured.out
        assert "Failed to load video generator state" in captured.out


class TestVideoGeneratorStateStoreSave:
    """Test VideoGeneratorStateStore.save()"""

    @pytest.mark.unit
    def test_save_valid_data(self, tmp_path):
        """Should save state data to file"""
        # Arrange
        state_file = tmp_path / "state.json"
        store = VideoGeneratorStateStore(state_path=str(state_file))

        data = {
            "selected_file": "test.mp4",
            "plan_id": "001A"
        }

        # Act
        store.save(data)

        # Assert
        assert state_file.exists()

        with open(state_file) as f:
            saved_data = json.load(f)

        assert saved_data == data

    @pytest.mark.unit
    def test_save_creates_directory(self, tmp_path):
        """Should create parent directory if it doesn't exist"""
        # Arrange
        state_file = tmp_path / "nested" / "dir" / "state.json"
        store = VideoGeneratorStateStore(state_path=str(state_file))

        data = {"key": "value"}

        # Act
        store.save(data)

        # Assert
        assert state_file.exists()

        with open(state_file) as f:
            saved_data = json.load(f)

        assert saved_data == data

    @pytest.mark.unit
    def test_save_no_state_path(self):
        """Should skip save when state_path is None"""
        # Arrange
        store = VideoGeneratorStateStore()

        data = {"key": "value"}

        # Act
        store.save(data)

        # Assert - Should not raise error, just skip

    @pytest.mark.unit
    @patch("builtins.open", side_effect=PermissionError("Permission denied"))
    def test_save_permission_error(self, mock_file, tmp_path, capsys):
        """Should print warning when save fails"""
        # Arrange
        state_file = tmp_path / "state.json"
        store = VideoGeneratorStateStore(state_path=str(state_file))

        data = {"key": "value"}

        # Act
        store.save(data)

        # Assert - Verify warning was printed
        captured = capsys.readouterr()
        assert "⚠️" in captured.out
        assert "Failed to save video generator state" in captured.out


class TestVideoGeneratorStateStoreUpdate:
    """Test VideoGeneratorStateStore.update()"""

    @pytest.mark.unit
    def test_update_existing_state(self, tmp_path):
        """Should update specific keys in existing state"""
        # Arrange
        state_file = tmp_path / "state.json"
        initial_data = {
            "selected_file": "old.mp4",
            "plan_id": "001A",
            "status": "pending"
        }

        with open(state_file, "w") as f:
            json.dump(initial_data, f)

        store = VideoGeneratorStateStore(state_path=str(state_file))

        # Act
        store.update(selected_file="new.mp4", status="completed")

        # Assert
        with open(state_file) as f:
            updated_data = json.load(f)

        assert updated_data["selected_file"] == "new.mp4"
        assert updated_data["status"] == "completed"
        assert updated_data["plan_id"] == "001A"  # Unchanged

    @pytest.mark.unit
    def test_update_creates_new_state(self, tmp_path):
        """Should create new state file when it doesn't exist"""
        # Arrange
        state_file = tmp_path / "state.json"
        store = VideoGeneratorStateStore(state_path=str(state_file))

        # Act
        store.update(selected_file="test.mp4", plan_id="001A")

        # Assert
        assert state_file.exists()

        with open(state_file) as f:
            data = json.load(f)

        assert data["selected_file"] == "test.mp4"
        assert data["plan_id"] == "001A"

    @pytest.mark.unit
    def test_update_no_state_path(self):
        """Should skip update when state_path is None"""
        # Arrange
        store = VideoGeneratorStateStore()

        # Act
        store.update(key="value")

        # Assert - Should not raise error, just skip

    @pytest.mark.unit
    def test_update_multiple_keys(self, tmp_path):
        """Should update multiple keys at once"""
        # Arrange
        state_file = tmp_path / "state.json"
        store = VideoGeneratorStateStore(state_path=str(state_file))

        # Act
        store.update(
            selected_file="test.mp4",
            plan_id="001A",
            status="completed",
            timestamp="2024-01-01"
        )

        # Assert
        with open(state_file) as f:
            data = json.load(f)

        assert len(data) == 4
        assert data["selected_file"] == "test.mp4"
        assert data["plan_id"] == "001A"
        assert data["status"] == "completed"
        assert data["timestamp"] == "2024-01-01"


class TestVideoGeneratorStateStoreClear:
    """Test VideoGeneratorStateStore.clear()"""

    @pytest.mark.unit
    def test_clear_existing_file(self, tmp_path):
        """Should remove existing state file"""
        # Arrange
        state_file = tmp_path / "state.json"
        with open(state_file, "w") as f:
            json.dump({"key": "value"}, f)

        assert state_file.exists()

        store = VideoGeneratorStateStore(state_path=str(state_file))

        # Act
        store.clear()

        # Assert
        assert not state_file.exists()

    @pytest.mark.unit
    def test_clear_file_not_exists(self, tmp_path):
        """Should not raise error when file doesn't exist"""
        # Arrange
        state_file = tmp_path / "nonexistent.json"
        store = VideoGeneratorStateStore(state_path=str(state_file))

        # Act
        store.clear()

        # Assert - Should not raise error

    @pytest.mark.unit
    def test_clear_no_state_path(self):
        """Should skip clear when state_path is None"""
        # Arrange
        store = VideoGeneratorStateStore()

        # Act
        store.clear()

        # Assert - Should not raise error

    @pytest.mark.unit
    @patch("os.remove", side_effect=PermissionError("Permission denied"))
    @patch("os.path.exists", return_value=True)
    def test_clear_permission_error(self, mock_exists, mock_remove, tmp_path, capsys):
        """Should print warning when clear fails"""
        # Arrange
        state_file = tmp_path / "state.json"
        store = VideoGeneratorStateStore(state_path=str(state_file))

        # Act
        store.clear()

        # Assert - Verify warning was printed
        captured = capsys.readouterr()
        assert "⚠️" in captured.out
        assert "Failed to clear video generator state" in captured.out


class TestVideoGeneratorStateStoreIntegration:
    """Integration tests for VideoGeneratorStateStore workflow"""

    @pytest.mark.unit
    def test_full_workflow_save_load_update_clear(self, tmp_path):
        """Should handle complete state lifecycle"""
        # Arrange
        state_file = tmp_path / "state.json"
        store = VideoGeneratorStateStore(state_path=str(state_file))

        # Act - Save initial state
        initial_data = {"selected_file": "video1.mp4", "status": "pending"}
        store.save(initial_data)

        # Act - Load state
        loaded = store.load()
        assert loaded == initial_data

        # Act - Update state
        store.update(status="completed", plan_id="001A")

        # Act - Load updated state
        updated = store.load()
        assert updated["status"] == "completed"
        assert updated["plan_id"] == "001A"
        assert updated["selected_file"] == "video1.mp4"

        # Act - Clear state
        store.clear()

        # Act - Load after clear
        final = store.load()
        assert final == {}

    @pytest.mark.unit
    def test_reconfiguration(self, tmp_path):
        """Should allow reconfiguration to different path"""
        # Arrange
        state_file_1 = tmp_path / "state1.json"
        state_file_2 = tmp_path / "state2.json"

        store = VideoGeneratorStateStore(state_path=str(state_file_1))

        # Act - Save to first path
        store.save({"file": "video1.mp4"})
        assert state_file_1.exists()

        # Act - Reconfigure to second path
        store.configure(str(state_file_2))

        # Act - Save to second path
        store.save({"file": "video2.mp4"})
        assert state_file_2.exists()

        # Assert - Both files exist with different content
        with open(state_file_1) as f:
            data1 = json.load(f)
        with open(state_file_2) as f:
            data2 = json.load(f)

        assert data1["file"] == "video1.mp4"
        assert data2["file"] == "video2.mp4"

    @pytest.mark.unit
    def test_concurrent_updates(self, tmp_path):
        """Should handle multiple sequential updates"""
        # Arrange
        state_file = tmp_path / "state.json"
        store = VideoGeneratorStateStore(state_path=str(state_file))

        # Act - Multiple updates
        store.update(key1="value1")
        store.update(key2="value2")
        store.update(key3="value3")
        store.update(key1="updated_value1")  # Overwrite key1

        # Assert
        final_state = store.load()
        assert final_state["key1"] == "updated_value1"
        assert final_state["key2"] == "value2"
        assert final_state["key3"] == "value3"
