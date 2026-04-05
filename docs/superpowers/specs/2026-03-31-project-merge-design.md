# 项目合并设计：心理咨询 × Mood Coco

## 概述

将两个项目合二为一：
- **心理咨询**（`psychologists`）— 全栈 AI 心理咨询平台（微信小程序 + FastAPI + PostgreSQL）
- **Mood Coco**（`moodcoco`）— 基于 OpenClaw 的 AI 情绪陪伴 Agent（纯 Markdown 配置驱动）

**合并逻辑**：心理咨询项目有完整的产品链路（前端 + 后端 + 数据库），但 AI 对话能力较浅。Mood Coco 基于 OpenClaw，拥有深度情绪框架（四步法）、10+ 专业 Skill、多渠道协议层，作为"大脑"注入心理咨询项目。

---

## 1. 仓库结构

**策略**：psychologists 为主仓库，ai-companion/ 以 Git Submodule 引入。

```
psychologists/                          ← 主仓库（开发团队）
├── backend/
│   ├── ai-companion/                   ← Git Submodule → moodcoco 仓库
│   │   ├── SOUL.md                     ←   人格定义（PM 维护）
│   │   ├── AGENTS.md                   ←   四步框架 + 安全协议（PM 维护）
│   │   ├── HEARTBEAT.md                ←   主动关怀规则（PM 维护）
│   │   ├── IDENTITY.md                 ←   可可身份（PM 维护）
│   │   ├── TOOLS.md                    ←   Tool 使用说明（PM 维护）
│   │   ├── skills/                     ←   10+ Skill 模块（PM 维护）
│   │   └── scripts/                    ←   exec 脚本源码（开发维护）
│   │
│   ├── openclaw_bridge/                ← 新增：OpenClaw Plugin（开发维护）
│   │   ├── openclaw.plugin.json
│   │   ├── index.ts                    ←   插件入口
│   │   └── adapters/
│   │       ├── ui_tools.ts             ←   18 个 UI Tool 注册
│   │       └── service_tools.ts        ←   Service Tool 注册
│   │
│   ├── api/routes/
│   │   ├── ws_socketio.py              ← 改造：ChatEngine → ChatProxy
│   │   ├── tool_bridge.py              ← 新增：Tool Bridge HTTP 端点
│   │   └── ...                         ← 其余业务 API 不变
│   │
│   ├── services/
│   │   ├── workspace_storage.py        ← 新增：WorkspaceStorage 抽象层
│   │   ├── course_service.py           ← 重构：从 Agent 下放的课程业务逻辑
│   │   ├── message_persistence.py      ← 重构：从 Agent 下放的消息持久化
│   │   ├── mood_service.py             ← 重构：从 Agent 下放的情绪业务逻辑
│   │   ├── mbti_service.py             ← 重构：从 Agent 下放的 MBTI 业务逻辑
│   │   └── ...                         ← 其余 Service 不变
│   │
│   ├── tools/                          ← 保留：18 个 UI Tool 的 Python 实现
│   ├── agents/                         ← 逐步废弃（迁移完成后删除）
│   └── ...
│
├── frontend/miniprogram/               ← 不变
│
└── openclaw.json                       ← OpenClaw 配置
```

### 团队分工

| 角色 | 工作目录 | 职责 |
|------|---------|------|
| PM | moodcoco 仓库（即 ai-companion/ submodule） | 维护 SOUL.md / AGENTS.md / Skills / HEARTBEAT.md |
| 开发 | psychologists 仓库 | 维护 backend/ / frontend/ / openclaw_bridge/ |
| 部署 | psychologists 仓库 CI/CD | `git submodule update` 拉最新 ai-companion → 构建 Docker 镜像 |

### Submodule 工作流

```bash
# PM 改行为配置
cd moodcoco && vim ai-companion/AGENTS.md && git push

# 开发更新 PM 的改动
cd psychologists && git submodule update --remote backend/ai-companion

# CI/CD 打包
git clone --recurse-submodules psychologists.git
docker build .
```

---

## 2. 对话链路

### 改造前

```
小程序 → Socket.IO → ws_socketio.py → ChatEngine → Agent.process_event()
                                                        ↓
                                                   LiteLLM → gpt-4
                                                        ↓
                                                   stream_chunk → 小程序
```

### 改造后

