# 迁移手册：心理咨询 × Mood Coco

## 总原则

1. **核心流程零丢失**：每一步完成后，核心流程（四步情绪对话、危机检测、持久化、课程流程、Heartbeat）和安全边界必须完好。允许差异清单见设计文档 §10
2. **TDD 驱动**：先录制行为信号基线（state_after + ui_events_emitted + response_contains），再改代码，基线通过率 ≥ 90% 才算完成
3. **可独立执行**：每一步都是一个完整的 evolve goal，可以独立运行
4. **依赖严格**：标注了 `blocked_by` 的步骤必须等前置步骤完成
5. **所有 OpenClaw 配置必须引用官方文档出处**：不可凭推测写配置

## 依赖关系图

```
M00-pre 执行环境预检
 └── M00 基础设施
      ├── M01 WorkspaceStorage 抽象
      │    └── M12 DatabaseBackend（延后到线上阶段）
      ├── M02 Tool Bridge 端点
      │    ├── M03 Service Tool 端到端
      │    └── M04 UI Tool 端到端（含 WebSocket 测试基础设施）
      ├── M05 ChatProxy 端到端
      │
      ├── [M03 + M04 + M05 全部完成后]
      │    ├── M06 MotivationAgent 迁移
      │    ├── M07 ChatAgent 迁移
      │    │    └── M08 MbtiAgent 迁移
      │    │         └── M09 MoodAgent 迁移
      │    │              └── M10-A CourseGenerateAgent 迁移
      │    │                   └── M10-B CourseDialogueAgent 迁移
      │    │
      │    ├── M11-A Skill 改造（Service-only，6 个，blocked_by M03）
      │    │
      │    └── M11-exec exec 脚本 Service 化（blocked_by M01 + M02）
      │         └── M11-B Skill 改造（exec-依赖，3 个）
      │
      └── [所有 Agent + Skill 迁移完成后]
           ├── M12 DatabaseBackend + 线上配置
           ├── M13 Docker 部署验证
           └── M14 清理旧代码
```

---

## 阶段一：基础设施（本地跑通前提）

### M00-pre: 执行环境预检

**目标**：验证 AI Agent 具备执行所有迁移步骤所需的环境条件，生成 `.migration_env` 供后续步骤引用。

**blocked_by**: 无

**做什么**：
1. 逐项执行预检清单（每项失败时 AI Agent 自主修复后重试）
2. 全部通过后，将关键路径写入 `{MOODCOCO_PATH}/.migration_env`

**预检清单**：

| 检查项 | 验证命令 | 通过条件 |
|--------|---------|---------|
| psychologists 仓库 | `ls ${PSYCHOLOGISTS_PATH}/backend/*.py` | 有 Python 文件 |
| Git submodule 支持 | `git submodule --version` | 返回版本号 |
| Python >= 3.10 | `python3 -c "import sys; assert sys.version_info >= (3,10)"` | 无 AssertionError |
| pytest + asyncio | `python3 -m pytest --version` | 返回版本号 |
| python-socketio client | `python3 -c "import socketio"` | 无 ImportError |
| OpenClaw CLI | `openclaw --version` | 返回版本号 |
| OPENROUTER_API_KEY | `test -n "$OPENROUTER_API_KEY"` | exit 0 |

**输出**：`.migration_env` 文件
```bash
PSYCHOLOGISTS_PATH=/Users/jianghongwei/Documents/psychologists
MOODCOCO_PATH=/Users/jianghongwei/Documents/moodcoco
```

**评估标准**：
| 维度 | 通过条件 | 权重 |
|------|---------|------|
| 所有检查通过 | 7 项预检全部 pass | 60% |
| env 文件有效 | `.migration_env` 存在且包含正确路径 | 30% |
| psychologists 可访问 | `ls ${PSYCHOLOGISTS_PATH}/backend/` 输出非空 | 10% |

---

### M00: 仓库结构搭建

**目标**：建立合并后的仓库结构，OpenClaw Gateway 能启动，两个项目现有功能不受影响。

**blocked_by**: M00-pre

