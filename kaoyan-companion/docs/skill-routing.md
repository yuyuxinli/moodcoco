# Skill 路由方案

## 问题

心情可可有三块业务，共用同一个 AI 身份（可可），但需要不同的能力集：

| 入口 | 业务 | 用户场景 |
|------|------|---------|
| `coco` | 心情可可 | 情绪陪伴、日常聊天 |
| `kaoyan` | 考研伴侣 | 考研备考规划、每日计划、知识测验 |
| `selfhelp` | 自助课 | 结构化心理自助课程 |

**核心需求：身份统一 + 能力隔离。**

- 统一：三个入口共享同一个 SOUL.md（人格）、USER.md（用户档案）、MEMORY.md（记忆）
- 隔离：用户从「考研伴侣」进来，看不到情绪陪伴的 skills；反之亦然

## 架构概览

```
┌──────────────────────────────────────────────────────┐
│                  OpenClaw Workspace                    │
│                  (kaoyan-companion/)                   │
│                                                        │
│  SOUL.md  USER.md  MEMORY.md  ← 三个 agent 共享       │
│                                                        │
│  skills/                                               │
│  ├── breathing-ground/   ← coco 专属                   │
│  ├── chat/               ← coco 专属                   │
│  ├── check-in/           ← coco 专属                   │
│  ├── course-dialogue/    ← selfhelp 专属               │
│  ├── decision-cooling/   ← coco 专属                   │
│  ├── diary/              ← coco 专属                   │
│  ├── farewell/           ← coco 专属                   │
│  ├── growth-story/       ← coco 专属                   │
│  ├── mbti-game/          ← selfhelp 专属               │
│  ├── mood-flow/          ← coco 专属                   │
│  ├── motivation-guide/   ← selfhelp 专属               │
│  ├── onboarding/         ← coco 专属                   │
│  ├── pattern-mirror/     ← coco 专属                   │
│  ├── personality-analysis/ ← selfhelp 专属             │
│  ├── relationship-guide/ ← coco 专属                   │
│  ├── weekly-reflection/  ← coco 专属                   │
│  ├── kaoyan-tracker/     ← kaoyan 专属                 │
│  ├── kaoyan-daily-plan/  ← kaoyan 专属                 │
│  ├── kaoyan-weekly/      ← kaoyan 专属                 │
│  ├── kaoyan-diagnosis/   ← kaoyan 专属                 │
│  ├── kaoyan-crisis/      ← kaoyan 专属                 │
│  ├── kaoyan-quiz/        ← kaoyan 专属                 │
│  └── (selfhelp 使用 course-dialogue + motivation-guide) │
│                                                        │
│  hooks/agent-bootstrap/  ← Layer 1: 注入入口标识        │
│  plugins/skill-router/   ← Layer 2+3: 过滤 + 拦截      │
└──────────────────────────────────────────────────────┘

        ▲              ▲              ▲
        │              │              │
   agent: coco    agent: kaoyan   agent: selfhelp
   (agentId=coco) (agentId=kaoyan) (agentId=selfhelp)
```

三个 agent 指向同一个 workspace，通过 `agentId` 区分入口。

## 三层隔离机制

### Layer 1: Bootstrap Hook — 注入入口标识

**文件：** `hooks/agent-bootstrap/handler.ts`

Agent 启动时，Bootstrap Hook 在 system prompt 中注入一段声明，告诉 AI 当前用户从哪个入口进来。

```
## 当前入口：考研伴侣

用户从「考研伴侣」入口进入。你只使用该入口对应的功能。
其他入口的功能对用户不可见，不要提及。
```

**作用：** 软约束。AI 知道自己该扮演哪个角色，不会主动提及其他业务的功能。

### Layer 2: Plugin — Skills 可见性过滤

**文件：** `plugins/skill-router/index.ts` → `before_prompt_build`

在 system prompt 发送给 AI 之前，Plugin 解析 `<available_skills>` XML 块，移除不属于当前入口的 skill 定义。

**效果：** AI 的 system prompt 中只包含当前入口的 skills。AI 不知道其他 skills 的存在，自然不会调用。

**作用：** 硬约束（可见性层面）。即使 AI 想调用，它看不到 skill 的定义，无法构造正确的调用。

### Layer 3: Plugin — 工具调用拦截

**文件：** `plugins/skill-router/index.ts` → `before_tool_call`

