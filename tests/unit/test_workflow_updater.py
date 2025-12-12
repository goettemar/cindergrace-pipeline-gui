import copy

from infrastructure.comfy_api.workflow_updater import WorkflowUpdater
from infrastructure.comfy_api.updaters import default_updaters


def test_updates_prompt_seed_and_resolution(sample_flux_workflow):
    workflow = copy.deepcopy(sample_flux_workflow)
    updater = WorkflowUpdater(default_updaters())

    updated = updater.update(
        workflow,
        prompt="updated prompt",
        seed=1234,
        width=1920,
        height=1080,
    )

    assert updated["1"]["inputs"]["text"] == "updated prompt"
    assert updated["4"]["inputs"]["seed"] == 1234
    assert updated["3"]["inputs"]["width"] == 1920
    assert updated["3"]["inputs"]["height"] == 1080
    # Original untouched
    assert sample_flux_workflow["1"]["inputs"]["text"] == "test prompt"


def test_updates_startframe_and_num_frames(sample_wan_workflow):
    workflow = copy.deepcopy(sample_wan_workflow)
    updater = WorkflowUpdater(default_updaters())

    updated = updater.update(
        workflow,
        startframe_path="/tmp/start.png",
        num_frames=120,
        seed=9999,
    )

    assert updated["1"]["inputs"]["image"] == "/tmp/start.png"
    assert updated["3"]["inputs"]["num_frames"] == 120
    assert updated["3"]["inputs"]["seed"] == 9999


def test_generic_seed_applies_to_unknown_nodes():
    workflow = {
        "42": {"class_type": "CustomNode", "inputs": {"seed": 1}},
    }
    updater = WorkflowUpdater(default_updaters())

    updated = updater.update(workflow, seed=777)

    assert updated["42"]["inputs"]["seed"] == 777
