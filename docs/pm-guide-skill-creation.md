# PM × Claude Code：从零创建一个 AI Skill

> 以「循环叹息」呼吸引导为实战案例。核心方法论只有一条：给 AI 一个标准，让它自己验证自己。

## 核心方法论

创建 Skill 的过程不是"PM 提需求 → Claude Code 写 → PM 测试 → 说不对 → 再改"。如果每一轮都要你亲自去飞书上试、亲自说"不对"，这个流程就不可能规模化。

真正的方法论只有两步：

**第一步：给 AI 一个明确的标准。**

你写清楚"做到什么样算对"。不是模糊地说"要有节奏感"，而是：

> "消息必须一条一条发。吸气那条发完之后等 4 秒再发下一条。总共 3 轮，每轮：4 秒吸气 → 2 秒追气 → 8 秒呼气。"

这个标准写在 SKILL.md 里，同时也是 AI 用来验证自己的依据。

**第二步：让 AI 自己验证自己。**

不是你去飞书上体验完告诉它"不对"。而是让 Claude Code 自己跑脚本、自己看日志、自己对比标准，自己判断"对不对"。

```bash
# AI 自己跑 DRY_RUN，对比输出是否符合标准
DRY_RUN=1 /usr/bin/python3 breathe-fast.py feishu 3

# AI 自己看 session JSONL，确认走的是脚本路径不是 fallback
# AI 自己对比脚本文案和 SKILL.md fallback 文案是否一致
```

**你只在两个时刻介入**：定标准，和标准本身需要改的时候。

---

## 这套方法论在实战中是怎么运转的

### 我定标准

我的需求很简单：

> 用户恐慌的时候，AI 带他做呼吸练习。消息要一条一条发，中间有节奏间隔。4 秒吸气、2 秒追气、8 秒呼气，3 轮。

这就是标准。Claude Code 据此写了 SKILL.md 和 breathe.sh 脚本。

### AI 验证自己——以及验证失败的教训

这个 Skill 前后改了 7 轮。回头看，**大部分轮次本不需要我介入**——如果 AI 从一开始就在正确地验证自己。

#### 问题 1：AI 说"好了"，但它在错误的环境里验证

Claude Code 在终端跑了脚本，消息一条一条发，节奏完美。它说"好了"。

但到飞书上一试，所有消息一次性全发过来了。

**根因**：Claude Code 用自己终端的 Python（pyenv）测试，但 AI 实际运行 `exec` 用的是系统 Python（`/usr/bin/python3`）。系统 Python 没装依赖 → 脚本 import 失败 → AI 走了 fallback → 一次性输出。

**教训**：验证必须在真实环境里做。

```bash
# 错：在自己的环境里验证
python3 breathe-fast.py feishu 3

# 对：在 AI 实际使用的环境里验证
/usr/bin/python3 breathe-fast.py feishu 3
```

#### 问题 2：AI 只看了 gateway 日志，没看决策日志

我说"为什么不分条发"，Claude Code 查了 gateway 日志，说"日志显示正常"。

但它查错了地方。gateway 日志只记录消息经过网关。AI 有没有跑脚本、脚本有没有报错——这些信息在 session JSONL 里。

```
~/.openclaw/agents/coco/sessions/<session-id>.jsonl
```

这个文件才是 AI 决策的真相来源。如果 Claude Code 一开始就看这个文件，会立刻发现"exec 返回了 ModuleNotFoundError"，根本不需要我反复说"不对"。

#### 问题 3：改了脚本，没改 fallback——自己没有对比验证

脚本文案更新成了带计数的版本（"鼻子吸气，数 4 秒 —— 1、2、3、4"），但 SKILL.md 的 fallback 还是旧文案。脚本一旦失败，用户看到的就是旧版本。

如果 AI 改完脚本后自己做一次对比——"脚本里的文案和 SKILL.md fallback 文案一样吗？"——这个问题根本不会发生。

### 总结：验证的三件事

