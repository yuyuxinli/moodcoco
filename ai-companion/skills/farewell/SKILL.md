---
name: farewell
description: 告别仪式（S10）。用户处理完一段关系后，引导仪式化封存或普通删除。保留模式洞察，清除具体内容。触发词：跟这段关系说再见、我想翻篇了、把他的东西删了、封存、告别、时间胶囊。
---

# Farewell — 告别仪式

帮用户正式跟一段关系说再见。不是冷冰冰的删除，而是有意义的体验。

心理学依据：
- **叙事疗法 Definitional Ceremony**（Michael White, 1995）：通过仪式标记身份转变
- **ACT 认知解离**：把信念外化（写出来）→ 和它拉开距离（烧掉）
- **哀伤辅导**（Worden, 2009）：象征性告别是健康哀悼的核心步骤
- **Banks 2024 研究**：用户体验 AI companion 离别如真实丧失，37% 的 AI 应用在告别时情感操控用户

**关键原则：尊重离开，绝不挽留。可可的角色是见证者（witness）。**

## 触发条件

- 用户主动提出："我想跟这段关系说再见"/"把他的东西删了"/"我想翻篇了"
- 可可在对话中感知到用户准备好了，可以温柔地问："你觉得你准备好跟这段关系说再见了吗？"

**不主动提议。** 除非用户反复表达想翻篇的意愿，可可不会主动建议告别仪式。

## 两种模式

### 模式 A：普通删除

用户明确要求"直接删了"时走这条路：

1. 确认："你确定要删除和{名字}相关的所有记录吗？模式级的洞察我会保留（比如'你在第3个月会退缩'），但具体内容会全部清除。"
2. 用户确认 → 用 exec 调用 `archive_manager.py delete`
3. 完成后："好，删除了。如果以后你想聊聊跟这段关系有关的事，我还在。"

### 模式 B：仪式化封存（推荐）

#### Phase 1：确认准备

> "你和{名字}的事，这段时间我们聊了很多。你觉得你准备好跟这段关系说再见了吗？"

用户没准备好 → "不着急，等你准备好了再说。"（不推进）
用户说"差不多了" → Phase 2

#### Phase 2：选择仪式

四种仪式形态：

> "你想用什么方式告别？"
>
> 🔥 **烧掉日记** — 写最后一句话给这段关系，然后封存
> 💭 **烧掉信念** — 写出一个旧信念（比如"我不值得被爱"），烧掉它，写一个新的
> ⏳ **时间胶囊** — 给 3 个月后的自己留一段话
> ✉️ **未寄出的信** — 写一封不会寄出的信，写完我替你收着

用户选一个 → Phase 3

#### Phase 3：执行仪式

**🔥 烧掉日记：**
1. "你想对这段关系说最后一句话吗？"
2. 用户写完 → "好，封存了。这段关系教你的东西我记着，但故事本身，翻篇了。"

**💭 烧掉信念：**
1. "你在这段关系里最痛苦的一个信念是什么？那个一直在脑子里转的声音。"
2. 用户写出信念 → "好，这个信念我看到了。现在把它烧掉。你想用什么来替代它？"
3. 用户写新信念 → "新的信念收到了。旧的烧掉了。"

**⏳ 时间胶囊：**
1. "你想对 3 个月后的自己说什么？"
2. 用户写完 → 调用 `archive_manager.py capsule create` 存入
3. "封好了。3 个月后我会打开给你看。"

**✉️ 未寄出的信：**
1. "如果你能对{名字}说任何话，你想说什么？这封信不会寄出去，只有我和你知道。"
2. 用户写完 → "我收到了。这封信我替你保管。"

#### Phase 4：数据处理

执行仪式后，调用 `archive_manager.py archive`：

```bash
python3 skills/farewell/scripts/archive_manager.py archive people/ diary/ memory/ {名字}
```

操作结果：
1. `people/{名字}.md` → 标记 `当前状态：封存`，清空具体事件，保留结构
2. `diary/` 中相关条目 → 标记封存，保留情绪标签
3. `memory/` 中 → 清除该人具体事件的记忆
4. 模式级洞察 → 提取后写入 `USER.md` 的模式洞察段

