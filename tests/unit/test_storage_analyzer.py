from services.model_manager.storage_analyzer import StorageAnalyzer
from services.model_manager.model_classifier import ModelStatus


class DummyClassifier:
    def __init__(self, data):
        self.data = data

    def classify_all_models(self):
        return self.data


def build_model(status, mtype, size):
    return {"status": status, "type": mtype, "size_bytes": size, "filename": f"{mtype}-{size}"}


def test_storage_overview_and_largest():
    data = {
        ModelStatus.USED: [build_model(ModelStatus.USED, "checkpoints", 10), build_model(ModelStatus.USED, "loras", 5)],
        ModelStatus.UNUSED: [build_model(ModelStatus.UNUSED, "checkpoints", 2)],
        ModelStatus.MISSING: [build_model(ModelStatus.MISSING, "loras", 0)],
    }
    analyzer = StorageAnalyzer(DummyClassifier(data))

    overview = analyzer.get_storage_overview()
    assert overview["counts"]["used"] == 2
    assert overview["totals"]["unused"] == 2

    largest = analyzer.get_largest_models(n=1)
    assert largest[0]["size_bytes"] == 10

    distribution = analyzer.get_size_distribution()
    assert "buckets" in distribution
