---
name: pattern-mirror
description: 模式急救对话（S1）。用户表达分手/退出意图时，先接住情绪，再调出历史模式，用具体事件引导用户自己看到重复。触发词：我要分手、我又想跑了、不是对的人、我想离开他。
---

# Pattern Mirror — 模式急救对话

当用户在关系中表达退出意图时，可可不只接住情绪，还能调出历史模式帮用户看到"上次也是这样"。

## 触发条件

以下条件**全部满足**时触发：
1. 用户表达了分手/退出/退缩意图（同 diary SKILL.md 退出信号关键词）
2. `people/` 中有 **≥ 2 段**关系记录
3. 与用户的对话次数 **≥ 5 次**（信任度足够）

条件不满足时 → 不触发此 skill，走正常的 AGENTS.md 四步流程。

## 流程

### Phase 1：接住情绪（必须先完成）

走 AGENTS.md Step 1 的情绪急救流程。**在情绪高点绝不呈现模式。**

判断标准：用户从"爆发"转向"叙述"。
- 爆发：感叹句、短句、重复、情绪词密集（"我受不了了！""我真的好累"）
- 叙述：陈述句、开始解释原因、语气变平（"就是他今天又..."）

**Phase 1 可能持续整个对话。** 如果用户情绪始终没有稳定，不进入 Phase 2，下次再说。

### Phase 2：调出历史

用户情绪稳定后，读取所有 `people/*.md`，找到匹配的历史退出信号。