每次改完，AI 应该自己检查这三件事：

1. **用 `/usr/bin/python3` 跑一遍** —— 确认在真实环境里能跑通
2. **看 session JSONL** —— 确认 AI 走的是脚本路径，不是 fallback
3. **脚本文案 vs SKILL.md fallback 逐字对比** —— 确认一致

这三件事都不需要我来做。AI 自己就能做。

---

## Skill 是什么

Skill 就是给 AI 看的 SOP。当用户状态匹配触发条件时，AI 读取这份手册，按步骤执行。

最小结构：

```
skills/my-skill/
└── SKILL.md       ← 就这一个文件
```

需要精确控制时序或调用外部服务时，加脚本：

```
skills/my-skill/
├── SKILL.md       ← 告诉 AI 怎么用
└── scripts/
    └── do-something.py
```

### SKILL.md 格式

```markdown
---
name: skill-id
description: 一句话说清什么时候触发
---

# 技能名称

## 怎么用
（步骤）

## 关键规则
（不要做什么——AI 特别爱自由发挥，你不拦着它就会做）

## 如果脚本执行失败
（fallback 文案，必须和脚本文案一致）

## 什么时候不要用
（反面清单）
```

### 在 AGENTS.md 中注册

```markdown
**Skill 调用规则（强制）：**
- **激动/恐慌** → `read("skills/breathing-ground/SKILL.md")`
```

写"强制"。不然 AI 可能觉得"这次不需要"就跳过了。

---

## 创建步骤

1. **写 SKILL.md** — 定义标准：什么时候触发、怎么执行、做到什么样算对
2. **让 Claude Code 写脚本**（如果需要）— 你审文案，它写代码
3. **在 AGENTS.md 加触发规则**
4. **让 Claude Code 自己验证** — 不是你去飞书上试
   - `/usr/bin/python3` 跑 DRY_RUN
   - 看 session JSONL 确认走了脚本路径
   - 对比脚本文案和 fallback 文案
5. **你在真实环境体验一次** — 确认标准本身对不对（体感层面）
6. **如果体感不对，修改标准** — 然后回到第 4 步

第 4 步是 AI 的活。第 5、6 步是你的活。

---

## 踩坑记录

| 坑 | 根因 | 本可以避免的方式 |
|----|------|----------------|
| 消息全发一起了 | 系统 Python 没装依赖，脚本 import 失败走 fallback | AI 用 `/usr/bin/python3` 自测 |
| "我在。"插在呼吸中间 | exec 是异步的，AI 不等脚本跑完就输出了 | AI 验证时看完整消息序列 |
| Claude Code 说"正常" | 查的是 gateway 日志，不是决策日志 | AI 看 session JSONL |
| 用户看到旧文案 | 改了脚本没改 SKILL.md fallback | AI 对比两处文案 |
| 练习时间翻倍 | 每条消息重新建连接，3.5 秒开销 | AI 算总时间是否符合标准 |
| 微信渠道体验很差 | 微信有 contextToken 机制和发送限制，消息丢失或乱序 | PM 决定砍渠道，先在飞书跑通 |

前五个坑，**没有一个需要 PM 亲自发现**。如果 AI 按标准自己验证自己，全都能在第一轮就抓住。最后一个是 PM 的活——微信这条路走不通，果断砍掉换飞书，不在技术问题上死磕。

---

## 项目结构

```
ai-companion/
├── AGENTS.md           ← AI 行为规则 + Skill 触发配置
├── IDENTITY.md         ← AI 人格
├── skills/
│   ├── breathing-ground/  ← 脚本驱动型 + 指导型
│   │   ├── SKILL.md
│   │   └── scripts/
│   │       ├── breathe-fast.py
│   │       └── breathe.sh
│   └── diary/             ← 指导型
│       └── SKILL.md
└── USER.md             ← 用户记忆
```

你最可能编辑的：`SKILL.md`（文案和规则）、`AGENTS.md`（触发条件）。都是 Markdown 文本文件。
