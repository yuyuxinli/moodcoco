# AI Bestie 专家评测使用说明

这份说明面向参与评测的专家。你不需要理解 Python、虚拟环境或源码结构。

## 1. 如何解压

把项目压缩包解压到一个容易找到的位置，例如桌面。

## 2. 如何进入目录

打开终端或命令行，进入解压后的 `anela-ai-bestie-v1` 目录。目录里应该能看到：

- `run_expert_eval.py`
- `run_windows.bat`
- `run_mac.command`
- `README_expert_eval.md`

## 3. 如何输入访问密钥

运行时如果系统没有找到访问密钥，会提示：

```text
请输入访问密钥（输入时不会显示）:
```

输入时屏幕上不会显示字符，这是正常的。

也可以在主菜单选择 `修改模型连接设置`，填写模型服务地址、模型名称和访问密钥。访问密钥不会写入项目配置文件。

如果需要用 `.env` 预设连接，可以在 `anela-ai-bestie-v1` 目录中新建 `.env` 文件，内容类似：

```text
EXPERT_ID=expert_001
EXPERT_EVAL_KEY=your_key_here
EXPERT_EVAL_SERVICE_URL=https://your-model-service.example/v1
EXPERT_EVAL_MODEL=MiniMax-M2.5
EXPERT_EVAL_TIMEOUT_SECONDS=20
EXPERT_EVAL_MAX_RETRIES=1
```

## 4. Windows 如何运行

双击 `run_windows.bat`。

如果是 32 位 Windows，脚本会自动尝试使用本机 Python，不会强制安装 `uv`。
如果窗口停在错误信息页，请截图发回；不要直接关闭窗口。

## 5. Mac 如何运行

双击 `run_mac.command`。

如果系统提示没有权限，可以在终端进入项目目录后运行：

```bash
chmod +x run_mac.command
./run_mac.command
```

如果提示没有 `uv`，按提示安装。

## 6. Skills 评测是什么

交互菜单包含两种专家评测类型：`Skills 场景标准化评测` 和 `Free Talk 自由对话评测`。
`修改模型连接设置` 只是连接设置，不是评测内容。

Skills 评测是一组标准场景。你先选择一个场景，系统会自动发送首句，
然后你可以继续多轮追问或测试。输入 `/end` 后再按整段对话评分。

每轮回复都会立即保存，即使中途退出，已完成的轮次也不会丢。
系统会把运行时 trace 写入输出文件，方便后续工程排查；专家评分时只需要看对话质量，不需要判断内部路由是否正确。
发送到模型服务后，界面只会显示最终的 `Assistant:` 回复；内部等待、调试信息和模型错误不会作为对话内容展示。
如果某轮模型服务超时、连接中断或返回 429/5xx，系统会自动重试，默认每次请求最多 2 次尝试、单次 20 秒超时。
如果重试后仍失败，该轮会显示错误，不会生成本地兜底回复；详细错误和请求统计会写入输出文件中的 `Runtime Error`，方便工程排查。

## 7. Free Talk 评测是什么

Free Talk 是自由多轮对话。你选择一个场景，然后像真实用户一样和 AI 对话。

## 8. 如何结束 Free Talk

在输入框中输入：

```text
/end
```

然后填写整体评分。

其他命令：

- `/help`: 查看命令
- `/save`: 手动保存当前对话
- `/quit`: 退出当前对话，已保存轮次不会删除

## 9. 结果保存在哪里

结果保存在：

```text
outputs/expert_eval/
```

Skills 结果在：

```text
outputs/expert_eval/skills/{你的专家ID}/
```

Free Talk 结果在：

```text
outputs/expert_eval/freetalk/{你的专家ID}/
```

## 10. 如何把 outputs 发回

评测完成后，把整个 `outputs` 文件夹压缩后发回即可。

## 11. 访问密钥安全说明

系统不会把你的访问密钥写入输出文件、日志、Markdown、CSV 或 JSONL。

所有输出写入前都会做脱敏处理。如果检测到疑似密钥，也只会显示遮罩后的形式。

## 12. 常见问题

### 没有 Python 怎么办

优先使用 `run_windows.bat` 或 `run_mac.command`。普通 64 位系统会通过 `uv` 准备运行环境。
32 位 Windows 如果没有 `uv`，需要本机已安装 Python 3.10 或更新版本。

### uv 安装失败怎么办

Windows 用户请先不要关闭窗口，把错误截图发回。32 位 Windows 上脚本会继续尝试本机 Python fallback。

### 访问密钥或模型设置输入错了怎么办

回到主菜单选择 `修改模型连接设置`，重新填写模型服务地址、模型名称或访问密钥。
系统不会把你输入过的访问密钥写入项目文件。

如果你写了 `.env`，请修改 `.env` 里的 `EXPERT_EVAL_KEY`。

### 中途退出怎么办

已完成的 case 和已保存的 Free Talk 轮次都会保留在 `outputs` 中。

### outputs 在哪里

在 `anela-ai-bestie-v1` 目录下的 `outputs` 文件夹。
