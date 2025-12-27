"""Tests for model_manager services."""
import os
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from services.model_manager.model_classifier import ModelClassifier, ModelStatus
from services.model_manager.archive_manager import ArchiveManager


class TestModelStatus:
    """Tests for ModelStatus enum."""

    def test_status_values(self):
        """Test status enum values."""
        assert ModelStatus.USED == "used"
        assert ModelStatus.UNUSED == "unused"
        assert ModelStatus.MISSING == "missing"


class TestModelClassifier:
    """Tests for ModelClassifier class."""

    @pytest.fixture
    def mock_workflow_scanner(self):
        """Create mock WorkflowScanner."""
        scanner = Mock()
        scanner.get_all_referenced_models.return_value = {
            "checkpoints": {"model_a.safetensors", "model_b.safetensors"},
            "loras": {"lora_1.safetensors"},
        }
        scanner.get_workflows_using_model.return_value = ["workflow1.json"]
        return scanner

    @pytest.fixture
    def mock_model_scanner(self):
        """Create mock ModelScanner."""
        scanner = Mock()
        scanner.scan_all_models.return_value = {
            "checkpoints": [
                {"filename": "model_a.safetensors", "size_bytes": 5000000000, "size_formatted": "5.0 GB", "path": "/models/checkpoints/model_a.safetensors"},
                {"filename": "model_c.safetensors", "size_bytes": 3000000000, "size_formatted": "3.0 GB", "path": "/models/checkpoints/model_c.safetensors"},
            ],
            "loras": [
                {"filename": "lora_1.safetensors", "size_bytes": 200000000, "size_formatted": "200 MB", "path": "/models/loras/lora_1.safetensors"},
                {"filename": "lora_2.safetensors", "size_bytes": 150000000, "size_formatted": "150 MB", "path": "/models/loras/lora_2.safetensors"},
            ],
        }
        return scanner

    @pytest.fixture
    def classifier(self, mock_workflow_scanner, mock_model_scanner):
        """Create ModelClassifier instance."""
        return ModelClassifier(mock_workflow_scanner, mock_model_scanner)

    # ========================================================================
    # Classification Tests
    # ========================================================================

    def test_classify_all_models_structure(self, classifier):
        """Test that classification returns correct structure."""
        result = classifier.classify_all_models()

        assert ModelStatus.USED in result
        assert ModelStatus.UNUSED in result
        assert ModelStatus.MISSING in result

    def test_classify_used_models(self, classifier):
        """Test classification of used models."""
        result = classifier.classify_all_models()

        used = result[ModelStatus.USED]
        used_filenames = [m["filename"] for m in used]

        # model_a and lora_1 are referenced AND exist
        assert "model_a.safetensors" in used_filenames
        assert "lora_1.safetensors" in used_filenames

    def test_classify_unused_models(self, classifier):
        """Test classification of unused models."""
        result = classifier.classify_all_models()

        unused = result[ModelStatus.UNUSED]
        unused_filenames = [m["filename"] for m in unused]

        # model_c and lora_2 exist but are not referenced
        assert "model_c.safetensors" in unused_filenames
        assert "lora_2.safetensors" in unused_filenames

    def test_classify_missing_models(self, classifier):
        """Test classification of missing models."""
        result = classifier.classify_all_models()

        missing = result[ModelStatus.MISSING]
        missing_filenames = [m["filename"] for m in missing]

        # model_b is referenced but doesn't exist
        assert "model_b.safetensors" in missing_filenames

    def test_classified_model_has_required_fields(self, classifier):
        """Test that classified models have all required fields."""
        result = classifier.classify_all_models()

        required_fields = ["status", "type", "filename", "size_bytes", "size", "workflows", "workflow_count"]

        for status in result:
            for model in result[status]:
                for field in required_fields:
                    assert field in model, f"Missing field: {field}"

    def test_used_model_has_path(self, classifier):
        """Test that used models have path."""
        result = classifier.classify_all_models()

        for model in result[ModelStatus.USED]:
            assert model["path"] is not None

    def test_missing_model_has_no_path(self, classifier):
        """Test that missing models have no path."""
        result = classifier.classify_all_models()

        for model in result[ModelStatus.MISSING]:
            assert model["path"] is None
            assert model["size"] == "N/A"

    # ========================================================================
    # Statistics Tests
    # ========================================================================

    def test_get_statistics_structure(self, classifier):
        """Test statistics structure."""
        stats = classifier.get_statistics()

        assert "total_used" in stats
        assert "total_unused" in stats
        assert "total_missing" in stats
        assert "used_size_bytes" in stats
        assert "unused_size_bytes" in stats
        assert "potential_savings" in stats
        assert "by_type" in stats

    def test_get_statistics_counts(self, classifier):
        """Test statistics counts are correct."""
        stats = classifier.get_statistics()

        assert stats["total_used"] == 2  # model_a, lora_1
        assert stats["total_unused"] == 2  # model_c, lora_2
        assert stats["total_missing"] == 1  # model_b

    def test_get_statistics_by_type(self, classifier):
        """Test statistics by type."""
        stats = classifier.get_statistics()

        assert "checkpoints" in stats["by_type"]["used"]
        assert "loras" in stats["by_type"]["unused"]

    # ========================================================================
    # Filter Tests
    # ========================================================================

    def test_get_models_by_status(self, classifier):
        """Test filtering by status."""
        unused = classifier.get_models_by_status(ModelStatus.UNUSED)

        assert len(unused) == 2
        for model in unused:
            assert model["status"] == ModelStatus.UNUSED

    def test_get_models_by_type_and_status(self, classifier):
        """Test filtering by type and status."""
        unused_loras = classifier.get_models_by_type_and_status("loras", ModelStatus.UNUSED)

        assert len(unused_loras) == 1
        assert unused_loras[0]["filename"] == "lora_2.safetensors"


