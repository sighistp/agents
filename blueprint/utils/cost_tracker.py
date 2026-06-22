import contextvars
import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)

PRICING = {"input": 0.27, "output": 1.10}

_current_project_id: contextvars.ContextVar[str] = contextvars.ContextVar('project_id', default='')

def set_project_context(project_id: str):
    _current_project_id.set(project_id)

class CostTracker:
    def __init__(self):
        self._costs: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def record_cost(self, response, project_id: str = "") -> None:
        pid = project_id or _current_project_id.get()
        if not pid:
            return
        try:
            usage = getattr(response, "usage_metadata", None)
            if not usage:
                return
            input_tokens = usage.get("input_tokens", 0) or 0
            output_tokens = usage.get("output_tokens", 0) or 0
            if input_tokens == 0 and output_tokens == 0:
                return
            with self._lock:
                if pid not in self._costs:
                    self._costs[pid] = {"project_id": pid, "total_calls": 0, "total_input_tokens": 0, "total_output_tokens": 0, "estimated_cost_usd": 0.0}
                data = self._costs[pid]
                data["total_calls"] += 1
                data["total_input_tokens"] += input_tokens
                data["total_output_tokens"] += output_tokens
                data["estimated_cost_usd"] = round(data["total_input_tokens"] / 1_000_000 * PRICING["input"] + data["total_output_tokens"] / 1_000_000 * PRICING["output"], 6)
        except Exception as e:
            logger.warning("Failed to record cost: %s", e, exc_info=True)

    def get_cost(self, project_id: str) -> dict:
        with self._lock:
            return self._costs.get(project_id, {})

_tracker = CostTracker()

def record_cost(response, project_id: str = "") -> None:
    _tracker.record_cost(response, project_id)

def get_cost(project_id: str) -> dict:
    return _tracker.get_cost(project_id)