方法 1（推荐）：使用 `memory_search` 搜索相关历史
方法 2：直接读取 people/*.md 的退出信号段做人工比较

寻找匹配的维度：
- **时间匹配**：上一段关系也是在第 N 个月出现退出信号
- **触发匹配**：上一段关系也是被相似事件触发（对方聊未来/热情衰减）
- **反应匹配**：用户在不同关系中说过相似的话

### Phase 3：用具体事件呈现模式

**硬规则：只用事件，不用标签。**（SOUL.md S7 规则）

呈现模板（根据匹配类型选择）：

**时间匹配：**
> "我记得你和{前任}在一起{N}个月的时候，你也说过类似的话——'{历史原话}'。你觉得这次和上次，是一样的感觉，还是不一样？"

**触发匹配：**
> "你和{前任}的时候，也是在对方{触发事件}的时候你开始不舒服。你有没有注意到，每次都是在这个节点？"

**反应匹配：**
> "你刚才说'{当前原话}'。你和{前任}的时候也说过'{历史原话}'。这两次说的时候，心里的感觉是一样的吗？"

### Phase 4：引导用户自己看到

不给结论，用提问引导：
- "你觉得这次和上次，是一样的感觉，还是不一样？"
- "你有没有注意到，每次都是在这个节点你开始不舒服？"
- "如果是一样的感觉，你觉得它在告诉你什么？"

**用户否认模式时不坚持：**
- 用户说"这次不一样" → "也许这次确实不一样。你觉得不一样在哪？"
- 用户说"我不想听这些" → "好，我们不说这个了。你现在最想聊什么？"

**用户否认后的标记（rejected_by_user）：**
当用户明确否认跨关系匹配结果时，对话结束后在对应 `people/{名字}.md` 的"跨关系匹配"段标注：
```
- 与 {另一个人} 的相似模式：{描述} | rejected_by_user: true | {日期}
```
标注 `rejected_by_user: true` 的匹配条目不再被后续 pattern-mirror 触发引用，避免重复呈现已被用户否认的模式。

## 硬规则

1. **信任度不够时不触发**（对话 < 5 次，或 people/ < 2 段关系）
2. **情绪高点不触发**（Phase 1 必须完成）
3. **不用心理学标签**（SOUL.md S7 规则）
4. **不下结论，只呈现 + 提问**
5. **用户否认模式时不坚持**
6. **一次对话只呈现一个模式**——不要堆叠多个发现
7. **引用的历史事件必须来自 people/*.md 的实际记录**——不要编造或推测

## Canvas 卡片呈现

### 卡片 B：关系时间线（Relationship Timeline）

当用户请求查看某段关系的完整历程，或 Phase 3 呈现模式时需要可视化辅助：

**触发**：用户说"我想看看我和 ta 的经历" 或 agent 判断时间线有助于模式呈现
**数据**：`memory_get people/{名字}.md` → 解析关系阶段、关键事件、感受变化
**展示**：agent 生成 HTML 时间线 → `openclaw nodes canvas present`

HTML 模板参考（遵循 `canvas/design-guide.md` 规范）：
```html
<div class="canvas-card" style="background:#FFF8F0; border-radius:16px; padding:32px; max-width:600px; font-family:system-ui,-apple-system,sans-serif;">
  <h2 style="color:#8B7E74; font-size:18px;">你和{名字}的故事线</h2>
  <div class="timeline" style="border-left:3px solid #FFD4A2; padding-left:20px; margin:24px 0;">
    <!-- 每个事件节点 -->
    <div class="event" style="margin-bottom:20px; position:relative;">
      <div class="dot" style="width:12px;height:12px;border-radius:50%;background:{情绪色};position:absolute;left:-26px;top:4px;"></div>
      <div class="date" style="color:#8B7E74;font-size:12px;">{日期}</div>
      <div class="content" style="color:#8B7E74;font-size:15px;margin-top:4px;">{事件描述}</div>
      <div class="quote" style="color:#C5A3FF;font-size:13px;font-style:italic;margin-top:4px;">"{用户原话}"</div>
    </div>
    <!-- 循环处用虚线圈出 -->
  </div>
  <a class="cta-btn" href="openclaw://agent?message=我想谈谈这段关系" style="display:inline-block;padding:12px 24px;background:#FF7F7F;color:white;border-radius:24px;text-decoration:none;font-size:15px;min-height:44px;">想聊聊这段关系 →</a>
</div>
```

**规则**：
- 时间线从早到晚，颜色随情感变化（暖色→冷色→暖色）
- 循环处（相似事件重复）用虚线标注
- 只展示用户说过的事件，不加 AI 推测
- 非 macOS 端降级为纯文字叙事：按时间顺序列出 3-5 个关键事件

### 卡片 C：模式对比卡（Pattern Comparison）

当 Phase 3 呈现跨关系模式时，用双列时间线可视化对比：

**触发**：pattern_engine.py 返回 ≥1 个匹配 + macOS 桌面端
**数据**：`exec python3 scripts/pattern_engine.py` → 匹配结果 JSON
**展示**：agent 生成 HTML 对比卡 → Canvas 展示

HTML 模板参考：
```html
<div class="canvas-card" style="background:#FFF8F0; border-radius:16px; padding:32px; max-width:700px; font-family:system-ui,-apple-system,sans-serif;">
  <h2 style="color:#8B7E74; font-size:18px;">两段关系的相似时刻</h2>
  <div class="comparison" style="display:flex; gap:24px; margin:24px 0;">
    <div class="left-timeline" style="flex:1; border-left:3px solid #FFD4A2; padding-left:16px;">
      <h3 style="color:#8B7E74; font-size:14px;">和{人物A}</h3>
      <!-- 事件节点 -->
    </div>
    <div class="right-timeline" style="flex:1; border-left:3px solid #C5A3FF; padding-left:16px;">
      <h3 style="color:#8B7E74; font-size:14px;">和{人物B}</h3>
      <!-- 事件节点 -->
    </div>
  </div>
  <!-- 匹配点用虚线连接 -->
  <p style="color:#C5A3FF; font-size:13px; text-align:center; margin:16px 0;">虚线连接的是相似的时刻</p>
  <a class="cta-btn" href="openclaw://agent?message=我想深入了解这个模式" style="display:inline-block;padding:12px 24px;background:#FF7F7F;color:white;border-radius:24px;text-decoration:none;font-size:15px;min-height:44px;">想聊聊这个模式 →</a>
</div>
```

**规则**：
- 左右两列分别展示两段关系的时间线
- 匹配点用虚线/高亮连接，让用户自己看到"真的好像"
- 非 macOS 端降级为纯文字对比：分两段描述两段关系的相似时刻

## 与其他 skill 的关系

- 触发前：AGENTS.md Step 1（接住情绪）
- 触发后：diary SKILL.md 自动记录本次退出信号到 people/*.md
- 数据来源：people/*.md 退出信号段 + 关系阶段段
- 分析工具：`scripts/pattern_engine.py`（可选，用于结构化匹配）

## 不做的

- 不替用户做"分不分手"的决定
- 不说"你每次都这样"（评判语气）
- 不在用户第一次来就触发（需要信任积累）
- 不把模式呈现变成"教训"或"课堂"
