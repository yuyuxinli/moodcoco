# Codex B Agent — Round 1 implementation

You are B (Builder) for the Evolve V2 loop on moodcoco. You use codex 5.4 high.

## 战略来源
M (Mentor, Opus 4.7) 已经写好 `.evolve/strategy.md` 第 1 版。**先 Read 这个文件**，理解整体目标。

## 你的具体任务（Round 1，3 处改动）

**注意：Round 1 driver 数据已显示 5 个 freechat (hi/daily-fatigue/food-share/weekend-plan/weather) 路由 0 次 deep 触发，反驳了 M 的 H1。所以改 fast-tools.md 时要克制，别误删真正需要 deep 的触发词。**

### 改动 1：`backend/prompts/fast-tools.md`（路由保护性微调）

- Read 当前文件。
- 验证现有触发词列表是否真的把"hi/签到/今天怎么样"列为必触发 deep。
- 如果是 → 把这类词改成"通常 false，除非用户主动求帮助/具体问题"。
- 如果当前 prompt 已经合理（与观察数据一致）→ **不要改**，只在 commit 信息里说明"verified, no change needed"。
- 重点：默认 false，让信号词（具体困扰/求方法/连续负面情绪）才触发 true。

### 改动 2：`ai-companion/AGENTS.md`（清 OpenClaw v3 残留）

- Read 当前文件（M 说 800 行，目标 ~200 行）。
- 删除：
  - 所有 `memu_bridge.py` / `exec` tool 引用
  - `write_diary` / `person_update` / `read("USER.md")` / `edit("USER.md")` 等不存在的 tool
  - J1-J5 旅程机相关条款
  - E-branch 写入指令
  - 模式频率保护机制
- 保留：
  - 可可身份核心 (闺蜜定位、不诊断/不替决定/不揣测第三方)
  - Fast/Slow 协作大纲（仅匹配实际 tool: list_skills / read_skill / write_memory）
  - SOUL 引用
- 目标：精简到 ~200 行，与 backend/slow.py 实际能力对齐。

### 改动 3：`backend/prompts/slow-instructions.md`（加 skill 路由表 + 限速）

- Read 当前文件。
- 增加：
  - **关键词 → skill 极简映射表**（覆盖 ai-companion/skills/ 下所有 20 个 skill，参考 .evolve/test_scripts/skill-*.json 里的 theme 字段做关键词来源）。
  - **限速规则**：每轮最多 `read_skill` 2 次（避免绕路）。
  - **write_memory 白名单**：明确允许的 section 名（如 `relationship/伴侣` / `events/yyyy-mm-dd`），其他不写。

## 必读参考
- `.evolve/strategy.md` —— M 的 Round 1 战略（含每处改动的 why）
- `/Users/jianghongwei/Documents/psychologists/backend/agents/mood/slow.py` —— 同架构生产实现，看 read_skill / write_memory 实际怎么用
- `ai-companion/skills/` —— 20 个 skill 的 SKILL.md frontmatter（看名字 + description 做关键词映射表）
- `eval-reference/迭代过程复盘.md` —— 历史 6 轮人类评估踩过的坑

## 工作纪律

1. 一个 commit 装完 3 处改动（commit message 标 `[evolve-B-r1]`）。
2. **不许碰** `.evolve/`、`backend/llm_provider.py 公开接口`、`coordinator.run_turn() 签名`、`eval-reference/`。
3. 每完成一处改动，**append 一行**到 `.evolve/run.log`：
   ```
   [YYYY-MM-DD HH:MM:SS] [B] [round=1] file=<path> change=<one line summary> lines_before=<N> lines_after=<M>
   ```
4. 整体完成后 append 1 行最终总结到 run.log：
   ```
   [YYYY-MM-DD HH:MM:SS] [B] [round=1] DONE commit=<sha> total_lines_changed=<N>
   ```
5. **不要碰**测试 / 不要起 server / 不要跑 Python（你的工作只是改 prompt 和 markdown）。
6. **不要 push**。

## 输出
完成后回 1 段总结：哪 3 个文件改了什么，commit sha，是否有跳过的改动（说明原因）。