**做什么**：
1. 在 psychologists 仓库的 backend/ 下添加 ai-companion/ 作为 Git Submodule（指向 moodcoco 仓库）
2. 创建 `backend/openclaw_bridge/` 目录，初始化为 OpenClaw Plugin 骨架
3. 在项目根目录创建 `openclaw.json` 基础配置
4. 确认 OpenClaw Gateway 能在本地启动，加载 ai-companion/ 作为 workspace

**不做什么**：
- 不改心理咨询项目的任何现有代码
- 不改 Mood Coco 的任何现有文件

**评估标准**：
| 维度 | 通过条件 | 权重 |
|------|---------|------|
| Gateway 启动 | `openclaw start` 成功，日志无报错 | 30% |
| Plugin 加载 | Gateway 日志显示 openclaw_bridge plugin loaded | 30% |
| 现有功能 | psychologists 项目的所有现有测试通过 | 20% |
| Submodule | `git submodule status` 显示 ai-companion/ 指向 moodcoco commit | 20% |

---

### M01: WorkspaceStorage 抽象层

**目标**：创建统一的用户数据存储接口，本地用 FileBackend。

**blocked_by**: M00

**做什么**：
1. 创建 `backend/services/workspace_storage.py`
2. 实现 `WorkspaceStorage` 抽象基类（read / write / list_dir / delete / search）
3. 实现 `FileBackend`（读写 ai-companion/ 目录下的文件）
4. 单元测试覆盖所有方法

**评估标准**：
| 维度 | 通过条件 | 权重 |
|------|---------|------|
| 接口完整 | ABC 定义了 read/write/list_dir/delete/search 五个方法 | 20% |
| FileBackend | 所有方法对文件系统的读写正确 | 30% |
| 测试覆盖 | 单元测试覆盖正常路径 + 文件不存在 + 目录不存在 + 中文内容 | 30% |
| 隔离性 | 不同 user_id 的数据互不影响 | 20% |

---

### M02: Tool Bridge HTTP 端点

**目标**：创建 FastAPI 端点，供 OpenClaw Plugin 通过 HTTP 调用后端 Tool 和 Service。

**blocked_by**: M00

**做什么**：
1. 创建 `backend/api/routes/tool_bridge.py`
2. 实现 `POST /api/tool-bridge/{tool_name}` 端点
3. 路由逻辑：识别 UI Tool（转调 ToolRegistry）和 Service Tool（转调 Service 层）
4. 从请求中提取 user_id（OpenClaw 会在请求头中传递）
5. 注册到 FastAPI app

**评估标准**：
| 维度 | 通过条件 | 权重 |
|------|---------|------|
| 端点可达 | `POST /api/tool-bridge/test` 返回 200 | 20% |
| UI Tool 路由 | 请求 ai_message → 正确转调 ToolRegistry | 30% |
| Service Tool 路由 | 请求 user_profile_get → 正确转调 Service 层 | 30% |
| user_id 提取 | 从请求头正确提取 user_id 传入 context | 20% |

---

### M03: 第一个 Service Tool 端到端

**目标**：实现 `user_profile_get`，验证完整链路：OpenClaw Agent → Plugin → tool_bridge → Service → WorkspaceStorage → 返回。

**blocked_by**: M01, M02

**做什么**：
1. 在 `backend/services/` 中创建 user_profile_service（从 WorkspaceStorage 读取 USER.md）
2. 在 tool_bridge 中注册 user_profile_get 路由
3. 在 openclaw_bridge Plugin 中注册 user_profile_get Tool（调 tool_bridge HTTP 端点）
4. 端到端测试：Agent 调用 user_profile_get → 返回 USER.md 内容

**评估标准**：
| 维度 | 通过条件 | 权重 |
|------|---------|------|
| Service 层 | user_profile_service.get() 返回 USER.md 内容 | 25% |
| tool_bridge | HTTP 请求 user_profile_get 返回正确 JSON | 25% |
| Plugin 注册 | OpenClaw Agent 的 tool list 中包含 user_profile_get | 25% |
| 端到端 | Agent 发消息 "查看我的画像" → 调用 user_profile_get → 返回内容 | 25% |

---

### M04: 第一个 UI Tool 端到端

**目标**：实现 `ai_options`，验证 UI Tool 链路：OpenClaw Agent → Plugin → tool_bridge → ToolRegistry → WebSocket 推前端。

**blocked_by**: M02

