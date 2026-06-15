# blueprint/tests/test_websocket_pause.py
import pytest
import asyncio
import threading
import inspect
from unittest.mock import AsyncMock, MagicMock, patch

def test_pause_handler_exists():
    """pause 消息处理逻辑应存在"""
    import blueprint.api.websocket as ws_mod
    source = inspect.getsource(ws_mod.ws_project)
    assert 'msg_type == "pause"' in source
    assert 'stop_event.set()' in source

def test_resume_handler_exists():
    """resume_execution 消息处理逻辑应存在"""
    import blueprint.api.websocket as ws_mod
    source = inspect.getsource(ws_mod.ws_project)
    assert 'msg_type == "resume_execution"' in source
    assert 'stop_event.clear()' in source

def test_stop_handler_exists():
    """stop 消息处理逻辑应存在"""
    import blueprint.api.websocket as ws_mod
    source = inspect.getsource(ws_mod.ws_project)
    assert 'msg_type == "stop"' in source

def test_heartbeat_function_exists():
    """_send_heartbeat 函数应存在且为 async"""
    from blueprint.api.websocket import _send_heartbeat
    assert callable(_send_heartbeat)
    assert inspect.iscoroutinefunction(_send_heartbeat)

@pytest.mark.asyncio
async def test_heartbeat_sends_messages():
    """_send_heartbeat 应在暂停期间发送心跳"""
    from blueprint.api.websocket import _send_heartbeat

    ws = AsyncMock()
    paused = [True]

    def is_paused():
        return paused[0]

    # 启动心跳，使用短间隔便于测试
    async def run_heartbeat():
        await _send_heartbeat(ws, "test-proj", is_paused, interval=0.1)

    task = asyncio.create_task(run_heartbeat())
    await asyncio.sleep(0.3)  # 等待至少一次心跳
    paused[0] = False  # 取消暂停
    await asyncio.sleep(0.2)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # 应该发送了至少一次心跳
    assert ws.send_json.call_count >= 1
    call_args = ws.send_json.call_args[0][0]
    assert call_args["type"] == "heartbeat"

def test_node_boundary_check_in_graph():
    """_run_async 中应在节点边界检查 stop_event"""
    import blueprint.api.websocket as ws_mod
    source = inspect.getsource(ws_mod._run_graph_sync)
    assert 'stop_event.is_set()' in source

def test_pause_state_variable_exists():
    """ws_project 中应有 paused 状态变量"""
    import blueprint.api.websocket as ws_mod
    source = inspect.getsource(ws_mod.ws_project)
    assert 'paused' in source
