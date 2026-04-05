---
name: personality-analysis
description: 人格分析报告生成——基于用户的 MBTI 类型和维度得分，生成深度个性化的人格解析报告。触发条件：generate_personality_analysis 事件，通常在 MBTI 测试完成后由前端发起。
---

# 人格分析报告生成

基于用户的 MBTI 人格类型和各维度得分，生成一份温暖、有深度、个性化的人格解析报告。

## 触发条件

- 收到 `generate_personality_analysis` 事件
- 事件数据中包含 `personalityType` 和 `personalityScore`

## 报告生成流程

### 1. 接收参数

从事件数据中提取：
- `personalityType`：MBTI 类型（如 "INTJ"）
- `personalityScore`：各维度得分（E/I/N/S/T/F/J/P 的百分比）
- `sessionInfo`：会话信息（可选）

### 2. 持久化消息

调用 `message_persist` 创建一条待处理的 AI 消息：
```
action: "create_pending"
session_id: "<当前 session>"
content_type: "ai_personality_analysis"
```

### 3. 生成报告

输出严格的 JSON 格式：

```json
{
  "Motto": "一句高度凝练的短句，为该人格类型奠定基调",
  "Definition": "积极正向的描述，让用户感受到独特优势",
  "Core Analysis": "四个维度的精确分析（能量/心智/本性/策略），必须引用具体得分",
  "Topic Guide": "人格类型解读",
  "Double-Edged Sword": "温和地指出挑战和内在冲突",
  "Growth Tips": "2-3 条具体可操作的行动建议",
  "Guiding Questions": {
    "过渡文字": "引导用户思考的过渡语",
    "问题1": "我如何...",
    "问题2": "我应该..."
  }
}
```

### 4. 保存报告

调用 `message_persist` 更新消息内容：
```
action: "update_content"
message_id: "<预创建的 message_id>"
response_data: <生成的 JSON 报告>
```

## 可用工具

### Service Tools
- `message_persist` — 消息的创建和更新

## 分析规则

1. **必须引用具体得分**：每个维度分析中都要提到用户的实际得分百分比
2. **温暖正向**：Definition 部分要让用户感受到被看见和被肯定
3. **具体可操作**：Growth Tips 不要泛泛而谈，要给出具体场景下的建议
4. **不贴标签**：不说"你是 XX 型人格所以 XX"，而是描述具体行为模式

## 硬规则

1. **不做医学诊断**：MBTI 是自我认知工具，不是诊断工具
2. **不过度解读**：得分差异小时（如 52% vs 48%），明确说明两种倾向都有
3. **不使用贬义描述**：每种人格类型都有独特价值，不暗示某种类型更好
4. **输出必须是有效 JSON**：确保前端能直接解析