**做什么**：
1. 在 openclaw_bridge Plugin 中注册 ai_options Tool
2. 在 tool_bridge 中实现 UI Tool 路由（识别 InteractionMode，调原有 ToolRegistry）
3. 实现 WebSocket 推送逻辑（通过 Socket.IO emit 推给前端）
4. 端到端测试：Agent 决定展示选项 → ai_options → 前端收到选项卡数据

**评估标准**：
| 维度 | 通过条件 | 权重 |
|------|---------|------|
| Plugin 注册 | ai_options 出现在 Agent tool list 中 | 20% |
| ToolRegistry 调用 | tool_bridge 正确找到 AI_OPTIONS Tool 并执行 | 25% |
| WebSocket 推送 | 前端 Socket.IO 收到 ai_options 的结构化 JSON | 30% |
| Agent 回调 | Plugin execute() 返回 "已推送到用户界面" 给 Agent | 25% |

---

### M05: ChatProxy 端到端

**目标**：实现小程序 → ChatProxy → OpenClaw Gateway → Agent 的完整对话链路。

**blocked_by**: M00

**做什么**：
1. 创建 `backend/services/chat_proxy.py`（ChatProxy 类）
2. 实现 send_to_openclaw()：HTTP 流式请求 OpenClaw Gateway
3. 实现 _convert_to_frontend_format()：OpenClaw 输出 → 前端 stream_chunk 格式
4. 修改 ws_socketio.py 的 handle_send_message：新增路由开关，可选走 ChatProxy 或原 ChatEngine
5. 端到端测试：前端发消息 → ChatProxy → OpenClaw Agent 回复 → 前端显示

**关键约束**：
- 路由开关默认走原 ChatEngine（不影响现有功能）
- 只有显式指定时才走 ChatProxy（用于测试新链路）

**评估标准**：
| 维度 | 通过条件 | 权重 |
|------|---------|------|
| 流式转发 | ChatProxy 正确流式接收 OpenClaw 输出并逐 chunk 转发 | 30% |
| 格式转换 | 转换后的 chunk 格式与原有 stream_chunk 格式兼容 | 25% |
| 路由开关 | 默认走旧 ChatEngine（现有测试全通过），开关打开走 ChatProxy | 25% |
| 端到端 | 前端发 "你好" → ChatProxy → Agent → 前端显示回复 | 20% |

---

## 阶段二：Agent 迁移（每个 Agent 一步）

### 通用迁移流程

每个 Agent 迁移都遵循相同的 4 步流程：

```
Step A: 录制行为基线
  → 在现有系统上跑测试场景，录制 input/output 对
  → 这些录制 = 回归测试基线

Step B: 提取 Service 层
  → 把 Agent 中的纯业务逻辑（非 LLM）提取到 Service
  → 通过 tool_bridge 暴露为 Service Tool
  → 注册到 OpenClaw Plugin
  → 验证：原有 Agent 仍然正常工作（不碰 Agent 代码，只是多了 Service）

Step C: 写 OpenClaw Skill
  → 创建 SKILL.md，描述对话策略
  → 在 SKILL.md 中引用 Service Tool 和 UI Tool（不引用 read/write/edit）
  → 集成测试：Agent + Skill + Tool → 对比 Step A 的基线

Step D: 切换
  → 修改路由开关，该 session type 走 OpenClaw
  → 全量验证 Step A 的所有测试场景
  → 通过后，该 Agent 迁移完成
```

---

### M06: MotivationAgent 迁移

**目标**：最简单的 Agent，仅有 Prompt 模板，作为迁移热身。

**blocked_by**: M03, M04, M05

**现有逻辑（196 LOC，仅 Prompt）**：
- SYSTEM_PROMPT：对话指令
- SCHEDULE_GENERATION_PROMPT：课程生成
- build_conversation_prompt()：动态 Prompt 构建
- build_schedule_prompt()：课表 Prompt 构建
- 3 阶段进度追踪：main_emotion → trigger_context → motivation_goal
- UI blocks 类型：text, options, thinking, schedule_preview, cta

**拆分**：
| 逻辑 | LLM? | 去向 |
|------|------|------|
| 对话引导 | 是 | OpenClaw Skill: skills/motivation/ |
| 进度追踪（3 point） | 否 | Service: motivation_service |
| UI block 格式化 | 否 | UI Tool: ai_options / ai_message |

