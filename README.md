# MoodCoco — AI 情感陪伴

基于 OpenClaw 的情感陪伴 AI，帮用户「看见自己」。

## 核心能力
- 看见情绪：从模糊到精确命名
- 看见原因：连接到深层需求
- 看见模式：识别跨场景的重复模式
- 看见方法：用户自己找到解决方向

## 技术栈
- OpenClaw Agent Workspace（.md + skills）
- 模型：minimax-m2.7 + thinking high
- 评估：Evolve 自动循环（5维度 × 15场景）

## 快速开始
```bash
openclaw agents add coco --workspace ./ai-companion
openclaw agent --agent coco --message "你好" --local --thinking high
```

