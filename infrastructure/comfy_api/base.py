from typing import Any, Dict


class NodeUpdater:
    """Base class for workflow node updaters."""

    target_types: tuple[str, ...] = ()

    def applies_to(self, node_type: str) -> bool:
        """Return True if this updater handles the given node type."""
        return node_type in self.target_types

    def update(self, node_data: Dict[str, Any], params: Dict[str, Any]) -> None:  # pragma: no cover - interface
        raise NotImplementedError("NodeUpdater.update must be implemented by subclasses")
