# Prompt Engineering — 5 Agent 推理策略优化

> 日期：2026-06-12
> 范围：5 个 Agent 的 system prompt 优化
> 策略：只改 prompt 文本，不改代码架构

## 一、目标

当前 5 个 Agent 的 prompt 缺少 L2 推理策略层：
- 无思维链（Chain of Thought）要求
- 无正负例（Good/Bad Examples）
- Tester 最薄弱（243 字），Developer 影响最大

优化后每个 prompt 统一结构：
1. **角色定义** — 一句话说清身份
2. **推理策略** — 分步骤引导 LLM 思考
3. **正负例** — 什么是好的/什么是坏的
4. **工具使用规则** — 怎么用工具
5. **输出要求** — 格式和质量标准

## 二、各 Agent 优化方案

### 通用：错误恢复指引（所有 Agent prompt 末尾）

```
## 错误恢复
如果你收到"上一次执行失败"的提示：
1. 先理解错误原因，不要重复同样的操作
2. 如果是格式错误，检查 JSON 结构
3. 如果是逻辑错误，换一种实现方式
4. 如果是工具调用错误，检查参数是否正确
```

### PM Agent（957 → ~1200 字）

**当前：** 有 6 步推理策略，无正负例
**新增：**
- 正例："做一个计算器" → 拆解为 US-001（加法）、US-002（减法）...
- 负例："做个好用的工具" → 太模糊，需要澄清
- 明确：简单需求（<15 字）直接拆解，不要求澄清

### Architect Agent（680 → ~1000 字）

**当前：** 有 4 阶段，无正负例，无思维链
**新增：**
- 思维链：先列约束 → 再选技术栈 → 再设计模块 → 最后输出
- ✅ 正例：前后端分离架构 + REST API + SQLite
- ❌ 负例：为简单计算器设计微服务架构（过度设计）
- 明确：MVP 阶段用最简方案，不要过度设计

### Developer Agent（507 → ~800 字）

**当前：** 只有规则和约束，无推理策略，无思维链
**新增：**
- 每轮决策框架（不是一次性输出，是 tool-calling 循环）：
  ```
  每轮调用工具前，先想：
  1. 我现在需要什么？（读文件？写文件？验证？）
  2. 这个工具调用能推进任务吗？
  3. 调用后我怎么判断成功/失败？
  ```
- ✅ 正例：index.html（结构）+ style.css（样式）+ app.js（逻辑），每个文件 < 100 行
- ❌ 负例：一个 index.html 包含 500 行 HTML+CSS+JS
- 工具使用策略：先 file_read 看现有代码，再 file_write，最后 execute_python 验证

### Tester Agent（243 → ~600 字）

**当前：** 最薄弱，只有基本规则
**新增：**
- 测试策略：先读代码理解逻辑 → 设计测试用例 → 逐个执行 → 汇总结果
- 测试用例设计方法：正常路径 + 边界条件 + 异常情况
- ✅ 正例：测试加法 1+1=2，测试除零报错，测试负数
- ❌ 负例：只测一个正常路径就说"测试通过"
- 测试失败时的输出示例（与 `_extract_test_passed` 对齐）：
  ```
  done(summary="2 passed, 1 failed: division(1,0) 返回 None 而非抛出异常，
  建议在 division 中加 if b==0: raise ValueError('除数不能为零')")
  ```

### Reviewer Agent（500 → ~800 字）

**当前：** 有审查维度，无思维链，无正负例
**新增：**
- 审查流程：先通读全部代码 → 逐文件审查 → 汇总问题 → 判定通过/不通过
- ✅ 正例："main.py:15 除零未处理，建议加 if 检查"
- ❌ 负例："代码有问题"（不给位置和建议）
- 通过标准与路由后果对齐：
  - `review_approved=true` → 代码进入交付
  - `review_approved=false` → 代码回到 Developer 重做
  - 无 critical 问题 → 通过；有 critical → 不通过
  - 明确告诉 Reviewer：你的判定直接决定流程走向

## 三、实施方式

直接修改 5 个 Agent 文件中的 `_SYSTEM_PROMPT` 常量。不改代码逻辑，不改工具定义，不改路由。

## 四、改动范围

| 文件 | 改什么 |
|------|--------|
| pm.py | PM_SYSTEM_PROMPT 加正负例 |
| architect.py | ARCHITECT_SYSTEM_PROMPT 加思维链 + 正负例 |
| developer.py | DEVELOPER_SYSTEM_PROMPT 加思维链 + 正负例 + 工具策略 |
| tester.py | TESTER_SYSTEM_PROMPT 全面重写（加策略 + 正负例） |
| reviewer.py | REVIEWER_SYSTEM_PROMPT 加审查流程 + 正负例 + 通过标准 |

## 五、测试策略

- 运行现有测试确认 prompt 修改不破坏功能
- 手动测试一个完整流程，观察 Agent 输出质量

## 六、不做的事

- ❌ 不改工具定义（tools.py）
- ❌ 不改代码逻辑（graph.py、developer.py 的 agent 函数）
- ❌ 不改 Proposer-Critic（discussion.py）
- ❌ 不改 Pydantic schema
