"""WebSocket module for real-time project execution streaming.

Architecture:
- Main loop: receives client messages (start/resume/rethink/cancel)
- Background task: runs graph in a thread pool, puts messages in queue
- Drainer task: reads from queue, sends to WebSocket

The graph runs in a thread so it doesn't block the event loop.
Race condition fix: use epoch counter to discard stale messages.
"""
import asyncio
import json
import re
import threading
import time
import uuid
from typing import Any
from collections import defaultdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from langgraph.types import Command

from devteam.agents.graph import create_graph
from devteam.agents.state import create_initial_state
from devteam.api.auth import decode_token

router = APIRouter()

# Rate limiting: max 3 start_project per minute per user
_rate_limits: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT_MAX = 3
_RATE_LIMIT_WINDOW = 60  # seconds
_last_cleanup = 0.0


def _check_rate_limit(user_id: str) -> bool:
    """Check if user has exceeded rate limit. Returns True if allowed."""
    global _last_cleanup
    now = time.time()

    # Periodic cleanup: remove stale entries every 5 minutes
    if now - _last_cleanup > 300:
        _last_cleanup = now
        stale_keys = [k for k, v in _rate_limits.items()
                      if all(now - t > _RATE_LIMIT_WINDOW for t in v)]
        for k in stale_keys:
            del _rate_limits[k]

    timestamps = _rate_limits[user_id]
    timestamps[:] = [t for t in timestamps if now - t < _RATE_LIMIT_WINDOW]
    if len(timestamps) >= _RATE_LIMIT_MAX:
        return False
    timestamps.append(now)
    return True


def _run_graph_sync(app, input_data, config, msg_queue, loop, stop_event, epoch):
    """Run LangGraph graph in a thread, putting messages into an async queue.

    Args:
        app: Compiled LangGraph app
        input_data: Initial state or Command
        config: LangGraph config
        msg_queue: Async queue for messages
        loop: Event loop for async operations
        stop_event: Threading event to signal graceful stop
        epoch: Generation counter to discard stale messages
    """
    import asyncio as _asyncio

    def _put(msg):
        """Put message into queue if not stopped and epoch matches."""
        if stop_event.is_set():
            return  # This execution was superseded
        msg["_epoch"] = epoch  # Tag with epoch for client-side filtering
        if loop and loop.is_running():
            _asyncio.run_coroutine_threadsafe(msg_queue.put(msg), loop)

    import asyncio as _asyncio

    project_id = ""
    if isinstance(input_data, dict):
        project_id = input_data.get("project_id", "unknown")
    elif config:
        project_id = config.get("configurable", {}).get("thread_id", "unknown")

    async def _run_async():
        """Run the graph asynchronously in a new event loop."""
        try:
            _put({"type": "state_sync", "project_id": project_id,
                  "data": {k: v for k, v in input_data.items() if k != "messages"} if isinstance(input_data, dict) else {}})

            current_state = input_data if isinstance(input_data, dict) else {}

            # Use async stream (required for async agent nodes)
            async for event in app.astream(input_data, config=config):
                if stop_event.is_set():
                    return

                for node_name, node_output in event.items():
                    if node_name == "__end__":
                        output = node_output if isinstance(node_output, dict) else {}
                        _put({"type": "project_done", "project_id": project_id,
                              "data": {"status": output.get("status", "delivered"),
                                       "current_agent": "done",
                                       "files": output.get("files", {})}})
                        return

                    if isinstance(node_output, dict):
                        current_state.update(node_output)
                        _put({"type": "agent_start", "project_id": project_id, "agent": node_name})
                        _put({"type": "agent_update", "project_id": project_id, "agent": node_name, "data": node_output})
                        _put({"type": "agent_done", "project_id": project_id, "agent": node_name})

            # Check if graph paused (interrupt) or completed
            final_status = current_state.get("status", "delivered")
            if final_status == "running":
                # Graph paused due to interrupt - send interrupt with architecture data
                _put({"type": "interrupt", "project_id": project_id,
                      "data": {
                          "type": "confirm",
                          "message": "请确认以下架构设计",
                          "architecture": current_state.get("architecture", {}),
                          "api_definitions": current_state.get("api_definitions", []),
                          "data_models": current_state.get("data_models", []),
                      }})
            else:
                # Graph completed normally
                _put({"type": "project_done", "project_id": project_id,
                      "data": {"status": final_status,
                               "current_agent": "done",
                               "files": current_state.get("files", {})}})
        except _asyncio.CancelledError:
            pass  # Task was cancelled
        except Exception as exc:
            if not stop_event.is_set():
                # Log the exception for debugging
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Graph execution error: {type(exc).__name__}: {exc}")

                # Check if this is a LangGraph interrupt
                if "GraphInterrupt" in type(exc).__name__ or "interrupt" in str(exc).lower():
                    # Extract interrupt data
                    interrupt_data = {}
                    if hasattr(exc, 'value'):
                        interrupt_data = exc.value if isinstance(exc.value, dict) else {"value": str(exc.value)}
                    # Ensure interrupt_data has required fields for frontend
                    if "type" not in interrupt_data:
                        interrupt_data["type"] = "confirm"
                    if "message" not in interrupt_data:
                        interrupt_data["message"] = "请确认"
                    _put({"type": "interrupt", "project_id": project_id,
                          "data": interrupt_data})
                else:
                    _put({"type": "error", "project_id": project_id,
                          "message": str(exc), "data": {"error": str(exc)}})

    # Run async code in a new event loop (since we're in a thread)
    try:
        _asyncio.run(_run_async())
    except _asyncio.CancelledError:
        pass


