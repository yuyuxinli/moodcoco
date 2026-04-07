# memU Fork 改动声明

> 上游仓库：https://github.com/nicepkg/memU
> Fork 时间：2026-04-05
> Fork 基准：memU main 分支最新版本

本项目 fork 了 memU 源码并做了以下修改，用于适配心情可可「关系智能」场景。
同步上游更新时，需要保留以下所有改动。

---

## 改动清单

### 1. `__init__.py` — Rust 扩展兼容

**原因**：memU 原版 `from memu._core import hello_from_bin` 需要编译 Rust pyo3 扩展，我们只用 Python 侧功能，不需要 Rust。

**改动**：`import` 用 `try-except ImportError` 包裹，fallback 到 `None`。`_rust_entry()` 在纯 Python 模式下返回提示字符串。

---

### 2. `app/settings.py` — Category 体系替换

**原因**：原版是 10 个通用英文 category（personal_info / preferences / relationships 等），不符合心情可可三维中文结构。

**改动**：替换 `default_categories()` 中的 category 列表为 5 个预定义 `self/*` 子 category：

| 原版 Category | 替换为 |
|--------------|--------|
| personal_info | self/核心信念 |
| preferences | self/行为模式 |
| relationships | self/价值观 |
| activities | self/情绪触发点 |
| goals | self/有效方法 |
| experiences, knowledge, opinions, habits, work_life | 删除（由 people/* 和 events/* 动态创建替代） |

---

### 3. `app/memorize.py` — 动态 Category 创建

**原因**：原版所有 category 必须预定义，无法处理 `people/妈妈`、`events/考研` 等用户特有的动态分类。

**改动**：
- `_persist_memory_items()` 中，静态映射失败后调用 `_ensure_dynamic_category()`
- 新增 `_ensure_dynamic_category()` 方法（约 48 行）：当 LLM 返回 `people/{name}` 或 `events/{name}` 格式时，自动创建对应 category 并更新运行时映射

---

### 4. `prompts/memory_type/profile.py` — 提取 Prompt 重写

**原因**：原版提取通用个人信息（英文），我们需要提取心理陪伴场景下的用户画像（中文）。

**改动**：重写整个 prompt，提取维度改为：
- 核心信念（关于自己的稳定看法）
- 情绪触发点（反复引发强烈情绪的情境）
- 沟通偏好（表达方式和沟通风格）
- 分配到 `self/*` 子 category

---

### 5. `prompts/memory_type/event.py` — 提取 Prompt 重写

**原因**：原版提取通用事件，我们需要区分人物关系事件和长周期事件，并支持多 category 分配。

**改动**：重写整个 prompt，提取维度改为：
- 人物关系事件（互动、冲突、支持）→ 分配到 `people/{人名}`
- 长周期事件进展（考研、求职、分手等）→ 分配到 `events/{事件名}`
- 退出信号（确定性标注：resolved / ongoing / escalated）
- 支持一条记忆分配到多个 category

---

### 6. `prompts/memory_type/behavior.py` — 提取 Prompt 重写

**原因**：原版提取通用行为习惯，我们需要提取心理行为模式和有效应对方法。

**改动**：重写整个 prompt，提取维度改为：
- 重复行为模式（跨关系出现的模式，如讨好、回避冲突）→ `self/行为模式`
- 有效应对方法（用户确认有效的策略，非 AI 建议）→ `self/有效方法`

---

### 7. `prompts/memory_type/knowledge.py` — 提取 Prompt 重写

**原因**：原版提取通用知识事实，我们需要提取人际关系网络和时间节点。

**改动**：重写整个 prompt，提取维度改为：
- 人际关系网络（人物之间的关系、角色）→ `people/{人名}`
- 关键时间节点（DDL、纪念日、考试日期）→ `events/{事件名}`
- 环境信息（城市、学校、公司）→ `self/核心信念`

---

## 未修改的文件

以下模块与原版完全一致，同步上游时可直接覆盖：

- `app/crud.py`, `app/patch.py`, `app/retrieve.py`, `app/service.py`
- `blob/` 全部
- `database/` 全部（inmemory + postgres）
- `embedding/` 全部
- `llm/` 全部
- `prompts/category_patch/`, `prompts/category_summary/`, `prompts/preprocess/`, `prompts/retrieve/`
- `prompts/memory_type/skill.py`
- `utils/`, `workflow/` 全部

## 同步上游操作指南

```bash
# 1. 添加上游远程
git remote add memu-upstream https://github.com/nicepkg/memU.git

# 2. 拉取上游最新
git fetch memu-upstream

# 3. 对比差异（只看我们改过的 7 个文件）
for f in __init__.py app/settings.py app/memorize.py \
         prompts/memory_type/profile.py prompts/memory_type/event.py \
         prompts/memory_type/behavior.py prompts/memory_type/knowledge.py; do
  echo "=== $f ==="
  git diff memu-upstream/main:src/memu/$f -- ai-companion/memu/$f
done

# 4. 未修改文件可直接同步
cp -r <upstream>/src/memu/database/ ai-companion/memu/database/
# ... 其他未修改目录同理
```
