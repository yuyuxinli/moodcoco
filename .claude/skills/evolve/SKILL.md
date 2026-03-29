---
name: evolve
description: 定义目标，AI 自动构建、评估、迭代，直到达标。配合 /loop 1m /evolve 持续运行。
triggers:
  - /evolve
---

# Evolve: 定义目标 → 自动构建 → 自动评估 → 迭代达标

## 概述

三阶段自治循环：Init（交互式）→ Build → Eval（自动循环）。

- **Init**：本文件。用户参与，引导式配置。
- **Loop**：`loop.md`。AI 自动运行，用户不参与（通过 `/loop 1m /evolve` 驱动）。

硬依赖：Python 3.8+、Git。其他一切由项目 adapter 声明。

---

## 触发路由

```
/evolve 触发
    ↓
检查 .evolve/ 是否存在？
    ├─ 存在 → 恢复逻辑（见下表）
    └─ 不存在 → 首次引导（Step 1 开始）
```

### 恢复逻辑

| 检测到的状态 | 行为 |
|-------------|------|
| `.evolve/` 存在但无 `adapter.py` | 从 Step 3 开始 |
| `adapter.py` 有，`program.md` 无 | 从 Step 4 开始 |
| `program.md` 有，`spec.md` 无 | 从 Step 5 校验开始 |
| `spec.md` 有，`results.tsv` 空或不存在 | 提示直接启动循环 |
| `results.tsv` 有数据 | 展示进度报告，提示继续 |

---

## Init 引导流程

### Step 1 — 项目扫描（自动，无交互）

扫描语言、框架、测试框架、目录结构。输出简短总结：

> 「检测到 FastAPI + PostgreSQL 项目，有 pytest，入口在 app/main.py」

### Step 2 — 理解目标（1-2 个问题）

- 「你要构建/改进什么？一句话描述」
- 如果描述模糊：「核心功能有哪些？逐条说」

### Step 3 — 研究 Eval 标准 + 生成 Adapter（自动）

1. 根据产品类型 + 技术栈，研究业内评估方法
2. 读 `.claude/skills/evolve/adapters/base.py` 了解接口定义
3. 读 `.claude/skills/evolve/adapters/web_app.py` 或 `teaching.py` 作为参考实现
4. 自动生成项目专属 `.evolve/adapter.py` + `.evolve/eval.yml`

展示评估维度给用户确认：

```
建议评估维度：
1. 功能完整性 — deterministic, npm test, 门槛 7.0
2. 代码质量 — llm-judged, 门槛 7.0
3. 数据一致性 — deterministic, 集成测试, 门槛 7.0

要调整吗？
```

用户确认/调整 → 写入 `.evolve/eval.yml` 和 `.evolve/adapter.py`。

#### eval.yml 格式

```yaml
dimensions:
  - name: 功能完整性
    type: deterministic
    cmd: npm test
    threshold: 7.0
  - name: 代码质量
    type: llm-judged
    threshold: 7.0
```

#### adapter.py 接口

```python
prerequisites = [{"name": "node", "check": "node --version", ...}]

def setup(project_dir: str) -> dict:       # → {"status": "ready"|"crash", ...}
def run_checks(project_dir, feature) -> dict:  # → {"scores": {...}, "details": "..."}
def teardown(info: dict) -> None:
```

### Step 4 — 引导填写 program.md（逐字段交互）

基于前面已收集的信息，预填大部分字段。逐字段确认：

```markdown
# Program

## 产品需求
<!-- 已从 Step 2 收集 -->

## 技术约束
- 栈：<!-- 从 Step 1 扫描结果预填 -->
- 依赖限制：只使用指定技术栈和现有依赖
- 允许的新依赖：<!-- 用户确认 -->
- 禁区：<!-- 用户填 -->

## Agent 规则
- 不修改 program.md
- 不修改 .claude/skills/evolve/ 下的文件
- 不安装新包（除非上方允许）
- 每个功能一个 git commit
- 所有进程输出重定向到 .evolve/run.log
- 永不停止——循环直到所有功能 pass/skip 或人类中断
```

生成 `.evolve/program.md`。

### Step 5 — 校验（自动）

#### Level 1：结构校验（阻断）

| 检查项 | 规则 | 失败提示 |
|--------|------|---------|
| 产品需求 | 至少 1 条非空 | 「产品需求为空。描述一下你要构建什么？」 |
| 模板占位符 | 不含 `{{` 或 `[填写...]` | 「program.md 第 N 行还是占位符」 |
| adapter.py | 存在且可 import | 「adapter.py 加载失败：{错误}」 |
| eval.yml | 至少 1 个评估维度 | 「没有评估维度。重新运行 /evolve」 |

#### Level 2：语义校验（警告）

| 检查项 | 规则 | 警告 |
|--------|------|-----|
| 需求粒度 | 单条 > 200 字 | 「第 N 条需求过长，建议拆分」 |
| 评估阈值 | 1-10 范围内 | 「阈值 N 超出 1-10 范围」 |

#### Level 3：环境校验（信息）

```python
import sys
sys.path.insert(0, '.claude/skills/evolve')
from prepare import load_adapter, load_eval_config

# 校验 adapter
adapter = load_adapter(".evolve/adapter.py")

# 校验 eval.yml
dims = load_eval_config(".evolve/eval.yml")

# 检查 adapter prerequisites
for prereq in adapter.prerequisites:
    # 运行 prereq["check"]，失败 → 提示安装命令
```

输出：

```
✓ 产品需求: 5 条
✓ 评估维度: 3 个 (功能完整性, 代码质量, 数据一致性)
✓ adapter: 可加载
✓ python3 — 3.11.5
✓ git — 2.43.0
⚠ Git 工作区有未提交改动（建议先 commit）

校验通过，进入 Planner 阶段？(Y/n)
```

### Step 6 — 选择 Evaluator（一个问题）

「用什么做评估？」
- A. Codex（推荐，独立评估最客观）
- B. Claude（另开一个实例）
- C. 其他

将选择记录到 `.evolve/program.md` 的 `## 评估方式` 部分。

### Step 7 — Planner 生成 spec.md（自动）

1. 创建 git 分支：`git checkout -b evolve/<tag>`
2. 读 `.evolve/program.md` + `.evolve/eval.yml`
3. 生成 `.evolve/spec.md`（功能列表 + 验收标准）
4. 创建 `.evolve/results.tsv`（header 行）
5. 创建 `.evolve/run.log`（空）
6. 将 `.evolve/` 加入 `.gitignore`

展示 spec.md 给用户审阅。确认后：

```
Init 完成。运行 /loop 1m /evolve 启动自动循环。
```

---

## prepare.py 函数参考

```bash
python -c "import sys; sys.path.insert(0, '.claude/skills/evolve'); from prepare import <func>; ..."
```

| 函数 | 签名 | 说明 |
|------|------|------|
| `load_eval_config` | `(eval_yml_path) → list[dict]` | 解析 eval.yml，返回维度列表 |
| `load_adapter` | `(adapter_path) → module` | 从文件路径加载 adapter |
| `append_result` | `(results_tsv, row) → None` | 追加一行到 results.tsv |
| `read_progress` | `(results_tsv) → dict` | 读取当前进度和状态机状态 |
| `generate_report` | `(results_tsv) → str` | 生成结构化进度报告 |
| `acquire_lock` | `(evolve_dir) → dict` | 获取并发锁 |
| `update_lock` | `(evolve_dir, phase, feature) → None` | 更新心跳 |
| `release_lock` | `(evolve_dir) → None` | 释放锁 |
