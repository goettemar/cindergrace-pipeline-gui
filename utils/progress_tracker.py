"""Progress tracking for long-running operations"""
from typing import Callable, Optional, Tuple


class ProgressTracker:
    """Track progress of pipeline operations"""

    def __init__(self, total_steps: int, callback: Optional[Callable] = None):
        """
        Initialize progress tracker

        Args:
            total_steps: Total number of steps in the operation
            callback: Optional Gradio progress callback function
        """
        self.total_steps = total_steps
        self.current_step = 0
        self.callback = callback
        self.status = "idle"

    def start(self, status: str = "Starting..."):
        """
        Start tracking

        Args:
            status: Initial status message
        """
        self.current_step = 0
        self.status = status
        self._update()

    def update(self, step: Optional[int] = None, status: Optional[str] = None):
        """
        Update progress

        Args:
            step: Current step number (optional)
            status: Status message (optional)
        """
        if step is not None:
            self.current_step = step
        if status is not None:
            self.status = status
        self._update()

    def increment(self, status: Optional[str] = None):
        """
        Increment progress by one step

        Args:
            status: Optional status message
        """
        self.current_step += 1
        if status:
            self.status = status
        self._update()

    def complete(self, status: str = "Complete"):
        """
        Mark operation as complete

        Args:
            status: Completion message
        """
        self.current_step = self.total_steps
        self.status = status
        self._update()

    def _update(self):
        """Internal method to call Gradio callback with progress"""
        if self.callback:
            progress_pct = self.current_step / self.total_steps if self.total_steps > 0 else 0
            self.callback(progress_pct, desc=self.status)

    def get_progress(self) -> Tuple[float, str]:
        """
        Get current progress

        Returns:
            Tuple of (percentage, status_text)
        """
        pct = (self.current_step / self.total_steps) * 100 if self.total_steps > 0 else 0
        return (pct, self.status)
