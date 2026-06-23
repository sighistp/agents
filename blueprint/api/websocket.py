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
import logging
import re
import threading
import time
import uuid
from typing import Any
from collections import defaultdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from langgraph.types import Command

from blueprint.agents.graph import create_graph
from blueprint.agents.state import create_initial_state
from blueprint.api.auth import decode_token

logger = logging.getLogger("blueprint.websocket")

router = APIRouter()

# Rate limiting: max 3 start_project per minute per user
_rate_limits: dict[str, list[float]] = defaultdict(list)
_rate_limits_lock = threading.Lock()
_RATE_LIMIT_MAX = 3
_RATE_LIMIT_WINDOW = 60  # seconds
_last_cleanup = 0.0


def _check_rate_limit(user_id: str) -> bool:
    """Check if user has exceeded rate limit. Returns True if allowed."""
    global _last_cleanup
    now = time.time()

    with _rate_limits_lock:
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


def _extract_agent_summary(node_name: str, node_output: dict) -> str:
    """从 Agent 输出中提取结构化摘要，用于 save_execution 的 result_summary。"""
    parts = []

    if node_name == "pm":
        stories = node_output.get("user_stories", [])
        features = node_output.get("features", [])
        if stories:
            parts.append(f"{len(stories)} 个用户故事")
        if features:
            parts.append(f"{len(features)} 个功能特性")

    elif node_name == "architect":
        arch = node_output.get("architecture", {})
        apis = node_output.get("api_definitions", [])
        models = node_output.get("data_models", [])
        if apis:
            parts.append(f"{len(apis)} 个 API")
        if models:
            parts.append(f"{len(models)} 个数据模型")
        if arch.get("description"):
            parts.append(arch["description"][:100])

    elif node_name == "developer":
        files = node_output.get("files", {})
        decisions = node_output.get("key_decisions", [])
        if files:
            parts.append(f"写入 {len(files)} 个文件: {', '.join(list(files.keys())[:5])}")
        if decisions:
            parts.append(f"决策: {'; '.join(decisions[:3])}")

    elif node_name == "tester":
        test_passed = node_output.get("test_passed", False)
        results = node_output.get("test_results", [])
        parts.append("通过" if test_passed else "未通过")
        if results:
            parts.append(results[0].get("summary", "")[:100])

    elif node_name == "reviewer":
        approved = node_output.get("review_approved", False)
        comments = node_output.get("review_comments", [])
        parts.append("通过" if approved else "不通过")
        if comments:
            parts.append(f"{len(comments)} 个问题")

    error = node_output.get("error")
    if error:
        parts.append(f"错误: {error[:100]}")

    return " | ".join(parts) if parts else f"{node_name} 完成"


def _extract_chat_message(node_name: str, node_output: dict) -> str | None:
    """从 Agent 输出中提取一条精简的用户可见消息（用于前端聊天显示）。"""
    # 优先用 Agent 最后一条 assistant 消息
    messages = node_output.get("messages", [])
    for msg in reversed(messages):
        if msg.get("name") == node_name and msg.get("role") == "assistant":
            content = msg.get("content", "").strip()
            if content and len(content) > 10:
                return content[:500]

    # 没有 assistant 消息，用结构化摘要
    return _extract_agent_summary(node_name, node_output)


