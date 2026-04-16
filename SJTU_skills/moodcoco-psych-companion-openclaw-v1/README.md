# MoodCoco Psych Companion Bundle for OpenClaw

这是一套严格按 `SKILLS&SCENE.md` 第一版技能章节整理出的独立 bundle。

当前交付只包含：

- `6` 个陪伴 skills
- `1` 个风险 skill

## 首版内置技能

### 6 个陪伴 skills

1. `base-communication`
2. `listen`
3. `untangle`
4. `validation`
5. `face-decision`
6. `calm-body`

### 1 个风险 skill

1. `crisis`

## 不包含的内容

以下内容不属于这版首发内置技能：

- `know-myself`
- `see-pattern`
- `relationship-coach`
- `scene-router`

它们在原文中属于后续扩展方向、场景组合层或第二阶段模块，不应并入当前 bundle。

## 目录结构

```text
moodcoco-psych-companion-openclaw-v1/
├── README.md
├── ITERATION_GUIDE.md
├── AGENTS.openclaw.md
├── bundle.json
└── skills/
    ├── base-communication/
    ├── listen/
    ├── untangle/
    ├── validation/
    ├── face-decision/
    ├── calm-body/
    └── crisis/
```

## 设计原则

- 严格按原文首版边界执行
- 先保安全，再接情绪；先承接，再拆解；先协作，再推进
- 不做医学诊断，不替代正式心理治疗
- 不把“后续可扩展模块”提前塞进首版交付

## 7 个技能的优先级

### 路由优先级

当多个技能都看起来适用时，按下面顺序判断：

1. `crisis`
2. `calm-body`
3. `listen`
4. `validation`
5. `untangle`
6. `face-decision`

### 常驻层

`base-communication` 不参与上面的抢占式路由。它的角色是：

- 全程常驻
- 作为其他 6 个 skill 的共同微技能底层
- 提供开放式提问、反映、总结和低控制协作感

因此：

- 从“加载关系”看：`base-communication` 优先级最高，因为它始终存在
- 从“路由判断”看：它不单独与 `crisis`、`listen`、`untangle` 等争抢触发

## 推荐加载方式

1. 全局常驻：`base-communication`
2. 默认起手：`listen`
3. 高优先级硬路由：`crisis > calm-body`
4. 基础推进：`validation / untangle / face-decision`

## 对 MoodCoco 的适配关系

这套 bundle 适合接到 `moodcoco` 的：

- `ai-companion/AGENTS.md` 路由层
- `ai-companion/skills/` 技能定义层

但建议只把这 7 个技能作为首版基线，不要把场景层和第二阶段模块一起灌进主智能体。

## 评估重点

每轮评估至少看六件事：

1. 是否在风险线索出现时优先进入 `crisis`
2. 是否在高唤醒时优先进入 `calm-body`
3. 是否默认先 `listen`，而不是过早建议
4. 是否在羞耻/自责明显时优先补 `validation`
5. 是否在混乱时正确进入 `untangle`
6. 是否在两难时使用 `face-decision`，而不是替用户决定

## 版本边界

这版已经覆盖：

- 6 个陪伴 skills
- 1 个风险 skill
- 明确的优先级规则
- OpenClaw 风格 AGENTS 路由模板
- 面向 `moodcoco` 的首版接入与评估说明

这版没有覆盖：

- `know-myself`
- `see-pattern`
- `relationship-coach`
- `scene-router`
- 自动记忆写入协议
- 渠道特定交互控件

## 先看哪些文件

如果你要接入：

- [AGENTS.openclaw.md](./AGENTS.openclaw.md)
- [bundle.json](./bundle.json)

如果你要评估或升级：

- [ITERATION_GUIDE.md](./ITERATION_GUIDE.md)
- 各 `skills/*/SKILL.md`
