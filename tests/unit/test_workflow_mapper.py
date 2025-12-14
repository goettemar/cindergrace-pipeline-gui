from services.model_manager.workflow_mapper import WorkflowMapper


class DummyScanner:
    def __init__(self, mapping):
        self.mapping = mapping

    def scan_all_workflows(self, use_cache=True):
        return self.mapping


def test_workflow_mapper_usage_details():
    mapping = {
        "workflow1.json": [{"filename": "a.safetensors", "type": "checkpoints", "node_id": "1", "node_type": "CheckpointLoader"}],
        "workflow2.json": [{"filename": "a.safetensors", "type": "checkpoints", "node_id": "2", "node_type": "CheckpointLoader"}],
    }
    mapper = WorkflowMapper(DummyScanner(mapping))

    details = mapper.get_model_usage_details("a.safetensors")
    assert len(details) == 2

    most_used = mapper.get_most_used_models(n=1)
    assert most_used[0]["workflow_count"] == 2

    least_used = mapper.get_least_used_models()
    assert not least_used  # same model used twice

    complexity = mapper.get_workflow_complexity()
    assert complexity["workflow1.json"] == 1
