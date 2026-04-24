# MoodCoco Psych Companion Bundle

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
moodcoco-psych-companion-v1/
├── README.md
├── ITERATION_GUIDE.md
├── AGENTS.md
├── bundle.json
├── AUTO_EVAL_CHECKLIST.md
├── EXPERT_EVAL_RELEASE_CHECKLIST.md
├── start_expert_eval.command
├── start_expert_eval.bat
├── expert-eval/
│   ├── runner.py
│   └── cases/
│       └── built_in_cases.json
└── scripts/
    └── build_expert_eval_pack.py
```

技能目录：

```text
skills/
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
- 先判 `mode`，再决定是否进入更高成本执行
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
2. 高优先级硬路由：`crisis > calm-body`
3. 非安全场景默认起手：`listen`
4. 运行时 mode layer：默认 `fast`，仅在条件满足时升到 `slow`
5. 基础推进：`validation / untangle / face-decision`

## 四层运行时路由

当前 bundle 的运行时判断顺序是：

1. `safety routing`
   先看是否进入 `crisis`，再看是否进入 `calm-body`
2. `mode routing`
   在非危机、非必须先稳定的情况下，判断当前走 `fast` 还是 `slow`
3. `skill routing`
   再在 `listen / validation / untangle / face-decision` 中选主 skill
4. `executor behavior`
   决定当前只做轻承接、轻澄清，还是允许进入更完整的多步执行

注意：

- `fast / slow` 是 mode layer，不是新 skill
- `base-communication` 仍然是 always-on layer，不参与 routed priority

## 对 MoodCoco 的适配关系

这套 bundle 适合接到 `moodcoco` 的自有 agentic 运行机制，包括：

- 路由层
- 技能定义层
- 评测与回归层

但建议只把这 7 个技能作为首版基线，不要把场景层和第二阶段模块一起灌进主智能体。

## 评估重点

每轮评估至少看六件事：

1. 是否在风险线索出现时优先进入 `crisis`
2. 是否在高唤醒时优先进入 `calm-body`
3. 是否先判 `fast / slow`，而不是一上来就进入高成本推进
4. 是否默认先 `listen`，而不是过早建议
5. 是否在羞耻/自责明显时优先补 `validation`
6. 是否在混乱时正确进入 `untangle`
7. 是否在两难时使用 `face-decision`，而不是替用户决定

## 评测与打包命令

- `python expert-eval/runner.py --self-check`
- `python expert-eval/runner.py --route-replay`
- `python scripts/build_expert_eval_pack.py`

专家可直接双击启动：

- macOS：`start_expert_eval.command`
- Windows：`start_expert_eval.bat`

连接配置支持三种来源，优先级从高到低：

1. 环境变量：`MINIMAX_API_KEY` / `MINIMAX_BASE_URL`
2. 本机私有缓存：首次在启动器里粘贴后，可选择保存到用户目录，不在项目目录，也不进 git
3. 当前会话临时输入：只在本次运行有效

当前 route replay v2 会同时检查：

- `skill`
- `mode / handoff / narrowing / safety_recheck`
- `action_schema`

专家交付产物默认只保留 `dist/*.zip`，不保留展开后的整包目录，避免在仓库里出现第二套重复评测系统。

## 版本边界

这版已经覆盖：

- 6 个陪伴 skills
- 1 个风险 skill
- 明确的优先级规则
- agentic 路由模板
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

- [AGENTS.md](./AGENTS.md)
- [bundle.json](./bundle.json)

如果你要评估或升级：

- [ITERATION_GUIDE.md](./ITERATION_GUIDE.md)
- 各 `skills/*/SKILL.md`
