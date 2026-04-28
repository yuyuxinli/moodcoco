# moodcoco 语音版实施计划

**状态：[DRAFT v0.1] — 2026-04-28 brainstorming**

> 这是基于近期架构讨论的实施起点，不是定稿。决策来源见 `~/.claude/projects/.../memory/`。
> 标记说明：
> - `[DECIDED]` 已收敛
> - `[OPEN]` 待决策
> - `[TODO]` 待动手
> - `[BRAINSTORM]` 待补充想法

---

## 0. 文档目的

把"双 agent + background + memU + LiveKit + AWS 印尼/中文双场景"这套讨论，落成可执行的实施路径。**不是产品需求文档，是工程实施文档**。

---

## 1. 目标与约束

### 1.1 产品形态 [DECIDED]

- 移动端语音 AI 心理伴侣（不是文本聊天）
- 用户发语音 / AI 回语音，文本是 fallback
- 中文先做，印尼版第二阶段

### 1.2 关键约束 [DECIDED]

| 维度 | 约束 |
|---|---|
| 隐私 | 心理对话不出 VPC（中文）；印尼场景 Bedrock VPC 内可接受 |
| 延迟 | filler ≤ 500ms，slow main TTFT ≤ 3s，整轮 ≤ 8s |
| 成本（前 1k 月活） | AWS 基础设施 ≤ $50/月，LLM ≤ $400/月 |
| 合规 | 印尼 PDP Law（数据本地化 + 用户告知）|

### 1.3 不做的 [DECIDED]

- 不做 Web 文本聊天版（当前的会被替换）
- 不做 Agentic RAG / GraphRAG / Letta
- 不做 reranker（库 < 5k chunks 不需要）
- 不做超过 fast/slow 的多 agent 架构

---

## 2. 整体架构

### 2.1 总览

```
[移动 App]
   ↓ LiveKit Room SDK (WebRTC)
[LiveKit Server (托管 or 自建)]
   ↓
[Backend EC2 t4g.small]
   ├─ FastAPI (HTTP debug API 保留)
   ├─ LiveKit AgentServer (语音入口)
   ├─ PreResponseAgent
   │     ├─ filler classifier
   │     ├─ fast filler (groq llama-8b)
   │     └─ slow main (待 LLM 选型)
   ├─ Background workers
   │     ├─ retrieval (Hybrid: BM25 + memU pgvector)
   │     ├─ skill router
   │     ├─ continue decider
   │     └─ memU 离线批处理 (每天 4AM)
   └─ Embedding 服务 (中文: 自部署 BGE-M3 / 印尼: Bedrock Cohere v3)
   ↓
[RDS PostgreSQL + pgvector]
```

### 2.2 关键框架选型 [DECIDED]

| 层 | 选择 | 来源 |
|---|---|---|
| 语音框架 | LiveKit Agents | github.com/livekit/agents |
| AI 框架 | PydanticAI + LiteLLM | 已用 |
| 记忆系统 | memU + 用户 6 类型魔改 | psychologists 迁移 |
| 数据库 | PostgreSQL + pgvector | RDS 托管 |
| 部署 | AWS（中文东京/新加坡，印尼雅加达）| 已选 |

### 2.3 [OPEN] 不确定的

- LiveKit Server：自建（livekit-server docker）还是用 LiveKit Cloud？
- LLM：minimax / Claude / Gemini / 多家组合？
- STT/TTS：Deepgram / Whisper / OpenAI / ElevenLabs？
- 移动端：原生 iOS/Android 还是 React Native / Flutter？

---

## 3. 关键组件设计

### 3.1 Voice Agent 三档延迟模型 [DECIDED]

```
用户消息进来
  ↓
filler classifier (50-150ms, 豆包 lite 或 mini)
  ├─ skip   → 直接 slow，无 filler
  ├─ normal → fast filler (5-10 词反应) + slow
  ├─ crisis → 硬编码"嗯..." + crisis skill 直接接管
  └─ deep   → 承诺式 filler ("这个事我想多想想") + thinking + 多段
```

### 3.2 Background 4 个 AI 决策点 [DECIDED]

| 决策 | 触发 | 模型 | 延迟 | 输出 |
|---|---|---|---|---|
| filler classifier | 入口 | 豆包 lite/mini | 50-150ms | skip/normal/crisis/deep |
| 是否搜索 | background | 豆包 lite/mini | 100-150ms | yes/no + query 改写 |
| skill 路由 | background | embed 粗筛 + 豆包 lite 精排 | 100-150ms | skill_id |
| 是否 continue | slow_v1 完成后 | 豆包 lite/mini | 100-150ms | yes/no |

**模型选择原则**：
- 决策类任务（4 个决策点 + memU 提取的 NOOP 判断）→ 豆包 lite/mini，便宜 + 中文强
- 主对话生成（slow main）→ [OPEN] 待 LLM 调研，候选含豆包 pro / minimax-m2.7 / Claude / Gemini
- API 接入：火山方舟（ark.cn-beijing.volces.com）OpenAI 兼容协议
- 环境变量（已配在 `.env`，用 `os.getenv()` 读）：`DOUBAO_API_KEY` / `DOUBAO_BASE_URL` / `DOUBAO_MODEL`

