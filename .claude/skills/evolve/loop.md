# Evolve Loop: Build → Eval 自动循环

本文件由 SKILL.md 的 Init 完成后加载。Agent 在自动循环中读此文件。

设计为配合 `/loop 1m /evolve` 使用——每轮是新会话，通过文件恢复上下文。

---

## 前置条件

每次 `/evolve` 被触发且 `.evolve/results.tsv` 存在时，进入此循环。

### 0. 并发锁

```python
import sys
sys.path.insert(0, '.claude/skills/evolve')
from prepare import acquire_lock, update_lock, release_lock

lock = acquire_lock(".evolve")
if not lock["acquired"]:
    print(f"⏳ {lock['reason']}")
    → 立即停止
```

每个关键步骤调用 `update_lock(".evolve", phase, feature)`。
完成时 `release_lock(".evolve")`。
崩溃后锁 2 分钟自动过期。

---

## 每轮必读清单

新会话，做任何判断前，**按顺序读取**：

| # | 文件 | 读取方式 | 目的 |
|---|------|---------|------|
| 1 | `.evolve/program.md` | 全文 | 用户策略和约束 |
| 2 | `.evolve/spec.md` | 全文 | 功能列表和验收标准 |
| 3 | `.evolve/eval.yml` | 全文 | 评估维度和阈值 |
| 4 | `.evolve/results.tsv` | 最后 10 行 | 当前进度 |
| 5 | `.evolve/evaluation.md` | 全文（如存在） | 上轮评审反馈 |
| 6 | git log --oneline -3 | 命令 | 最近改了什么 |

```python
from prepare import read_progress, load_eval_config, load_adapter

progress = read_progress(".evolve/results.tsv")
dimensions = load_eval_config(".evolve/eval.yml")
adapter = load_adapter(".evolve/adapter.py")
```

---

## 状态机路由

```python
if progress["phase"] == "init":
    → 说明 Init 未完成，提示运行 /evolve 重新初始化

elif progress["total_iterations"] >= 100:
    → Done Flow（全局上限）

elif progress["phase"] == "build":
    # 检查是否所有功能已完成/跳过
    # 读 spec.md 提取 spec_features
    # done = set(progress["completed_features"] + progress["skipped_features"])
    # if set(spec_features) <= done → Done Flow
    → Build Flow

elif progress["phase"] == "eval":
    → Eval Flow
```

### 尾行映射

```
没有数据行              → Init 未完成
plan/keep              → Build（取 spec 第一个功能）
build/keep             → Eval（当前功能完成，评审）
build/crash            → Build（读 run.log 修复；连续 crash ≥ 3 → skip）
contract/pass          → Build（开始编码）
contract/fail          → Build（重写 contract）
eval/pass              → Build（下一个未完成功能）
eval/fail              → Build（读 evaluation.md 修复；连续 fail > 3 → reset）
eval/skip              → Build（下一个未完成功能）
所有功能 pass/skip      → Done
全局迭代 ≥ 100         → Done
```

---

## Build Flow

### 选择功能

读 `.evolve/spec.md`，按顺序找第一个不在 `progress["completed_features"]` 且不在 `progress["skipped_features"]` 的功能。

### 新功能流程

1. 写 Sprint Contract（`.evolve/sprint_contract.md`）
2. 快速审核 contract
3. 记录 `contract/pass` 或 `contract/fail`
4. 开始编码

### 修复轮（eval/fail 后）

1. 读 `.evolve/evaluation.md` 的修复优先级
2. 按优先级修复
3. 直接编码（复用已有 contract）

### 编码规则

**输出隔离：**

```bash
# 所有构建/测试命令重定向到 run.log
npm run build > .evolve/run.log 2>&1
python -m pytest > .evolve/run.log 2>&1
```

- crash 时 `tail -n 50 .evolve/run.log` 诊断
- 不将原始长输出灌入 agent 上下文

**编码流程：**

1. 实现功能
2. `git add` + `git commit`（每个功能一个 commit）
3. 追加 results.tsv

**简单性原则：**

- 默认禁止新依赖（除非 program.md 允许）
- 同等达标选更简实现
- 删代码后效果不变 = 好结果

**成功记录：**

```python
from prepare import append_result
append_result(".evolve/results.tsv", {
    "commit": "<hash>", "phase": "build", "feature": "<name>",
    "scores": "-", "total": "-", "status": "keep",
    "summary": "implemented <brief>"
})
```

