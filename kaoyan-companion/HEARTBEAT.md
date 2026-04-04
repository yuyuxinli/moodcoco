# Heartbeat 考研主动关怀

> 考研 workspace 专用 Heartbeat 规则。所有 Cron 触发都服务于备考流程。

---

## Cron 触发规则

考研 workspace 有 4 个定时触发点，按优先级从高到低排列。**同一时间段只执行一条规则，命中即停。**

### 规则 1：每日计划推送（08:00 / 在职考生 07:00）

- **触发时机**：每日 08:00（在职考生 07:00）
- **Cron**：`0 8 * * *`（在职：`0 7 * * *`）
- **检查条件**：`kaoyan_diagnosis_date` 非空 且 `kaoyan_plan_active != false`
- **执行动作**：`read("skills/kaoyan-daily-plan/SKILL.md")` → 运行计划生成引擎 → ai_message 推送 → 写入 plan_history
- **依赖 Skill**：`kaoyan-daily-plan`

### 规则 2：崩溃行为信号检测（10:00）

- **触发时机**：每日 10:00
- **Cron**：`0 10 * * *`
- **检查条件**：`kaoyan_target_school` 存在
- **检查动作**：检查 `memory/kaoyan/tracker/` 最近 2-3 天是否有文件
- **执行条件**：连续 2 天无 tracker 文件 → 轻量探测；`streak.consecutive_none >= 3` → 崩溃接住
- **执行动作**：轻量探测或触发 `kaoyan-crisis`
- **依赖 Skill**：`kaoyan-crisis`

### 规则 3：每日打勾追踪（22:00）

- **触发时机**：每日 22:00
- **Cron**：`0 22 * * *`
- **检查条件**：`kaoyan_target_school` 存在 且 `kaoyan_tracker_preference != "dislike"`
- **检查动作**：检查今天是否已打过勾、是否处于 F6 崩溃后抑制期
- **执行条件**：今日未打勾 且 未处于崩溃后 3 天抑制期
- **执行动作**：`read("skills/kaoyan-tracker/SKILL.md")` → 触发打勾流程
- **依赖 Skill**：`kaoyan-tracker`

### 规则 4：周报（周日 20:00）

- **触发时机**：每周日 20:00
- **Cron**：`0 20 * * 0`
- **检查条件**：`kaoyan_target_school` 存在 且 `kaoyan_weekly_preference != "disabled"` 且本周 tracker ≥ 3 天
- **执行条件**：本周有 ≥ 3 天 tracker 数据（含 done_none/bad_day）
- **执行动作**：`read("skills/kaoyan-weekly/SKILL.md")` → 汇总本周数据 → 生成周报 → 写入 weekly_cache
- **依赖 Skill**：`kaoyan-weekly`
- **互斥**：周日 20:00 发周报后，22:00 不发打勾提醒（周报已包含打勾功能）

---

## Cron 优先级总表

| 优先级 | 规则 | 触发时机 | Skill |
|--------|------|---------|-------|
| 1 | 每日计划推送 | 08:00（在职 07:00） | kaoyan-daily-plan |
| 2 | 崩溃行为信号检测 | 10:00 | kaoyan-crisis |
| 3 | 每日打勾追踪 | 22:00 | kaoyan-tracker |
| 4 | 周报 | 周日 20:00 | kaoyan-weekly |

---

## 触发互斥补充规则

- **用户主动来聊时取消待发 Cron**：如果用户在 Cron 发送前主动发起对话，取消当天的待发消息。用户主动来了就不需要被提醒。
- **崩溃后抑制**：F6 触发后 3 天内，规则 3（打勾追踪）不推送。规则 1（计划推送）降级为 minimal 模式。
- **周日互斥**：周日 20:00 发周报后，22:00 不发打勾提醒。

---

## 边界

- 不在用户睡觉时间（23:00-07:00）推送任何消息
- 如果用户说"别发了""不想收到提醒"，停止所有 Cron 推送
- 崩溃后恢复期（Day 1-3），只在 08:00 推送 minimal 计划，其他 Cron 暂停
