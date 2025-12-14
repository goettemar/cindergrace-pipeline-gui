import os
import time
from datetime import datetime, timedelta

from services.model_manager.model_filter import ModelFilter
from services.model_manager.model_classifier import ModelStatus


def test_model_filter_chain(tmp_path):
    file_recent = tmp_path / "recent.ckpt"
    file_old = tmp_path / "old.ckpt"
    file_recent.write_text("x")
    file_old.write_text("y")

    # make old file older
    old_time = time.time() - 86400 * 5
    os.utime(file_old, (old_time, old_time))

    models = [
        {"filename": "recent.ckpt", "size_bytes": 10, "path": str(file_recent), "workflow_count": 2, "status": ModelStatus.USED},
        {"filename": "old.ckpt", "size_bytes": 1, "path": str(file_old), "workflow_count": 0, "status": ModelStatus.UNUSED},
    ]

    cutoff = datetime.utcnow() - timedelta(days=1)
    filtered = (
        ModelFilter(models)
        .by_status(ModelStatus.UNUSED)
        .by_size_range(min_bytes=0, max_bytes=5)
        .by_workflow_count(max_count=0)
        .by_modified_date(before=cutoff)
        .apply()
    )
    assert len(filtered) == 1
    assert filtered[0]["filename"] == "old.ckpt"
