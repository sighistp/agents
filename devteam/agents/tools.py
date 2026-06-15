"""工具定义：OpenAI function calling 格式"""
import json
from typing import Any


FILE_WRITE = {
    "type": "function",
    "function": {
        "name": "file_write",
        "description": "写入文件到项目目录。路径规则：不能含 .. 或绝对路径，不能写入 .env/settings.json/.git 等敏感文件。内容约束：不能含 import subprocess/os.system/eval/exec 等危险模式。",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "相对路径，如 main.py 或 static/style.css。不能含 .. 或以 / 开头"},
                "content": {"type": "string", "description": "文件内容"}
            },
            "required": ["path", "content"]
        }
    }
}

FILE_READ = {
    "type": "function",
    "function": {
        "name": "file_read",
        "description": "读取项目目录中的文件。路径规则同 file_write。",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "相对路径，如 main.py 或 static/style.css"}
            },
            "required": ["path"]
        }
    }
}

EXECUTE_PYTHON = {
    "type": "function",
    "function": {
        "name": "execute_python",
        "description": "在沙箱中执行 Python 代码并返回输出。代码在临时目录运行，项目文件会自动复制过去。不能含 import subprocess/os.system/eval/exec 等危险模式。",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "要执行的 Python 代码"},
                "timeout": {"type": "integer", "description": "超时秒数（默认15，最大30）"}
            },
            "required": ["code"]
        }
    }
}

DONE = {
    "type": "function",
    "function": {
        "name": "done",
        "description": "标记任务完成，输出结构化结果",
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "完成总结"},
                "files_modified": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "修改的文件列表"
                },
                "key_decisions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "关键决策"
                }
            },
            "required": ["summary"]
        }
    }
}

DEVELOPER_TOOLS = [FILE_WRITE, FILE_READ, EXECUTE_PYTHON, DONE]
TESTER_TOOLS = [FILE_READ, EXECUTE_PYTHON, DONE]

# Reviewer 专用 done 工具 — 包含审查字段，确保 LLM 输出结构化审查结论
REVIEWER_DONE = {
    "type": "function",
    "function": {
        "name": "done",
        "description": "完成审查并提交结论",
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "审查总结"},
                "review_approved": {
                    "type": "boolean",
                    "description": "审查是否通过（true=通过，false=不通过）"
                },
                "review_comments": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "file": {"type": "string", "description": "文件路径"},
                            "line": {"type": "integer", "description": "行号"},
                            "severity": {"type": "string", "enum": ["critical", "important", "minor"], "description": "严重程度"},
                            "description": {"type": "string", "description": "问题描述"},
                            "suggestion": {"type": "string", "description": "修复建议"}
                        },
                        "required": ["severity", "description"]
                    },
                    "description": "审查发现的问题列表"
                }
            },
            "required": ["summary", "review_approved"]
        }
    }
}
REVIEWER_TOOLS = [FILE_READ, REVIEWER_DONE]


def get_call_name(call: Any) -> str:
    """提取 tool_call 的 name，兼容 dict 和对象。"""
    if isinstance(call, dict):
        return call.get("name", call.get("function", {}).get("name", ""))
    return call.function.name


def get_call_args(call: Any) -> dict:
    """提取 tool_call 的 arguments 并解析为 dict，兼容 dict 和对象。"""
    import json
    if isinstance(call, dict):
        # DeepSeek 返回 "args"(dict)，OpenAI 返回 "arguments"(str)
        args_val = call.get("args")
        if isinstance(args_val, dict):
            return args_val
        raw = call.get("arguments") or call.get("function", {}).get("arguments", "{}")
    else:
        raw = call.function.arguments
    if not raw or not isinstance(raw, str):
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def serialize_call(call: Any) -> dict:
    """将 tool_call 转为 OpenAI 协议格式。兼容 LangChain 对象和 dict。"""
    if isinstance(call, dict):
        name = call.get("name", call.get("function", {}).get("name", ""))
        # DeepSeek 用 "args"(dict)，OpenAI 用 "arguments"(str)
        args_val = call.get("args")
        if isinstance(args_val, dict):
            arguments = json.dumps(args_val, ensure_ascii=False)
        else:
            arguments = call.get("arguments", call.get("function", {}).get("arguments", ""))
        return {
            "id": call.get("id", ""),
            "type": "function",
            "function": {"name": name, "arguments": arguments}
        }
    return {
        "id": call.id,
        "type": "function",
        "function": {
            "name": call.function.name,
            "arguments": call.function.arguments,
        }
    }
