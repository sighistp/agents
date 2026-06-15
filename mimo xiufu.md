# Blueprint 企业级落地方案

> **项目:** Blueprint — 多 Agent 协同 AI 开发团队
> **编写日期:** 2026-06-15
> **目标:** 从 MVP 升级到可部署、可运维、可扩展的企业级系统
> **当前状态:** 323+ 测试全过，核心功能跑通，但存在安全隐患、架构瓶颈、运维缺失

---

## 目录

1. [安全加固](#1-安全加固)
2. [基础设施升级](#2-基础设施升级)
3. [LLM 运维体系](#3-llm-运维体系)
4. [可观测性](#4-可观测性)
5. [多租户与权限](#5-多租户与权限)
6. [扩展性设计](#6-扩展性设计)
7. [实施路线图](#7-实施路线图)
8. [风险清单](#8-风险清单)

---

## 1. 安全加固

### 1.1 认证与密钥管理

**现状:**
- JWT Secret 自动生成 + 文件持久化（`.Blueprint_secret`）
- API Key 明文存 `.env`

**目标方案:**

| 层级 | 现状 | 企业级方案 | 优先级 |
|------|------|-----------|--------|
| JWT Secret | 文件存储 | 环境变量注入，生产用 Vault | P0 |
| API Key | .env 明文 | AWS Secrets Manager / HashiCorp Vault | P0 |
| Token 过期 | 无过期 | Access Token 15min + Refresh Token 7d | P0 |
| 密码存储 | 需确认 | bcrypt 哈希 + salt | P0 |

**实施细节:**

```python
# config.py 改造
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 密钥从环境变量读取，不落盘
    jwt_secret: str  # 必须从 Blueprint_JWT_SECRET 环境变量读取
    llm_api_key: str  # 必须从 Blueprint_LLM_API_KEY 环境变量读取
    
    # 生产环境禁用默认值
    model_config = SettingsConfigDict(
        env_prefix="Blueprint_",
        env_file=".env",  # 仅开发环境
    )
```

**JWT 改造:**

```python
# auth.py
from datetime import datetime, timedelta

ACCESS_TOKEN_EXPIRE = timedelta(minutes=15)
REFRESH_TOKEN_EXPIRE = timedelta(days=7)

def create_access_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.utcnow() + ACCESS_TOKEN_EXPIRE,
        "type": "access"
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")

def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.utcnow() + REFRESH_TOKEN_EXPIRE,
        "type": "refresh"
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
```

### 1.2 沙箱隔离

**现状:** subprocess 直接执行，无资源限制

**目标方案:**

| 方案 | 隔离度 | 复杂度 | 适用场景 |
|------|--------|--------|---------|
| subprocess + cgroup | 中 | 低 | 开发/测试 |
| Docker 容器 | 高 | 中 | 生产环境 |
| gVisor/Firecracker | 最高 | 高 | 多租户/不可信代码 |

**Docker 沙箱实现:**

```python
# sandbox/docker_executor.py
import docker

client = docker.from_env()

def execute_in_sandbox(code: str, language: str, timeout: int = 30) -> dict:
    """在 Docker 容器中执行代码"""
    image = "Blueprint-sandbox:latest"
    
    container = client.containers.run(
        image,
        command=["python", "-c", code],
        detach=True,
        remove=True,
        network_mode="none",  # 禁用网络
        mem_limit="256m",     # 内存限制
        cpu_period=100000,
        cpu_quota=50000,      # 50% CPU
        read_only=True,       # 只读文件系统
        tmpfs={"/tmp": "size=100m"},  # 可写临时目录
        volumes={
            "/tmp/sandbox": {"bind": "/workspace", "mode": "rw"}
        }
    )
    
    try:
        result = container.wait(timeout=timeout)
        logs = container.logs().decode("utf-8", errors="replace")
        return {
            "success": result["StatusCode"] == 0,
            "stdout": logs,
            "stderr": "" if result["StatusCode"] == 0 else logs,
            "returncode": result["StatusCode"]
        }
    except Exception as e:
        container.kill()
        return {"success": False, "error": str(e)}
    finally:
        container.remove(force=True)
```

**Dockerfile:**

```dockerfile
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs npm && \
    rm -rf /var/lib/apt/lists/*
RUN useradd -m sandbox
USER sandbox
WORKDIR /workspace
```

### 1.3 输入安全

**现状:** 启发式注入检测（可绕过）

**企业级方案:**

| 防御层 | 措施 |
|--------|------|
| L1 前端 | DOMPurify 清理用户输入（已实现） |
| L2 API | Pydantic 严格 schema 校验 |
| L3 Agent | LLM Guard 输入检测 |
| L4 输出 | 代码静态分析 + 敏感信息扫描 |
| L5 沙箱 | 网络隔离 + 文件系统只读 |

**LLM Guard 集成:**

```python
# utils/guard.py 升级
from llm_guard import scan_prompt
from llm_guard.input_scanners import TokenLimit, NoRefusal, BanTopics

def check_prompt_safety(prompt: str) -> tuple[bool, str]:
    """使用 LLM Guard 检查输入安全性"""
    scanners = [
        TokenLimit(max_token_count=4096),
        NoRefusal(),
        BanTopics(topics=["violence", "self-harm", "illegal"]),
    ]
    sanitized, results = scan_prompt(scanners, prompt)
    
    for scanner_name, (is_valid, score) in results.items():
        if not is_valid:
            return False, f"输入安全检查失败: {scanner_name}"
    
    return True, sanitized
```

### 1.4 HTTPS & 传输安全

**Nginx 配置:**

```nginx
server {
    listen 443 ssl http2;
    server_name Blueprint.yourcompany.com;

    ssl_certificate /etc/ssl/certs/Blueprint.pem;
    ssl_certificate_key /etc/ssl/private/Blueprint.key;
    ssl_protocols TLSv1.2 TLSv1.3;

    # 安全头
    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options DENY always;
    add_header X-XSS-Protection "1; mode=block" always;

    location / {
        proxy_pass http://app:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 2. 基础设施升级

### 2.1 数据库迁移: SQLite → PostgreSQL

**现状:** SQLite 单文件，无并发写支持，无备份

**迁移方案:**

```python
# models.py — SQLAlchemy ORM
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Index
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase, relationship

class Base(DeclarativeBase):
    pass

class Project(Base):
    __tablename__ = "projects"
    
    id = Column(String(36), primary_key=True)  # UUID
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)
    requirement = Column(Text, nullable=False)
    status = Column(String(20), default="active")  # active/completed/failed
    current_step = Column(String(50))
    iteration = Column(Integer, default=0)
    created_at = Column(DateTime, server_default="now()")
    updated_at = Column(DateTime, server_default="now()", onupdate="now()")
    
    # 索引
    __table_args__ = (
        Index("idx_project_user", "user_id"),
        Index("idx_project_status", "status"),
    )

class AgentExecution(Base):
    __tablename__ = "agent_executions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    agent_name = Column(String(50), nullable=False)
    iteration = Column(Integer, nullable=False)
    input_summary = Column(Text)
    tool_calls = Column(Text)  # JSON
    result_summary = Column(Text)
    status = Column(String(20), default="success")
    created_at = Column(DateTime, server_default="now()")
    
    __table_args__ = (
        Index("idx_exec_project", "project_id", "agent_name", "iteration"),
    )

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    role = Column(String(20), nullable=False)  # user/assistant/tool
    name = Column(String(50))
    content = Column(Text, nullable=False)
    metadata = Column(Text)  # JSON: tool_calls, etc.
    created_at = Column(DateTime, server_default="now()")
    
    __table_args__ = (
        Index("idx_msg_project", "project_id"),
    )
```

**数据库连接池配置:**

```python
# database.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

DATABASE_URL = "postgresql+asyncpg://user:password@localhost:5432/Blueprint"

engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,        # 连接池大小
    max_overflow=10,     # 最大溢出连接
    pool_timeout=30,     # 连接超时
    pool_recycle=1800,   # 连接回收时间
    echo=False,          # 生产环境关闭 SQL 日志
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
```

**Alembic 迁移:**

```bash
# 初始化
alembic init alembic

# 生成迁移
alembic revision --autogenerate -m "initial schema"

# 执行迁移
alembic upgrade head
```

### 2.2 缓存层: Redis

**用途:**

| 缓存对象 | TTL | 说明 |
|----------|-----|------|
| LLM 响应 | 1h | 相同 prompt 不重复调用 |
| 用户 Session | 15min | Token 刷新 |
| API 限流计数 | 1min | 滑动窗口限流 |
| 项目状态 | 5min | 减少数据库查询 |

**实现:**

```python
# utils/cache.py
import redis.asyncio as redis
import json
from functools import wraps

redis_client = redis.from_url("redis://localhost:6379/0")

def cache_key(*args, **kwargs) -> str:
    """生成缓存 key"""
    return f"Blueprint:{hash(str(args) + str(sorted(kwargs.items())))}"

async def cached(ttl: int = 3600):
    """缓存装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            key = cache_key(func.__name__, *args, **kwargs)
            cached_value = await redis_client.get(key)
            if cached_value:
                return json.loads(cached_value)
            
            result = await func(*args, **kwargs)
            await redis_client.setex(key, ttl, json.dumps(result))
            return result
        return wrapper
    return decorator

# 使用示例
@cached(ttl=3600)
async def call_llm_cached(messages: list, model: str) -> str:
    """带缓存的 LLM 调用"""
    return await call_llm_async(messages, model)
```

**限流实现:**

```python
# utils/rate_limiter.py
import time

class SlidingWindowRateLimiter:
    def __init__(self, redis_client, max_requests: int, window_seconds: int):
        self.redis = redis_client
        self.max_requests = max_requests
        self.window = window_seconds
    
    async def is_allowed(self, key: str) -> bool:
        now = time.time()
        window_start = now - self.window
        
        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, self.window)
        
        results = await pipe.execute()
        request_count = results[2]
        
        return request_count <= self.max_requests

# 使用: 每用户每分钟最多 10 次请求
limiter = SlidingWindowRateLimiter(redis_client, max_requests=10, window_seconds=60)
```

### 2.3 Docker Compose 部署

**docker-compose.yml:**

```yaml
version: "3.8"

services:
  app:
    build: .
    ports:
      - "8080:8080"
    environment:
      - Blueprint_JWT_SECRET=${JWT_SECRET}
      - Blueprint_LLM_API_KEY=${LLM_API_KEY}
      - DATABASE_URL=postgresql+asyncpg://Blueprint:password@postgres:5432/Blueprint
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: Blueprint
      POSTGRES_USER: Blueprint
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U Blueprint"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  nginx:
    image: nginx:alpine
    ports:
      - "443:443"
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./certs:/etc/ssl/certs
    depends_on:
      - app

  # LLM Worker (异步任务队列)
  worker:
    build: .
    command: celery -A worker worker --loglevel=info
    environment:
      - DATABASE_URL=postgresql+asyncpg://Blueprint:password@postgres:5432/Blueprint
      - REDIS_URL=redis://redis:6379/1
      - Blueprint_LLM_API_KEY=${LLM_API_KEY}
    depends_on:
      - postgres
      - redis

volumes:
  postgres_data:
  redis_data:
```

**Dockerfile:**

```dockerfile
FROM python:3.12-slim AS base

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl nodejs npm && \
    rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 应用代码
COPY Blueprint/ Blueprint/
COPY frontend/dist/ Blueprint/static/

# 非 root 用户
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

CMD ["python", "-m", "Blueprint.start"]
```

---

## 3. LLM 运维体系

### 3.1 模型路由与容灾

**现状:** 单模型 DeepSeek，无容灾

**目标:**

```
请求 → 模型路由器
         ├── 主力: DeepSeek v4 flash (成本低, 速度快)
         ├── 备用: MIMO v2.5 Pro (推理强)
         └── 兜底: GPT-4o (质量高, 成本高)
```

**实现:**

```python
# llm/router.py
from enum import Enum
import random

class ModelTier(Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    FALLBACK = "fallback"

class LLMRouter:
    def __init__(self):
        self.models = {
            ModelTier.PRIMARY: {
                "name": "deepseek-chat",
                "base_url": "https://api.deepseek.com",
                "weight": 0.7,  # 70% 流量
                "max_retries": 2,
            },
            ModelTier.SECONDARY: {
                "name": "mimo-v2.5-pro",
                "base_url": "https://token-plan-cn.xiaomimimo.com/v1",
                "weight": 0.2,  # 20% 流量
                "max_retries": 1,
            },
            ModelTier.FALLBACK: {
                "name": "gpt-4o",
                "base_url": "https://api.openai.com/v1",
                "weight": 0.1,  # 10% 流量
                "max_retries": 1,
            },
        }
        self.failure_counts = {tier: 0 for tier in ModelTier}
        self.circuit_breakers = {tier: False for tier in ModelTier}
    
    async def call(self, messages: list, **kwargs) -> str:
        """带容灾的 LLM 调用"""
        tiers = list(ModelTier)
        random.shuffle(tiers)  # 随机打散顺序
        
        for tier in tiers:
            if self.circuit_breakers[tier]:
                continue
            
            try:
                result = await self._call_model(tier, messages, **kwargs)
                self.failure_counts[tier] = 0  # 重置失败计数
                return result
            except Exception as e:
                self.failure_counts[tier] += 1
                if self.failure_counts[tier] >= 5:
                    self.circuit_breakers[tier] = True  # 熔断
                    logger.warning(f"模型 {tier.value} 熔断，5次失败")
                continue
        
        raise Exception("所有 LLM 模型均不可用")
```

### 3.2 Token 计量与成本控制

```python
# llm/metrics.py
import time
from dataclasses import dataclass, field
from collections import defaultdict

@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    model: str = ""
    agent: str = ""
    timestamp: float = field(default_factory=time.time)

class TokenMeter:
    """Token 计量器"""
    
    # 价格表 (USD per 1K tokens)
    PRICING = {
        "deepseek-chat": {"input": 0.00014, "output": 0.00028},
        "mimo-v2.5-pro": {"input": 0.0008, "output": 0.0032},
        "gpt-4o": {"input": 0.005, "output": 0.015},
    }
    
    def __init__(self):
        self.usages: list[TokenUsage] = []
        self.daily_cost: dict[str, float] = defaultdict(float)
    
    def record(self, usage: TokenUsage):
        """记录一次调用"""
        pricing = self.PRICING.get(usage.model, {"input": 0, "output": 0})
        usage.cost_usd = (
            usage.prompt_tokens / 1000 * pricing["input"] +
            usage.completion_tokens / 1000 * pricing["output"]
        )
        self.usages.append(usage)
        
        day = time.strftime("%Y-%m-%d")
        self.daily_cost[day] += usage.cost_usd
    
    def check_budget(self, daily_limit: float = 10.0) -> bool:
        """检查是否超预算"""
        today = time.strftime("%Y-%m-%d")
        return self.daily_cost[today] < daily_limit
    
    def get_report(self) -> dict:
        """生成使用报告"""
        total_cost = sum(u.cost_usd for u in self.usages)
        total_tokens = sum(u.total_tokens for u in self.usages)
        avg_latency = sum(u.latency_ms for u in self.usages) / len(self.usages) if self.usages else 0
        
        by_model = defaultdict(lambda: {"calls": 0, "tokens": 0, "cost": 0})
        for u in self.usages:
            by_model[u.model]["calls"] += 1
            by_model[u.model]["tokens"] += u.total_tokens
            by_model[u.model]["cost"] += u.cost_usd
        
        return {
            "total_calls": len(self.usages),
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 4),
            "avg_latency_ms": round(avg_latency, 1),
            "by_model": dict(by_model),
        }
```

### 3.3 Prompt 版本管理

```python
# prompts/manager.py
import json
from pathlib import Path
from datetime import datetime

class PromptManager:
    def __init__(self, prompts_dir: str = "prompts"):
        self.dir = Path(prompts_dir)
        self.dir.mkdir(exist_ok=True)
    
    def get_prompt(self, name: str, version: str = "latest") -> str:
        """获取 prompt"""
        if version == "latest":
            version = self._get_latest_version(name)
        
        prompt_file = self.dir / f"{name}_v{version}.txt"
        if not prompt_file.exists():
            raise FileNotFoundError(f"Prompt {name} v{version} not found")
        
        return prompt_file.read_text(encoding="utf-8")
    
    def save_prompt(self, name: str, content: str, changelog: str = "") -> str:
        """保存新版本 prompt"""
        version = self._get_next_version(name)
        prompt_file = self.dir / f"{name}_v{version}.txt"
        prompt_file.write_text(content, encoding="utf-8")
        
        # 记录变更日志
        log_file = self.dir / f"{name}_changelog.jsonl"
        entry = {
            "version": version,
            "timestamp": datetime.now().isoformat(),
            "changelog": changelog,
        }
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        
        return version
    
    def rollback(self, name: str, target_version: str):
        """回滚到指定版本"""
        source = self.dir / f"{name}_v{target_version}.txt"
        if not source.exists():
            raise FileNotFoundError(f"Version {target_version} not found")
        
        latest = self.dir / f"{name}_latest.txt"
        latest.write_text(source.read_text(encoding="utf-8"))
```

---

## 4. 可观测性

### 4.1 结构化日志

```python
# utils/logger.py 升级
import structlog
import logging

def setup_logging(level: str = "INFO"):
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )
    
    logging.basicConfig(level=level, format="%(message)s")

# 使用
logger = structlog.get_logger()

# Agent 执行日志
logger.info("agent_execution",
    agent="developer",
    project_id="proj-123",
    iteration=2,
    tool_calls=3,
    duration_ms=4500,
    tokens_used=1200,
)

# LLM 调用日志
logger.info("llm_call",
    model="deepseek-chat",
    prompt_tokens=800,
    completion_tokens=400,
    latency_ms=3200,
    cost_usd=0.0002,
)
```

### 4.2 Prometheus 指标

```python
# metrics/prometheus.py
from prometheus_client import Counter, Histogram, Gauge

# LLM 指标
llm_calls_total = Counter(
    "Blueprint_llm_calls_total",
    "Total LLM API calls",
    ["model", "agent", "status"]
)

llm_latency_seconds = Histogram(
    "Blueprint_llm_latency_seconds",
    "LLM API call latency",
    ["model"],
    buckets=[0.5, 1, 2, 5, 10, 30, 60]
)

llm_tokens_total = Counter(
    "Blueprint_llm_tokens_total",
    "Total tokens consumed",
    ["model", "type"]  # type: prompt/completion
)

llm_cost_usd = Counter(
    "Blueprint_llm_cost_usd_total",
    "Total LLM cost in USD",
    ["model"]
)

# Agent 指标
agent_executions_total = Counter(
    "Blueprint_agent_executions_total",
    "Total agent executions",
    ["agent", "status"]
)

agent_duration_seconds = Histogram(
    "Blueprint_agent_duration_seconds",
    "Agent execution duration",
    ["agent"],
    buckets=[1, 5, 10, 30, 60, 120]
)

# 项目指标
projects_total = Gauge(
    "Blueprint_projects_total",
    "Total projects",
    ["status"]
)

active_projects = Gauge(
    "Blueprint_active_projects",
    "Currently active projects"
)
```

### 4.3 OpenTelemetry 分布式追踪

```python
# tracing/setup.py
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource

def setup_tracing(service_name: str = "Blueprint"):
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    
    exporter = OTLPSpanExporter(endpoint="localhost:4317", insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    
    trace.set_tracer_provider(provider)
    return trace.get_tracer(service_name)

tracer = setup_tracing()

# 使用
async def run_agent(agent_name: str, state: dict):
    with tracer.start_as_current_span(f"agent.{agent_name}") as span:
        span.set_attribute("agent.name", agent_name)
        span.set_attribute("project.id", state.get("project_id"))
        
        result = await agent_function(state)
        
        span.set_attribute("agent.status", "success")
        span.set_attribute("agent.duration_ms", result.get("duration_ms"))
        return result
```

### 4.4 Grafana Dashboard

```json
{
  "dashboard": {
    "title": "Blueprint 监控面板",
    "panels": [
      {
        "title": "LLM 调用成功率",
        "type": "stat",
        "query": "rate(Blueprint_llm_calls_total{status='success'}[5m]) / rate(Blueprint_llm_calls_total[5m]) * 100"
      },
      {
        "title": "LLM 延迟分布",
        "type": "heatmap",
        "query": "histogram_quantile(0.95, rate(Blueprint_llm_latency_seconds_bucket[5m]))"
      },
      {
        "title": "Token 消耗趋势",
        "type": "graph",
        "query": "rate(Blueprint_llm_tokens_total[1h])"
      },
      {
        "title": "每日成本",
        "type": "graph",
        "query": "Blueprint_llm_cost_usd_total"
      },
      {
        "title": "活跃项目数",
        "type": "stat",
        "query": "Blueprint_active_projects"
      },
      {
        "title": "Agent 执行分布",
        "type": "piechart",
        "query": "Blueprint_agent_executions_total"
      }
    ]
  }
}
```

---

## 5. 多租户与权限

### 5.1 RBAC 权限模型

```python
# models/user.py
from enum import Enum

class Role(Enum):
    ADMIN = "admin"      # 管理员: 全部权限
    DEVELOPER = "developer"  # 开发者: 创建/编辑项目
    VIEWER = "viewer"    # 只读: 查看项目

class Permission(Enum):
    PROJECT_CREATE = "project:create"
    PROJECT_READ = "project:read"
    PROJECT_UPDATE = "project:update"
    PROJECT_DELETE = "project:delete"
    SETTINGS_READ = "settings:read"
    SETTINGS_UPDATE = "settings:update"
    USER_MANAGE = "user:manage"
    USAGE_VIEW = "usage:view"

# 权限矩阵
ROLE_PERMISSIONS = {
    Role.ADMIN: [
        Permission.PROJECT_CREATE, Permission.PROJECT_READ,
        Permission.PROJECT_UPDATE, Permission.PROJECT_DELETE,
        Permission.SETTINGS_READ, Permission.SETTINGS_UPDATE,
        Permission.USER_MANAGE, Permission.USAGE_VIEW,
    ],
    Role.DEVELOPER: [
        Permission.PROJECT_CREATE, Permission.PROJECT_READ,
        Permission.PROJECT_UPDATE,
        Permission.SETTINGS_READ,
    ],
    Role.VIEWER: [
        Permission.PROJECT_READ,
        Permission.SETTINGS_READ,
    ],
}
```

### 5.2 配额管理

```python
# models/quota.py
from dataclasses import dataclass

@dataclass
class Quota:
    max_projects: int = 10
    max_concurrent_projects: int = 3
    max_llm_calls_per_day: int = 1000
    max_tokens_per_day: int = 500000
    max_storage_mb: int = 1024

class QuotaManager:
    def __init__(self, db_session):
        self.db = db_session
    
    async def check_quota(self, user_id: str, action: str) -> bool:
        """检查用户配额"""
        quota = await self.get_user_quota(user_id)
        
        if action == "project:create":
            count = await self.count_projects(user_id)
            return count < quota.max_projects
        
        if action == "llm:call":
            usage = await self.get_daily_usage(user_id)
            return usage["llm_calls"] < quota.max_llm_calls_per_day
        
        return True
    
    async def record_usage(self, user_id: str, metric: str, value: int):
        """记录用量"""
        await self.db.execute(
            "INSERT INTO usage_logs (user_id, metric, value, created_at) "
            "VALUES (?, ?, ?, datetime('now'))",
            [user_id, metric, value]
        )
```

### 5.3 用量计费

```python
# billing/calculator.py
from decimal import Decimal

class BillingCalculator:
    # 计费规则
    PLANS = {
        "free": {
            "monthly_price": 0,
            "included_tokens": 100000,
            "overage_per_1k_tokens": Decimal("0.001"),
        },
        "pro": {
            "monthly_price": 29,
            "included_tokens": 1000000,
            "overage_per_1k_tokens": Decimal("0.0005"),
        },
        "enterprise": {
            "monthly_price": 299,
            "included_tokens": 10000000,
            "overage_per_1k_tokens": Decimal("0.0002"),
        },
    }
    
    def calculate_invoice(self, plan: str, tokens_used: int) -> dict:
        """计算账单"""
        plan_config = self.PLANS[plan]
        
        if tokens_used <= plan_config["included_tokens"]:
            overage = 0
        else:
            overage_tokens = tokens_used - plan_config["included_tokens"]
            overage = (overage_tokens / 1000) * plan_config["overage_per_1k_tokens"]
        
        total = Decimal(plan_config["monthly_price"]) + overage
        
        return {
            "plan": plan,
            "base_price": plan_config["monthly_price"],
            "tokens_used": tokens_used,
            "included_tokens": plan_config["included_tokens"],
            "overage_tokens": max(0, tokens_used - plan_config["included_tokens"]),
            "overage_cost": float(overage),
            "total": float(total),
        }
```

---

## 6. 扩展性设计

### 6.1 Agent 插件系统

```python
# agents/registry.py
from abc import ABC, abstractmethod
from typing import Type

class BaseAgent(ABC):
    """Agent 基类，第三方可继承"""
    
    @abstractmethod
    def name(self) -> str: ...
    
    @abstractmethod
    async def execute(self, state: dict) -> dict: ...
    
    @abstractmethod
    def tools(self) -> list: ...

class AgentRegistry:
    _agents: dict[str, Type[BaseAgent]] = {}
    
    @classmethod
    def register(cls, agent_class: Type[BaseAgent]):
        """注册 Agent"""
        cls._agents[agent_class.name()] = agent_class
        return agent_class
    
    @classmethod
    def get(cls, name: str) -> Type[BaseAgent]:
        """获取 Agent"""
        return cls._agents.get(name)
    
    @classmethod
    def list_all(cls) -> list[str]:
        """列出所有注册的 Agent"""
        return list(cls._agents.keys())

# 第三方 Agent 示例
@AgentRegistry.register
class GitAgent(BaseAgent):
    def name(self) -> str:
        return "git"
    
    async def execute(self, state: dict) -> dict:
        # 实现 Git 操作
        pass
    
    def tools(self) -> list:
        return ["git_commit", "git_push", "git_diff"]
```

### 6.2 工具市场

```python
# tools/marketplace.py
from dataclasses import dataclass
from typing import Callable

@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict
    handler: Callable
    category: str  # file, network, database, etc.
    author: str
    version: str

class ToolMarketplace:
    def __init__(self):
        self.tools: dict[str, ToolDefinition] = {}
    
    def publish(self, tool: ToolDefinition):
        """发布工具"""
        self.tools[tool.name] = tool
    
    def search(self, category: str = None, query: str = None) -> list[ToolDefinition]:
        """搜索工具"""
        results = list(self.tools.values())
        
        if category:
            results = [t for t in results if t.category == category]
        
        if query:
            results = [t for t in results if query.lower() in t.description.lower()]
        
        return results
    
    def install(self, tool_name: str, agent_name: str):
        """为 Agent 安装工具"""
        tool = self.tools[tool_name]
        # 将工具添加到 Agent 的工具列表
        pass
```

### 6.3 多语言模板

```python
# templates/registry.py
TEMPLATES = {
    "python-flask": {
        "name": "Python Flask Web 应用",
        "files": {
            "app.py": "templates/python-flask/app.py.j2",
            "requirements.txt": "templates/python-flask/requirements.txt.j2",
            "templates/index.html": "templates/python-flask/index.html.j2",
        },
        "commands": {
            "setup": "pip install -r requirements.txt",
            "run": "python app.py",
            "test": "pytest tests/",
        }
    },
    "react-spa": {
        "name": "React SPA 应用",
        "files": {
            "package.json": "templates/react/package.json.j2",
            "src/App.tsx": "templates/react/App.tsx.j2",
            "src/index.tsx": "templates/react/index.tsx.j2",
        },
        "commands": {
            "setup": "npm install",
            "run": "npm start",
            "test": "npm test",
        }
    },
    "vue-spa": {
        "name": "Vue 3 SPA 应用",
        "files": {
            "package.json": "templates/vue/package.json.j2",
            "src/App.vue": "templates/vue/App.vue.j2",
            "src/main.js": "templates/vue/main.js.j2",
        },
        "commands": {
            "setup": "npm install",
            "run": "npm run dev",
            "test": "npm test",
        }
    },
    "go-api": {
        "name": "Go REST API",
        "files": {
            "main.go": "templates/go/main.go.j2",
            "go.mod": "templates/go/go.mod.j2",
        },
        "commands": {
            "setup": "go mod tidy",
            "run": "go run .",
            "test": "go test ./...",
        }
    },
}
```

---

## 7. 实施路线图

### 第一阶段: 安全加固 + 基础设施（1-2 周）

```
Week 1:
├─ Day 1-2: JWT 改造 (access/refresh token, 环境变量注入)
├─ Day 3-4: Docker 沙箱 (Dockerfile + docker_executor.py)
├─ Day 5:   HTTPS + Nginx 配置
└─ Day 6-7: 数据库迁移 (SQLite → PostgreSQL + Alembic)

Week 2:
├─ Day 1-2: Redis 缓存层 (LLM 响应缓存, session)
├─ Day 3-4: Docker Compose 编排
├─ Day 5:   CI/CD (GitHub Actions)
└─ Day 6-7: 集成测试 + 修复
```

### 第二阶段: LLM 运维 + 可观测性（2-3 周）

```
Week 3:
├─ Day 1-3: 模型路由器 (多模型容灾, 熔断)
├─ Day 4-5: Token 计量 + 成本控制
└─ Day 6-7: Prompt 版本管理

Week 4:
├─ Day 1-2: 结构化日志 (structlog)
├─ Day 3-4: Prometheus 指标
├─ Day 5:   OpenTelemetry 追踪
└─ Day 6-7: Grafana Dashboard

Week 5:
├─ Day 1-3: 告警规则 (LLM 失败, 成本超预算)
├─ Day 4-5: 日志聚合 (ELK/Loki)
└─ Day 6-7: 性能测试 + 优化
```

### 第三阶段: 多租户 + 扩展性（3-4 周）

```
Week 6:
├─ Day 1-3: RBAC 权限模型
├─ Day 4-5: 多租户数据隔离
└─ Day 6-7: 配额管理

Week 7:
├─ Day 1-3: Agent 插件系统
├─ Day 4-5: 工具市场
└─ Day 6-7: 多语言模板

Week 8:
├─ Day 1-3: 用量计费
├─ Day 4-5: 管理后台
└─ Day 6-7: 文档 + 培训

Week 9:
├─ Day 1-5: 全面测试 (E2E + 安全 + 负载)
├─ Day 6-7: 上线准备 + 灰度发布
```

---

## 8. 风险清单

| # | 风险 | 影响 | 缓解措施 |
|---|------|------|---------|
| 1 | LLM API 不稳定 | Agent 执行失败 | 多模型容灾 + 重试 |
| 2 | 沙箱逃逸 | 安全漏洞 | Docker 隔离 + 网络禁用 |
| 3 | 成本失控 | 预算超支 | 每日限额 + 告警 |
| 4 | 数据泄露 | 合规风险 | 加密存储 + 审计日志 |
| 5 | 并发瓶颈 | 性能下降 | 连接池 + 异步架构 |
| 6 | 代码生成质量差 | 用户体验 | 测试验证 + 人工审查 |
| 7 | 多租户隔离不足 | 数据串租户 | 数据库级隔离 + Row-Level Security |

---

## 附录: 技术选型对比

### 数据库

| 选项 | 优点 | 缺点 | 适用 |
|------|------|------|------|
| SQLite | 简单, 零配置 | 无并发写, 无网络访问 | 开发/测试 |
| PostgreSQL | 功能全, 性能好 | 需运维 | 生产环境 |
| MySQL | 成熟, 生态好 | 功能不如 PG | 生产环境 |

### 缓存

| 选项 | 优点 | 缺点 | 适用 |
|------|------|------|------|
| Redis | 功能多, 性能好 | 需运维 | 生产环境 |
| Memcached | 简单, 高性能 | 功能少 | 纯缓存场景 |

### 消息队列

| 选项 | 优点 | 缺点 | 适用 |
|------|------|------|------|
| Celery + Redis | 功能全, 文档好 | 复杂 | 异步任务 |
| RQ | 简单 | 功能少 | 小规模 |
| BullMQ | 性能好 | Node.js 生态 | 前端任务 |

---

> **下一步:** 选择第一阶段的任务开始实施，建议从 JWT 改造 + Docker 沙箱开始。