class TestArchiveManager:
    """Tests for ArchiveManager class."""

    @pytest.fixture
    def archive_dir(self, tmp_path):
        """Create archive directory."""
        archive = tmp_path / "archive"
        archive.mkdir()
        return archive

    @pytest.fixture
    def models_dir(self, tmp_path):
        """Create models directory with test files."""
        models = tmp_path / "models"
        models.mkdir()

        # Create test model files
        (models / "checkpoints").mkdir()
        (models / "loras").mkdir()

        (models / "checkpoints" / "model_a.safetensors").write_bytes(b"x" * 1000)
        (models / "loras" / "lora_1.safetensors").write_bytes(b"y" * 500)

        return models

    @pytest.fixture
    def manager(self, archive_dir, models_dir):
        """Create ArchiveManager instance."""
        return ArchiveManager(str(archive_dir), str(models_dir))

    # ========================================================================
    # Move to Archive Tests
    # ========================================================================

    def test_move_to_archive_success(self, manager, models_dir, archive_dir):
        """Test successful move to archive."""
        model_path = models_dir / "checkpoints" / "model_a.safetensors"

        success, message = manager.move_to_archive(str(model_path), "checkpoints")

        assert success is True
        assert not model_path.exists()
        assert (archive_dir / "checkpoints" / "model_a.safetensors").exists()

    def test_move_to_archive_source_not_found(self, manager):
        """Test move with non-existent source."""
        success, message = manager.move_to_archive("/nonexistent/file.safetensors", "checkpoints")

        assert success is False
        assert "not found" in message

    def test_move_to_archive_already_exists(self, manager, models_dir, archive_dir):
        """Test move when file already in archive."""
        model_path = models_dir / "checkpoints" / "model_a.safetensors"

        # Create existing archive file
        (archive_dir / "checkpoints").mkdir()
        (archive_dir / "checkpoints" / "model_a.safetensors").write_bytes(b"existing")

        success, message = manager.move_to_archive(str(model_path), "checkpoints")

        assert success is False
        assert "already exists" in message

    def test_move_to_archive_dry_run(self, manager, models_dir):
        """Test dry run doesn't actually move files."""
        model_path = models_dir / "checkpoints" / "model_a.safetensors"

        success, message = manager.move_to_archive(str(model_path), "checkpoints", dry_run=True)

        assert success is True
        assert "Would move" in message
        assert model_path.exists()  # File still exists

    def test_move_to_archive_creates_directory(self, manager, models_dir, archive_dir):
        """Test that archive directory is created."""
        model_path = models_dir / "checkpoints" / "model_a.safetensors"

        # Archive type dir doesn't exist yet
        assert not (archive_dir / "checkpoints").exists()

        manager.move_to_archive(str(model_path), "checkpoints")

        assert (archive_dir / "checkpoints").exists()

    # ========================================================================
    # Restore from Archive Tests
    # ========================================================================

    def test_restore_from_archive_success(self, manager, models_dir, archive_dir):
        """Test successful restore from archive."""
        # Setup: Put file in archive, remove from models
        (archive_dir / "loras").mkdir()
        (archive_dir / "loras" / "archived_lora.safetensors").write_bytes(b"archived")

        success, message = manager.restore_from_archive("archived_lora.safetensors", "loras")

        assert success is True
        assert (models_dir / "loras" / "archived_lora.safetensors").exists()
        # Original stays in archive (copied, not moved)
        assert (archive_dir / "loras" / "archived_lora.safetensors").exists()

    def test_restore_from_archive_not_found(self, manager):
        """Test restore when file not in archive."""
        success, message = manager.restore_from_archive("nonexistent.safetensors", "checkpoints")

        assert success is False
        assert "not found" in message

    def test_restore_from_archive_already_exists(self, manager, models_dir, archive_dir):
        """Test restore when file already exists in models."""
        # Setup: File exists in both
        (archive_dir / "loras").mkdir()
        (archive_dir / "loras" / "lora_1.safetensors").write_bytes(b"archived")
        # lora_1.safetensors already exists in models

        success, message = manager.restore_from_archive("lora_1.safetensors", "loras")

        assert success is False
        assert "already exists" in message

    def test_restore_from_archive_dry_run(self, manager, archive_dir, models_dir):
        """Test dry run doesn't actually restore files."""
        (archive_dir / "checkpoints").mkdir()
        (archive_dir / "checkpoints" / "model_x.safetensors").write_bytes(b"data")

        success, message = manager.restore_from_archive("model_x.safetensors", "checkpoints", dry_run=True)

        assert success is True
        assert "Would restore" in message
        assert not (models_dir / "checkpoints" / "model_x.safetensors").exists()

    def test_restore_handles_windows_paths(self, manager, archive_dir, models_dir):
        """Test that Windows-style paths are handled."""
        (archive_dir / "checkpoints").mkdir()
        (archive_dir / "checkpoints" / "model.safetensors").write_bytes(b"data")

        success, _ = manager.restore_from_archive("subdir\\model.safetensors", "checkpoints")

        # Should extract just filename
        assert success is True

    # ========================================================================
    # Check Archive Tests
    # ========================================================================

    def test_check_if_in_archive_exists(self, manager, archive_dir):
        """Test check when file is in archive."""
        (archive_dir / "loras").mkdir()
        (archive_dir / "loras" / "test_lora.safetensors").write_bytes(b"data")

        result = manager.check_if_in_archive("test_lora.safetensors", "loras")

        assert result is True

    def test_check_if_in_archive_not_exists(self, manager):
        """Test check when file is not in archive."""
        result = manager.check_if_in_archive("nonexistent.safetensors", "loras")

        assert result is False

    def test_check_if_in_archive_flat_structure(self, manager, archive_dir):
        """Test check with flat archive structure."""
        # File directly in archive root, not in type subfolder
        (archive_dir / "model.safetensors").write_bytes(b"data")

        result = manager.check_if_in_archive("model.safetensors", "checkpoints")

        assert result is True

    # ========================================================================
    # Scan Archive Tests
    # ========================================================================

    def test_scan_archive_empty(self, manager):
        """Test scanning empty archive."""
        result = manager.scan_archive()

        assert result == {}

    def test_scan_archive_with_files(self, manager, archive_dir):
        """Test scanning archive with files."""
        (archive_dir / "checkpoints").mkdir()
        (archive_dir / "loras").mkdir()
        (archive_dir / "checkpoints" / "model.safetensors").write_bytes(b"data")
        (archive_dir / "loras" / "lora_a.safetensors").write_bytes(b"data")
        (archive_dir / "loras" / "lora_b.safetensors").write_bytes(b"data")

        result = manager.scan_archive()

        assert "checkpoints" in result
        assert "loras" in result
        assert len(result["checkpoints"]) == 1
        assert len(result["loras"]) == 2

    def test_scan_archive_sorted(self, manager, archive_dir):
        """Test that scan results are sorted."""
        (archive_dir / "loras").mkdir()
        (archive_dir / "loras" / "z_lora.safetensors").write_bytes(b"data")
        (archive_dir / "loras" / "a_lora.safetensors").write_bytes(b"data")

        result = manager.scan_archive()

        assert result["loras"] == ["a_lora.safetensors", "z_lora.safetensors"]

    # ========================================================================
    # Batch Operations Tests
    # ========================================================================

    def test_batch_move_to_archive(self, manager, models_dir):
        """Test batch move operation."""
        models = [
            {"path": str(models_dir / "checkpoints" / "model_a.safetensors"), "type": "checkpoints"},
            {"path": str(models_dir / "loras" / "lora_1.safetensors"), "type": "loras"},
        ]

        result = manager.batch_move_to_archive(models)

        assert len(result["success"]) == 2
        assert len(result["failed"]) == 0

    def test_batch_move_partial_failure(self, manager, models_dir):
        """Test batch move with some failures."""
        models = [
            {"path": str(models_dir / "checkpoints" / "model_a.safetensors"), "type": "checkpoints"},
            {"path": "/nonexistent/model.safetensors", "type": "checkpoints"},
        ]

        result = manager.batch_move_to_archive(models)

        assert len(result["success"]) == 1
        assert len(result["failed"]) == 1

    def test_batch_restore_from_archive(self, manager, archive_dir, models_dir):
        """Test batch restore operation."""
        (archive_dir / "checkpoints").mkdir()
        (archive_dir / "checkpoints" / "model_x.safetensors").write_bytes(b"data")
        (archive_dir / "checkpoints" / "model_y.safetensors").write_bytes(b"data")

        models = [
            {"filename": "model_x.safetensors", "type": "checkpoints"},
            {"filename": "model_y.safetensors", "type": "checkpoints"},
        ]

        result = manager.batch_restore_from_archive(models)

        assert len(result["success"]) == 2

    # ========================================================================
    # Archive Size Tests
    # ========================================================================

    def test_get_archive_size_empty(self, manager):
        """Test size of empty archive."""
        size = manager.get_archive_size()

        assert size == 0

    def test_get_archive_size_with_files(self, manager, archive_dir):
        """Test size calculation with files."""
        (archive_dir / "checkpoints").mkdir()
        (archive_dir / "checkpoints" / "model.safetensors").write_bytes(b"x" * 1000)
        (archive_dir / "checkpoints" / "model2.safetensors").write_bytes(b"y" * 500)

        size = manager.get_archive_size()

        assert size == 1500

    # ========================================================================
    # Delete from Archive Tests
    # ========================================================================

    def test_delete_from_archive_without_confirm(self, manager):
        """Test delete requires confirmation."""
        models = [{"filename": "model.safetensors", "type": "checkpoints"}]

        result = manager.delete_from_archive(models, confirm=False)

        assert len(result["success"]) == 0
        assert "not confirmed" in result["failed"][0]

    def test_delete_from_archive_success(self, manager, archive_dir):
        """Test successful delete from archive."""
        (archive_dir / "checkpoints").mkdir()
        (archive_dir / "checkpoints" / "model.safetensors").write_bytes(b"data")

        models = [{"filename": "model.safetensors", "type": "checkpoints"}]

        result = manager.delete_from_archive(models, confirm=True)

        assert len(result["success"]) == 1
        assert not (archive_dir / "checkpoints" / "model.safetensors").exists()

    def test_delete_from_archive_not_found(self, manager):
        """Test delete when file not in archive."""
        models = [{"filename": "nonexistent.safetensors", "type": "checkpoints"}]

        result = manager.delete_from_archive(models, confirm=True)

        assert len(result["failed"]) == 1
        assert "not found" in result["failed"][0]

    # ========================================================================
    # Operation Log Tests
    # ========================================================================

    def test_get_operation_log_empty(self, manager):
        """Test getting log when no operations logged."""
        log = manager.get_operation_log()

        assert log == []

    def test_operation_logging(self, manager, models_dir):
        """Test that operations are logged."""
        model_path = models_dir / "checkpoints" / "model_a.safetensors"
        manager.move_to_archive(str(model_path), "checkpoints")

        # Trigger an operation that logs
        manager.create_archive_index()

        log = manager.get_operation_log()
        assert len(log) >= 1
        assert "action" in log[0]
        assert "timestamp" in log[0]

    # ========================================================================
    # Archive Index Tests
    # ========================================================================

    def test_create_archive_index(self, manager, archive_dir):
        """Test creating archive index."""
        (archive_dir / "checkpoints").mkdir()
        (archive_dir / "checkpoints" / "model.safetensors").write_bytes(b"data")

        index_path = manager.create_archive_index()

        assert Path(index_path).exists()
        with open(index_path) as f:
            index = json.load(f)
        assert "checkpoints" in index
        assert len(index["checkpoints"]) == 1

    def test_create_archive_index_includes_metadata(self, manager, archive_dir):
        """Test that index includes file metadata."""
        (archive_dir / "loras").mkdir()
        (archive_dir / "loras" / "lora.safetensors").write_bytes(b"data")

        index_path = manager.create_archive_index()

        with open(index_path) as f:
            index = json.load(f)

        file_info = index["loras"][0]
        assert "filename" in file_info
        assert "size_bytes" in file_info
        assert "modified" in file_info

    # ========================================================================
    # Archive All Unused Tests
    # ========================================================================

    def test_archive_all_unused_by_type(self, manager, models_dir):
        """Test archiving all unused models of a type."""
        unused_models = [
            {"path": str(models_dir / "checkpoints" / "model_a.safetensors"), "type": "checkpoints"},
        ]

        result = manager.archive_all_unused_by_type("checkpoints", unused_models)

        assert len(result["success"]) == 1

    def test_archive_all_unused_with_callback(self, manager, models_dir):
        """Test archive with progress callback."""
        callback_calls = []

        def callback(current, total, filename):
            callback_calls.append((current, total, filename))

        unused_models = [
            {"path": str(models_dir / "checkpoints" / "model_a.safetensors"), "type": "checkpoints"},
        ]

        manager.archive_all_unused_by_type("checkpoints", unused_models, progress_callback=callback)

        assert len(callback_calls) == 1

    # ========================================================================
    # Restore All Missing Tests
    # ========================================================================

    def test_restore_all_missing(self, manager, archive_dir, models_dir):
        """Test restoring all missing models."""
        (archive_dir / "checkpoints").mkdir()
        (archive_dir / "checkpoints" / "missing_model.safetensors").write_bytes(b"data")

        missing_models = [
            {"filename": "missing_model.safetensors", "type": "checkpoints"}
        ]

        result = manager.restore_all_missing(missing_models)

        assert len(result["success"]) == 1
        assert (models_dir / "checkpoints" / "missing_model.safetensors").exists()
