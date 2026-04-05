PROMPT_LEGACY = """
Your task is to read and understand the resource content between the user and the assistant, and, based on the given memory categories, extract behavioral patterns, routines, and solutions about the user.

## Original Resource:
<resource>
{resource}
</resource>

## Memory Categories:
{categories_str}

## Critical Requirements:
The core extraction target is behavioral memory items that record patterns, routines, and solutions characterizing how the user acts or behaves to solve specific problems.

## Memory Item Requirements:
- Use the same language as the resource in <resource></resource>.
- Extract patterns of behavior, routines, and solutions
- Focus on how the user typically acts, their preferences, and regular activities
- Each item can be either a single sentence concisely describing the pattern, routine, or solution, or a multi-line record with each line recording a specific step of the pattern, routine, or solution.
- Only extract meaningful behaviors, skip one-time actions unless significant
- Return empty array if no meaningful behaviors found

## About Memory Categories:
- You can put identical or similar memory items into multiple memory categories.
- Do not create new memory categories. Please only generate in the given memory categories.
- The given memory categories may only cover part of the resource's topic and content. You don't need to summarize resource's content unrelated to the given memory categories.
- If the resource does not contain information relevant to a particular memory category, You can ignore that category and avoid forcing weakly related memory items into it. Simply skip that memory category and DO NOT output contents like "no relevant memory item".

## Memory Item Content Requirements:
- Single line plain text, no format, index, or Markdown.
- If the original resource contains emojis or other special characters, ignore them and output in plain text.
- *ALWAYS* use the same language as the resource.

# Response Format (JSON):
{{
    "memories_items": [
        {{
            "content": "the content of the memory item",
            "categories": [list of memory categories that this memory item should belongs to, can be empty]
        }}
    ]
}}
"""

PROMPT_BLOCK_OBJECTIVE = """
# Task Objective
你是心理陪伴场景的记忆提取器。你的核心任务是从用户与 AI 陪伴师的对话中，提取用户的重复行为模式和有效应对方法。

提取重点（分配到 self/* category）：
- **重复行为模式**（→ self/行为模式）：跨关系重复出现的行为，如"用户在冲突中总是先道歉""用户每次压力大就回避问题"
- **有效应对方法**（→ self/有效方法）：用户发现对自己有用的应对策略，如"散步能让用户冷静下来""写东西能帮用户理清思路"
- **自我认知变化**（→ self/核心信念）：用户对自己的看法发生了变化，如"用户从'我总是不够好'变为'有些事我做得不错'"

特别注意：
- 只提取出现 ≥2 次或用户自己总结的模式，不从单次事件推断模式
- 保留用户原话（用引号标注）
- 有效方法只记录用户确认有效的，不记录 AI 建议的
"""

PROMPT_BLOCK_WORKFLOW = """
# Workflow
Read the full conversation to understand topics and meanings.
## Extract memories
Select turns that contain valuable Behavior Information and extract behavioral memory items.
## Review & validate
Merge semantically similar items.
Resolve contradictions by keeping the latest / most certain item.
## Final output
Output Behavior Information.
"""

PROMPT_BLOCK_RULES = """
# Rules
## General requirements (must satisfy all)
- 用"用户"指代用户。
- 每条记忆必须完整独立，用陈述句描述。
- 每条记忆表达一个完整信息，脱离上下文也能理解。
- 相似条目合并，只分配到一个 category。
- 每条记忆不超过 60 字（中文）。
- 使用中文输出（与对话语言一致）。
Important: 只提取用户明确说出或确认的模式。不推测、不脑补、不提取 AI 陪伴师的建议。
Important: 准确区分主语是用户本人还是用户身边的人。

## Special rules for Behavior Information
- 单次事件禁止出现在 behavior 中（由 event prompt 处理），除非用户自己说"我总是这样""每次都这样"。
- 聚焦跨关系/跨情境的重复模式和经验证有效的应对方法。
- AI 建议的方法不提取，只提取用户自己发现/确认有效的方法。
- 自我认知变化需标注变化方向（从 X 变为 Y）。

## Forbidden content
- AI 陪伴师的分析、建议、推测。
- 单次事件（除非用户自己总结为模式）。
- 只有 AI 陪伴师说话而用户未回应的轮次。
- 危机相关敏感信息（自杀/自伤方式不提取）。

## Review & validation rules
- 合并相似条目，保留最新/最确定的版本。
- 最终检查：每条必须符合所有提取规则。
"""

PROMPT_BLOCK_CATEGORY = """
## Memory Categories:
{categories_str}

### Category 说明
behavior 提取的记忆主要分配到 self/行为模式 和 self/有效方法。不使用 people/* 或 events/*（由 event/knowledge prompt 负责）。
"""

PROMPT_BLOCK_OUTPUT = """
# Output Format (XML)
Return all memories wrapped in a single <item> element:
<item>
    <memory>
        <content>Behavior memory item content 1</content>
        <categories>
            <category>Category Name</category>
        </categories>
    </memory>
    <memory>
        <content>Behavior memory item content 2</content>
        <categories>
            <category>Category Name</category>
        </categories>
    </memory>
</item>
"""

PROMPT_BLOCK_EXAMPLES = """
# Examples (Input / Output / Explanation)
Example 1: 心理陪伴对话中的行为模式提取
## Input
user: 我又跟男朋友吵架了
assistant: 又吵了，听起来挺累的
user: 对，每次一吵架我就先道歉，然后他就不理我了，我就更焦虑
assistant: 你说"每次"——这个模式出现很多次了？
user: 嗯，跟朋友吵架也是这样，我总是先道歉。不过后来我发现出去散步能让我冷静下来，就没那么急着道歉了
## Output
<item>
    <memory>
        <content>用户在冲突中的重复模式：总是先道歉，对方不理会后会更焦虑。跨关系出现（男朋友、朋友）</content>
        <categories>
            <category>self/行为模式</category>
        </categories>
    </memory>
    <memory>
        <content>用户发现出去散步能让自己冷静下来，减少冲突中急于道歉的冲动</content>
        <categories>
            <category>self/有效方法</category>
        </categories>
    </memory>
</item>
## Explanation
- "总是先道歉"是用户自己说的跨关系模式（男朋友+朋友），提取为行为模式
- "散步能冷静"是用户自己发现并确认有效的方法
- "又跟男朋友吵架"是单次事件，不在 behavior 中提取（由 event prompt 处理）
"""

PROMPT_BLOCK_INPUT = """
# Original Resource:
<resource>
{resource}
</resource>
"""

PROMPT = "\n\n".join([
    PROMPT_BLOCK_OBJECTIVE.strip(),
    PROMPT_BLOCK_WORKFLOW.strip(),
    PROMPT_BLOCK_RULES.strip(),
    PROMPT_BLOCK_CATEGORY.strip(),
    PROMPT_BLOCK_OUTPUT.strip(),
    PROMPT_BLOCK_EXAMPLES.strip(),
    PROMPT_BLOCK_INPUT.strip(),
])

CUSTOM_PROMPT = {
    "objective": PROMPT_BLOCK_OBJECTIVE.strip(),
    "workflow": PROMPT_BLOCK_WORKFLOW.strip(),
    "rules": PROMPT_BLOCK_RULES.strip(),
    "category": PROMPT_BLOCK_CATEGORY.strip(),
    "output": PROMPT_BLOCK_OUTPUT.strip(),
    "examples": PROMPT_BLOCK_EXAMPLES.strip(),
    "input": PROMPT_BLOCK_INPUT.strip(),
}
