# 心情可可 Demo · PM 上手指南

一个双栏 AI 对话测试台：左 Coco（蓝）/ 右模拟用户（粉），可两 AI 自动对聊、单步步进、或人工代替用户。用来打磨 Coco 的 Prompt。

**核心原则：你是 PM，不敲代码。所有事靠 Codex（你说中文，它改代码）。**

---

## 0. 前置：拿两样东西

- **GitHub 账号**：让蒋宏伟把你加成 `jiangleo/moodcoco` 仓库 collaborator（告诉他你的 GitHub 用户名）
- **OpenRouter Key**：找蒋宏伟要一个带限额的 key（别自己去充钱）

---

## 1. 手动一次，只做这三步

打开 macOS 终端（Spotlight 搜"终端"），复制粘贴：

### 1.1 装 Codex（这一步必须手动，因为后面全靠它）
```bash
# 如果从没装过 Homebrew，先装 brew：
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 装 node 和 codex
brew install node
npm install -g @openai/codex

# 登录 codex（按提示贴 ChatGPT 账号 或 OpenAI API Key）
codex login
```

### 1.2 拉代码
```bash
cd ~/Documents
git clone https://github.com/jiangleo/moodcoco.git
cd moodcoco
git checkout feat/web-chat-ui
```

### 1.3 进 Codex
```bash
codex
```

---

## 2. 剩下的全丢给 Codex

进 Codex 交互界面后，**直接复制粘贴下面这段中文给它**，一路按 `y` 批准它的操作：

> 帮我把这个项目跑起来。我是一个 PM，电脑是 macOS，不太懂代码。请你：
>
> 1. 检查我电脑上缺什么：git、python 3.12+、uv、node 20+。缺哪个用 brew 装哪个。
> 2. 读项目根目录的 README.md、pyproject.toml、web/package.json，理解这是什么架构。
> 3. 后端：在项目根目录跑 `uv sync` 装 Python 依赖。
> 4. 前端：`cd web && npm install` 装 Node 依赖。
> 5. 配 .env：`cp .env.example .env` 后停下来，告诉我把 OPENROUTER_API_KEY 换成真的 key（我等会儿自己去改）。
> 6. 教我怎么在两个终端窗口分别跑后端（`uv run uvicorn backend.api:app --reload --port 8000`）和前端（`cd web && npm run dev`）。
> 7. 最后告诉我浏览器打开哪个地址能看到页面。
>
> 每一步做完告诉我你做了什么、遇到什么错。我会按 y 批准。

Codex 会自己搞定安装、依赖、并告诉你下一步。

---

## 3. 跑通的样子（第一次验收）

在两个终端里分别跑起来（Codex 会教你）后：

- 浏览器打开 **http://localhost:3000**
- 右栏选一个 persona（玉玉 / 阿瑶 / 小雨 / 小桔）
- 点"开始自动对话"
- **左边蓝色气泡开始冒字** = ✅ 跑通了

跑不通？回到 Codex 窗口，**直接截图扔给它** + 说"报这个错怎么办"。它会排查。

---

## 4. 第一个练手任务（不要一上来就改 Prompt）

先确认 "Codex 改代码 → 浏览器看到变化" 这个闭环通了。回到 Codex 窗口输：

> 把 web/app/page.tsx 左栏 Coco 那一侧的背景色改成浅绿色 #E8F5E9

看到它列 diff → 按 `y` → 浏览器自动刷新 → 左栏变浅绿 = ✅ 工作流通了。

**这之后你才开始改 Prompt。**

---

## 5. 日常改 Prompt（核心工作）

进 `~/Documents/moodcoco` 目录，输 `codex`，然后直接说中文。几个范例：

- "把 Coco 的 SOUL.md 里的语气改得更像大学学姐，少用书面词"
- "fast 路径现在给建议太快了，在 fast-instructions.md 里加一条：先追问一次再回应"
- "listen 场景的 SKILL.md 加一个例子，用户说'好累'的时候 Coco 怎么接"
- "玉玉这个 persona 现在太冷淡了，让她更容易炸一点"

### 最常改的文件（告诉 Codex 能更快，不告诉它也会找）

| 想改什么 | 文件 |
|---|---|
| Coco 人格 / 语气 / 灵魂 | `backend/prompts/SOUL.md` |
| Coco 身份 / 边界 / 不能做什么 | `backend/prompts/IDENTITY.md` |
| 行为规则（四步法 / 安全红线） | `backend/prompts/AGENTS.md` |
| 快回复（Fast 路径）规则 | `backend/prompts/fast-instructions.md` |
| 深思考（Slow 路径）规则 | `backend/prompts/slow-instructions.md` |
| 具体场景话术 | `backend/skills/<场景名>/SKILL.md` |
| 模拟用户人设 | `eval-reference/personas/*.md` |
| 页面布局 / 颜色 / 按钮 | `web/app/page.tsx`、`web/components/*.tsx` |

### 工作节奏
1. 说一句需求 → Codex 列 diff
2. diff 看得懂就 `y`，看不懂就让它解释："这段是干啥的？"
3. 浏览器刷新验证（有时要重启后端，Codex 会提醒）
4. 满意了再说下一句

---

## 6. 存档 & 把改动发回来

每改完一批想保存（别攒一堆再提交）：

> 帮我 commit 一下，message 写"改了 Coco 的语气更像学姐"

Codex 会执行 `git add -A && git commit -m "..."`。然后你手动跑：
```bash
git push
```

PR 会自动刷新，**不用重开**。蒋宏伟会在 PR 里 review 并合并。

---

## 7. 卡住怎么办

| 症状 | 对策 |
|---|---|
| 前端 404 / 白屏 | Codex 里说"前端打不开，帮我排查"+ 贴终端错误 |
| Coco 不说话 / 401 错误 | `.env` 的 OPENROUTER_API_KEY 没配或失效 |
| Codex 改崩了，想退回去 | Codex 里说"撤销刚才的改动" |
| 撤销也救不回来 | 终端跑 `git checkout -- .`（回到最后一次 commit） |
| 死活跑不通 | 截图 + 录屏甩群，别死磕超过 30 分钟 |

---

## 核心心法

1. **别自己敲代码**，全交给 Codex
2. **看 diff 判断好坏**，看不懂就问它
3. **小步提交**，一次改一个点
4. **跑不通先问 Codex，再问人**
