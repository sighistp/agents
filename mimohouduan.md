# Blueprint 功能扩展计划（前端 + 后端）

> **日期:** 2026-06-15
> **原则:** 所有新功能独立于现有链路，不修改 PM→Architect→Developer→Tester→Reviewer 核心流程
> **当前前端:** 5 个页面、12 个组件、3 个 Store、2 个 Composable

---

## 目录

1. [代码质量评分](#1-代码质量评分)
2. [变更历史对比](#2-变更历史对比)
3. [Agent 思考过程可视化](#3-agent-思考过程可视化)
4. [代码安全扫描](#4-代码安全扫描)
5. [项目文档自动生成](#5-项目文档自动生成)
6. [Webhook 通知](#6-webhook-通知)
7. [CLI 工具](#7-cli-工具)
8. [项目模板市场](#8-项目模板市场)
9. [知识库集成](#9-知识库集成)
10. [部署脚本生成](#10-部署脚本生成)
11. [API 开放平台](#11-api-开放平台)
12. [协作模式](#12-协作模式)
13. [项目评分与排行榜](#13-项目评分与排行榜)
14. [前端架构改造](#14-前端架构改造)
15. [实施优先级](#15-实施优先级)

---

## 1. 代码质量评分

### 1.1 后端实现

**新增文件:** `Blueprint/utils/quality_scorer.py`

```python
# 评分维度（满分 100）
SCORE_DIMENSIONS = {
    "complexity": {"weight": 25, "desc": "代码复杂度"},
    "test_coverage": {"weight": 25, "desc": "测试覆盖"},
    "security": {"weight": 20, "desc": "安全风险"},
    "maintainability": {"weight": 15, "desc": "可维护性"},
    "documentation": {"weight": 15, "desc": "文档完整度"},
}

class QualityScorer:
    def score_project(self, project_dir: str) -> dict:
        """对整个项目打分"""
        files = self._scan_files(project_dir)
        
        scores = {}
        scores["complexity"] = self._score_complexity(files)
        scores["test_coverage"] = self._score_test_coverage(files)
        scores["security"] = self._score_security(files)
        scores["maintainability"] = self._score_maintainability(files)
        scores["documentation"] = self._score_documentation(files)
        
        total = sum(scores[k] * SCORE_DIMENSIONS[k]["weight"] / 100 
                     for k in scores)
        
        return {
            "total": round(total, 1),
            "dimensions": scores,
            "grade": self._grade(total),
            "suggestions": self._generate_suggestions(scores),
        }
    
    def _score_complexity(self, files: list) -> float:
        """基于代码行数、嵌套深度、函数长度"""
        # 使用 radon 或自定义计算
        pass
    
    def _score_test_coverage(self, files: list) -> float:
        """基于测试文件数 vs 源文件数"""
        pass
    
    def _score_security(self, files: list) -> float:
        """基于安全扫描结果"""
        pass
```

**新增端点:**

```python
# api/projects.py 新增
@router.get("/api/projects/{project_id}/quality")
async def get_quality_score(project_id: str):
    """获取项目质量评分"""
    project_dir = _resolve_project_dir(project_id)
    scorer = QualityScorer()
    return scorer.score_project(project_dir)
```

### 1.2 前端改动

**修改文件:** `frontend/src/components/OutputPanel.vue`

```
改动: 在文件列表上方新增「质量评分」卡片
├── 总分大数字（颜色：绿>80 / 黄60-80 / 红<60）
├── 五个维度的横向进度条
├── 等级标签（A/B/C/D/F）
└── 改进建议列表（折叠）
```

**新增组件:** `frontend/src/components/QualityScore.vue`（约 120 行）

```
Props: projectId
功能:
├── mounted 时调用 GET /api/projects/:id/quality
├── 渲染雷达图（用 Canvas 或 CSS 实现，不引入图表库）
├── 渲染维度进度条
└── 渲染建议列表
```

**修改文件:** `frontend/src/stores/project.js`

```
新增 state: qualityScore: null
新增 action: fetchQuality(projectId)
```

---

## 2. 变更历史对比

### 2.1 后端实现

**新增文件:** `Blueprint/utils/diff_engine.py`

```python
import difflib
import json

class DiffEngine:
    def __init__(self, project_dir: str):
        self.project_dir = Path(project_dir)
        self.snapshots_dir = self.project_dir / ".snapshots"
        self.snapshots_dir.mkdir(exist_ok=True)
    
    def save_snapshot(self, iteration: int):
        """保存当前所有文件的快照"""
        snapshot = {}
        for f in self.project_dir.rglob("*"):
            if f.is_file() and not f.name.startswith("."):
                snapshot[str(f.relative_to(self.project_dir))] = f.read_text(
                    encoding="utf-8", errors="replace"
                )
        
        snap_file = self.snapshots_dir / f"iter_{iteration:03d}.json"
        snap_file.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
    
    def compare(self, iter_a: int, iter_b: int) -> dict:
        """对比两个迭代的差异"""
        snap_a = self._load_snapshot(iter_a)
        snap_b = self._load_snapshot(iter_b)
        
        all_files = set(snap_a.keys()) | set(snap_b.keys())
        diffs = {}
        
        for filepath in all_files:
            content_a = snap_a.get(filepath, "")
            content_b = snap_b.get(filepath, "")
            
            if content_a != content_b:
                diff = list(difflib.unified_diff(
                    content_a.splitlines(keepends=True),
                    content_b.splitlines(keepends=True),
                    fromfile=f"iter_{iter_a}/{filepath}",
                    tofile=f"iter_{iter_b}/{filepath}",
                ))
                diffs[filepath] = {
                    "type": "modified" if filepath in snap_a and filepath in snap_b 
                           else ("added" if filepath in snap_b else "deleted"),
                    "diff": "".join(diff),
                    "additions": sum(1 for l in diff if l.startswith("+")),
                    "deletions": sum(1 for l in diff if l.startswith("-")),
                }
        
        return {
            "iterations": [iter_a, iter_b],
            "files_changed": len(diffs),
            "total_additions": sum(d["additions"] for d in diffs.values()),
            "total_deletions": sum(d["deletions"] for d in diffs.values()),
            "diffs": diffs,
        }
    
    def list_snapshots(self) -> list[int]:
        """列出所有快照的迭代号"""
        return sorted([
            int(f.stem.split("_")[1]) 
            for f in self.snapshots_dir.glob("iter_*.json")
        ])
```

**在 Agent 执行链路中调用（不影响流程）:**

```python
# agents/graph.py 的 deliver_node 中
async def deliver_node(state):
    # ... 现有逻辑 ...
    
    # 新增: 保存快照（失败不影响交付）
    try:
        diff_engine = DiffEngine(project_dir)
        diff_engine.save_snapshot(state.get("iteration", 0))
    except Exception:
        pass  # 快照失败不影响主流程
    
    return { ... }
```

### 2.2 前端改动

**新增组件:** `frontend/src/components/DiffViewer.vue`（约 150 行）

```
Props: projectId, iterA, iterB
功能:
├── 调用 GET /api/projects/:id/diff?a=&b=
├── 文件列表（左栏，显示变更文件名 + 增删统计）
├── 差异视图（右栏，逐行对比，绿=新增，红=删除）
├── 统计摘要（X 个文件变更，+N 行，-M 行）
└── 迭代选择下拉框（可切换对比目标）
```

**修改文件:** `frontend/src/pages/ProjectDetailPage.vue`

```
改动: 在「开发日志」tab 旁边新增「变更对比」tab
├── 两个下拉框选择对比的迭代
├── 渲染 DiffViewer 组件
└── 显示变更统计
```

**新增端点:**

```python
@router.get("/api/projects/{project_id}/diff")
async def get_diff(project_id: str, a: int, b: int):
    diff_engine = DiffEngine(_resolve_project_dir(project_id))
    return diff_engine.compare(a, b)
```

---

## 3. Agent 思考过程可视化

### 3.1 后端实现

**改造 `Blueprint/utils/memory.py`:**

```python
# 新增: 记录 LLM 原始输入输出
class AgentTrace:
    def __init__(self, project_id: str):
        self.project_id = project_id
    
    def record_trace(self, agent_name: str, iteration: int, 
                     prompt: str, response: str, tools_called: list):
        """记录 Agent 的完整思考链"""
        trace = {
            "project_id": self.project_id,
            "agent": agent_name,
            "iteration": iteration,
            "prompt": prompt,           # 发给 LLM 的完整 prompt
            "response": response,        # LLM 的原始返回
            "tools_called": tools_called, # 工具调用列表
            "timestamp": time.time(),
        }
        # 写入 SQLite agent_traces 表
        self._save_trace(trace)
    
    def get_traces(self, agent_name: str = None, 
                   iteration: int = None) -> list:
        """获取 trace 记录"""
        pass
```

**在各 Agent 中调用（不改核心逻辑）:**

```python
# agents/developer.py 中，在 LLM 调用后
async def developer_agent(state):
    # ... 现有逻辑 ...
    
    # 新增: 记录 trace（失败不影响主流程）
    try:
        trace = AgentTrace(state["project_id"])
        trace.record_trace(
            "developer", state.get("iteration", 0),
            prompt=prompt,              # build_developer_prompt 的结果
            response=raw_response,      # LLM 原始返回
            tools_called=tool_calls,    # 工具调用列表
        )
    except Exception:
        pass
    
    return { ... }
```

### 3.2 前端改动

**新增组件:** `frontend/src/components/AgentTracePanel.vue`（约 200 行）

```
Props: projectId, agentName, iteration
功能:
├── 调用 GET /api/projects/:id/traces?agent=&iteration=
├── 可折叠的 Trace 面板
│   ├── 📤 发送的 Prompt（可折叠，语法高亮）
│   ├── 📥 LLM 原始响应（可折叠，语法高亮）
│   ├── 🔧 工具调用列表
│   │   ├── file_write: path=xxx, content=...
│   │   ├── execute_python: code=...
│   │   └── done: summary=...
│   └── ⏱️ 耗时、Token 数
└── 时间线展示（多个迭代的 trace 排列）
```

**修改文件:** `frontend/src/components/AgentCard.vue`

```
改动: Agent 卡片下方新增「查看思考过程」按钮
├── 点击展开 AgentTracePanel
├── 传入当前 agentName 和 iteration
└── 状态：等待时不显示，执行中/完成后可查看
```

**修改文件:** `frontend/src/stores/project.js`

```
新增 state: agentTraces: {}  // { agentName: [trace1, trace2, ...] }
新增 action: fetchTraces(projectId, agentName, iteration)
```

**新增端点:**

```python
@router.get("/api/projects/{project_id}/traces")
async def get_traces(project_id: str, agent: str = None, iteration: int = None):
    trace = AgentTrace(project_id)
    return trace.get_traces(agent_name=agent, iteration=iteration)
```

---

## 4. 代码安全扫描

### 4.1 后端实现

**新增文件:** `Blueprint/utils/security_scanner.py`

```python
from dataclasses import dataclass
from enum import Enum

class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

@dataclass
class SecurityIssue:
    file: str
    line: int
    severity: Severity
    category: str
    description: str
    suggestion: str

class SecurityScanner:
    def scan_project(self, project_dir: str) -> dict:
        """扫描整个项目"""
        issues = []
        issues.extend(self._scan_secrets(project_dir))
        issues.extend(self._scan_injection(project_dir))
        issues.extend(self._scan_xss(project_dir))
        issues.extend(self._scan_dependencies(project_dir))
        issues.extend(self._scan_best_practices(project_dir))
        
        summary = {
            "total": len(issues),
            "critical": sum(1 for i in issues if i.severity == Severity.CRITICAL),
            "high": sum(1 for i in issues if i.severity == Severity.HIGH),
            "medium": sum(1 for i in issues if i.severity == Severity.MEDIUM),
            "low": sum(1 for i in issues if i.severity == Severity.LOW),
            "score": self._calculate_score(issues),
            "issues": [asdict(i) for i in issues],
        }
        return summary
    
    def _scan_secrets(self, project_dir: str) -> list[SecurityIssue]:
        """检测硬编码密钥"""
        patterns = [
            r'(?i)(api[_-]?key|secret|password|token)\s*[=:]\s*["\'][^"\']+["\']',
            r'(?i)AWS_(ACCESS|SECRET)_KEY',
            r'-----BEGIN (RSA |EC )?PRIVATE KEY-----',
        ]
        # 扫描所有文件，匹配模式
        pass
    
    def _scan_injection(self, project_dir: str) -> list[SecurityIssue]:
        """检测 SQL 注入风险"""
        patterns = [
            r'execute\([^)]*%s[^)]*\)',      # Python f-string SQL
            r'execute\([^)]*\{[^}]+\}[^)]*\)',
            r'query\([^)]*\+[^)]*\)',          # 字符串拼接 SQL
        ]
        pass
    
    def _scan_xss(self, project_dir: str) -> list[SecurityIssue]:
        """检测 XSS 风险"""
        patterns = [
            r'innerHTML\s*=',                  # innerHTML 直接赋值
            r'dangerouslySetInnerHTML',
            r'document\.write\(',
            r'\.html\([^)]*\+',                # jQuery .html() 拼接
        ]
        pass
    
    def _scan_dependencies(self, project_dir: str) -> list[SecurityIssue]:
        """检查依赖漏洞"""
        # 如果有 requirements.txt，检查已知漏洞
        # 如果有 package.json，运行 npm audit
        pass
    
    def _calculate_score(self, issues: list) -> float:
        """计算安全分数（0-100）"""
        penalty = sum({
            Severity.CRITICAL: 30,
            Severity.HIGH: 15,
            Severity.MEDIUM: 5,
            Severity.LOW: 2,
            Severity.INFO: 0,
        }.get(i.severity, 0) for i in issues)
        return max(0, 100 - penalty)
```

### 4.2 前端改动

**新增组件:** `frontend/src/components/SecurityReport.vue`（约 150 行）

```
Props: projectId
功能:
├── 调用 GET /api/projects/:id/security
├── 安全分数（大数字，颜色编码）
├── 严重程度分布（横向柱状图，Critical/High/Medium/Low 各多少）
├── 问题列表
│   ├── 按严重程度排序
│   ├── 每个问题: 文件路径 + 行号 + 描述 + 修复建议
│   └── 可折叠查看代码片段
└── 「重新扫描」按钮
```

**修改文件:** `frontend/src/pages/ProjectDetailPage.vue`

```
改动: 新增「安全报告」tab
├── 渲染 SecurityReport 组件
├── 与「文件预览」「开发日志」并列
└── 项目完成后自动触发扫描
```

**新增端点:**

```python
@router.get("/api/projects/{project_id}/security")
async def security_scan(project_id: str):
    scanner = SecurityScanner()
    return scanner.scan_project(_resolve_project_dir(project_id))
```

---

## 5. 项目文档自动生成

### 5.1 后端实现

**新增文件:** `Blueprint/utils/doc_generator.py`

```python
class DocGenerator:
    def generate_readme(self, project_dir: str, requirement: str) -> str:
        """根据代码和需求生成 README.md"""
        files = self._scan_files(project_dir)
        tech_stack = self._detect_tech_stack(files)
        
        readme = f"""# {self._project_name(project_dir)}

## 简介
{requirement}

## 技术栈
{self._format_tech_stack(tech_stack)}

## 安装与运行
{self._generate_install_guide(tech_stack)}

## 项目结构
{self._generate_tree(project_dir)}

## API 文档
{self._generate_api_docs(files)}

## 开发说明
{self._generate_dev_guide(tech_stack)}
"""
        return readme
    
    def generate_api_docs(self, project_dir: str) -> dict:
        """生成 OpenAPI 文档"""
        # 扫描 Python 文件，提取 FastAPI/Flask 路由
        # 扫描 JS 文件，提取 Express 路由
        pass
    
    def generate_architecture_diagram(self, project_dir: str) -> str:
        """生成 Mermaid 架构图"""
        files = self._scan_files(project_dir)
        return self._files_to_mermaid(files)
```

### 5.2 前端改动

**新增组件:** `frontend/src/components/DocPreview.vue`（约 100 行）

```
Props: projectId
功能:
├── 调用 GET /api/projects/:id/docs
├── Tab 切换: README / API 文档 / 架构图
├── README 渲染为 HTML（Markdown → HTML）
├── API 文档用表格展示
├── 架构图用 Mermaid 渲染
└── 「下载文档」按钮（下载 .md 文件）
```

**修改文件:** `frontend/src/pages/ProjectDetailPage.vue`

```
改动: 新增「项目文档」tab
├── 渲染 DocPreview 组件
└── 项目完成后自动生成
```

**新增端点:**

```python
@router.get("/api/projects/{project_id}/docs")
async def get_docs(project_id: str):
    gen = DocGenerator()
    project_dir = _resolve_project_dir(project_id)
    meta = _read_meta(project_id)
    return {
        "readme": gen.generate_readme(project_dir, meta.get("requirement", "")),
        "api_docs": gen.generate_api_docs(project_dir),
        "architecture": gen.generate_architecture_diagram(project_dir),
    }
```

---

## 6. Webhook 通知

### 6.1 后端实现

**新增文件:** `Blueprint/utils/webhook.py`

```python
import httpx
import hashlib
import hmac

class WebhookManager:
    def __init__(self):
        self.webhooks: list[dict] = []
    
    async def notify(self, event: str, payload: dict):
        """发送 Webhook 通知"""
        for webhook in self.webhooks:
            if event in webhook.get("events", ["*"]):
                await self._send(webhook, event, payload)
    
    async def _send(self, webhook: dict, event: str, payload: dict):
        """发送单个 Webhook"""
        body = {
            "event": event,
            "timestamp": time.time(),
            "data": payload,
        }
        
        # 签名验证
        if webhook.get("secret"):
            body_str = json.dumps(body, ensure_ascii=False)
            signature = hmac.new(
                webhook["secret"].encode(),
                body_str.encode(),
                hashlib.sha256
            ).hexdigest()
        
        headers = {"Content-Type": "application/json"}
        if webhook.get("secret"):
            headers["X-Webhook-Signature"] = f"sha256={signature}"
        
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(webhook["url"], json=body, headers=headers)

# 支持的事件类型
EVENTS = {
    "project.completed": "项目完成",
    "project.failed": "项目失败",
    "project.started": "项目开始",
    "agent.error": "Agent 出错",
    "review.rejected": "审查拒绝",
}
```

### 6.2 前端改动

**修改文件:** `frontend/src/pages/SettingsPage.vue`

```
改动: 新增「Webhook 设置」区域
├── Webhook URL 输入框
├── 事件类型多选框（completed/failed/started/error）
├── Secret 输入框（签名验证）
├── 「测试」按钮（发送测试事件）
├── 「保存」按钮
└── 已保存的 Webhook 列表（可编辑/删除）
```

**新增端点:**

```python
# api/settings.py 新增
@router.get("/api/settings/webhooks")
@router.post("/api/settings/webhooks")
@router.delete("/api/settings/webhooks/{webhook_id}")
@router.post("/api/settings/webhooks/{webhook_id}/test")
```

---

## 7. CLI 工具

### 7.1 实现

**新增文件:** `Blueprint/cli.py`

```python
import click
import httpx
import websockets
import json

@click.group()
@click.option("--server", default="http://localhost:8080", help="Blueprint 服务器地址")
@click.option("--token", envvar="Blueprint_TOKEN", help="认证 Token")
@click.pass_context
def cli(ctx, server, token):
    ctx.ensure_object(dict)
    ctx.obj["server"] = server
    ctx.obj["token"] = token

@cli.command()
@click.argument("requirement")
@click.option("--wait", is_flag=True, help="等待完成")
@click.pass_context
def create(ctx, requirement, wait):
    """创建新项目"""
    server = ctx.obj["server"]
    token = ctx.obj["token"]
    
    # 创建项目
    resp = httpx.post(f"{server}/api/projects", 
                      json={"requirement": requirement},
                      headers={"Authorization": f"Bearer {token}"})
    project_id = resp.json()["id"]
    click.echo(f"项目已创建: {project_id}")
    
    if wait:
        # WebSocket 等待完成
        asyncio.run(_wait_for_completion(server, token, project_id))

@cli.command()
@click.argument("project_id")
@click.pass_context
def status(ctx, project_id):
    """查看项目状态"""
    server = ctx.obj["server"]
    token = ctx.obj["token"]
    
    resp = httpx.get(f"{server}/api/projects/{project_id}/state",
                     headers={"Authorization": f"Bearer {token}"})
    state = resp.json()
    click.echo(f"状态: {state['status']}")
    click.echo(f"迭代: {state['iteration']}/{state['max_iterations']}")

@cli.command()
@click.argument("project_id")
@click.option("--output", "-o", default=".", help="输出目录")
@click.pass_context
def download(ctx, project_id, output):
    """下载项目文件"""
    server = ctx.obj["server"]
    token = ctx.obj["token"]
    
    resp = httpx.get(f"{server}/api/projects/{project_id}/download",
                     headers={"Authorization": f"Bearer {token}"})
    # 保存 zip 文件
    Path(output).mkdir(exist_ok=True)
    (Path(output) / f"{project_id}.zip").write_bytes(resp.content)
    click.echo(f"已下载到 {output}/{project_id}.zip")

@cli.command()
@click.pass_context
def list_projects(ctx):
    """列出所有项目"""
    server = ctx.obj["server"]
    token = ctx.obj["token"]
    
    resp = httpx.get(f"{server}/api/projects",
                     headers={"Authorization": f"Bearer {token}"})
    for p in resp.json():
        click.echo(f"{p['id']}  {p['status']:10s}  {p['name']}")

def main():
    cli()

if __name__ == "__main__":
    main()
```

**在 `requirements.txt` 中新增:** `click`

**在 `pyproject.toml` 或 `setup.py` 中注册:**

```python
# entry_points
"console_scripts": [
    "Blueprint=Blueprint.cli:main",
]
```

### 7.2 前端改动

**无需前端改动。** CLI 是独立工具，通过 REST API 与后端通信。

---

## 8. 项目模板市场

### 8.1 后端实现

**新增文件:** `Blueprint/templates/registry.py`

```python
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent / "presets"

class TemplateRegistry:
    def __init__(self):
        self.templates = self._load_templates()
    
    def _load_templates(self) -> dict:
        """从 presets/ 目录加载模板"""
        templates = {}
        for template_dir in TEMPLATES_DIR.iterdir():
            if template_dir.is_dir():
                meta_file = template_dir / "meta.json"
                if meta_file.exists():
                    meta = json.loads(meta_file.read_text())
                    templates[meta["id"]] = {
                        "id": meta["id"],
                        "name": meta["name"],
                        "description": meta["description"],
                        "category": meta["category"],
                        "files": self._list_template_files(template_dir),
                        "preview_image": meta.get("preview_image"),
                    }
        return templates
    
    def get_template(self, template_id: str) -> dict:
        """获取模板内容"""
        template_dir = TEMPLATES_DIR / template_id
        files = {}
        for f in template_dir.rglob("*"):
            if f.is_file() and f.name != "meta.json":
                files[str(f.relative_to(template_dir))] = f.read_text("utf-8")
        return files
    
    def list_templates(self, category: str = None) -> list:
        """列出模板"""
        templates = list(self.templates.values())
        if category:
            templates = [t for t in templates if t["category"] == category]
        return templates
```

### 8.2 前端改动

**新增页面:** `frontend/src/pages/TemplatesPage.vue`（约 200 行）

```
路由: /templates
功能:
├── 模板分类导航（全部 / Web应用 / API / 移动端 / 工具）
├── 模板卡片网格
│   ├── 预览图
│   ├── 模板名称
│   ├── 描述
│   ├── 技术栈标签
│   └── 「使用此模板」按钮
├── 模板详情弹窗
│   ├── 文件结构预览
│   ├── 每个文件的内容预览
│   └── 「创建项目」按钮（跳转到工作台，预填模板）
└── 搜索框
```

**新增组件:** `frontend/src/components/TemplateCard.vue`（约 60 行）

```
Props: template
功能:
├── 展示模板预览图（或默认图标）
├── 名称 + 描述
├── 技术栈标签
└── 点击事件 → 打开详情
```

**修改文件:** `frontend/src/router.js`

```
新增路由: /templates → TemplatesPage.vue
```

**修改文件:** `frontend/src/App.vue`

```
导航栏新增「模板」链接
```

**新增端点:**

```python
@router.get("/api/templates")
@router.get("/api/templates/{template_id}")
```

---

## 9. 知识库集成

### 9.1 后端实现

**新增文件:** `Blueprint/knowledge/base.py`

```python
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

class KnowledgeBase:
    def __init__(self, persist_dir: str = "Blueprint/data/knowledge"):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.embeddings = OpenAIEmbeddings()
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
        )
    
    def add_document(self, doc_id: str, content: str, metadata: dict = None):
        """添加文档到知识库"""
        chunks = self.splitter.split_text(content)
        metadatas = [{"doc_id": doc_id, **(metadata or {})} for _ in chunks]
        
        vectorstore = Chroma.from_texts(
            chunks,
            self.embeddings,
            metadatas=metadatas,
            persist_directory=str(self.persist_dir),
        )
    
    def query(self, query: str, k: int = 5) -> list[dict]:
        """查询相关文档"""
        vectorstore = Chroma(
            persist_directory=str(self.persist_dir),
            embedding_function=self.embeddings,
        )
        results = vectorstore.similarity_search_with_score(query, k=k)
        return [
            {"content": doc.page_content, "metadata": doc.metadata, "score": score}
            for doc, score in results
        ]
    
    def get_context(self, requirement: str) -> str:
        """获取需求相关的知识库上下文"""
        results = self.query(requirement, k=3)
        if not results:
            return ""
        
        context = "相关技术文档参考:\n"
        for r in results:
            context += f"\n---\n{r['content']}\n"
        return context
```

### 9.2 集成到 Agent（不改流程）

```python
# agents/pm.py 或 agents/developer.py 中
async def developer_agent(state):
    # 新增: 获取知识库上下文（如果有的话）
    knowledge_context = ""
    try:
        kb = KnowledgeBase()
        knowledge_context = kb.get_context(state["requirement"])
    except Exception:
        pass  # 知识库不可用时跳过
    
    # 将知识库上下文注入 prompt
    prompt = build_developer_prompt(state)
    if knowledge_context:
        prompt += f"\n\n{knowledge_context}"
    
    # ... 后续逻辑不变 ...
```

### 9.3 前端改动

**修改文件:** `frontend/src/pages/SettingsPage.vue`

```
改动: 新增「知识库」设置区域
├── 上传文档按钮（支持 .md / .txt / .pdf / .docx）
├── 已上传文档列表
│   ├── 文档名
│   ├── 大小
│   ├── 上传时间
│   └── 删除按钮
├── 「清空知识库」按钮
└── 状态显示（文档数、chunk 数）
```

**新增端点:**

```python
@router.post("/api/knowledge/upload")
@router.get("/api/knowledge/list")
@router.delete("/api/knowledge/{doc_id}")
@router.post("/api/knowledge/query")  # 测试查询
```

---

## 10. 部署脚本生成

### 10.1 后端实现

**新增文件:** `Blueprint/utils/deploy_generator.py`

```python
class DeployGenerator:
    """根据项目类型自动生成部署配置"""
    
    def generate(self, project_dir: str, project_type: str = "auto") -> dict:
        """生成所有部署文件"""
        if project_type == "auto":
            project_type = self._detect_type(project_dir)
        
        files = {}
        
        # Docker
        files["Dockerfile"] = self._generate_dockerfile(project_type)
        files["docker-compose.yml"] = self._generate_compose(project_type)
        files[".dockerignore"] = self._generate_dockerignore()
        
        # Nginx（Web 应用）
        if project_type in ("flask", "fastapi", "vue", "react", "static"):
            files["nginx.conf"] = self._generate_nginx(project_type)
        
        # CI/CD
        files[".github/workflows/deploy.yml"] = self._generate_github_actions(project_type)
        
        # 启动脚本
        files["start.sh"] = self._generate_start_script(project_type)
        if sys.platform == "win32":
            files["start.bat"] = self._generate_start_bat(project_type)
        
        return files
    
    def _detect_type(self, project_dir: str) -> str:
        """自动检测项目类型"""
        files = list(Path(project_dir).rglob("*"))
        
        if any(f.name == "manage.py" for f in files):
            return "django"
        if any(f.name == "app.py" or f.name == "main.py" for f in files):
            # 检查是否用了 Flask/FastAPI
            for f in files:
                if f.suffix == ".py":
                    content = f.read_text("utf-8", errors="replace")
                    if "from flask" in content.lower():
                        return "flask"
                    if "from fastapi" in content.lower():
                        return "fastapi"
            return "python"
        if any(f.name == "package.json" for f in files):
            return "node"
        if any(f.name == "go.mod" for f in files):
            return "go"
        return "static"
    
    def _generate_dockerfile(self, project_type: str) -> str:
        """生成 Dockerfile"""
        templates = {
            "flask": """FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["python", "app.py"]
""",
            "fastapi": """FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
""",
            "node": """FROM node:20-alpine
WORKDIR /app
COPY package*.json .
RUN npm ci
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npm", "start"]
""",
            "static": """FROM nginx:alpine
COPY . /usr/share/nginx/html
EXPOSE 80
""",
        }
        return templates.get(project_type, templates["static"])
    
    def _generate_compose(self, project_type: str) -> str:
        """生成 docker-compose.yml"""
        services = {
            "app": {
                "build": ".",
                "ports": ["${PORT:-8080}:${PORT:-8080}"],
                "restart": "unless-stopped",
            }
        }
        
        if project_type in ("flask", "fastapi", "django"):
            services["db"] = {
                "image": "postgres:16-alpine",
                "environment": {
                    "POSTGRES_DB": "app",
                    "POSTGRES_USER": "app",
                    "POSTGRES_PASSWORD": "${DB_PASSWORD}",
                },
                "volumes": ["db_data:/var/lib/postgresql/data"],
            }
            services["app"]["depends_on"] = ["db"]
        
        return yaml.dump({"services": services, "volumes": {"db_data": None}}, 
                         default_flow_style=False)
```

### 10.2 前端改动

**新增组件:** `frontend/src/components/DeployPanel.vue`（约 150 行）

```
Props: projectId
功能:
├── 调用 GET /api/projects/:id/deploy
├── 项目类型自动检测结果
├── 生成的文件列表
│   ├── Dockerfile（语法高亮预览）
│   ├── docker-compose.yml（预览）
│   ├── nginx.conf（预览）
│   ├── .github/workflows/deploy.yml（预览）
│   └── start.sh / start.bat（预览）
├── 「一键复制」按钮（复制单个文件内容）
├── 「全部下载」按钮（zip 打包）
└── 「自定义」按钮（修改端口、环境变量等参数后重新生成）
```

**修改文件:** `frontend/src/pages/ProjectDetailPage.vue`

```
改动: 新增「部署配置」tab
├── 渲染 DeployPanel 组件
├── 项目完成后可查看/下载部署文件
└── 与「文件预览」「安全报告」并列
```

**新增端点:**

```python
@router.get("/api/projects/{project_id}/deploy")
async def generate_deploy_files(project_id: str, project_type: str = "auto"):
    gen = DeployGenerator()
    project_dir = _resolve_project_dir(project_id)
    files = gen.generate(project_dir, project_type)
    return {"files": files, "detected_type": gen._detect_type(project_dir)}
```

---

## 11. API 开放平台

### 11.1 后端实现

**新增文件:** `Blueprint/api/public.py`

```python
from fastapi import APIRouter, Depends, Header
from typing import Optional

router = APIRouter(prefix="/api/v1", tags=["public"])

class APIKeyAuth:
    """API Key 认证"""
    def __init__(self):
        self.api_keys: dict[str, dict] = {}  # key -> {user_id, quota, ...}
    
    async def verify(self, x_api_key: str = Header(...)):
        if x_api_key not in self.api_keys:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return self.api_keys[x_api_key]

auth = APIKeyAuth()

@router.post("/projects")
async def create_project_api(
    requirement: str,
    template_id: str = None,
    user=Depends(auth.verify),
):
    """API 创建项目（供第三方系统调用）"""
    # 创建项目
    project_id = f"api-{uuid4().hex[:12]}"
    
    # 启动 Agent 执行（异步）
    asyncio.create_task(run_project_async(project_id, requirement, template_id))
    
    return {"project_id": project_id, "status": "started"}

@router.get("/projects/{project_id}")
async def get_project_api(project_id: str, user=Depends(auth.verify)):
    """查询项目状态"""
    state = get_project_state(project_id)
    return {
        "project_id": project_id,
        "status": state["status"],
        "iteration": state["iteration"],
        "files": list(state.get("files", {}).keys()),
    }

@router.get("/projects/{project_id}/download")
async def download_project_api(project_id: str, user=Depends(auth.verify)):
    """下载项目文件"""
    # 返回 zip 文件
    pass

@router.post("/webhook/register")
async def register_webhook_api(
    url: str,
    events: list[str],
    user=Depends(auth.verify),
):
    """注册 Webhook（接收项目完成通知）"""
    pass
```

**API 文档:**

```yaml
# 自动生成 OpenAPI 文档
openapi: 3.0.0
info:
  title: Blueprint API
  version: 1.0.0
  description: |
    Blueprint 开放 API，允许第三方系统创建和管理 AI 开发项目。
    
    ## 认证
    所有请求需要在 Header 中携带 `X-API-Key`。
    
    ## 速率限制
    - 免费版: 10 次/分钟
    - Pro 版: 100 次/分钟
    - 企业版: 1000 次/分钟
```

### 11.2 前端改动

**新增页面:** `frontend/src/pages/ApiDocsPage.vue`（约 200 行）

```
路由: /api-docs
功能:
├── API 概览（版本、认证方式、速率限制）
├── 交互式 API 文档
│   ├── 每个端点的说明
│   ├── 请求参数表格
│   ├── 响应示例
│   └── 「Try it」按钮（直接调用 API）
├── API Key 管理
│   ├── 生成新 Key
│   ├── 列出已创建的 Key
│   ├── 查看使用统计
│   └── 删除 Key
├── 使用示例
│   ├── cURL 示例
│   ├── Python 示例
│   └── JavaScript 示例
└── Webhook 配置
```

**新增组件:** `frontend/src/components/ApiKeyManager.vue`（约 100 行）

```
功能:
├── API Key 列表（掩码显示，只显示前 8 位 + ...）
├── 「创建新 Key」按钮
├── 每个 Key 的使用统计（调用次数、最后使用时间）
├── 「复制」按钮（复制完整 Key）
├── 「删除」按钮（确认后删除）
└── 速率限制状态显示
```

**修改文件:** `frontend/src/App.vue`

```
导航栏新增「API 文档」链接
```

**新增端点:**

```python
# api/api_keys.py
@router.get("/api/v1/keys")
@router.post("/api/v1/keys")
@router.delete("/api/v1/keys/{key_id}")
@router.get("/api/v1/keys/{key_id}/usage")
```

---

## 12. 协作模式

### 12.1 后端实现

**新增文件:** `Blueprint/collaboration/session.py`

```python
import asyncio
from collections import defaultdict

class CollaborationSession:
    """多人协作会话"""
    
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.users: dict[str, dict] = {}  # user_id -> {name, cursor, selection}
        self.locks: dict[str, str] = {}   # file_path -> user_id（文件锁）
        self.changes: list[dict] = []     # 变更历史
        self._broadcast_queue = asyncio.Queue()
    
    def join(self, user_id: str, user_name: str):
        """用户加入协作"""
        self.users[user_id] = {
            "name": user_name,
            "cursor": None,
            "selection": None,
            "joined_at": time.time(),
        }
        self._broadcast({
            "type": "user_joined",
            "user_id": user_id,
            "user_name": user_name,
        })
    
    def leave(self, user_id: str):
        """用户离开"""
        # 释放所有文件锁
        self.locks = {k: v for k, v in self.locks.items() if v != user_id}
        del self.users[user_id]
        self._broadcast({"type": "user_left", "user_id": user_id})
    
    def lock_file(self, user_id: str, file_path: str) -> bool:
        """锁定文件（防止同时编辑）"""
        if file_path in self.locks:
            return False  # 已被其他用户锁定
        self.locks[file_path] = user_id
        self._broadcast({
            "type": "file_locked",
            "file_path": file_path,
            "user_id": user_id,
        })
        return True
    
    def unlock_file(self, user_id: str, file_path: str):
        """释放文件锁"""
        if self.locks.get(file_path) == user_id:
            del self.locks[file_path]
            self._broadcast({
                "type": "file_unlocked",
                "file_path": file_path,
            })
    
    def apply_change(self, user_id: str, file_path: str, 
                     operation: str, position: int, content: str):
        """应用变更（CRDT 简化版）"""
        change = {
            "user_id": user_id,
            "file_path": file_path,
            "operation": operation,  # insert / delete / replace
            "position": position,
            "content": content,
            "timestamp": time.time(),
        }
        self.changes.append(change)
        self._broadcast({
            "type": "file_changed",
            **change,
        })
    
    def update_cursor(self, user_id: str, file_path: str, position: int):
        """更新光标位置"""
        if user_id in self.users:
            self.users[user_id]["cursor"] = {"file": file_path, "position": position}
            self._broadcast({
                "type": "cursor_moved",
                "user_id": user_id,
                "file": file_path,
                "position": position,
            })
    
    def get_state(self) -> dict:
        """获取协作状态"""
        return {
            "users": self.users,
            "locks": self.locks,
            "recent_changes": self.changes[-100:],  # 最近 100 条变更
        }
```

**WebSocket 扩展:**

```python
# api/websocket.py 新增协作消息处理
async def handle_collaboration_message(ws, message, session):
    """处理协作相关消息"""
    msg_type = message.get("type")
    
    if msg_type == "collab_join":
        session.join(message["user_id"], message["user_name"])
        await ws.send_json({"type": "collab_state", "data": session.get_state()})
    
    elif msg_type == "collab_lock":
        success = session.lock_file(message["user_id"], message["file_path"])
        await ws.send_json({"type": "collab_lock_result", "success": success})
    
    elif msg_type == "collab_change":
        session.apply_change(
            message["user_id"], message["file_path"],
            message["operation"], message["position"], message["content"]
        )
    
    elif msg_type == "collab_cursor":
        session.update_cursor(message["user_id"], message["file_path"], message["position"])
```

### 12.2 前端改动

**新增组件:** `frontend/src/components/CollabPanel.vue`（约 120 行）

```
Props: projectId
功能:
├── 在线用户列表（头像 + 名字 + 状态）
├── 每个用户的光标位置（文件名 + 行号）
├── 文件锁状态（哪些文件被谁锁定）
├── 「邀请协作者」按钮（生成分享链接）
└── 协作消息流（谁在编辑什么）
```

**新增组件:** `frontend/src/components/CollabCursor.vue`（约 40 行）

```
Props: userName, color
功能:
├── 光标行的彩色标记
├── 用户名标签（悬浮在光标上方）
└── 选择区域高亮
```

**修改文件:** `frontend/src/composables/useWebSocket.js`

```
改动: 新增协作消息处理
├── collab_state → 初始化协作状态
├── user_joined / user_left → 更新在线用户
├── file_locked / file_unlocked → 更新锁状态
├── file_changed → 应用远程变更
├── cursor_moved → 更新远程光标
└── send: 发送 collab_join / collab_lock / collab_change / collab_cursor
```

**修改文件:** `frontend/src/pages/ProjectDetailPage.vue`

```
改动: 文件预览区域集成协作
├── 渲染 CollabPanel（右侧面板）
├── 编辑器中渲染 CollabCursor（其他用户光标）
├── 编辑文件时自动发送 collab_change
└── 打开文件时自动 collab_lock
```

**新增端点:**

```python
@router.get("/api/projects/{project_id}/collab/invite")
async def create_invite_link(project_id: str):
    """生成协作邀请链接"""
    token = create_collab_token(project_id)
    return {"invite_url": f"/collab/{token}"}
```

---

## 13. 项目评分与排行榜

### 13.1 后端实现

**新增文件:** `Blueprint/utils/ranking.py`

```python
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class ProjectScore:
    project_id: str
    user_id: str
    username: str
    name: str
    quality_score: float      # 代码质量分（0-100）
    complexity_score: float   # 需求复杂度分（0-100）
    speed_score: float        # 完成速度分（0-100）
    total_score: float        # 综合分（加权）
    iteration_count: int      # 迭代次数
    file_count: int           # 文件数
    created_at: str
    likes: int = 0
    views: int = 0

class RankingManager:
    def __init__(self, db_session):
        self.db = db_session
    
    async def calculate_score(self, project_id: str) -> ProjectScore:
        """计算项目综合评分"""
        # 1. 代码质量分（来自 QualityScorer）
        quality = await self._get_quality_score(project_id)
        
        # 2. 需求复杂度分（基于 Agent 输出的复杂度指标）
        complexity = await self._get_complexity_score(project_id)
        
        # 3. 速度分（基于完成时间 vs 需求复杂度）
        speed = await self._get_speed_score(project_id)
        
        # 加权计算
        total = quality * 0.4 + complexity * 0.3 + speed * 0.3
        
        return ProjectScore(
            project_id=project_id,
            total_score=round(total, 1),
            quality_score=quality,
            complexity_score=complexity,
            speed_score=speed,
        )
    
    async def get_ranking(self, period: str = "weekly", 
                          sort_by: str = "total_score",
                          limit: int = 50) -> list[ProjectScore]:
        """获取排行榜"""
        if period == "daily":
            since = datetime.now() - timedelta(days=1)
        elif period == "weekly":
            since = datetime.now() - timedelta(weeks=1)
        elif period == "monthly":
            since = datetime.now() - timedelta(days=30)
        else:
            since = datetime.min
        
        rows = await self.db.fetch_all("""
            SELECT ps.*, p.name, p.username, p.likes, p.views
            FROM project_scores ps
            JOIN projects p ON ps.project_id = p.id
            WHERE ps.created_at >= ?
            ORDER BY ps.{sort_by} DESC
            LIMIT ?
        """, [since, limit])
        
        return [ProjectScore(**row) for row in rows]
    
    async def like_project(self, project_id: str, user_id: str):
        """点赞项目"""
        # 防重复点赞
        existing = await self.db.fetch_one(
            "SELECT 1 FROM project_likes WHERE project_id=? AND user_id=?",
            [project_id, user_id]
        )
        if existing:
            return False
        
        await self.db.execute(
            "INSERT INTO project_likes (project_id, user_id) VALUES (?, ?)",
            [project_id, user_id]
        )
        await self.db.execute(
            "UPDATE projects SET likes = likes + 1 WHERE id = ?",
            [project_id]
        )
        return True
```

### 13.2 前端改动

**新增页面:** `frontend/src/pages/RankingPage.vue`（约 250 行）

```
路由: /ranking
功能:
├── 时间范围切换（今日 / 本周 / 本月 / 全部）
├── 排序方式（综合分 / 质量 / 复杂度 / 速度）
├── 排行榜表格
│   ├── 排名（1-3 名金银铜图标）
│   ├── 项目名称（可点击跳转详情）
│   ├── 用户名
│   ├── 综合分（大数字 + 等级标签）
│   ├── 三个维度分数（小型进度条）
│   ├── 迭代次数 / 文件数
│   ├── 点赞数
│   └── 「点赞」按钮
├── 排行榜统计卡片
│   ├── 总项目数
│   ├── 本周新增
│   ├── 平均质量分
│   └── 最高分项目
└── 侧边栏：我的项目排名
```

**新增组件:** `frontend/src/components/RankingCard.vue`（约 80 行）

```
Props: rank, project, sortBy
功能:
├── 排名图标（🥇🥈🥉 或数字）
├── 项目名称 + 用户名
├── 分数展示（根据 sortBy 突出显示对应维度）
├── 点赞按钮 + 计数
└── 点击跳转到项目详情
```

**新增组件:** `frontend/src/components/StatsCard.vue`（约 40 行）

```
Props: title, value, icon, color
功能:
├── 统计卡片（大数字 + 标题 + 图标）
└── 用于排行榜页面的统计区域
```

**修改文件:** `frontend/src/App.vue`

```
导航栏新增「排行榜」链接
```

**新增端点:**

```python
# api/ranking.py
@router.get("/api/ranking")
@router.get("/api/ranking/{project_id}/score")
@router.post("/api/ranking/{project_id}/like")
@router.get("/api/ranking/my")
```

---

## 14. 前端架构改造

### 14.1 当前问题

| 问题 | 说明 |
|------|------|
| ProjectDetailPage 过大 | 772 行，承担了太多职责 |
| Store 职责不清 | project.js 既管消息又管文件又管状态 |
| 组件通信复杂 | 父子组件传参层级过深 |
| 无全局错误处理 | API 错误散落在各处 |

### 14.2 改造方案

#### 14.2.1 拆分 ProjectDetailPage

```
当前: ProjectDetailPage.vue (772行)
拆分为:
├── ProjectDetailPage.vue (约 100 行)
│   └── 只负责 Tab 切换和布局
├── components/project/
│   ├── ProjectInfoCard.vue      (项目信息)
│   ├── ProjectFilesPanel.vue    (文件预览/下载)
│   ├── ProjectLogPanel.vue      (开发日志)
│   ├── ProjectTimeline.vue      (执行时间线)
│   ├── QualityScore.vue         (质量评分)        ← 新增
│   ├── DiffViewer.vue           (变更对比)        ← 新增
│   ├── SecurityReport.vue       (安全报告)        ← 新增
│   ├── DocPreview.vue           (项目文档)        ← 新增
│   └── AgentTracePanel.vue      (思考过程)        ← 新增
```

#### 14.2.2 Store 拆分

```
当前:
├── auth.js (25行)
├── project.js (115行)  ← 过大
└── websocket.js (9行)

目标:
├── auth.js (25行) — 不变
├── project.js (60行) — 只管项目元数据
├── chat.js (50行) — 只管消息和聊天
├── agent.js (40行) — 只管 Agent 状态和输出
├── files.js (30行) — 只管文件预览和下载
└── websocket.js (9行) — 不变
```

#### 14.2.3 全局错误处理

**新增文件:** `frontend/src/utils/errorHandler.js`

```javascript
// 全局错误处理器
export function setupErrorHandler(app) {
  app.config.errorHandler = (err, instance, info) => {
    console.error('Vue error:', err, info)
    // 上报到监控系统
    reportError(err, info)
  }
  
  // 未捕获的 Promise 错误
  window.addEventListener('unhandledrejection', (event) => {
    console.error('Unhandled rejection:', event.reason)
    reportError(event.reason)
  })
}
```

**新增组件:** `frontend/src/components/Toast.vue`（约 50 行）

```
功能:
├── 全局消息提示（成功/警告/错误/信息）
├── 自动消失（3秒）
├── 可手动关闭
├── 堆叠显示（多条消息同时出现）
└── 通过 eventBus 或 provide/inject 调用
```

#### 14.2.4 新增 Composable

**新增:** `frontend/src/composables/useNotification.js`

```javascript
import { ref } from 'vue'

const notifications = ref([])
let id = 0

export function useNotification() {
  function notify(message, type = 'info', duration = 3000) {
    const n = { id: ++id, message, type, visible: true }
    notifications.value.push(n)
    
    setTimeout(() => {
      n.visible = false
      setTimeout(() => {
        notifications.value = notifications.value.filter(x => x.id !== n.id)
      }, 300)
    }, duration)
  }
  
  return {
    notifications,
    success: (msg) => notify(msg, 'success'),
    error: (msg) => notify(msg, 'error'),
    warning: (msg) => notify(msg, 'warning'),
    info: (msg) => notify(msg, 'info'),
  }
}
```

**新增:** `frontend/src/composables/useLocalStorage.js`

```javascript
export function useLocalStorage(key, defaultValue) {
  const stored = localStorage.getItem(key)
  const data = ref(stored ? JSON.parse(stored) : defaultValue)
  
  watch(data, (val) => {
    localStorage.setItem(key, JSON.stringify(val))
  }, { deep: true })
  
  return data
}
```

### 14.3 新增 API 方法

**修改文件:** `frontend/src/api/index.js`

```javascript
// 新增: 质量评分
api.getQualityScore = (projectId) => request(`/api/projects/${projectId}/quality`)

// 新增: 变更对比
api.getDiff = (projectId, a, b) => request(`/api/projects/${projectId}/diff?a=${a}&b=${b}`)

// 新增: 安全扫描
api.getSecurityReport = (projectId) => request(`/api/projects/${projectId}/security`)

// 新增: 项目文档
api.getProjectDocs = (projectId) => request(`/api/projects/${projectId}/docs`)

// 新增: Agent 思考过程
api.getTraces = (projectId, agent, iteration) => {
  const params = new URLSearchParams()
  if (agent) params.set('agent', agent)
  if (iteration) params.set('iteration', iteration)
  return request(`/api/projects/${projectId}/traces?${params}`)
}

// 新增: 模板
api.getTemplates = (category) => request(`/api/templates${category ? `?category=${category}` : ''}`)
api.getTemplate = (id) => request(`/api/templates/${id}`)

// 新增: Webhook
api.getWebhooks = () => request('/api/settings/webhooks')
api.saveWebhook = (data) => request('/api/settings/webhooks', { method: 'POST', body: data })
api.deleteWebhook = (id) => request(`/api/settings/webhooks/${id}`, { method: 'DELETE' })
api.testWebhook = (id) => request(`/api/settings/webhooks/${id}/test`, { method: 'POST' })

// 新增: 知识库
api.uploadKnowledge = (file) => {
  const form = new FormData()
  form.append('file', file)
  return request('/api/knowledge/upload', { method: 'POST', body: form })
}
api.getKnowledgeList = () => request('/api/knowledge/list')
api.deleteKnowledge = (docId) => request(`/api/knowledge/${docId}`, { method: 'DELETE' })
```

---

## 15. 实施优先级

### 第一批: 增强体验（1-2 周）

| # | 功能 | 前端改动 | 后端改动 | 工作量 |
|---|------|---------|---------|--------|
| 1 | 代码质量评分 | +QualityScore 组件 | +quality_scorer.py | 2 天 |
| 2 | 变更历史对比 | +DiffViewer 组件 | +diff_engine.py | 3 天 |
| 3 | Agent 思考过程 | +AgentTracePanel 组件 | +AgentTrace 类 | 2 天 |

### 第二批: 安全与文档（1-2 周）

| # | 功能 | 前端改动 | 后端改动 | 工作量 |
|---|------|---------|---------|--------|
| 4 | 代码安全扫描 | +SecurityReport 组件 | +security_scanner.py | 3 天 |
| 5 | 项目文档生成 | +DocPreview 组件 | +doc_generator.py | 2 天 |
| 6 | Webhook 通知 | SettingsPage 扩展 | +webhook.py | 2 天 |
| 7 | 部署脚本生成 | +DeployPanel 组件 | +deploy_generator.py | 2 天 |

### 第三批: 平台化（2-3 周）

| # | 功能 | 前端改动 | 后端改动 | 工作量 |
|---|------|---------|---------|--------|
| 8 | API 开放平台 | +ApiDocsPage + ApiKeyManager | +api/public.py | 3 天 |
| 9 | 项目评分排行榜 | +RankingPage + RankingCard | +ranking.py | 3 天 |
| 10 | CLI 工具 | 无 | +cli.py | 2 天 |

### 第四批: 协作与生态（3-4 周）

| # | 功能 | 前端改动 | 后端改动 | 工作量 |
|---|------|---------|---------|--------|
| 11 | 协作模式 | +CollabPanel + CollabCursor | +collaboration/ | 5 天 |
| 12 | 项目模板市场 | +TemplatesPage + TemplateCard | +template_registry | 3 天 |
| 13 | 知识库集成 | SettingsPage 扩展 | +knowledge/base.py | 5 天 |

### 第五批: 架构升级（2-3 周）

| # | 功能 | 前端改动 | 后端改动 | 工作量 |
|---|------|---------|---------|--------|
| 14 | 前端拆分重构 | ProjectDetailPage 拆分 + Store 拆分 | 无 | 3 天 |
| 15 | 全局错误处理 | +Toast + errorHandler | 无 | 1 天 |

---

## 附录: 文件变更汇总

### 新增文件

| 文件 | 类型 | 行数估算 |
|------|------|---------|
| `Blueprint/utils/quality_scorer.py` | 后端 | ~150 |
| `Blueprint/utils/diff_engine.py` | 后端 | ~120 |
| `Blueprint/utils/security_scanner.py` | 后端 | ~200 |
| `Blueprint/utils/doc_generator.py` | 后端 | ~150 |
| `Blueprint/utils/webhook.py` | 后端 | ~80 |
| `Blueprint/utils/deploy_generator.py` | 后端 | ~200 |
| `Blueprint/utils/ranking.py` | 后端 | ~150 |
| `Blueprint/cli.py` | 后端 | ~150 |
| `Blueprint/knowledge/base.py` | 后端 | ~100 |
| `Blueprint/templates/registry.py` | 后端 | ~80 |
| `Blueprint/api/public.py` | 后端 | ~120 |
| `Blueprint/collaboration/session.py` | 后端 | ~150 |
| `frontend/src/components/QualityScore.vue` | 前端 | ~120 |
| `frontend/src/components/DiffViewer.vue` | 前端 | ~150 |
| `frontend/src/components/AgentTracePanel.vue` | 前端 | ~200 |
| `frontend/src/components/SecurityReport.vue` | 前端 | ~150 |
| `frontend/src/components/DocPreview.vue` | 前端 | ~100 |
| `frontend/src/components/DeployPanel.vue` | 前端 | ~150 |
| `frontend/src/components/CollabPanel.vue` | 前端 | ~120 |
| `frontend/src/components/CollabCursor.vue` | 前端 | ~40 |
| `frontend/src/components/TemplateCard.vue` | 前端 | ~60 |
| `frontend/src/components/RankingCard.vue` | 前端 | ~80 |
| `frontend/src/components/StatsCard.vue` | 前端 | ~40 |
| `frontend/src/components/ApiKeyManager.vue` | 前端 | ~100 |
| `frontend/src/components/Toast.vue` | 前端 | ~50 |
| `frontend/src/pages/TemplatesPage.vue` | 前端 | ~200 |
| `frontend/src/pages/RankingPage.vue` | 前端 | ~250 |
| `frontend/src/pages/ApiDocsPage.vue` | 前端 | ~200 |
| `frontend/src/composables/useNotification.js` | 前端 | ~30 |
| `frontend/src/composables/useLocalStorage.js` | 前端 | ~15 |
| `frontend/src/utils/errorHandler.js` | 前端 | ~20 |
| `frontend/src/components/project/` (9个) | 前端 | ~600 |

### 修改文件

| 文件 | 改动内容 |
|------|---------|
| `Blueprint/agents/graph.py` | deliver_node 加快照保存 |
| `Blueprint/agents/developer.py` | 加 trace 记录 |
| `Blueprint/agents/tester.py` | 加 trace 记录 |
| `Blueprint/agents/reviewer.py` | 加 trace 记录 |
| `Blueprint/api/projects.py` | 新增 7 个端点（quality/diff/security/docs/deploy/collab/invite） |
| `Blueprint/api/settings.py` | 新增 webhook 端点 |
| `Blueprint/api/websocket.py` | 新增协作消息处理 |
| `Blueprint/utils/memory.py` | 新增 AgentTrace 类 |
| `frontend/src/pages/ProjectDetailPage.vue` | 拆分为子组件 + 新增 5 个 tab + 协作集成 |
| `frontend/src/pages/SettingsPage.vue` | 新增 Webhook + 知识库区域 |
| `frontend/src/stores/project.js` | 拆分为 project + chat + agent + files |
| `frontend/src/components/AgentCard.vue` | 加「查看思考过程」按钮 |
| `frontend/src/api/index.js` | 新增 20+ 个 API 方法 |
| `frontend/src/router.js` | 新增 /templates /ranking /api-docs 路由 |
| `frontend/src/App.vue` | 导航栏加「模板」「排行榜」「API 文档」链接 |
| `frontend/src/composables/useWebSocket.js` | 新增协作消息处理 |
| `requirements.txt` | 新增 click, chromadb, httpx, pyyaml |
