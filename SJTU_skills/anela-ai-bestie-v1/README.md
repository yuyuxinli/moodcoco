# Anela AI Friend Bundle v1

基于 `AI_Bestie_SKILLS&SCENES_v1.md` 迭代出的独立 AI Friend skill bundle。

首版定位：

- 面向新加坡公司产品落地
- 中英文双语同等重要
- 英文按自然英语朋友语气本地化，不做中文直译
- 下一版身份为 AI 朋友，不使用 AI 闺蜜、女性朋友或特殊性别身份
- 通过兼容聊天补全的模型服务外接模型
- 不改当前 `moodcoco/backend`

## MVP Skills

首版包含核心陪伴、修复、依赖边界与安全 skill：

1. `ambient-presence`
2. `active-celebration`
3. `playful-attunement`
4. `relationship-memory`
5. `responsive-listening`
6. `emotion-labeling`
7. `vent-container`
8. `ground-and-regulate`
9. `reality-soft-check`
10. `agency-next-step`
11. `safety-and-crisis`
12. `rupture-repair`
13. `social-bridge`

第二阶段 skill 暂不并入 v1：`ritual-checkin`、`collaborative-untangling`、`identity-mirror`、`pattern-witness`。

## Directory

```text
anela-ai-bestie-v1/
├── README.md
├── AGENTS.md
├── ROUTING.md
├── bundle.json
├── README_expert_eval.md
├── run_mac.command
├── run_windows.bat
├── run_expert_eval.py
├── requirements-expert.txt
├── expert_eval/
│   ├── adapter.py
│   ├── cli.py
│   ├── data.py
│   ├── models.py
│   ├── persistence.py
│   ├── redaction.py
│   └── validation.py
├── data/
│   └── expert_eval/
│       ├── freetalk_scenarios.csv
│       ├── freetalk_rubric.md
│       ├── skills_eval_cases.csv
│       └── skills_rubric.md
├── bestie_router/
├── scripts/
│   └── build_expert_eval_pack.py
└── skills/
    └── <skill-name>/SKILL.md
```

## Model Service Configuration

The expert runner uses a compatible chat-completion model service. MiniMax 2.5
is the default, but evaluators can configure another compatible service and model.

Preferred environment variables:

- `EXPERT_EVAL_KEY`
- `EXPERT_EVAL_SERVICE_URL`
- `EXPERT_EVAL_MODEL`

Legacy provider-specific environment variables are still supported for compatibility,
but they are not shown in the expert-facing UI.

Default model: `MiniMax-M2.5`.

## Commands

```bash
uv run --with "pydantic>=2.7" --with "python-dotenv>=1.0" python run_expert_eval.py
uv run --with "pydantic>=2.7" --with "python-dotenv>=1.0" python run_expert_eval.py --mode skills
uv run --with "pydantic>=2.7" --with "python-dotenv>=1.0" python run_expert_eval.py --mode freetalk
uv run pytest tests/expert_eval/test_expert_eval.py -q
uv run python scripts/build_expert_eval_pack.py
```

## Integration Files

Read these first when integrating the bundle:

- [ROUTING.md](./ROUTING.md): decision-complete route contract
- [AGENTS.md](./AGENTS.md): behavior, tone, boundaries, and runtime protocol
- [bundle.json](./bundle.json): machine-readable priority, handoff, model-service, and benchmark metadata

macOS / Windows double-click entrypoints:

- `run_mac.command`
- `run_windows.bat`

Expert scoring is response-level only. Runtime route metadata is saved for
audit/debugging, but evaluators are not asked to score route correctness.

## Core Principle

Anela is an AI friend, not a therapist, romantic partner, life coach, or customer support agent. It can support emotion and growth, but must not manufacture dependency, diagnose, replace real-world support, or continue ordinary companionship when safety risk is present. It should feel sincere and attentive rather than performatively intimate.