作为最后防线，当 AI 尝试读取 `skills/<skill-name>/` 下的文件时，Plugin 检查该 skill 是否在当前入口的白名单中。不在白名单的读取请求会被阻断，返回错误信息。

**作用：** 硬约束（执行层面）。即使 Layer 2 没有完全过滤（比如 AI 通过其他途径得知 skill 名称），Layer 3 也会阻止实际访问。

### 为什么需要三层？

| 层 | 类型 | 防什么 |
|----|------|--------|
| Layer 1 | 软约束 | AI 主动提及其他业务功能 |
| Layer 2 | 硬约束（可见性） | AI 看到并尝试调用非授权 skill |
| Layer 3 | 硬约束（执行） | AI 通过任何途径访问非授权 skill 文件 |

单独任何一层都不够：
- 只有 Layer 1 → AI 可能忽略指令
- 只有 Layer 2 → AI 可能通过文件路径直接读取 skill
- 只有 Layer 3 → AI 会向用户暴露其他业务功能的存在（虽然调用会失败）

## 配置

### OpenClaw Config — 三个 agent 指向同一 workspace

每个 agent 在 OpenClaw 平台上配置时，都指向同一个 workspace，但设置不同的 `agentId`：

```yaml
# Agent: 心情可可
workspace: kaoyan-companion
agentId: coco

# Agent: 考研伴侣
workspace: kaoyan-companion
agentId: kaoyan

# Agent: 自助课
workspace: kaoyan-companion
agentId: selfhelp
```

### SKILL_ROUTES 路由规则

在 `plugins/skill-router/index.ts` 中定义：

```typescript
const SKILL_ROUTES: Record<string, string[]> = {
  coco: [
    // 心情可可：核心 AI 陪伴 skills（12 个）
    "breathing-ground",
    "chat",
    "check-in",
    "course-dialogue",
    "decision-cooling",
    "diary",
    "farewell",
    "growth-story",
    "mbti-game",
    "mood-flow",
    "motivation-guide",
    "onboarding",
    "pattern-mirror",
    "personality-analysis",
    "relationship-guide",
    "weekly-reflection",
  ],
  kaoyan: [
    // 考研伴侣：考研备考相关 skills（6 个）
    "kaoyan-tracker",
    "kaoyan-daily-plan",
    "kaoyan-weekly",
    "kaoyan-diagnosis",
    "kaoyan-crisis",
    "kaoyan-quiz",
  ],
  selfhelp: [
    // 自助课（growth 成长入口）：自助心理课程相关 skills
    "course-dialogue",
    "motivation-guide",
  ],
};

// 所有入口共享的 skills
const SHARED_SKILLS: string[] = [];
```

### SKILL_ROUTES 修改指南

**添加新 skill 到已有入口：**

1. 在 `skills/` 下创建 skill 目录（如 `skills/coco-mood-diary/`）
2. 在 `SKILL_ROUTES` 对应入口的数组中添加 skill 名称
3. 完成。无需修改其他文件

**添加跨入口共享的 skill：**

1. 创建 skill 目录
2. 将 skill 名称添加到 `SHARED_SKILLS` 数组
3. 该 skill 对所有入口可见

## 工作原理

### 用户请求流程

```
用户发送消息
    │
    ▼
OpenClaw 选择 agent（根据入口/binding）
    │
    ▼
Layer 1: Bootstrap Hook 触发
    │  注入 ENTRY_POINT.md 到 system prompt
    │  内容："当前入口：考研伴侣"
    ▼
Layer 2: before_prompt_build 触发
    │  解析 <available_skills> XML
    │  移除非白名单 skills
    │  AI 只看到 kaoyan-* skills
    ▼
AI 生成回复
    │  可能调用 skill → 需要读取 skill 文件
    ▼
Layer 3: before_tool_call 触发
    │  检查目标文件路径
    │  路径包含 skills/kaoyan-tracker/ → 在白名单中 → 放行
    │  路径包含 skills/coco-mood-diary/ → 不在白名单 → 阻断
    ▼
回复返回用户
```

### Skills 加载和过滤时序

```
1. Agent 启动
   └── Bootstrap Hook 写入 ENTRY_POINT.md（agentId → 入口名称）

2. System Prompt 构建
   ├── OpenClaw 加载 SOUL.md, USER.md, MEMORY.md（共享）
   ├── OpenClaw 加载所有 skills 到 <available_skills>
   └── before_prompt_build 过滤，只保留白名单 skills

3. 对话运行中
   └── 每次 read 工具调用 → before_tool_call 检查路径
```

