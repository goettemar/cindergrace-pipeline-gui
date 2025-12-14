"""Workflow Mapper - Map model references to workflows and back."""
from __future__ import annotations

from collections import defaultdict, Counter
from typing import Dict, List, Optional

from infrastructure.logger import get_logger
from services.model_manager.workflow_scanner import WorkflowScanner

logger = get_logger(__name__)


class WorkflowMapper:
    """Provides model-to-workflow and workflow-to-model mappings."""

    def __init__(self, workflow_scanner: WorkflowScanner):
        self.workflow_scanner = workflow_scanner
        self.logger = logger
        self._cache: Optional[Dict[str, List[Dict]]] = None

    def _get_workflow_map(self) -> Dict[str, List[Dict]]:
        if self._cache is None:
            self._cache = self.workflow_scanner.scan_all_workflows()
        return self._cache

    def get_model_usage_details(self, filename: str) -> List[Dict]:
        """Return workflows and node info for a model filename."""
        workflow_map = self._get_workflow_map()
        results: List[Dict] = []

        for workflow_name, models in workflow_map.items():
            for model in models:
                if model.get("filename") == filename:
                    results.append({
                        "workflow": workflow_name,
                        "model_type": model.get("type"),
                        "node_id": model.get("node_id"),
                        "node_type": model.get("node_type"),
                        "filename": filename,
                    })

        return results

    def get_workflow_dependencies(self, workflow_name: str) -> List[Dict]:
        """Return all models used in the given workflow."""
        workflow_map = self._get_workflow_map()
        return workflow_map.get(workflow_name, [])

    def get_most_used_models(self, n: int = 10) -> List[Dict]:
        """Return top N models used across workflows."""
        workflow_map = self._get_workflow_map()
        counter: Counter = Counter()

        for models in workflow_map.values():
            unique_models = {(m["filename"], m.get("type")) for m in models}
            counter.update({name: 1 for name, _ in unique_models})

        most_common = counter.most_common(n)
        return [
            {"filename": name, "workflow_count": count}
            for name, count in most_common
        ]

    def get_least_used_models(self) -> List[Dict]:
        """Return models referenced in only one workflow."""
        workflow_map = self._get_workflow_map()
        model_to_workflows: Dict[str, set] = defaultdict(set)

        for workflow_name, models in workflow_map.items():
            for model in models:
                model_to_workflows[model["filename"]].add(workflow_name)

        return [
            {"filename": name, "workflow_count": len(workflows)}
            for name, workflows in model_to_workflows.items()
            if len(workflows) == 1
        ]

    def get_workflow_complexity(self) -> Dict[str, int]:
        """Return model count per workflow."""
        workflow_map = self._get_workflow_map()
        return {workflow: len(models) for workflow, models in workflow_map.items()}
