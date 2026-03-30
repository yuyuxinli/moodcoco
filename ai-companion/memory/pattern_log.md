# 模式呈现频率记录

<!-- 记录每次模式呈现，用于频率保护。pattern-mirror 和 growth-story 共享此文件。 -->

## 记录格式

<!--
每次模式呈现后 **必须** 追加一条记录，格式如下：
- {日期}: {类型: timing/trigger/reaction/growth} | 涉及: {人物列表} | status: {状态} | cooldown_until: {日期}

status 值定义：
  - presented    — 完成呈现，用户有反应（惊讶/好奇）→ 冷却 14 天
  - denied       — 用户否认模式 → 冷却 30 天
  - interrupted  — 中途中断（转话题/离开）→ 不消耗配额，7 天后可重试
  - emotional_flooding — 情绪淹没，回到 F05 → 冷却 14 天 + 备注"下次需更温和"

频率限制规则（触发前必须检查）：
  1. 本周已呈现次数 < 2（含 growth-story）
  2. 相同模式的 cooldown_until 已过
  3. 被 denied 的模式 cooldown_until 已过（30 天）
-->

## 模式呈现记录
