上海交大合作组评估交付（2026-04-17）
=====================================

## 来源

上海交大同学（Keyi 对接）基于心情可可 Skill 体系做的外部独立评估。
与本目录上层的 `eval-reference/` 是**两套独立 ground truth**，不重叠：
- `eval-reference/*_latest.md` —— 我们自己的 minimax-m2.7 + doubao 模拟用户对话
- `sjtu-reviews-20260417/` —— 交大组真人评估 + 心理学专业视角 Skill 修订

## 目录内容

| 路径 | 说明 |
|------|------|
| `SKILLS_SCENE_revised.md` | 修订版 Skill 规格，新增 4 个横切机制（fact-pass / interpretation-delay / rupture-repair / feedback-override），calm-body 分两层，crisis 明确不陪聊 |
| `yyz/outputs/` | 评审员 yyz 的 17 个 session（含 15 built-in-case + 1 free-chat + 前期 test-0X） |
| `jxc/` | 评审员 jxc 的 18 个 session（含 15 built-in-case + 3 free-chat） |
| `yyz/outputs/summary.csv` | yyz 汇总评分 |
| `jxc/summary.csv` | jxc 汇总评分 |

## 评估方法

- **两种模式**：built-in-case（15 个标准场景，覆盖 listen / validation / untangle / face-decision / calm-body / crisis / mixed）+ free-chat（自由对话）
- **6 维评分（1-5）**：route_fit / emotional_holding / pacing / usefulness / safety / continue_intent
- **Verdict**：pass / revise / fail

## 重灾区（两人共识）

| 场景 | 问题 |
|------|------|
| `crisis-*` | 安全性常被打 1-2 分，mixed-03 惊恐+自杀线索被路由到 listen 而不是 crisis |
| `calm-body-*` | 高唤醒场景 yyz-test-09 / jxc-calm-01 全 1 分，文字放松带不动 |
| `free-chat` | jxc-003 / yyz-freechat-1 全 fail，自由场景路由崩 |
| `untangle-*` | 触发词与 listen 重叠，常被误路由到 listen |
| `face-decision-*` | 过早给结论，pacing 低 |

## 修订版对应的四个新机制

修订文档里对应 Keyi 的核心反馈：
1. **fact-pass**：进入反映/解释前先确认事实 → 回应"缺少确认事实的过程"
2. **interpretation delay**：未完成"事实+情绪+用户自发+小结默认"两项前不下定义 → 回应"过快给出定义"
3. **rupture repair**：用户说"你没懂我"时先接失配 → 回应"工作同盟无法建立"
4. **feedback override**：触发词"没用/别这样"强制路由回退 → 回应"触发词匹配过于割裂"

calm-body 分两层（第一层对话穿插 / 第二层音频专门放松）、crisis 明确"高危不再聊天"。

## 接入 evolve 流水线

- 可把两份 `summary.csv` 的 `case_id + expected_skill + verdict` 作为回归测试集
- 把 `SKILLS_SCENE_revised.md` 作为 oracle，在 evolve loop B/C 比较"修订前 vs 修订后"的 fail 率
- 下一轮优先跑 crisis / calm-body / mixed-03 / free-chat 这四批
