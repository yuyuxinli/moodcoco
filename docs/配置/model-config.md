# 模型配置说明

## 推荐主模型

**minimax-m2.7**（via OpenRouter），开启 `thinking: high`。

## Failover Chain

```
minimax-m2.7 → doubao-seed-2-0-pro-260215 → openrouter/auto
```

主模型不可用时依次降级，保证服务连续性。

## 不推荐模型

**deepseek-v3.2** — 不推荐，原因：
- 响应慢（约 80 秒/条），严重影响用户体验
- 存在内部推理泄漏风险，不适合生产环境

## 配置方法

在项目根目录的 `openclaw.json` 中，找到 `agents.list` 下 `coco` 的条目，修改 `model` 字段：

```json
{
  "agents": {
    "list": [
      {
        "name": "coco",
        "model": "openrouter/minimax/minimax-m2.7",
        "thinking": "high",
        "fallback": [
          "doubao-seed-2-0-pro-260215",
          "openrouter/auto"
        ]
      }
    ]
  }
}
```

> 注：`openrouter/` 前缀表示经由 OpenRouter 路由。具体字段名称以 openclaw 实际支持的 schema 为准。
