from __future__ import annotations

import copy
from typing import Any, Dict, Iterable, List, Optional

from infrastructure.comfy_api.base import NodeUpdater
from infrastructure.comfy_api.updaters import default_updaters


class WorkflowUpdater:
    """Orchestrates workflow parameter updates using pluggable node updaters."""

    def __init__(self, updaters: Optional[Iterable[NodeUpdater]] = None):
        self.updaters: List[NodeUpdater] = list(updaters) if updaters else list(default_updaters())

    def update(self, workflow: Dict[str, Any], **params: Any) -> Dict[str, Any]:
        """Return a deep-copied workflow with injected parameters."""
        workflow_copy = copy.deepcopy(workflow)
        if not isinstance(workflow_copy, dict):
            return workflow_copy

        for node_id, node_data in workflow_copy.items():
            if not isinstance(node_data, dict):
                continue

            node_type = node_data.get("class_type", "")
            inputs = node_data.get("inputs", {})
            if not isinstance(inputs, dict):
                node_data["inputs"] = {}

            for updater in self.updaters:
                if updater.applies_to(node_type):
                    updater.update(node_data, params)

            # Persist inputs back in case an updater replaced them
            node_data["inputs"] = node_data.get("inputs", inputs)

        return workflow_copy