```
小程序 → Socket.IO → ws_socketio.py → ChatProxy → OpenClaw Gateway (localhost:18789)
                                                        ↓
                                                   Agent Runtime
                                                   (AGENTS.md 四步框架)
                                                        ↓
                                              ┌─────────┼─────────┐
                                              ↓         ↓         ↓
                                         Brain Tool  UI Tool   Service Tool
                                         (内置)     (→前端)   (→Service层)
                                                        ↓         ↓
                                                   tool_bridge.py
                                                        ↓         ↓
                                                  WebSocket推送  Service执行
                                                        ↓
                                                   stream_chunk → 小程序
```

### ChatProxy 实现

> **会话隔离**：OpenClaw Gateway 的 `/v1/chat/completions` 通过 `user` 字段派生稳定的 session key，同一 user 的多次请求复用同一 session。
> 出处：`/docs/gateway/openai-http-api.md` — "If the request includes an OpenAI `user` string, the Gateway derives a stable session key from it"

```python
class ChatProxy:
    """薄代理层：小程序 ↔ OpenClaw Gateway，携带用户身份"""

    async def send_to_openclaw(self, message: str, user_id: str) -> AsyncGenerator:
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{settings.OPENCLAW_URL}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.OPENCLAW_TOKEN}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "openclaw:coco",    # 指定 agent id
                    "messages": [{"role": "user", "content": message}],
                    "stream": True,
                    "user": user_id,             # 关键：派生稳定 session key，确保会话隔离
                }
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        yield self._convert_to_frontend_format(line[6:])
```

> **user_id 来源**：ws_socketio.py 的 connect 事件中，从 JWT token 或 auth 参数提取 user_id，通过 `sio.save_session(sid, {"user_id": user_id})` 保存，后续 send_message 事件中取出传给 ChatProxy。

### Tool Bridge 的 user_id 传递

OpenClaw Plugin 调用 tool_bridge 时，需要将 user_id 通过自定义头传入：

```typescript
// openclaw_bridge — Plugin execute() 中
const userId = context?.session?.user ?? "anonymous";
const res = await fetch(`${backendUrl}/api/tool-bridge/${tool.name}`, {
    method: "POST",
    headers: {
        "Content-Type": "application/json",
        "x-coco-user-id": userId,     // 传入 user_id
    },
    body: JSON.stringify(params),
});
```

```python
# tool_bridge.py — 提取 user_id
def extract_user_id(request: Request) -> str:
    return request.headers.get("x-coco-user-id", "anonymous")
```

### 组件变化

| 组件 | 处理 |
|------|------|
| ChatEngine | **删除**，ChatProxy 替代 |
| MoodAgent / ChatAgent / MbtiAgent | **删除**，OpenClaw Agent + Skills 替代 |
| CourseDialogueAgent / CourseGenerateAgent | **删除**，OpenClaw Skills 替代 |
| LessonAgent / QuizAgent / MotivationAgent | **删除**，OpenClaw Skills 替代 |
| L0-L5 上下文架构 | **删除**，OpenClaw workspace bootstrap + compaction 替代 |
| LiteLLM | **删除**，OpenClaw 管模型调用 |
| ws_socketio.py 连接管理 | **保留** |
| ToolRegistry + 18 个 UI Tool | **保留** |
| ToolMonitor | **保留** |
| 所有业务 API | **保留** |
| 语音服务 | **保留** |
| 前端 | **不变** |

---

## 3. Tool 统一架构

### Tool 分类

所有 Tool 按行为分为三类：

```
OpenClaw Agent 可用的 Tool
│
├── 【UI Tool】→ tool_bridge → 前端
│   按 InteractionMode 决定行为：
│   ├── FIRE_AND_FORGET：直推前端，回 Agent "已发送"
│   ├── OPTIONAL：推前端 + 回 Agent 结构化结果
│   └── BLOCKING：推前端，Agent 等待用户交互
│
├── 【Service Tool】→ tool_bridge → Service 层
│   用户数据读写 + 业务逻辑执行
│   Agent 不关心底层是文件还是 DB
│
└── 【禁用的 Tool】线上环境
    read / write / edit / exec 全部 deny
```

### UI Tool 清单（18 个，保留原有实现）

