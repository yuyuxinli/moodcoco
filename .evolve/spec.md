# Feature Specs

## F1: eval_s1 — S1 专属评分标准

创建 `.evolve/eval_s1.yml`，替代通用 `eval.yml` 用于 S1 评估。

**改动**：
1. 对话质量 8 分锚点：去掉"跨会话记忆召回 2 次以上"和"模式识别引用 2 个事件"
2. 替换为 S1 适用标准：精准情绪命名、安全边界无违规、首轮承接质量、收尾有温度
3. 数据正确性：去掉 about_self/about_relations 检查（批处理约束）
4. 功能验证：xiaobo_relation_type_correct 标记 not_applicable
5. 保留原 eval.yml 不动（其他场景仍用）

**验收**：eval_s1.yml 存在，YAML 格式合法，三个维度均有锚点，不含不适用条件。

---

## F2: test-infra — 测试脚本改进

基于 `.evolve/b_output/run_s1_v9.py` 改进测试基础设施。

**改动**：
1. Turn 7 拆成两条消息：先发"他就是小白，是我男朋友"，等回复后再发"好了我好一点了，谢谢你"
2. send_and_wait 改进：tool call 完成后继续等待文字回复（最多额外等 15 秒）
3. 新增 run_s1_median.py：调用 run_s1 三次，取各维度中位数作为最终分数
4. 每次运行输出保存到 .evolve/b_output/S1_raw_v{N}.json（N 自增）

**验收**：run_s1_v10.py 存在，Turn 7 是两条消息，send_and_wait 有 tool_call 后继续等待逻辑。run_s1_median.py 存在。

---

## F3: l1-format — L1 JSON 格式控制 prompt

在 moodcoco/ai-companion/ 下创建 L1 格式控制文档。

**改动**：
1. 创建 `ai-companion/FORMAT_MINIPROGRAM.md`：小程序端 JSON 输出格式约束
   - 定义 content_type 枚举和每种类型的 JSON schema
   - 告诉 Agent "每条回复必须是合法 JSON，包含 content_type 字段"
   - 包含正确示例和错误示例
2. 创建 `ai-companion/FORMAT_TEXT.md`：OpenClaw 端纯文本格式约束（简单）

**验收**：FORMAT_MINIPROGRAM.md 存在，包含所有 16 种 content_type 的 schema 定义。FORMAT_TEXT.md 存在。

---

## F4: tool-types — OpenClaw Plugin Tool 类型定义

在 psychologists/backend/openclaw_bridge/ 下补齐 Tool 类型。

**改动**：
1. 创建 `openclaw_bridge/types/` 目录
2. 为 18 个 UI Tool 补齐参数类型定义（枚举替代自由字符串）
3. 参考 psychologists/backend/tools/ 下现有 Python Tool 定义，提取参数类型
4. 更新 ui_tools.ts 和 service_tools.ts 引用类型定义

**验收**：types/ 目录存在，至少覆盖 ai_message / ai_options / ai_mood_select / ai_safety_brake 四个核心 Tool 的类型定义。