**评估标准**：
| 维度 | 通过条件 | 权重 |
|------|---------|------|
| 对话质量 | Agent 能完成 3 阶段对话收集 | 30% |
| 进度追踪 | Service Tool 正确记录和返回进度 | 25% |
| UI 交互 | 选项卡、文本消息正确推送到前端 | 25% |
| 回归 | 原有 MotivationAgent 的功能场景全部覆盖 | 20% |

---

### M07: ChatAgent 迁移

**目标**：建立纯 LLM 对话的迁移模式，验证消息持久化链路。

**blocked_by**: M06

**现有逻辑（695 LOC）**：
- 自由对话（LLM 流式输出）
- 消息持久化：pre-create → 流式累积 → update（或 delete）
- 对话历史查询 + 过滤（skip null/empty，limit 1000）
- 人格分析报告生成（8 维度评分）
- JSON 解析 fallback
- 异步 session summary
- 欢迎消息生成（enter 事件）

**拆分**：
| 逻辑 | LLM? | 去向 |
|------|------|------|
| 自由对话 | 是 | OpenClaw Agent 原生 |
| 人格分析报告 | 是 | OpenClaw Skill: skills/personality-analysis/ |
| 消息持久化 | 否 | Service Tool: message_persist |
| 历史查询+过滤 | 否 | Service Tool: conversation_history |
| JSON 解析 fallback | 否 | Service: message_persistence.parse_response() |
| 异步 summary | 否 | Service: session_service.trigger_summary() |
| 欢迎消息 | 是 | OpenClaw Skill（或 AGENTS.md 首次对话规则） |

**评估标准**：
| 维度 | 通过条件 | 权重 |
|------|---------|------|
| 对话流畅 | 多轮自由对话正常，流式输出无断裂 | 25% |
| 消息持久化 | 用户消息和 AI 回复都正确保存到 PostgreSQL | 25% |
| 人格分析 | 触发分析 → 生成 8 维度报告 → 保存 | 20% |
| 历史连续 | 新会话能查到之前的对话历史 | 15% |
| 回归 | 原有 ChatAgent 的所有交互场景覆盖 | 15% |

---

### M08: MbtiAgent 迁移

**目标**：验证异步任务模式（报告生成是后台任务）。

**blocked_by**: M07

**现有逻辑（400 LOC）**：
- MBTI 对话引导
- 保存答案：save_user_mbti_answer(session_id, question_id, answer)
- Likert 1-5 量表映射
- 异步报告生成：event_dispatcher.start_mbti_report_generation()
- 事件路由：UserMessageEvent / UserActionEvent("generate_report") / UserActionEvent("mbti_answer")

**拆分**：
| 逻辑 | LLM? | 去向 |
|------|------|------|
| MBTI 对话引导 | 是 | OpenClaw Skill: skills/mbti-game/ |
| 保存答案 | 否 | Service Tool: mbti_save_answer |
| Likert 映射 | 否 | Service: mbti_service.map_likert() |
| 报告生成任务 | 否 | Service Tool: mbti_generate_report |

**评估标准**：
| 维度 | 通过条件 | 权重 |
|------|---------|------|
| 对话引导 | Agent 能引导用户完成 MBTI 问答 | 25% |
| 答案保存 | 每个答案正确保存到数据库 | 25% |
| 报告生成 | 异步任务触发成功，报告生成完整 | 25% |
| 回归 | 量表映射、事件路由全部正确 | 25% |

---

### M09: MoodAgent 迁移

**目标**：验证 Tool Bridge 完整能力（UI Tool + Service Tool + TTS）。

**blocked_by**: M08

**现有逻辑（300 LOC）**：
- 状态机：MOOD_SELECT → CHATTING → RECOVERY
- Tool 架构：OpenAI Function Calling，白名单控制
- 情绪类型验证（EmotionType enum）
- 情绪选择后上下文注入（ContextInjection）
- TTS 音频合成（MiniMax TTS → Socket.IO emit）
- input_mode 历史记录

