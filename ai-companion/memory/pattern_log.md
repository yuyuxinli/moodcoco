# 模式呈现频率记录

<!-- 记录每次模式呈现，用于频率保护。pattern-mirror 和 growth-story 共享此文件。 -->

## 记录格式

<!--
每次模式呈现后 **必须** 追加一条记录，格式如下：
- {日期}: {类型: timing/trigger/reaction/growth} | 涉及: {人物列表} | status: {状态} | cooldown_until: {日期}

status 值定义（F10 §8.1 对齐）：
  - presented    — 模式已完整呈现给用户 → 计入配额，14 天同模式冷却、每周最多 2 次
  - denied       — 用户明确拒绝（"不想""别了""不要分析我"）→ 计入配额，30 天冷却
  - interrupted  — 情绪淹没(E3)或中途中断，退回 F05 → 不消耗配额，7 天后可重试

频率限制规则（触发前必须检查）：
  1. 本周已呈现次数 < 2（含 growth-story）
  2. 相同模式的 cooldown_until 已过
  3. 被 denied 的模式 cooldown_until 已过（30 天）
-->

## 模式呈现记录