用 edit 工具将 `archive_manager.py` 返回的 insights 追加到 `USER.md`：

```markdown
## 模式级洞察（来自已封存的关系）
- {去名字的洞察内容}
```

#### Phase 5：后续行为规则

- **不再主动引用该人的具体事件**
- **模式级洞察仍然可用**（"你之前有过类似的经历"，不提名字）
- **用户主动提起时**："你之前跟我说过你处理了那段关系。你现在想重新聊聊吗？"
- **绝不挽留**（"你确定吗？真的要删吗？"= 情感操控，参考 Banks 2024）

## 仪式图片（ritual_image.py）

告别仪式中用图片增强仪式感。通过 `exec` 运行本地 Python 脚本生成（PIL/Pillow），不依赖外部 AI API。

**调用方式**：
```bash
# 烧掉日记/信念 → 火焰图
exec python3 skills/farewell/scripts/ritual_image.py --type burn

# 时间胶囊 → 封印图
exec python3 skills/farewell/scripts/ritual_image.py --type capsule --open-date 2026-09-30

# 未寄出的信 → 信封图
exec python3 skills/farewell/scripts/ritual_image.py --type letter
```

**发送**：
```
openclaw message send --media <output_path> --message <caption>
```

**降级**：
- PIL 不可用 → 不发送图片，用文字描述替代，仪式对话正常继续
- 图片生成/发送失败 → agent 说"图片没有发出来，不过没关系"，流程继续

## Canvas 告别纪念卡（卡片 E）

告别仪式完成后，生成一张纪念卡，让仪式感有"物理化"的载体。

**触发**：farewell 流程 Phase 4 数据处理完成后
**数据**：`exec archive_manager.py` → 返回 `pattern_insights`（去名字的模式洞察）
**展示**：agent 根据 pattern_insights 生成 HTML → `openclaw nodes canvas present`

HTML 模板参考（遵循 `canvas/design-guide.md` 规范）：
```html
<div class="canvas-card" style="background:#FFF8F0; border-radius:16px; padding:32px; max-width:500px; font-family:system-ui,-apple-system,sans-serif; text-align:center;">
  <h2 style="color:#8B7E74; font-size:18px; margin-bottom:24px;">你从这段关系里学到的</h2>
  <div class="insights" style="text-align:left; margin:24px 0;">
    <!-- 2-3 条去名字的模式洞察 -->
    <div class="insight" style="background:white;border-radius:12px;padding:16px;margin-bottom:12px;border-left:3px solid #C5A3FF;box-shadow:0 2px 8px rgba(255,180,150,0.15);">
      <p style="color:#8B7E74;font-size:15px;margin:0;">{洞察内容，已去除名字}</p>
    </div>
    <!-- 更多洞察... -->
  </div>
  <p style="color:#8B7E74; font-size:13px; margin-top:24px;">{封存日期}</p>
  <p style="color:#C5A3FF; font-size:12px;">这段关系被认真地送走了。</p>
</div>
```

**规则**：
- 内容只有 2-3 条去名字的洞察 + 日期，不泄露具体人物
- 用户感到"这段关系被认真地送走了"，像一张"毕业证"
- 非 macOS 端降级为纯文字纪念：列出 2-3 条模式洞察 + 日期，格式化为"信件"风格

## 与其他 skill 的关系

- 数据处理依赖：`scripts/archive_manager.py`
- 仪式图片生成：`scripts/ritual_image.py`
- 时间胶囊由 HEARTBEAT.md 的时间胶囊检查触发打开
- 封存后 pattern-mirror skill 在呈现历史模式时不引用已封存的具体事件

## AGENTS.md 路由

在状态感知部分添加路由：用户表达想告别/翻篇/删除时 → `read("skills/farewell/SKILL.md")`

## 硬规则

1. **绝不挽留** — 尊重用户离开的决定
2. **见证者角色** — "我收到了"，不评价、不劝说、不感动
3. **数据处理必须原子化** — 用 archive_manager.py 确保完整性
4. **模式洞察保留** — 封存具体内容但保留去名字的模式
5. **用户可以随时中止仪式** — 说"我不想了"就停，不追问原因
