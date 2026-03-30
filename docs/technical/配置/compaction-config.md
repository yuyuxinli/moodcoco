# 长对话压缩配置（Compaction）

## 默认行为

OpenClaw compaction 默认使用 **safeguard 模式**，在压缩对话时尽量保留关键信息，但默认策略并不了解心情可可的业务场景。

## 推荐自定义压缩指令

在 `openclaw.json` 中配置自定义压缩指令，确保压缩后保留对情绪陪伴最关键的上下文：

```
压缩时必须保留：用户的反复情绪模式、核心困扰关键词、人物关系（people/ 目录中的人名）、本次对话中发现的新模式
```

## 配置方法

在 `openclaw.json` 的 `agents.defaults.compaction` 字段中填入自定义指令：

```json
{
  "agents": {
    "defaults": {
      "compaction": "压缩时必须保留：用户的反复情绪模式、核心困扰关键词、人物关系（people/ 目录中的人名）、本次对话中发现的新模式"
    }
  }
}
```

## 触发时机

- **自动触发**：对话长度超过模型 context window 时自动触发
- **手动触发**：输入 `/compact` 命令立即执行压缩