**拆分**：
| 逻辑 | LLM? | 去向 |
|------|------|------|
| 情绪对话引导 | 是 | OpenClaw Agent（AGENTS.md 四步框架天然覆盖） |
| 情绪恢复引导 | 是 | OpenClaw Skill: skills/mood-recovery/ |
| 状态机推进 | 否 | Service Tool: mood_transition |
| 情绪类型验证 | 否 | Service: mood_service.validate_emotion() |
| 上下文注入 | 否 | Service: mood_service.get_emotion_context() |
| TTS 合成 | 否 | Service Tool: audio_synthesize |
| input_mode 记录 | 否 | Service: mood_service.track_input_mode() |

**评估标准**：
| 维度 | 通过条件 | 权重 |
|------|---------|------|
| 情绪选择 | 用户选择情绪 → Agent 正确响应 | 20% |
| 四步框架 | 对话体现看见情绪→原因→模式→方法 | 20% |
| TTS | 语音合成正常工作，前端播放无异常 | 20% |
| 状态转换 | MOOD_SELECT→CHATTING→RECOVERY 正确流转 | 20% |
| 回归 | 所有 Tool 白名单、上下文注入行为一致 | 20% |

---

### M10-A: CourseGenerateAgent 迁移

**目标**：验证复杂状态机（6 步对话 + 2 步思考 + 课程生成）。

**blocked_by**: M09

**现有逻辑（588 LOC）**：
- 6 步对话收集：main_emotion(2步) → trigger_context(2步) → motivation_goal(2步)
- 2 步思考：知识匹配 → 大纲生成
- 课程大纲生成（5 天课表）
- 进度追踪（3 point completion）
- step 归一化（int/str 转换）
- fallback 默认课程结构
- 场景/知识加载

**拆分**：
| 逻辑 | LLM? | 去向 |
|------|------|------|
| 6 步对话引导 | 是 | OpenClaw Skill: skills/course-generate/ |
| thinking step 1（知识匹配） | 是 | Skill 内 Agent 自主推理 |
| thinking step 2（大纲生成） | 是 | Skill 内 Agent 自主推理 |
| 课程大纲输出 | 是 | Skill 内 Agent 生成 |
| 进度追踪 | 否 | Service Tool: course_generate_progress |
| step 归一化 | 否 | Service: course_service.normalize_step() |
| fallback 默认课程 | 否 | Service: course_service.get_default_curriculum() |
| 场景/知识加载 | 否 | Service Tool: course_load_context |

**评估标准**：
| 维度 | 通过条件 | 权重 |
|------|---------|------|
| 6 步收集 | Agent 正确引导完成 6 步对话 | 25% |
| 思考过程 | 知识匹配 + 大纲生成流程正常 | 20% |
| 课程生成 | 输出合理的 5 天课程表 | 20% |
| 进度追踪 | 3 point completion 正确记录 | 15% |
| 回归 | fallback、step 归一化等边界情况覆盖 | 20% |

---

### M10-B: CourseDialogueAgent 迁移

**目标**：最复杂的 Agent，7 个子模块全部迁移。

**blocked_by**: M10-A

**现有逻辑（492 LOC + 子模块）**：
- dialogue_handler：多轮课程对话 + preset options 生成 + completion 检测
- practice_handler：练习题生成 + 答案评估
- micro_lesson_handler：微课卡片生成 + 音频合成
- next_card_handler：课程步骤推进
- common_methods：共享工具方法
- prompt_builder：Prompt 构建
- 事件路由：7 种 UserActionEvent

**拆分**：
| 逻辑 | LLM? | 去向 |
|------|------|------|
| 课程对话引导 | 是 | OpenClaw Skill: skills/course-dialogue/ |
| 微课卡片内容生成 | 是 | OpenClaw Skill: skills/micro-lesson/ |
| 练习题生成 | 是 | OpenClaw Skill: skills/quiz-practice/ |
| init_dialogue | 否 | Service Tool: course_init_dialogue |
| next_card | 否 | Service Tool: course_advance_card |
| submit_answer + 评分 | 否 | Service Tool: course_submit_answer |
| completion 检测 | 否 | Service Tool: course_check_completion |
| preset options 解析 | 否 | Service: course_service.parse_options() |
| 音频合成 + 写回 | 否 | Service Tool: audio_synthesize |

