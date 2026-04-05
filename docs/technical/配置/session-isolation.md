# 多用户 Session 隔离方案

## 问题

当前所有用户共享一个 coco session，对话历史混在一起。不同微信用户发来的消息由同一个 session 处理，导致：

- USER.md（用户画像/记忆）被多个用户的内容混写
- diary/ 日记条目跨用户污染
- 可可无法区分"这是谁在说话"，上下文错乱

## 方案

配置 `dmScope: "per-channel-peer"`，让每个微信用户获得独立的 session。

## 配置方法

在 `openclaw.json` 中，找到 `session` 配置块，添加或修改 `dmScope` 字段：

```json
{
  "session": {
    "dmScope": "per-channel-peer"
  }
}
```

`per-channel-peer` 的含义：每个（channel, peer）组合对应一个独立 session key。对于微信私聊，channel 是 `openclaw-weixin`，peer 是发信人的 wxid，因此每位微信用户天然隔离。

## 效果

- 每个用户的 USER.md 独立存储，记录各自的情绪偏好、历史事件
- diary/ 日记条目按用户隔离，互不可见
- 可可对每位用户维持独立的上下文，不会把 A 的事情说给 B 听
- 跨用户零污染

## 群组场景

群消息使用群专属的 session key：

```
agent:coco:openclaw-weixin:group:{groupId}
```

群内所有成员共享该群的 session（群聊是公共空间，这是预期行为）。群 session 与私聊 session 完全隔离，群里的对话不会影响任何用户的私聊记忆。

如需群内也按成员隔离（较少见），可将群消息的 peer 设为 `{groupId}:{senderId}` 组合键，但通常群场景不需要这样处理。

## Sandbox 多租户隔离

除了 `dmScope` 隔离对话历史，还需配置 sandbox 实现用户数据文件隔离：

```json
{
  "agents": {
    "defaults": {
      "sandbox": {
        "mode": "all",
        "scope": "per-sender",
        "workspaceAccess": "rw"
      }
    }
  }
}
```

`per-sender` 的含义：每个发送者获得独立的 sandbox workspace。SOUL.md、AGENTS.md、skills/ 从主 workspace 自动复制，USER.md、people/、diary/、memory/ 在各自 sandbox 中独立积累。

两层隔离共同工作：
- `dmScope: per-channel-peer` → 对话历史隔离
- `sandbox.scope: per-sender` → 文件数据隔离（含 memory_search 搜索范围）

---

## ⚠️ 重要澄清：线上多租户由后端实现，非 OpenClaw

**本文档描述的是 OpenClaw 本地测试场景的隔离方案。**

线上环境的多租户隔离由 `psychologists` 后端项目（FastAPI）实现，不依赖 OpenClaw sandbox：

| 关注点 | 线上方案（psychologists 后端） | 本地测试（OpenClaw） |
|--------|-------------------------------|---------------------|
| 用户隔离 | JWT → `user_id` (UUID)，所有表都有 `user_id` 外键 | `dmScope: per-channel-peer`（单租户测试足够） |
| 记忆存储 | `MemoryItem` + `MemoryCategory` 表，按 user_id 隔离 | `memory/` 目录（本地文件，仅测试用） |
| 用户档案 | DB `User.profile_data` + `MemoryCategory(type=profile)` | `USER.md`（本地文件，仅测试用） |
| 人物档案 | `MemoryItem(entity_name, entity_type, entity_relation)` | `people/*.md`（本地文件，仅测试用） |
| Context 注入 | L3 层：`MemoryLoader.load_user_memory(user_id)` → Markdown → system prompt | `memory_search` 工具读本地文件 |

**结论：** moodcoco workspace 是**模板**（SOUL.md、AGENTS.md、Skills），不是数据存储。线上用户数据全部走 DB，按 `user_id` 天然隔离。`sandbox.scope: per-sender` 在 OpenClaw 中实际不是合法值（仅支持 session/agent/shared），本地测试单租户即可。