@router.websocket("/ws/project")
async def ws_project(websocket: WebSocket):
    """WebSocket endpoint for real-time project execution."""
    # Extract token from query params (preferred for WebSocket) or Authorization header
    token = websocket.query_params.get("token")
    if not token:
        # Fallback to Authorization header
        auth_header = websocket.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]

    if not token:
        await websocket.close(code=4001, reason="Missing authentication token")
        return

    # Verify token
    payload = decode_token(token)
    if payload is None:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    user_id = payload.get("sub", "anonymous")

    await websocket.accept()

    graph_app = None
    current_state = None
    project_id = None
    cancelled = False
    msg_queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    # Race condition prevention
    stop_event = threading.Event()
    epoch = 0
    graph_thread = None
    drainer_task = None

    async def _drain_queue():
        """Continuously drain queue and send to WebSocket."""
        while True:
            try:
                ev_msg = await asyncio.wait_for(msg_queue.get(), timeout=1.0)
                # Skip messages from old epochs
                msg_epoch = ev_msg.pop("_epoch", 0)
                if msg_epoch < epoch:
                    continue  # Stale message, discard
                await websocket.send_json(ev_msg)
                if ev_msg.get("type") in ("project_done", "error"):
                    return
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                return
            except Exception:
                return

    def _start_graph(input_data, config=None):
        """Start graph execution in background with proper cleanup."""
        nonlocal graph_thread, drainer_task, epoch, stop_event

        # 1. Signal old thread to stop (old event stays set)
        stop_event.set()

        # 2. Wait for old thread to finish (with timeout)
        if graph_thread and graph_thread.is_alive():
            graph_thread.join(timeout=2.0)
            if graph_thread.is_alive():
                # Thread is stuck, epoch filtering will discard its messages
                pass

        # 3. Cancel old drainer
        if drainer_task and not drainer_task.done():
            drainer_task.cancel()

        # 4. Clear queue (discard stale messages)
        while not msg_queue.empty():
            try:
                msg_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        # 5. Increment epoch and create NEW stop event (old one stays set)
        epoch += 1
        stop_event = threading.Event()  # New event, old thread's event stays set

        # 6. Start new graph thread
        graph_thread = threading.Thread(
            target=_run_graph_sync,
            args=(graph_app, input_data, config, msg_queue, loop, stop_event, epoch),
            daemon=True
        )
        graph_thread.start()

        # 7. Start new drainer
        drainer_task = asyncio.create_task(_drain_queue())

    while True:
        try:
            raw = await websocket.receive_text()
        except WebSocketDisconnect:
            break
        except Exception:
            break

        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            await websocket.send_json({"type": "error", "message": "Invalid JSON"})
            continue

        msg_type = msg.get("type")

        if msg_type == "start_project":
            # Rate limiting
            if not _check_rate_limit(user_id):
                await websocket.send_json({"type": "error", "message": "Rate limit exceeded. Try again later."})
                continue

            requirement = msg.get("requirement")
            if not requirement:
                await websocket.send_json({"type": "error", "message": "Missing 'requirement' field"})
                continue

            project_id = msg.get("project_id", str(uuid.uuid4()))
            if not re.match(r'^[a-zA-Z0-9_-]+$', project_id):
                await websocket.send_json({"type": "error", "message": "Invalid project_id"})
                continue

            current_state = create_initial_state(project_id, requirement)
            graph_app = create_graph()
            cancelled = False
            # Pass config with thread_id for checkpointer
            config = {"configurable": {"thread_id": project_id}}
            _start_graph(current_state, config)

        elif msg_type == "resume":
            if graph_app is None:
                await websocket.send_json({"type": "error", "message": "No active project"})
                continue
            decision = msg.get("decision", "approved")
            config = {"configurable": {"thread_id": project_id}}
            _start_graph(Command(resume=decision), config)

        elif msg_type == "rethink":
            if graph_app is None:
                await websocket.send_json({"type": "error", "message": "No active project"})
                continue
            feedback = msg.get("feedback", "")
            config = {"configurable": {"thread_id": project_id}}

            # Get latest state from checkpoint (not stale current_state)
            try:
                snapshot = graph_app.get_state(config)
                latest_state = snapshot.values.copy()
                latest_state["user_feedback"] = feedback
                graph_app.update_state(config, {"user_feedback": feedback})
            except Exception:
                # Fallback to current_state if checkpoint not available
                latest_state = current_state.copy() if current_state else {}
                latest_state["user_feedback"] = feedback

            cancelled = False
            _start_graph(latest_state, config)

        elif msg_type == "cancel":
            cancelled = True
            stop_event.set()  # Signal graph thread to stop
            if drainer_task and not drainer_task.done():
                drainer_task.cancel()
            await websocket.send_json({
                "type": "project_done", "project_id": project_id,
                "data": {"status": "cancelled", "current_agent": "done"},
            })

        elif msg_type == "reconnect":
            pid = msg.get("project_id", project_id)
            await websocket.send_json({
                "type": "state_sync", "project_id": pid,
                "data": {k: v for k, v in (current_state or {}).items() if k != "messages"},
            })

        else:
            await websocket.send_json({"type": "error", "message": f"Unknown: {msg_type}"})