**Crash 记录：**

```python
append_result(".evolve/results.tsv", {
    "commit": "<hash>", "phase": "build", "feature": "<name>",
    "scores": "-", "total": "0", "status": "crash",
    "summary": "<error>"
})
```

### 失败处理

```
consecutive_crashes >= 3
  → skip, 继续下一功能

consecutive_fails <= 3
  → 读 evaluation.md 修复 → 重新 Build

consecutive_fails > 3 and not has_been_reset
  → git reset --hard <base_commit>
  → 记录 reset，允许重试 1 次

consecutive_fails > 3 and has_been_reset
  → skip（已重试仍失败）
```

---

## Eval Flow

### 环境准备

```python
env = adapter.setup(project_dir)
if env["status"] == "crash":
    append_result(..., status="crash", summary=f"setup failed: {env['error']}")
    → 返回 Build Flow
```

### 确定性评分

```python
check_result = adapter.run_checks(project_dir, feature)
deterministic_scores = check_result["scores"]
# e.g. {"测试通过率": 9.2}
```

### LLM 评审

读 `.evolve/program.md` 的评估方式：
- **Codex**：通过 codex CLI 调用
- **Claude**：spawn 独立 Agent
- **其他**：按 program.md 配置

评审 prompt 基于 eval.yml 的维度定义动态生成。只评 `type: llm-judged` 的维度。

评审输出写入 `.evolve/eval_codex.md`（或 `.evolve/eval_claude.md`）。

### 评分汇总

```python
final_scores = {}
for dim in dimensions:
    name = dim["name"]
    if dim["type"] == "deterministic":
        final_scores[name] = deterministic_scores.get(name, 0)
    else:
        final_scores[name] = llm_scores.get(name, 0)

# 判断：任一维度低于 threshold → fail
status = "pass"
for dim in dimensions:
    if final_scores.get(dim["name"], 0) < dim["threshold"]:
        status = "fail"
```

写汇总到 `.evolve/evaluation.md`，包含：
- 各维度分数和门槛
- PASS/FAIL 结论
- 修复优先级（红/黄/绿）

### 记录结果

```python
scores_str = "/".join(str(final_scores.get(d["name"], "-")) for d in dimensions)
total = round(sum(final_scores.values()) / len(final_scores), 1) if final_scores else 0

append_result(".evolve/results.tsv", {
    "commit": "<hash>", "phase": "eval", "feature": "<name>",
    "scores": scores_str, "total": str(total),
    "status": status,
    "summary": "all pass" if status == "pass" else "<维度> 低于门槛"
})
```

### 清理 + 更新报告

```python
adapter.teardown(env.get("info", {}))

from prepare import generate_report
report = generate_report(".evolve/results.tsv")
Path(".evolve/report.md").write_text(report)
```

---

## Done Flow

所有功能 pass/skip，或迭代达 100 轮：

```python
report = generate_report(".evolve/results.tsv")
release_lock(".evolve")
```

输出报告给用户，停止循环。

---

## Agent 规则

1. **不修改 program.md** — 人和 agent 的合约
2. **不修改 .claude/skills/evolve/ 下的文件** — 评估基础设施不可篡改
3. **不安装新包** — 除非 program.md 允许
4. **每个功能一个 commit**
5. **results.tsv 只追加**
6. **输出重定向到 .evolve/run.log**
7. **简单优先** — 同等效果选更简实现
8. **永不停止** — 直到所有功能 pass/skip 或人类中断。不问"是否继续"。
9. **可 spawn subagent** — 通过 Agent tool 并行处理独立子任务（限于不同文件）

---

## 文件权限矩阵

| 文件 | 人 | Planner | Generator | Evaluator |
|------|-----|---------|-----------|-----------|
| program.md | 读写 | 只读 | 只读 | 只读 |
| eval.yml | 读写 | 只读 | 只读 | 只读 |
| adapter.py | 读写 | 只读 | 只读 | 只读 |
| spec.md | 读 | 写 | 只读 | 只读 |
| results.tsv | 读 | 追加 | 追加 | 追加 |
| evaluation.md | 读 | - | 读 | 写 |
| run.log | 读 | - | 写 | 写 |
| 项目代码 | 读写 | - | 读写 | 只读 |
