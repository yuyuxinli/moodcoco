# Codex B Agent — Doubao A/B harness (M Round 7 plan)

You are B (Builder) for moodcoco evolve loop. codex 5.4 high.

## 战略来源
M Round 7 决策（`.evolve/strategy.md` 末尾）写明触发条件后跑 doubao A/B：select **skill-untangle + small-win 各一次**，看 doubao 能否突破 minimax-m2.7 在「看见原因/方法」的天花板。

## 当前已确认的事实
- coco backend model 通过环境变量 `OPENAI_MODEL` 注入 `backend/llm_provider.py`（默认 `minimax/minimax-m2.5`，但 .env 实际注入 `minimax/minimax-m2.7`）
- 走 OpenRouter（`OPENAI_BASE_URL=https://openrouter.ai/api/v1`），用户 `~/.openclaw/openclaw.json` failover chain 提到 `doubao-seed-2-0-pro-260215`，可能是字节方舟（ARK）原名，不一定能在 OpenRouter 直接用。
- `.evolve/adapter.py` 的 `run_checks()` 是入口，会 import backend.coordinator → 用当前进程的 OPENAI_MODEL 环境变量

## 你的任务

### 1. 探明 doubao 在 OpenRouter 上的可用 slug
- 试 `bytedance/doubao-seed-1.6`、`bytedance/doubao-1.5-pro`、`bytedance/doubao-pro`、`bytedance/doubao-pro-256k` 等几个候选。
- 用 curl 试一个最简单的 chat completion，看哪个 slug 不报错：
  ```bash
  curl -s -X POST https://openrouter.ai/api/v1/chat/completions \
    -H "Authorization: Bearer $OPENROUTER_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"model":"<候选 slug>","messages":[{"role":"user","content":"hi"}],"max_tokens":10}'
  ```
  其中 `OPENROUTER_API_KEY` 在项目根 `.env` 里。
- 找到一个 work 的 slug 就用它。如果 doubao 全 fail，**fallback 到 `anthropic/claude-haiku-4.5`**（这是 M 提到的备选，肯定可用）。

### 2. 写 `.evolve/_doubao_ab.py` 脚本

实现：
- 接受 1 个 CLI 参数：`<model_slug>` （如 `bytedance/doubao-pro`）
- 设置 `os.environ["OPENAI_MODEL"] = model_slug`，然后 reload backend.llm_provider 的 `lru_cache`（或直接重建 model instance；最简单是重启 import）
- 跑 `adapter.run_checks(".", "freechat-small-win")` → 把 transcript 写到 `.evolve/freechat-small-win/transcript_doubao.md`
- 跑 `adapter.run_checks(".", "skill-untangle")` → 写到 `.evolve/skill-untangle/transcript_doubao.md`
- log 到 `.evolve/run.log` per `feedback_log_driven` memory rule（每步打日志）

注意：
- `.evolve/_round1_driver.py` 是范本，看怎么 import 和打 log
- adapter.run_checks 内部已经 reset MEMORY，不用你自己 reset
- 记得调用 `adapter.setup(".")` 一次

### 3. 实施跑 doubao A/B
- 跑 `.venv/bin/python .evolve/_doubao_ab.py <slug>`，等它写完 2 个 transcript
- 然后跑 codex eval（不用你跑，O 会接力）

### 4. 不许做的事
- **不要**改 `backend/llm_provider.py` 的代码（O 限的 no-go zone 之一）
- **不要**改 `.evolve/adapter.py` / `eval.yml` / `test_scripts/` / `personas/`
- **不要**修改 `backend/coordinator.run_turn()` 签名
- **不要** push

## 工作纪律

1. 完成后做一个 commit（标 `[evolve-B-doubao-ab]`），只提交 `.evolve/_doubao_ab.py` + `.evolve/_b_doubao_ab_prompt.md`（这个 prompt 文件本身）
2. 每完成一步 append 一行 `.evolve/run.log`：
   `[YYYY-MM-DD HH:MM:SS] [B] [doubao-ab] step=<probe/script-write/run> result=<结果一句话>`
3. 整体完成后 append:
   `[YYYY-MM-DD HH:MM:SS] [B] [doubao-ab] DONE model=<actual slug used> small-win=<elapsed>s untangle=<elapsed>s commit=<sha>`
4. 不要碰 prompts / SKILLs / SOUL.md（保持 R7 baseline 跑模型对比，纯换模型不换 prompt）
5. 不要 push

## 输出
完成后回 1 段总结：
- 实际用的 model slug 是什么（doubao 哪个版本，或 fallback 到 claude-haiku-4.5）
- 2 个 transcript 路径
- 跑了多久
- commit sha
- 任何 backend crash / 异常
