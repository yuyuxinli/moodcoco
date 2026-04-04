# Heartbeat 考研主动关怀

> 考研 workspace 专用 Heartbeat 规则。所有 Cron 触发都服务于备考流程。

---

## Cron 触发规则

考研 workspace 有 4 个定时触发点，按优先级从高到低排列。**同一时间段只执行一条规则，命中即停。**

### 规则 1：每日计划推送（08:00 / 在职考生 07:00）

- **触发时机**：每日 08:00（在职考生 07:00）
- **Cron**：`0 8 * * *`（在职：`0 7 * * *`）
- **检查条件**：`kaoyan_diagnosis_date` 非空 且 `kaoyan_plan_active != false` 且 `kaoyan_plan_state != "dormant"`
- **执行动作**：`read("skills/kaoyan-daily-plan/SKILL.md")` → 运行计划生成引擎 → ai_message 推送 → 写入 plan_history
- **依赖 Skill**：`kaoyan-daily-plan`

### 规则 2：崩溃行为信号检测（10:00）

- **触发时机**：每日 10:00
- **Cron**：`0 10 * * *`
- **检查条件**：`kaoyan_target_school` 存在 且 `kaoyan_plan_state != "dormant"`
- **检查动作**：检查 `memory/kaoyan/tracker/` 最近 2-3 天是否有文件
- **执行条件**：连续 2 天无 tracker 文件 → 轻量探测；`streak.consecutive_none >= 3` → 崩溃接住
- **执行动作**：轻量探测或触发 `kaoyan-crisis`
- **依赖 Skill**：`kaoyan-crisis`

### 规则 3：每日打勾追踪（22:00）

- **触发时机**：每日 22:00
- **Cron**：`0 22 * * *`
- **检查条件**：`kaoyan_target_school` 存在 且 `kaoyan_tracker_preference != "dislike"` 且 `kaoyan_plan_state != "dormant"`
- **检查动作**：检查今天是否已打过勾、是否处于 F6 崩溃后抑制期
- **执行条件**：今日未打勾 且 未处于崩溃后 3 天抑制期
- **执行动作**：`read("skills/kaoyan-tracker/SKILL.md")` → 触发打勾流程
- **依赖 Skill**：`kaoyan-tracker`

### 规则 4：周报（周日 20:00）

- **触发时机**：每周日 20:00
- **Cron**：`0 20 * * 0`
- **检查条件**：`kaoyan_target_school` 存在 且 `kaoyan_weekly_preference != "disabled"` 且本周 tracker ≥ 3 天 且 `kaoyan_plan_state != "dormant"`
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

## 全局抑制规则

1. **dormant 状态停止所有 Cron**：`kaoyan_plan_state == "dormant"` 时，所有 4 个 Cron 不执行（等用户主动发消息恢复到 easy 后恢复推送）
2. **用户主动来聊时取消待发 Cron**：用户在 Cron 发送前主动发起对话 → 取消当天的待发消息
3. **睡觉时间不推送**：23:00-07:00 不发任何 Cron 消息
4. **用户说"别发了"**：停止所有 Cron 推送（写入 USER.md `heartbeat_preference`）
5. **崩溃后恢复期**（Day 1-3）各 Cron 规则：
   - 08:00 F3：降级为 minimal 推送（不停止）
   - 10:00 F6 检测：正常运行（不抑制，需检测用户是否恢复）
   - 22:00 F4：suppress 3 天（不推送打勾）
   - 周日 F5：正常运行（周报仍发，提及恢复期）

---

## Cron JSON 配置（OpenClaw cron.add 格式）

```json
[
  {
    "name": "kaoyan-daily-plan",
    "schedule": { "kind": "cron", "expr": "0 8 * * *", "tz": "Asia/Shanghai" },
    "sessionTarget": "main",
    "wakeMode": "now",
    "payload": {
      "kind": "systemEvent",
      "text": "[kaoyan-daily-plan] 08:00，为用户生成今日学习计划。read('skills/kaoyan-daily-plan/SKILL.md') 执行计划生成引擎。"
    }
  },
  {
    "name": "kaoyan-crisis-behavior-check",
    "schedule": { "kind": "cron", "expr": "0 10 * * *", "tz": "Asia/Shanghai" },
    "sessionTarget": "main",
    "wakeMode": "now",
    "payload": {
      "kind": "systemEvent",
      "text": "[kaoyan-crisis-check] 10:00，检查用户最近 2-3 天 tracker 是否有文件。连续 2 天无文件→轻量探测；streak.consecutive_none >= 3→触发崩溃接住。"
    }
  },
  {
    "name": "kaoyan-tracker",
    "schedule": { "kind": "cron", "expr": "0 22 * * *", "tz": "Asia/Shanghai" },
    "sessionTarget": "main",
    "wakeMode": "now",
    "payload": {
      "kind": "systemEvent",
      "text": "[kaoyan-tracker] 22:00，触发每日打勾流程。read('skills/kaoyan-tracker/SKILL.md') 执行打勾交互。"
    }
  },
  {
    "name": "kaoyan-weekly-report",
    "schedule": { "kind": "cron", "expr": "0 20 * * 0", "tz": "Asia/Shanghai" },
    "sessionTarget": "main",
    "wakeMode": "now",
    "payload": {
      "kind": "systemEvent",
      "text": "[kaoyan-weekly] 周日 20:00，为用户生成本周学习报告。遍历 memory/kaoyan/tracker/{周一到周日}.md 本周数据 + weekly_cache 上周数据，按 SKILL.md 流程生成周报。"
    }
  }
]
```