| Tool | InteractionMode | 用途 |
|------|----------------|------|
| ai_message | FIRE_AND_FORGET | 发送文本消息 |
| ai_options | OPTIONAL | 显示选项卡 |
| ai_mood_select | OPTIONAL | 情绪选择器 |
| ai_praise_popup | FIRE_AND_FORGET | 赞美弹窗 |
| ai_relationship | OPTIONAL | 关系卡片 |
| ai_mood_recovery | FIRE_AND_FORGET | 情绪恢复引导 |
| ai_thought_feeling | OPTIONAL | 想法-感受捕捉 |
| ai_body_sensation | OPTIONAL | 身体感受选择 |
| ai_complete_conversation | FIRE_AND_FORGET | 标记对话完成 |
| ai_emotion_response | FIRE_AND_FORGET | 情绪感知回复 |
| ai_feeling_exploration | OPTIONAL | 感受探索引导 |
| ai_safety_brake | BLOCKING | 危机信号检测 |
| ai_quiz_practice | OPTIONAL | 互动测验 |
| ai_lesson_card | FIRE_AND_FORGET | 课程卡片 |
| ai_micro_lesson_batch | FIRE_AND_FORGET | 批量微课 |
| ai_course_complete | FIRE_AND_FORGET | 课程完成 |
| ai_growth_greeting | FIRE_AND_FORGET | 成长问候 |

### Service Tool 清单（从 Agent 业务逻辑下放）

| Tool | 来源 | 用途 |
|------|------|------|
| user_profile_get | MoodAgent 情绪状态读取 | 获取用户画像（USER.md 或 DB） |
| user_profile_update | MoodAgent 触发点/偏好更新 | 更新用户画像 |
| person_get | diary Skill 关系读取 | 获取关系档案 |
| person_update | diary Skill 关系写入 | 更新关系档案 |
| person_list | pattern-mirror 跨关系查询 | 列出所有关系人 |
| diary_write | diary Skill 日记写入 | 写入六元组情绪日记 |
| diary_read | weekly-reflection 回顾 | 读取日记条目 |
| memory_search | 跨会话记忆搜索 | 语义搜索用户记忆 |
| pattern_match | exec pattern_engine.py | 跨关系模式匹配 |
| emotion_count | exec emotion_counter.py | 情绪统计 |
| growth_track | exec growth_tracker.py | 成长检测 |
| course_init_dialogue | CourseDialogueAgent._handle_init_dialogue | 初始化课程对话上下文 |
| course_advance_card | CourseDialogueAgent.next_card_handler | 推进课程步骤 |
| course_submit_answer | CourseDialogueAgent.practice_handler | 提交答案 + 评分 |
| course_check_completion | CourseDialogueAgent.check_completion_ready | 完成检测 |
| course_generate_curriculum | CourseGenerateAgent 课程大纲生成 | 6 步收集 + 生成课表 |
| mbti_save_answer | MbtiAgent.save_user_mbti_answer | 保存 MBTI 答案 |
| mbti_generate_report | MbtiAgent 异步报告生成 | 触发报告生成任务 |
| audio_synthesize | MoodAgent TTS 合成 | 文本转语音 |
| message_persist | ChatAgent 消息持久化 | 创建/更新/删除消息 |
| conversation_history | ChatAgent 历史查询 | 获取对话历史 |

### OpenClaw Plugin 注册

```typescript
// openclaw_bridge/index.ts
export default function (api: PluginAPI) {
  const backendUrl = process.env.BACKEND_URL || "http://localhost:8000";

  // 注册 UI Tools
  registerUITools(api, backendUrl);

  // 注册 Service Tools
  registerServiceTools(api, backendUrl);
}

// openclaw_bridge/adapters/ui_tools.ts
export function registerUITools(api: PluginAPI, backendUrl: string) {
  for (const tool of UI_TOOL_DEFINITIONS) {
    api.registerTool({
      name: tool.name,
      description: tool.description,
      parameters: tool.parameters,  // 从原有 ToolBase.parameters 搬过来
      async execute(_id, params) {
        const res = await fetch(`${backendUrl}/api/tool-bridge/${tool.name}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(params),
        });
        const result = await res.json();
        if (tool.interaction_mode === "fire_and_forget") {
          return { content: [{ type: "text", text: "已推送到用户界面" }] };
        }
        return { content: [{ type: "text", text: JSON.stringify(result) }] };
      },
    });
  }
}

