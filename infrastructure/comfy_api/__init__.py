"""Strategy-style workflow updaters for ComfyUIAPI."""

from infrastructure.comfy_api.client import ComfyUIAPI
from infrastructure.comfy_api.base import NodeUpdater
from infrastructure.comfy_api.workflow_updater import WorkflowUpdater
from infrastructure.comfy_api.updaters import (
    BasicSchedulerUpdater,
    CLIPTextEncodeUpdater,
    EmptyLatentImageUpdater,
    GenericSeedUpdater,
    HunyuanVideoSamplerUpdater,
    KSamplerUpdater,
    LoadImageUpdater,
    RandomNoiseUpdater,
    SaveImageUpdater,
    SaveVideoUpdater,
)

__all__ = [
    "ComfyUIAPI",
    "NodeUpdater",
    "WorkflowUpdater",
    "BasicSchedulerUpdater",
    "CLIPTextEncodeUpdater",
    "EmptyLatentImageUpdater",
    "GenericSeedUpdater",
    "HunyuanVideoSamplerUpdater",
    "KSamplerUpdater",
    "LoadImageUpdater",
    "RandomNoiseUpdater",
    "SaveImageUpdater",
    "SaveVideoUpdater",
]
