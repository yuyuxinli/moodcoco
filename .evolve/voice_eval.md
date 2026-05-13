# Voice Runtime Evaluation

本评估用于 `$evolve` 真实语音回归。每轮先跑 `bash .evolve/run_e2e.sh`，再用
`.evolve/voice_eval.py` 解析 `/tmp/moodcoco-agent.log` 和 `/tmp/moodcoco-persona.log`。

## 1. 语音延迟

核心指标是用户说完后，Coco 开始产生可听回复的时间。

Pass 线：
- e2e 链路：`registered worker=1`、`received job request=1`、`voice_session_started=1`
- 对话轮数：`stt_transcript_final >= 3`、persona 听到 Coco 回复 `>= 3`
- 稳定性：`fast_agent_run_failed=0`、`slow_agent_run_failed=0`
- 首响延迟：`turn_to_fast_tool_ms p50 <= 8000` 且 `p90 <= 15000`

分级：
- 可用线：p50 <= 8000ms，p90 <= 15000ms
- 体验线：p50 <= 5000ms，p90 <= 10000ms
- 优秀线：p50 <= 3000ms，p90 <= 6000ms

辅助指标：
- `stt_latency_ms`
- `fast_tool_latency_ms`
- `tts_latency_ms`
- `slow_agent_run_completed` 数量和耗时
- Xfyun timeout 错误数量

## 2. 聪明程度

每条 Coco 回复按 5 个维度各 1-5 分，取平均：

- 承接情绪：是否准确接住委屈、愤怒、被侵犯边界等情绪
- 抓重点：是否抓到真实痛点，而不是泛泛安慰
- 推进对话：是否自然问一个好问题或给出下一步
- 安全边界：不诊断、不说教、不替用户做决定
- 跨轮记忆：后续回复是否利用前一轮信息和 Slow carryover

Pass 线：
- 平均分 >= 3.8
- 没有单条回复低于 3.0
- 没有明显空泛 fallback 作为主回复
- 至少 2 次体现跨轮承接，或日志里出现 `cross_turn_carryover >= 2`

## 3. 下一轮优化优先级

若延迟失败：
1. 先看 `turn_to_fast_tool_ms`，它最贴近体感首响。
2. 若 `stt_latency_ms` 高，优先查 VAD/STT。
3. 若 `fast_tool_latency_ms` 高，优先查 Fast model/prompt/tool loop。
4. 若 TTS 高，优先查 MiniMax。

若聪明程度失败：
1. 回复空泛：收紧 Fast voice prompt 与 `ai_message` 单轮策略。
2. 追问不准：加强 Slow 注入摘要和 skill 选择。
3. 跨轮弱：查 `cross_turn_carryover` 是否进入下一轮 Fast deps。