[OPEN] 这 4 个决策的 prompt 还要单独 evolve 调优。

### 3.3 检索两层 [DECIDED]

```
Layer 1（全量注入，每轮）：
  memU 6 类 Category Summary → ~2k tokens 直接进 system prompt
  延迟：~5ms（数据库读）

Layer 2（按需检索，由"是否搜索"决策触发）：
  user_msg → BM25 (jieba+rank_bm25)  ┐
                                      ├→ RRF k=60 → top-5 MemoryItem
            → memU retrieve_rag      ┘  注入 slow context
            (pgvector)
  延迟：~50ms
```

[OPEN] BM25 实现方式：
- 选项 A：jieba + rank_bm25 内存版（每次 query 重算，1k 规模 < 5ms）
- 选项 B：PostgreSQL FTS + GIN 索引（持久化，生态统一但中文要 zhparser 扩展）

### 3.4 memU 集成 [DECIDED]

**写入侧（保留 psychologists 现有实现）**：
- 离线批处理：每天 4:00 AM
- 阈值：累积 ≥ 100 条新消息才提取
- 6 类型并行 LLM 提取（profile/event/behavior/knowledge/goals/relationships）
- 全局并发 80

**读取侧（新增 Layer 2，激活 memU 自带能力）**：
- VectorIndexConfig.provider = "pgvector"
- MetadataStoreConfig.provider = "postgres"
- embedding base_url 指向自部署 BGE-M3（中文）或 Bedrock Cohere（印尼）

### 3.5 Skill 路由 [DECIDED]

- 进程启动时把 20 个 SKILL.md 的 description 预 embed
- 在线：user_msg embed（reuse retrieval 那次）+ 余弦 top-3 + 小模型精排选 1

---

## 4. 数据模型

### 4.1 核心表 [DECIDED]

```sql
User (id, created_at, locale, ...)
Session (id, user_id, started_at, is_memorized)
Message (id, session_id, role, content, audio_url, created_at)
                                                   ↑ Resource 层

MemoryItem (id, user_id, memory_type, content, speech_time, embedding, ...)
MemoryCategory (id, user_id, memory_type, name, summary, ...)
MemoryCategoryItem (category_id, item_id, weight)
```

### 4.2 索引

- `MemoryItem.embedding`: pgvector HNSW
- `MemoryItem(user_id, memory_type)`: btree
- `Message(session_id, created_at)`: btree
- [OPEN] BM25 需要的 GIN 索引（如果走 PG FTS 路线）

---

## 5. API 设计

### 5.1 [DECIDED] 保留的 HTTP API
- `POST /chat`：当前调试 API，保留作 PM/SJTU 同事调试用
- `GET /memory/{user_id}`：管理员查看记忆

### 5.2 [TODO] 新增的语音 API
- LiveKit Room（WebRTC）：用户语音入口
- `GET /livekit-token`：发 LiveKit 连接 token
- `POST /admin/trigger-memorize/{user_id}`：手动触发提取（调试）

### 5.3 [BRAINSTORM] 移动端协议
- 原生 SDK：iOS Swift Package、Android AAR
- 跨平台：React Native / Flutter LiveKit binding
- 哪条路看团队配置

---

## 6. 部署架构

### 6.1 中文版（极简）[DECIDED]

```
Region: ap-northeast-1 东京（或 ap-southeast-1 新加坡）

[Cloudflare 免费 DNS+CDN]
   ↓
[EC2 t4g.small ($15/月)]
   ├─ FastAPI + LiveKit AgentServer
   ├─ BGE-M3 via Infinity (端口 7997)
   └─ daily_memorize_task (systemd timer)
   ↓
[RDS db.t4g.micro pgvector ($15/月，首年 Free)]

LLM: 火山方舟（豆包系列，国内）+ OpenRouter（境外备选）
LiveKit Server: [OPEN] 自建 vs Cloud

月成本（前 1k 用户）：AWS $30 + LLM $135-370
```

### 6.2 印尼版 [DECIDED]

```
Region: ap-southeast-3 雅加达（PDP Law 强制本地化）

[Cloudflare]
   ↓
[EC2 t4g.small]
   ├─ FastAPI + LiveKit AgentServer
   └─ daily_memorize_task
   ↓
[RDS db.t4g.micro pgvector]
   ↓
[Bedrock Cohere Embed Multilingual v3 ($2/月)]

LLM: [TODO 用户调研]，候选 Gemini 2.0 Flash / Claude Haiku / SahabatAI

月成本：AWS $32 + LLM 待估
```

### 6.3 [OPEN] 高可用版
- 留到 1k 真实用户后再做
- Multi-AZ RDS、ALB、Auto Scaling

---

## 7. 实施阶段（建议拆 6 个 Phase）

### Phase 0：基础设施（1 周）
- [ ] AWS 账号 + IAM 角色
- [ ] RDS PostgreSQL 起 + 启用 pgvector 扩展
- [ ] EC2 + 域名 + Cloudflare
- [ ] GitHub Actions CI/CD