async def _send_heartbeat(ws, project_id, is_paused_fn, interval=10):
    """Send heartbeat periodically during pause to keep WebSocket alive."""
    while is_paused_fn():
        try:
            await asyncio.sleep(interval)
            if is_paused_fn():
                await ws.send_json({"type": "heartbeat", "project_id": project_id})
        except Exception:
            break


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

    project_id = ""
    if isinstance(input_data, dict):
        project_id = input_data.get("project_id", "unknown")
    elif config:
        project_id = config.get("configurable", {}).get("thread_id", "unknown")

    async def _run_async():
        """Run the graph asynchronously in a new event loop."""
        from blueprint.utils.cost_tracker import set_project_context
        set_project_context(project_id)

        from blueprint.utils.memory import get_memory
        mem = get_memory()

        # Heartbeat task: update heartbeat every 10 seconds during execution
        async def _heartbeat_loop():
            while not stop_event.is_set():
                try:
                    mem.update_heartbeat(project_id)
                    await _asyncio.sleep(10)
                except Exception:
                    break

        heartbeat_task = _asyncio.create_task(_heartbeat_loop())

        try:
            # Save snapshot on project start
            if isinstance(input_data, dict):
                mem.save_snapshot(
                    project_id,
                    requirement=input_data.get("requirement", ""),
                    current_step="pm",
                    status="active"
                )
            logger.info(f"[{project_id}] Graph started")

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
                        mem.save_snapshot(project_id, status="delivered", current_step="done")
                        logger.info(f"[{project_id}] Graph completed (delivered)")
                        _put({"type": "project_done", "project_id": project_id,
                              "data": {"status": output.get("status", "delivered"),
                                       "current_agent": "done",
                                       "files": output.get("files", {})}})
                        return

                    if isinstance(node_output, dict):
                        current_state.update(node_output)

                        # Convert messages to dicts (handle BaseMessage objects)
                        raw_msgs = node_output.get("messages", [])
                        dict_msgs = [
                            m.model_dump() if hasattr(m, 'model_dump')
                            else (m.dict() if hasattr(m, 'dict') else m)
                            for m in raw_msgs
                        ]

                        # Extract tool_calls from messages (nested inside AIMessage.tool_calls)
                        all_tool_calls = []
                        for m in dict_msgs:
                            tc = m.get("tool_calls")
                            if tc:
                                all_tool_calls.extend(tc)
                        tool_calls_json = json.dumps(all_tool_calls, ensure_ascii=False) if all_tool_calls else None

                        # 提取结构化摘要（节约 token，只存有用信息）
                        summary = _extract_agent_summary(node_name, node_output)
                        mem.save_execution(
                            project_id, node_name,
                            iteration=current_state.get("iteration", 0),
                            result_summary=summary,
                            status="success" if not node_output.get("error") else "error",
                            tool_calls=tool_calls_json
                        )
                        # 存一条精简消息到聊天记录（不是完整 LLM 对话）
                        chat_msg = _extract_chat_message(node_name, node_output)
                        if chat_msg:
                            mem.save_message(
                                project_id,
                                role="assistant",
                                name=node_name,
                                content=chat_msg[:2000]
                            )
                        # Save full conversation to memory (only current agent's messages)
                        agent_msgs = [m for m in dict_msgs if m.get("name") == node_name or m.get("role") == "tool"]
                        if agent_msgs:
                            mem.save_conversation(project_id, node_name, current_state.get("iteration", 0), agent_msgs)
                        # Update snapshot step
                        mem.save_snapshot(project_id, current_step=node_name, iteration=current_state.get("iteration", 0))
                        mem.update_heartbeat(project_id)

                        logger.info(f"[{project_id}] Agent {node_name} done (iter={current_state.get('iteration', 0)})")
                        # 过滤消息：只发带 agent name 的消息，不发 system prompt 等内部消息
                        # 用 dict_msgs（已转换）而非 raw BaseMessage 对象
                        filtered_output = {k: v for k, v in node_output.items() if k != "messages"}
                        filtered_output["messages"] = [
                            m for m in dict_msgs
                            if m.get("name") == node_name or m.get("role") == "tool"
                        ]
                        _put({"type": "agent_start", "project_id": project_id, "agent": node_name})
                        _put({"type": "agent_update", "project_id": project_id, "agent": node_name, "data": filtered_output})
                        _put({"type": "agent_done", "project_id": project_id, "agent": node_name})
                        # Send cost update after each agent completes
                        try:
                            from blueprint.utils.cost_tracker import get_cost
                            cost_data = get_cost(project_id)
                            if cost_data:
                                _put({"type": "cost_update", "project_id": project_id, "data": cost_data})
                        except Exception:
                            pass

                # Node boundary: check if execution should pause
                if stop_event.is_set():
                    _put({"type": "paused", "project_id": project_id})
                    # Wait until stop_event is cleared (user resumes)
                    while stop_event.is_set():
                        await _asyncio.sleep(0.5)

            # Check if graph paused (interrupt) or completed
            # Use get_state to detect pending interrupts reliably
            has_interrupt = False
            try:
                graph_state = app.get_state(config)
                if graph_state.next:  # Has pending nodes = interrupted
                    has_interrupt = True
                    # Extract interrupt value if available
                    interrupt_val = {}
                    if graph_state.tasks:
                        for task in graph_state.tasks:
                            if hasattr(task, 'interrupts') and task.interrupts:
                                interrupt_val = task.interrupts[0].value if task.interrupts[0].value else {}
                    _put({"type": "interrupt", "project_id": project_id,
                          "data": {
                              "type": interrupt_val.get("type", "confirm"),
                              "message": interrupt_val.get("message", "请确认"),
                              "architecture": interrupt_val.get("architecture", current_state.get("architecture", {})),
                              "api_definitions": interrupt_val.get("api_definitions", current_state.get("api_definitions", [])),
                              "data_models": interrupt_val.get("data_models", current_state.get("data_models", [])),
                              "error": interrupt_val.get("error", ""),
                              "files": interrupt_val.get("files", list(current_state.get("files", {}).keys())),
                          }})
            except Exception as e:
                logger.warning(f"[{project_id}] Failed to check graph state: {e}")

            if not has_interrupt:
                final_status = current_state.get("status", "delivered")
                if final_status == "running":
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
                logger.error(f"[{project_id}] Graph execution error: {type(exc).__name__}: {exc}")

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
                    # Update snapshot status on error
                    try:
                        mem.save_snapshot(project_id, status="error")
                    except Exception:
                        pass
                    _put({"type": "error", "project_id": project_id,
                          "message": str(exc), "data": {"error": str(exc)}})
        finally:
            heartbeat_task.cancel()

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
    logger.info(f"WebSocket connected: user={user_id}")

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
    paused = False
    heartbeat_task = None
    _sent_files = set()  # Track sent files for incremental updates

    async def _drain_queue():
        """Continuously drain queue and send to WebSocket."""
        nonlocal _sent_files
        while True:
            try:
                ev_msg = await asyncio.wait_for(msg_queue.get(), timeout=1.0)
                # Skip messages from old epochs
                msg_epoch = ev_msg.pop("_epoch", 0)
                if msg_epoch < epoch:
                    continue  # Stale message, discard
                # Incremental file sending: only send new/changed files
                msg_type = ev_msg.get("type")
                if msg_type in ("agent_update", "project_done"):
                    data = ev_msg.get("data", {})
                    all_files = data.get("files", {})
                    if all_files:
                        new_files = {k: v for k, v in all_files.items() if k not in _sent_files}
                        data["files"] = new_files
                        _sent_files.update(new_files.keys())
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

        # Set tool progress callback (if enabled)
        from blueprint.config import settings
        if settings.tool_progress_enabled:
            from blueprint.agents.tool_executor import set_progress_callback
            set_progress_callback(lambda **kw: _put({
                "type": "tool_progress",
                "project_id": project_id,
                "data": kw,
            }))
        else:
            from blueprint.agents.tool_executor import set_progress_callback
            set_progress_callback(None)

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
            logger.info(f"WebSocket disconnected: user={user_id}")
            break
        except Exception:
            logger.info(f"WebSocket error/disconnect: user={user_id}")
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
            logger.info(f"[{project_id}] Starting project: {requirement[:80]}...")
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

        elif msg_type == "pause":
            stop_event.set()
            paused = True
            await websocket.send_json({"type": "paused", "project_id": project_id})
            heartbeat_task = asyncio.create_task(_send_heartbeat(websocket, project_id, lambda: paused))

        elif msg_type == "resume_execution":
            stop_event.clear()
            paused = False
            # 取消心跳任务
            if heartbeat_task and not heartbeat_task.done():
                heartbeat_task.cancel()
            await websocket.send_json({"type": "resumed", "project_id": project_id})

        elif msg_type == "stop":
            stop_event.set()
            paused = False
            cancelled = True
            if heartbeat_task and not heartbeat_task.done():
                heartbeat_task.cancel()
            if drainer_task and not drainer_task.done():
                drainer_task.cancel()
            await websocket.send_json({
                "type": "stopped", "project_id": project_id,
                "data": {"status": "stopped", "current_agent": "done"}
            })

        elif msg_type == "reconnect":
            pid = msg.get("project_id", project_id)
            await websocket.send_json({
                "type": "state_sync", "project_id": pid,
                "data": {k: v for k, v in (current_state or {}).items() if k != "messages"},
            })

        else:
            await websocket.send_json({"type": "error", "message": f"Unknown: {msg_type}"})