## 维护指南

### 添加新 skill

1. 在 `skills/` 下创建目录：`skills/<skill-name>/SKILL.md`
2. 在 `plugins/skill-router/index.ts` 的 `SKILL_ROUTES` 中，把 skill 名称加到对应入口的数组里
3. 如果是共享 skill，加到 `SHARED_SKILLS` 数组

**命名约定：** 建议用业务前缀（`kaoyan-`、`coco-`、`selfhelp-`），方便识别归属。但路由靠的是 `SKILL_ROUTES` 配置，不是前缀。

---

## 备注

### 多租户说明

本 workspace 是**模板**，不是数据存储。线上多租户由 `psychologists` 后端实现：

- 后端通过 JWT → `user_id` (UUID) 隔离所有用户数据（session、memory、people 等全部在 DB 中按 user_id 外键隔离）
- 记忆系统：`MemoryItem` + `MemoryCategory` 表，6 种类型（profile/relationships/events/behavior/goals/knowledge），通过 L3 Context 层注入 LLM prompt
- workspace 中的 `USER.md`、`memory/`、`people/` 仅用于 OpenClaw 本地单租户测试
- 详见 `docs/technical/配置/session-isolation.md`

### Selfhelp 自助课入口

`SKILL_ROUTES.selfhelp` 包含 4 个 skill（从 coco 迁移而来）：
- `course-dialogue`：学练聊三阶段课程流程
- `motivation-guide`：课程生成引导对话
- `mbti-game`：MBTI 对话式人格测试
- `personality-analysis`：MBTI 测试完成后生成人格解析报告

课程内容数据存放在 `skills/course-dialogue/references/courses/`，从 psychologists 后端 DB 导出。
当前 3 门完整课程：春节返乡焦虑、热闹里的孤独、深夜的思念。

**产品层级**：moodcoco = coco（核心陪伴）+ growth（成长），growth = selfhelp + kaoyan + ...

### 添加新业务入口

1. 在 `SKILL_ROUTES` 中添加新的 key（如 `career: [...]`）
2. 在 `hooks/agent-bootstrap/handler.ts` 的 `ENTRY_NAMES` 中添加对应的中文名
3. 在 OpenClaw 平台上创建新 agent，设置对应的 `agentId`
4. 创建该入口专属的 skills

### 调试 skill 路由问题

**症状：AI 说"我没有这个功能"**
- 检查 `SKILL_ROUTES` 中是否包含该 skill 名称
- 确认 skill 名称拼写与 `skills/` 目录名一致
- 确认 agent 的 `agentId` 正确

**症状：AI 提及了其他业务的功能**
- 检查 Layer 1 的 `ENTRY_POINT.md` 是否正确注入（看 system prompt）
- 检查 Layer 2 是否正确过滤了 `<available_skills>`（看过滤后的 prompt）
- 如果是 AI 凭"常识"提及（不是调用 skill），只能靠 Layer 1 的软约束

**症状：AI 调用了非授权 skill 但没被拦截**
- 检查 Layer 3 的路径匹配逻辑
- 确认文件路径中包含 `skills/<skill-name>/` 模式
- 确认 `before_tool_call` 正确识别了工具名（read/Read/read_file）

## 局限性和注意事项

1. **Layer 1 是软约束。** AI 可能在极端情况下忽略 ENTRY_POINT.md 的指令。Layer 2 和 3 才是真正的硬隔离。

2. **SKILL_ROUTES 是静态配置。** 修改后需要重启 agent 才能生效。不支持运行时动态切换。

3. **`<available_skills>` XML 格式依赖。** Layer 2 的过滤依赖 OpenClaw 平台输出特定格式的 XML。如果平台更新了格式，需要同步更新正则。

4. **Layer 3 只拦截 read 类工具。** 如果 AI 通过其他方式（如 shell 命令）读取文件，Layer 3 无法拦截。但在 OpenClaw 环境下，AI 通常不会有 shell 访问权限。

5. **共享身份意味着共享记忆。** 三个入口共享 MEMORY.md，所以用户在「考研伴侣」中说的话，「心情可可」也能看到。这是设计意图（可可认识这个用户），但需要注意隐私边界。

6. **agentId 传递依赖 OpenClaw 平台。** 如果平台没有在 `event.context.agentId` 中传入 agent 标识，整个路由机制不会生效（但也不会报错，只是不做过滤）。
