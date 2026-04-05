# Program: 关系智能 v3 — memU 记忆引擎 + 13 Skill + 15 场景

基于 `docs/product/product-experience-design-v3.md` 五层产品架构，17 Feature 全量落地。

## Product Requirements

1. 引入 memU 记忆引擎（fork 后修改），替代二次读取文件（people/*.md, diary/*.md, memory/*.md）
2. 8 个通用 Skill 引擎（base-communication, listen, untangle, crisis, calm-body, see-pattern, face-decision, know-myself）
3. 5 个运维 Skill 重构对接 memU（diary, onboarding, farewell, check-in, weekly-reflection）
4. 15 个场景 reference 材料（恋爱/家人/室友/朋友/考研/考公/实习/求职/毕业/学业/失眠/认识自己/容貌焦虑/随便聊聊/SOS）
5. AGENTS.md 总重构（13 skill 路由 + 15 场景路由 + memU 集成）
6. 首次读取文件（USER.md, MEMORY.md）保持写入，二次读取文件由 memU 全权管理

## Feature List

Group A — 地基层：
- [ ] F01: memU 记忆引擎集成（fork 源码 + 改 prompt + 动态 category + 桥接脚本）
- [ ] F02: base-communication（承接/澄清/轻推动三组技术）
- [ ] F03: listen（纯倾听）
- [ ] F04: untangle（拆解混乱）
- [ ] F05: crisis（QPR 危机干预）
- [ ] F06: calm-body（身体稳定，原 breathing-ground 升级）

Group B — 高级引擎 + 运维：
- [ ] F07: see-pattern（跨关系模式 + 成长叙事，原 pattern-mirror + growth-story 合并）
- [ ] F08: face-decision（决策支持 + 冷却，原 decision-cooling 扩展）
- [ ] F09: know-myself（自我探索）
- [ ] F10: diary（日记重构，对接 memU）
- [ ] F11: onboarding（首次相遇，对接 memU）
- [ ] F12: farewell（告别仪式，对接 memU）

Group C — 交互层 + 场景：
- [ ] F13: check-in + weekly-reflection（对接 memU）
- [ ] F14: 程序主动触发（洞察推送/跟进/成长提醒）
- [ ] F15: 场景路由 + 推荐（15 场景入口）
- [ ] F16: 15 个场景 reference 材料
- [ ] F17: AGENTS.md 总重构

## Evaluation Criteria

详见 eval.yml。5 个核心维度 + 1 个 OpenClaw 对话测试。

## Technical Constraints

- 工作区：ai-companion/（OpenClaw workspace）
- memU 源码：/Users/jianghongwei/Documents/GitHub/memU/（fork 到 ai-companion/memu/）
- 首次读取文件不能废弃：USER.md, MEMORY.md, SOUL.md, IDENTITY.md, HEARTBEAT.md
- 二次读取文件由 memU 替代：people/*.md, diary/*.md, memory/*.md
- 数据库：PostgreSQL（线上已有），向量检索暂不开
- LLM：minimax-m2.7 via OpenRouter
- OpenClaw 测试：openclaw agent --agent coco --local -m "test" --json
- Skill 上限 15 个（当前设计 13 个）
- 不改 OpenClaw 源码

## Agent Rules

- Do not modify program.md
- Do not modify files under .claude/skills/evolve/
- Git commit after each agent run
- 参考文档（B agent 必读）：
  - 产品设计：`docs/product/product-experience-design-v3.md`
  - 需求文档：`ai-companion/docs/relationship-intelligence-upgrade.md`
  - 交大架构：`ai-companion/docs/product-knowledge-architecture-v1.0.md`
  - 现有行为规范：`ai-companion/AGENTS.md`
  - memU 源码：`/Users/jianghongwei/Documents/GitHub/memU/src/memu/`
  - 现有 Skill（参考格式）：`ai-companion/skills/diary/SKILL.md`、`ai-companion/skills/pattern-mirror/SKILL.md`
