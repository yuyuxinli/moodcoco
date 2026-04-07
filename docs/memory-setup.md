# 跨 Session 记忆搜索配置

本文档说明如何为 ai-companion Agent 启用 `memory_search` 工具，使 Agent 能在每次对话开始时自动检索历史记忆。

## 工作原理

Agent 在对话开始时调用 `memory_search`，对 `memory/*.md` 和 `USER.md` 建立的索引执行语义搜索，返回与当前话题最相关的历史片段，用于跨场景模式连接。

## 配置方法

在项目的 `agents.json`（或等效的 Agent 配置文件）中添加以下字段：

```json
{
  "agents": {
    "defaults": {
      "memorySearch": {
        "enabled": true,
        "provider": "local",
        "includeDefaultMemory": true
      }
    }
  }
}
```

### 配置项说明

| 字段 | 值 | 说明 |
|------|----|------|
| `enabled` | `true` | 开启 memory_search 工具 |
| `provider` | `"local"` | 使用本地文件系统索引（默认，无需外部服务） |
| `includeDefaultMemory` | `true` | 自动索引 `MEMORY.md` 和 `memory/**/*.md` |

## 被索引的文件

启用后，以下文件会被自动索引：

- `MEMORY.md`（如存在）— 全局记忆
- `memory/**/*.md` — 每次对话后写入的情绪日志
- `USER.md` — 用户基础档案（称呼、核心困扰、反复模式）

## memory/ 目录的写入规范

每次对话结束后，Agent 应将关键信息写入 `memory/` 下的日志文件，文件名格式建议：

```
memory/YYYY-MM-DD-<简短主题>.md
```

每个日志文件只记录提炼后的信息，不存原始对话：

```markdown
# 2026-03-29 — 和男友吵架

- 触发点：对方没有及时回消息
- 核心情绪：被忽视的委屈（脆弱层），表面是愤怒（保护层）
- 深层需求：被重视、确定性
- 有效方法：先命名情绪，再问"这件事让你最在意的是什么"
- 模式提示：第 2 次提到"是不是我太敏感"
```

## 使用示例

对话开始时，Agent 内部执行：

```
memory_search(query="男友 回消息 被忽视")
```

如果找到相关记忆，Agent 会在回应中自然地连接：

> "上次你提到，他没回消息会让你觉得不被重视——这次是又有这种感觉了吗？"

如果没有找到相关记忆，Agent 正常开始对话，不提"没找到记录"。