### Phase 1：后端骨架（1-2 周）
- [ ] memU 数据库 schema 迁移到 RDS
- [ ] 把 psychologists 的 `backend/context/l3_memory/` 整体搬过来
- [ ] 适配 LiteLLM → PydanticAI/OpenRouter
- [ ] HTTP /chat 端点（保留作调试）能跑通

### Phase 2：检索层（1 周）
- [ ] 激活 memU retrieve_rag（pgvector + 自部署 BGE-M3）
- [ ] 加 BM25（[OPEN] jieba 内存 vs PG FTS）
- [ ] RRF 融合
- [ ] **关键：跑 100 query 的召回率对比**（前面调研建议的 baseline）

### Phase 3：4 个 AI 决策点（1 周）
- [ ] filler classifier
- [ ] 是否搜索 decider
- [ ] skill 路由
- [ ] continue decider
- [ ] 每个 prompt 单独 evolve 调优

### Phase 4：LiveKit 语音版（2-3 周）
- [ ] LiveKit AgentServer 接入
- [ ] STT/TTS 选型 + 接入
- [ ] 中文 filler 词表（需要真人录音验证 8-10 条）
- [ ] crisis 硬编码语气词路径
- [ ] 移动端 LiveKit SDK 集成

### Phase 5：印尼版（4-6 周）
- [ ] 切到雅加达 region
- [ ] Bedrock Cohere v3
- [ ] LLM 选型落地
- [ ] SKILL.md 印尼版本（必须找当地心理咨询师重写，不能机翻）
- [ ] PDP Law 法务过审
- [ ] 印尼语 filler 词表

### [OPEN] Phase 6：监控/迭代
- 用户行为分析
- evolve loop 怎么衔接到新架构
- A/B 测试框架

---

## 8. 风险登记

### 8.1 工程风险
- **memU 迁移**：psychologists 用 LiteLLM + SQLAlchemy，moodcoco 当前是 PydanticAI + 文件，迁移工作量比预估大
- **LiveKit 适配中文**：filler 词表 + crisis 硬编码 + TTS prosody 一致性，行业经验少
- **Hybrid 检索 BM25 路线**：jieba 内存版 vs PG FTS 取舍未定

### 8.2 产品风险
- **印尼文化适配**：SKILL.md 翻译 ≠ 本地化
- **LLM 选型未定**：影响成本估算 50% 误差
- **现有 evolve loop 怎么衔接**：当前是文本对话评估，语音版评估方法要重新设计

### 8.3 合规/隐私风险
- **PDP Law 细节未过审**
- **音频数据存储策略**：是否保留？保留多久？匿名化？

---

## 9. 待 brainstorm 的开放问题

把这些先列下来，随时往下面加：

1. **LiveKit Cloud vs 自建 livekit-server？**
   - Cloud：托管，但月费按流量
   - 自建：再多一个 EC2

2. **现有 evolve loop / SJTU bundle / web 调试页要怎么活下来？**
   - 都丢掉？还是 v1 保留作内部测试？
   - 评估方法（4 personas）怎么搬到语音版？

3. **音频数据保留策略？**
   - 实时转文本后立即丢？
   - 留 7 天 debug？
   - 永久存（PDP Law 风险大）？

4. **用户身份/账号体系？**
   - 当前 stateless，新版必须有 user_id
   - 微信登录？手机号？

5. **记忆"遗忘"机制？**
   - memU 是 append 模式，旧记忆永远在
   - 用户能"忘掉某事"吗？UI 怎么做？

6. **SKILL.md 体系怎么演进？**
   - 当前 20 个 + SJTU 7-skill bundle
   - 语音版要砍到几个？合并？

7. **错误兜底**：
   - LLM 失败怎么办？
   - 检索失败怎么办？
   - 静默 > 5s 怎么办？

8. **付费模式**：
   - 免费？订阅？按对话付费？
   - 决定 LLM 成本承受度

9. **数据看板**：
   - 用户留存、对话深度、危机命中率怎么看？

10. **印尼版能不能复用中文版的"经验"？**
    - 心理学理论是普世的吗？哪些是？哪些不是？

---

## 10. 下一步

[BRAINSTORM] 这个文档先放着，下次讨论可以选其中一个开放问题深入：

- 如果聚焦工程：选 Phase 0/1 的具体执行细节
- 如果聚焦产品：选第 9 节的开放问题（建议从 1、4、8 开始）
- 如果聚焦评估：怎么把 evolve loop 衔接到语音版

---

## 附：参考资源

- LiveKit fast-preresponse.py：`/Users/jianghongwei/Documents/GitHub/agents/examples/voice_agents/fast-preresponse.py`
- memU 上游：`/Users/jianghongwei/Documents/GitHub/memU`
- psychologists 魔改：`/Users/jianghongwei/Documents/psychologists/backend/context/l3_memory/`
- memory 决策记录：`~/.claude/projects/-Users-jianghongwei-Documents-moodcoco/memory/`