// openclaw_bridge/adapters/service_tools.ts
export function registerServiceTools(api: PluginAPI, backendUrl: string) {
  for (const tool of SERVICE_TOOL_DEFINITIONS) {
    api.registerTool({
      name: tool.name,
      description: tool.description,
      parameters: tool.parameters,
      async execute(_id, params) {
        const res = await fetch(`${backendUrl}/api/tool-bridge/${tool.name}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(params),
        });
        return { content: [{ type: "text", text: await res.text() }] };
      },
    });
  }
}
```

### FastAPI Tool Bridge

```python
# api/routes/tool_bridge.py
@router.post("/api/tool-bridge/{tool_name}")
async def execute_tool(tool_name: str, request: Request, db: AsyncSession = Depends(get_db)):
    args = await request.json()
    user_id = extract_user_id(request)  # 从 OpenClaw 请求头提取

    # UI Tool → 转调原有 ToolRegistry
    if tool_registry.has_tool(tool_name.upper()):
        tool = tool_registry.get_tool(tool_name.upper())
        context = build_context(user_id, db)
        result = await tool.execute(args, context)

        if tool.interaction_mode == InteractionMode.FIRE_AND_FORGET:
            await push_to_frontend(result)
            return {"status": "pushed"}
        return result.to_dict()

    # Service Tool → 转调 Service 层
    service = service_registry.get(tool_name)
    return await service.execute(user_id, args, db)
```

---

## 4. 存储架构

### 原则

Agent 不直接操作文件系统或数据库。所有用户数据读写通过 Service Tool 完成。Service 层内部通过 WorkspaceStorage 抽象决定底层实现。

### 线上环境禁用文件操作

```json5
// openclaw.json — 线上配置
{
  "tools": {
    "deny": ["read", "write", "edit", "exec"],
  }
}
```

### WorkspaceStorage 抽象

```python
class WorkspaceStorage(ABC):
    @abstractmethod
    async def read(self, user_id: str, path: str) -> Optional[str]: ...

    @abstractmethod
    async def write(self, user_id: str, path: str, content: str) -> None: ...

    @abstractmethod
    async def list_dir(self, user_id: str, dir_path: str) -> list[str]: ...

    @abstractmethod
    async def delete(self, user_id: str, path: str) -> None: ...

    @abstractmethod
    async def search(self, user_id: str, query: str) -> list[dict]: ...


class FileBackend(WorkspaceStorage):
    """本地开发：直接读写 ai-companion/ 目录下的文件"""

    def __init__(self, workspace_path: str):
        self.root = Path(workspace_path)

    async def read(self, user_id, path):
        file = self.root / path
        return file.read_text() if file.exists() else None

    async def write(self, user_id, path, content):
        file = self.root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content)


class DatabaseBackend(WorkspaceStorage):
    """线上生产：PostgreSQL"""

    async def read(self, user_id, path):
        row = await db.fetchone(
            "SELECT content FROM workspace_files WHERE user_id=$1 AND path=$2",
            user_id, path
        )
        return row["content"] if row else None

    async def write(self, user_id, path, content):
        await db.execute(
            "INSERT INTO workspace_files (user_id, path, content, updated_at) "
            "VALUES ($1, $2, $3, NOW()) "
            "ON CONFLICT (user_id, path) DO UPDATE SET content=$3, updated_at=NOW()",
            user_id, path, content
        )


# 启动时根据环境选择
storage = FileBackend("ai-companion/") if APP_ENV == "development" else DatabaseBackend()
```

### 数据库表

```sql
CREATE TABLE workspace_files (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    path VARCHAR(512) NOT NULL,
    content TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (user_id, path)
);

CREATE INDEX idx_workspace_user_path ON workspace_files (user_id, path);
CREATE INDEX idx_workspace_user ON workspace_files (user_id);
```

### 文件分类

| 类型 | 示例 | 本地 | 线上 |
|------|------|------|------|
| 模板文件（只读） | SOUL.md, AGENTS.md, skills/ | Git 目录 | Docker 镜像 |
| 用户数据（读写） | USER.md, people/*.md, diary/*.md | 本地文件 | PostgreSQL |

### 一致性保证

1. **模板文件**：Git 保证本地和线上一致（CI 构建镜像时 submodule 一起打包）
2. **Service Tool 接口**：本地和线上调用完全相同的 Tool 名 + 参数
3. **CI 双跑测试**：集成测试分别用 FileBackend 和 DatabaseBackend 各跑一遍，结果必须一致

---

## 5. Agent 迁移策略

### 拆分原则

每个现有 Agent 的代码按"是否需要 LLM"拆分：
- **需要 LLM 的逻辑** → 迁移为 OpenClaw Skill（SKILL.md）
- **纯业务逻辑** → 下放到 Service 层，通过 Service Tool 暴露

### 各 Agent 拆分明细

#### MoodAgent（300 LOC）

| 逻辑 | 需要 LLM | 去向 |
|------|---------|------|
| 情绪对话引导 | 是 | OpenClaw Agent 四步框架（AGENTS.md 已有） |
| 情绪选择后上下文注入 | 否 | Service: mood_service.inject_emotion_context() |
| TTS 音频合成 | 否 | Service Tool: audio_synthesize |
| input_mode 历史记录 | 否 | Service: mood_service.track_input_mode() |
| EmotionType 验证 | 否 | Service: mood_service.validate_emotion() |

#### ChatAgent（695 LOC）

| 逻辑 | 需要 LLM | 去向 |
|------|---------|------|
| 自由对话 | 是 | OpenClaw Agent 原生能力 |
| 人格分析报告 | 是 | OpenClaw Skill: skills/personality-analysis/ |
| 消息持久化（pre-create → update → delete） | 否 | Service Tool: message_persist |
| 对话历史查询 + 过滤 | 否 | Service Tool: conversation_history |
| JSON 解析 fallback | 否 | Service: message_persistence.parse_response() |
| 异步 session summary | 否 | Service: session_service.trigger_summary() |

#### MbtiAgent（400 LOC）

| 逻辑 | 需要 LLM | 去向 |
|------|---------|------|
| MBTI 对话引导 | 是 | OpenClaw Skill: skills/mbti-game/ |
| 保存答案 | 否 | Service Tool: mbti_save_answer |
| Likert 量表映射 | 否 | Service: mbti_service.map_likert() |
| 异步报告生成 | 否 | Service Tool: mbti_generate_report |

#### CourseDialogueAgent（492 LOC + 子模块）

| 逻辑 | 需要 LLM | 去向 |
|------|---------|------|
| 课程对话引导 | 是 | OpenClaw Skill: skills/course-dialogue/ |
| 微课卡片生成 | 是 | OpenClaw Skill: skills/micro-lesson/ |
| 练习题生成 | 是 | OpenClaw Skill: skills/quiz-practice/ |
| init_dialogue（加载课程上下文） | 否 | Service Tool: course_init_dialogue |
| next_card（推进步骤） | 否 | Service Tool: course_advance_card |
| submit_answer（评分） | 否 | Service Tool: course_submit_answer |
| completion 检测 | 否 | Service Tool: course_check_completion |
| 音频合成 + 写回 | 否 | Service Tool: audio_synthesize |
| preset options 解析 + emoji 清洗 | 否 | Service: course_service.parse_options() |

#### CourseGenerateAgent（588 LOC）

| 逻辑 | 需要 LLM | 去向 |
|------|---------|------|
| 6 步对话收集用户信息 | 是 | OpenClaw Skill: skills/course-generate/ |
| thinking step 1/2 | 是 | OpenClaw Skill 内（Agent 自主调 LLM） |
| 课程大纲生成 | 是 | OpenClaw Skill 内 |
| 进度追踪 | 否 | Service Tool: course_generate_progress |
| step 归一化 | 否 | Service: course_service.normalize_step() |
| fallback 默认课程 | 否 | Service: course_service.get_default_curriculum() |
| 场景/知识加载 | 否 | Service Tool: course_load_context |

### TDD 迁移流程

每个 Agent 迁移都经过 4 个阶段：

```
Phase 1: 录制行为测试
  → 对现有 Agent 录制 input/output 对
  → 覆盖：正常流程 + 状态转换 + 错误处理 + 边界条件
  → 这些测试 = "功能不丢失" 的验收标准

Phase 2: 下放 Service 层
  → 把 Agent 内部的纯业务方法提取到 Service
  → 通过 tool_bridge 暴露为 Service Tool
  → Phase 1 的测试验证行为一致

Phase 3: 写 OpenClaw Skill
  → SKILL.md 描述对话策略（PM 可维护）
  → 配置可用 Tool 白名单
  → 集成测试：Agent + Skill + Tool → 对比 Phase 1 预期输出

Phase 4: 灰度切换
  → 新会话走 OpenClaw，旧会话走原 Agent
  → 对比两个系统输出质量
  → 确认无损后关闭旧 Agent
```

### 迁移顺序（从简到难）

| 顺序 | Agent | 复杂度 | 目标 |
|------|-------|--------|------|
| 1 | MotivationAgent | 低 | 热身，验证 Skill 机制 |
| 2 | ChatAgent | 中 | 建立 ChatProxy 基础链路 |
| 3 | MbtiAgent | 中 | 验证异步任务模式 |
| 4 | MoodAgent | 高 | 验证 Tool Bridge（UI Tool + Service Tool） |
| 5 | CourseGenerateAgent | 高 | 验证复杂状态机 |
| 6 | CourseDialogueAgent | 最高 | 最后攻坚（7 子模块） |

---

## 6. OpenClaw 配置

> **配置出处**：sandbox/session/heartbeat 字段参考 `/docs/gateway/configuration-reference.md`、`/docs/gateway/heartbeat.md`

```json5
// openclaw.json
{
  "agents": {
    "list": [
      {
        "name": "coco",
        "model": "openrouter/minimax/minimax-m2.7",
        "thinking": "high",
        "fallback": ["doubao-seed-2-0-pro-260215", "openrouter/auto"],
        "workspace": "./backend/ai-companion"
      }
    ],
    "defaults": {
      "sandbox": {
        "mode": "all",
        // sandbox.scope 有效值：session / agent / shared
        // 出处：/docs/gateway/configuration-reference.md 第 1265-1269 行
        // 注意：moodcoco 原配置用了 "per-sender"，但 per-sender 是 session.scope 的值
        // （出处：/docs/concepts/session.md 第 252 行）
        // 此处沿用项目原配置，迁移时需验证 OpenClaw 实际行为
        "scope": "per-sender",
        "workspaceAccess": "rw"
      },
      // Heartbeat 配置（出处：/docs/gateway/heartbeat.md 第 28-46 行）
      // 支持渠道：whatsapp / telegram / discord / googlechat / slack / msteams / signal / imessage
      "heartbeat": {
        "every": "30m",
        "target": "last",          // 推送到最近联系的渠道
        "lightContext": true,      // 只注入 HEARTBEAT.md，减少 token
        "activeHours": {
          "start": "08:00",
          "end": "23:00",
          "tz": "Asia/Shanghai"
        }
      },
      "bootstrapMaxChars": 80000,
      "bootstrapTotalMaxChars": 300000,
      "compaction": "压缩时保留：情绪模式、核心困扰、关系人、本轮新发现的模式"
    }
  },
  "session": {
    // dmScope 有效值：main / per-peer / per-channel-peer / per-account-channel-peer
    // 出处：/docs/gateway/configuration-reference.md 第 1608-1612 行
    "dmScope": "per-channel-peer"
  },
  "tools": {
    "profile": "minimal",
    "deny": ["read", "write", "edit", "exec"],
    // Tool 分组：不同对话场景加载不同 Tool 子集，避免 37 个 Tool 全量开放
    // 具体分组方案见下方"Tool 分组"章节
    "allow": [
      // 【组 A】情绪陪伴核心
      "ai_message", "ai_options", "ai_mood_select", "ai_praise_popup",
      "ai_emotion_response", "ai_feeling_exploration", "ai_thought_feeling",
      "ai_body_sensation", "ai_safety_brake", "ai_mood_recovery",
      "user_profile_get", "user_profile_update", "diary_write", "diary_read",
      "person_get", "person_update", "person_list", "memory_search",
      // 【组 B】模式觉察（A 基础上追加）
      "pattern_match", "emotion_count", "growth_track",
      "ai_complete_conversation",
      // 【组 C】课程学习
      "ai_lesson_card", "ai_micro_lesson_batch", "ai_course_complete",
      "ai_quiz_practice",
      "course_init_dialogue", "course_advance_card",
      "course_submit_answer", "course_check_completion",
      // 【组 D】课程生成
      "course_generate_curriculum", "course_load_context",
      // 【组 E】MBTI
      "mbti_save_answer", "mbti_generate_report",
      // 【全局常驻】
      "ai_growth_greeting", "audio_synthesize",
      "message_persist", "conversation_history"
    ]
  },
  "streaming": {
    "humanDelay": "natural",
    "breakPreference": "sentence"
  },
  "timestamp": "on",
  "elapsed": "on"
}
```

### Tool 分组

不同对话场景加载不同 Tool 子集，避免 LLM 在 37 个 Tool 中选错。每组控制在 ~15 个以内。

| 场景组 | Tool 数量 | 触发条件 | 包含 |
|--------|----------|---------|------|
| A 情绪陪伴 | ~15 | 默认/日常闲聊/情绪对话 | ai_message, ai_options, ai_mood_select, diary_write, person_get, memory_search 等 |
| B 模式觉察 | A + 4 | pattern-mirror / weekly-reflection 触发时 | pattern_match, emotion_count, growth_track, ai_complete_conversation |
| C 课程学习 | ~12 | 用户进入课程场景 | ai_lesson_card, course_init, course_advance, course_submit 等 |
| D 课程生成 | ~8 | 用户触发课程生成 | course_generate_curriculum, course_load_context |
| E MBTI | ~8 | 用户进入 MBTI 测试 | mbti_save_answer, mbti_generate_report |

> **类型约束**：所有 Tool 的 parameters 使用枚举类型代替自由字符串（如 `emotion: "焦虑" | "悲伤" | "愤怒"` 而非 `emotion: string`），减少 LLM 选择歧义。类型定义在 `openclaw_bridge/types/` 目录下，前后端共享。开发前先补齐所有 Tool 的 Type 定义。

> **具体哪个场景开放哪些 Tool 的权限表，由用户最终确定。**

---

## 7. 部署架构

### 同机部署

```
┌─────────────────────────────────────────┐
│  单台服务器 / Docker Compose             │
│                                         │
│  ┌──────────────┐  ┌─────────────────┐  │
│  │ FastAPI       │  │ OpenClaw Gateway│  │
│  │ :8000         │←→│ :18789          │  │
│  │               │  │                 │  │
│  │ Chat Proxy    │  │ Agent Runtime   │  │
│  │ Tool Bridge   │  │ (coco)          │  │
│  │ 业务 API      │  │                 │  │
│  │ WebSocket     │  │ Plugin:         │  │
│  └──────┬────────┘  │ openclaw_bridge │  │
│         │           └─────────────────┘  │
│  ┌──────┴────────┐                       │
│  │ PostgreSQL    │                       │
│  │ Redis         │                       │
│  └───────────────┘                       │
└─────────────────────────────────────────┘
```

### Docker Compose 示意

```yaml
services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
    environment:
      - APP_ENV=production
      - OPENCLAW_URL=http://openclaw:18789
    depends_on: [postgres, redis, openclaw]

  openclaw:
    image: openclaw/gateway
    ports: ["18789:18789"]
    volumes:
      - ./backend/ai-companion:/workspace:ro  # 模板文件只读挂载
    environment:
      - BACKEND_URL=http://backend:8000

  postgres:
    image: postgres:16
    volumes: [pgdata:/var/lib/postgresql/data]

  redis:
    image: redis:7
```

---

## 8. 多渠道扩展与 Heartbeat

合并后，OpenClaw Gateway 天然支持多渠道。小程序通过 FastAPI 代理访问，其他渠道直连 Gateway。

> **Heartbeat 出处**：`/docs/gateway/heartbeat.md` 第 224-226 行 — 支持渠道：whatsapp / telegram / discord / googlechat / slack / msteams / signal / imessage

| 渠道 | 接入方式 | 可用功能 | Heartbeat 推送 |
|------|---------|---------|---------------|
| 微信小程序 | FastAPI ChatProxy → Gateway | 全部（页面/课程/测验/语音） | 需适配（微信订阅消息 API 或下次登录补发） |
| Telegram | 直连 Gateway | 对话 + 情绪日记 + check-in | 原生支持（Bot API 直推） |
| WhatsApp | 直连 Gateway | 对话 + 情绪日记 + check-in | 原生支持（Baileys 推送） |
| 微信公众号 | 直连 Gateway | 对话 + 情绪日记 | 原生支持（客服消息 / 模板消息） |
| Discord | 直连 Gateway | 对话 + 情绪日记 + check-in | 原生支持（Bot 推送） |
| macOS 桌面 | 直连 Gateway | 对话 + pattern-mirror 可视化 | 原生支持（Node 通知） |

轻量渠道的 Agent 使用相同的 AGENTS.md / Skills，但 UI Tool 不可用时自动降级为纯文本。

### Heartbeat 规则（从 HEARTBEAT.md 迁入）

| 优先级 | 规则 | 触发条件 | 说明 |
|--------|------|---------|------|
| 1 | 决策冷却回访 | 每次 Heartbeat | 检查 pending_followup 是否到期 |
| 2 | 时间胶囊检查 | 每日 | 检查时间胶囊是否到期 |
| 3 | 周日回顾 | 周日 20:00 | 本周 ≥3 条日记时触发 weekly-reflection |
| 4 | 日记提醒 | 每日 21:30 | 今天无日记 + 距上次提醒 ≥48h |

> 微信小程序的 Heartbeat 推送需要额外适配（微信平台限制：小程序无长连接推送 API），但**不影响其他渠道的 Heartbeat 功能**。微信端的适配方案在迁移阶段确定。

---

## 9. Skill 改造

现有 Mood Coco 的 10+ Skills（SKILL.md）里使用了 OpenClaw 内置文件操作（read/write/edit），这些需要全部改成 Service Tool 调用。

### 改造示例

```markdown
# 改造前（diary/SKILL.md）
当用户想记录情绪时：
1. 读取 read("USER.md") 获取用户偏好
2. 引导用户完成六元组记录
3. 写入 write("diary/2026/03/2026-03-31.md", content)
4. 如果提到人名，读取 read("people/小凯.md") 并更新

# 改造后
当用户想记录情绪时：
1. 调用 user_profile_get() 获取用户偏好
2. 引导用户完成六元组记录
3. 调用 diary_write(date="2026-03-31", entry=content)
4. 如果提到人名，调用 person_get(name="小凯") 并通过 person_update() 更新
```

### 需要改造的 Skill 清单

| Skill | 涉及的文件操作 | 改为 Service Tool |
|-------|---------------|------------------|
| diary | read/write USER.md, people/*.md, diary/*.md | user_profile_get, person_get/update, diary_write |
| check-in | read/write USER.md, diary/*.md | user_profile_get, diary_write |
| pattern-mirror | read people/*.md, exec pattern_engine.py | person_list, person_get, pattern_match |
| relationship-guide | read people/*.md, USER.md | person_get, user_profile_get |
| relationship-skills | read people/*.md | person_get |
| decision-cooling | read/write memory/pending_followup.md | user_profile_get/update (followup 字段) |
| farewell | edit people/*.md (archive) | person_update (archive 状态) |
| growth-story | exec growth_tracker.py, read diary/*.md | growth_track, diary_read |
| weekly-reflection | read diary/*.md, exec emotion_counter.py | diary_read, emotion_count |
| breathing-ground | 无文件操作 | 无需改造 |

### 改造原则

- SKILL.md 里只引用 Service Tool 名称，不出现任何文件路径
- 本地和线上使用同一份 SKILL.md，环境差异在 Service 层内部处理
- PM 修改 SKILL.md 时只需要知道 Tool 名称和参数，不需要关心存储细节

---

## 10. 核心流程零丢失定义

### 必须零丢失（用户直接感知）

| 核心流程 | 验收标准 |
|---------|---------|
| 四步情绪对话 | 看见情绪→原因→模式→方法，每步都能触发 |
| 危机信号检测 | ai_safety_brake 在用户表达伤害意图时必须触发 |
| 对话历史持久化 | 用户换设备/刷新后仍能看到历史消息 |
| 用户画像写入 | 对话后用户画像被正确更新 |
| 情绪日记写入 | diary_write 产生的日记在后续 diary_read 中可查 |
| 课程完整流程 | 课程卡片→练习题→提交答案→完成检测 |
| Heartbeat 主动关怀 | 4 条规则在支持的渠道上正常触发 |

### 安全边界零丢失（不可妥协）

1. 不输出诊断性结论（"你有抑郁症"）
2. 不替用户做决定（"你应该离开他"）
3. 不对不在场的人做动机判断（"他不在乎你"）
4. 危机信号必须触发 ai_safety_brake，阻塞式等待
5. 不向第三方泄露用户隐私细节

### 允许差异（迁移中可接受降级）

| 功能 | 允许的差异 |
|------|---------|
| MBTI 报告 | 生成延迟从 <5s 增加到 <30s |
| 课程大纲生成 | 6 步收集可简化为 3 步，后续 Skill 迭代 |
| pattern-mirror 可视化 | 允许纯文本描述，无需图表 |
| 语音输入 | 允许延迟增加 <500ms |
| 微信小程序 Heartbeat | 降级为队列式（下次登录补发），其他渠道正常推送 |
| 周日回顾格式 | 允许纯文本，无需特殊卡片 |

---

## 11. 风险与对策

| 风险 | 对策 |
|------|------|
| Agent 迁移丢失核心流程 | TDD 驱动：录制行为信号基线（state_after + ui_events + response_contains） |
| OpenClaw 不支持覆盖内置 Tool | 方案 3 已规避：deny 内置 Tool，只用自定义 Tool |
| Tool Bridge 延迟 | localhost HTTP，<5ms，可忽略 |
| Tool 数量过多导致 LLM 选错 | Tool 分组（每组 ~15 个） + 类型约束（枚举代替自由字符串） |
| 10 万用户 DB 压力 | workspace_files 表加索引，热数据 Redis 缓存 |
| PM 和开发改动冲突 | Submodule pin 版本，开发决定何时更新 |
| OpenClaw Gateway 单点故障 | 健康检查 + 自动重启，ChatProxy 超时降级 |
| Skill 与 Service Tool 接口不匹配 | 集成测试覆盖，CI 双跑（FileBackend + DatabaseBackend） |
| exec 脚本线上不可用 | 全部 Service 化，原 exec 逻辑迁移到 Python Service |
| sandbox.scope 配置待验证 | 沿用项目原配置 per-sender，迁移 M00 时验证 OpenClaw 实际行为 |
| 微信小程序 Heartbeat 推送限制 | 其他渠道原生支持；微信端单独适配（订阅消息 API 或下次登录补发） |
| 会话隔离（多用户串话） | ChatProxy 传 user 字段给 OpenClaw，派生稳定 session key |
