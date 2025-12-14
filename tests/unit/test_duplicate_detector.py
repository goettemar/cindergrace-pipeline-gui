import os

from services.model_manager.duplicate_detector import DuplicateDetector
from services.model_manager.model_classifier import ModelStatus


def test_duplicate_detector_find_duplicates(tmp_path):
    file_a = tmp_path / "model_a.safetensors"
    file_b = tmp_path / "model_b.safetensors"
    file_c = tmp_path / "model_c.safetensors"

    file_a.write_bytes(b"same-content")
    file_b.write_bytes(b"same-content")
    file_c.write_bytes(b"different")

    models_by_type = {
        "checkpoints": [
            {"path": str(file_a), "filename": file_a.name, "size_bytes": file_a.stat().st_size, "status": ModelStatus.USED},
            {"path": str(file_b), "filename": file_b.name, "size_bytes": file_b.stat().st_size, "status": ModelStatus.UNUSED},
            {"path": str(file_c), "filename": file_c.name, "size_bytes": file_c.stat().st_size, "status": ModelStatus.UNUSED},
        ]
    }

    detector = DuplicateDetector(use_partial_hash=False)
    duplicates = detector.find_duplicates(models_by_type, use_partial_hash=False)

    assert len(duplicates) == 1
    group = duplicates[0]
    assert group["suggested_keep"]["filename"] == file_a.name
    assert {f["filename"] for f in group["files"]} == {file_a.name, file_b.name}