**评估标准**：
| 维度 | 通过条件 | 权重 |
|------|---------|------|
| 课程对话 | 多轮对话流畅，preset options 正确展示 | 20% |
| 微课 | 卡片生成完整，音频合成正常 | 20% |
| 练习 | 题目生成合理，答案评分正确 | 20% |
| 步骤推进 | init → card → card → ... → complete 全流程 | 20% |
| 回归 | 7 种事件路由全部覆盖，completion 检测正确 | 20% |

---

### M11-A: Skill 改造（Service-only，6 个）

**目标**：改造不依赖 exec 脚本的 6 个 Skill，用 Service Tool 替换 read/write/edit 调用。

**blocked_by**: M03

**需改造**：

| Skill | 原文件操作 | 改为 |
|-------|-----------|------|
| diary | read/write USER.md, people/*.md, diary/*.md | user_profile_get, person_get/update, diary_write |
| check-in | read/write USER.md, diary/*.md | user_profile_get, diary_write |
| relationship-guide | read people/*.md, USER.md | person_get, user_profile_get |
| relationship-skills | read people/*.md | person_get |
| decision-cooling | read/write memory/pending_followup.md | user_profile_get/update |
| farewell | edit people/*.md | person_update |

**评估标准**：
| 维度 | 通过条件 | 权重 |
|------|---------|------|
| 零文件引用 | 6 个 SKILL.md 中不出现 read/write/edit 调用 | 30% |
| Service Tool 引用 | 正确引用 Service Tool 名称（工具已在 M03 注册） | 30% |
| 功能覆盖 | 每个 Skill 的核心场景 pytest 测试通过 | 40% |

---

### M11-exec: exec 脚本 Service 化

**目标**：将 3 个 exec 脚本包装为 async Service 函数，注册为 Service Tool。

**blocked_by**: M01, M02

**做什么**：
1. 在 `backend/services/exec_service.py` 中创建 3 个 async 包装函数：
   - `pattern_match(user_id, target, min_relations, storage)` — 包装 pattern_engine.py
   - `emotion_count(user_id, message, session_id, threshold, storage)` — 包装 emotion_counter.py
   - `growth_track(user_id, since, im_types, storage)` — 包装 growth_tracker.py
2. 在 `tool_bridge.py` 中注册 3 个路由
3. 在 `openclaw_bridge/adapters/service_tools.ts` 中注册 3 个 Tool 定义
4. 编写 `tests/test_exec_service.py`

**不做什么**：不修改 moodcoco 中的脚本逻辑（原地包装）

**评估标准**：
| 维度 | 通过条件 | 权重 |
|------|---------|------|
| 函数签名 | 3 个 async 函数均接受 user_id + storage 参数 | 15% |
| tool_bridge 注册 | `POST /api/tool-bridge/pattern_match` 等 3 个端点返回 200 | 25% |
| Plugin 注册 | Agent tool list 中包含 pattern_match / emotion_count / growth_track | 25% |
| 集成测试 | `pytest tests/test_exec_service.py` 全绿 | 35% |

---

### M11-B: Skill 改造（exec-依赖，3 个）

**目标**：改造依赖 exec 脚本的 3 个 Skill。

**blocked_by**: M11-exec

**需改造**：

| Skill | 原文件操作 | 改为 |
|-------|-----------|------|
| pattern-mirror | read people/*.md, exec pattern_engine.py | person_list, person_get, pattern_match |
| growth-story | exec growth_tracker.py, read diary/*.md | growth_track, diary_read |
| weekly-reflection | read diary/*.md, exec emotion_counter.py | diary_read, emotion_count |

**评估标准**：
| 维度 | 通过条件 | 权重 |
|------|---------|------|
| 零文件引用 | 3 个 SKILL.md 中不出现 exec/read 调用 | 30% |
| Service Tool 存在 | pattern_match/emotion_count/growth_track 已在 tool_bridge 注册 | 30% |
| 功能覆盖 | 每个 Skill 的核心场景 pytest 测试通过 | 40% |

---

## 阶段三：线上就绪

### M12: DatabaseBackend 实现

**目标**：实现 WorkspaceStorage 的 PostgreSQL 后端，所有 Service Tool 在数据库模式下正常工作。

**blocked_by**: M01, M06-M10B 全部完成

**做什么**：
1. 创建 workspace_files 表（user_id + path + content + updated_at，唯一索引）
2. 实现 DatabaseBackend（read/write/list_dir/delete/search）
3. 用 FileBackend 的全部测试跑 DatabaseBackend，结果一致
4. search 方法：基于 PostgreSQL 全文搜索或对接 Chroma

**评估标准**：
| 维度 | 通过条件 | 权重 |
|------|---------|------|
| 表结构 | workspace_files 表创建成功，索引正确 | 15% |
| CRUD | read/write/list_dir/delete 全部正确 | 30% |
| 一致性 | FileBackend 的所有测试用例在 DatabaseBackend 上全部通过 | 35% |
| search | 语义搜索返回相关结果 | 20% |

---

### M13: Docker 部署验证

**目标**：Docker Compose 一键启动，端到端功能验证。

**blocked_by**: M12

**做什么**：
1. 编写 Docker Compose（backend + openclaw + postgres + redis）
2. openclaw.json 生产配置（deny read/write/edit/exec）
3. 环境变量配置（APP_ENV=production → 使用 DatabaseBackend）
4. 端到端测试：在 Docker 环境中跑完整用户流程

**评估标准**：
| 维度 | 通过条件 | 权重 |
|------|---------|------|
| 一键启动 | `docker compose up` 所有服务正常启动 | 20% |
| 对话 | 用户发消息 → Agent 回复 → 前端显示 | 25% |
| 课程 | 完整课程流程（生成→对话→微课→练习）可走通 | 25% |
| 持久化 | 重启容器后用户数据不丢失 | 15% |
| 生产配置 | Agent 无法调用 read/write/edit/exec，只用 Service Tool | 15% |

---

### M14: 清理旧代码

**目标**：删除所有已迁移的旧 Agent 代码和废弃依赖。

**blocked_by**: M13

**做什么**：
1. 删除 `backend/agents/` 目录下所有已迁移的 Agent
2. 删除 ChatEngine
3. 删除 L0-L5 上下文构建器（如果不再被其他模块引用）
4. 删除 LiteLLM 依赖（如果不再被其他模块引用）
5. 确认所有测试通过

**不删除**：
- tools/ 目录（UI Tool 仍在使用）
- services/ 目录（Service 层是核心）
- ws_socketio.py（保留，但内部走 ChatProxy）

**评估标准**：
| 维度 | 通过条件 | 权重 |
|------|---------|------|
| 无残留 | 删除的文件不被任何现有代码 import | 40% |
| 测试通过 | 全部测试通过 | 40% |
| 依赖清理 | pyproject.toml 中移除不再使用的依赖 | 20% |

---

## 快速参考：依赖与预计规模

| 步骤 | blocked_by | 预计涉及文件数 | 核心输出 |
|------|-----------|---------------|---------|
| M00-pre | 无 | 1 | .migration_env 环境预检 |
| M00 | M00-pre | 5-10 | 仓库结构 + OpenClaw 启动 |
| M01 | M00 | 2-3 | WorkspaceStorage + FileBackend |
| M02 | M00 | 2-3 | tool_bridge.py 端点 |
| M03 | M01, M02 | 5-8 | 第一个 Service Tool 端到端 |
| M04 | M02 | 5-8 | 第一个 UI Tool 端到端 + WebSocket 测试基础设施 |
| M05 | M00 | 3-5 | ChatProxy 端到端（含 user_id 传递） |
| M06 | M03-M05 | 3-5 | MotivationAgent → Skill |
| M07 | M06 | 8-12 | ChatAgent → Skill + Service |
| M08 | M07 | 6-10 | MbtiAgent → Skill + Service |
| M09 | M08 | 8-12 | MoodAgent → Skill + Service + UI Tool |
| M10-A | M09 | 8-12 | CourseGenerateAgent → Skill + Service |
| M10-B | M10-A | 15-20 | CourseDialogueAgent → Skill + Service（最大） |
| M11-A | M03 | 6-8 | 6 个 Service-only Skill 改造 |
| M11-exec | M01, M02 | 3-5 | 3 个 exec 脚本 Service 化 |
| M11-B | M11-exec | 3-5 | 3 个 exec-依赖 Skill 改造 |
| M12 | M01, 全部 Agent+Skill 完成 | 3-5 | DatabaseBackend |
| M13 | M12 | 5-8 | Docker Compose 部署 |
| M14 | M13 | 删除为主 | 清理旧代码 |
