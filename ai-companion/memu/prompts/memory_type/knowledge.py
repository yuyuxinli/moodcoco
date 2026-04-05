PROMPT_LEGACY = """
Your task is to read and understand the resource content between the user and the assistant, and, based on the given memory categories, extract knowledge and information that the user learned or discussed.

## Original Resource:
<resource>
{resource}
</resource>

## Memory Categories:
{categories_str}

## Critical Requirements:
The core extraction target is factual memory items that reflect knowledge, concepts, definitions, and factual information that the resource content suggests.

## Memory Item Requirements:
- Use the same language as the resource in <resource></resource>.
- Each memory item should be complete and standalone.
- Each memory item should express a complete piece of information, and is understandable without context and reading other memory items.
- Extract factual knowledge, concepts, definitions, and explanations
- Focus on objective information that can be learned or referenced
- Each item should be a descriptive sentence.
- Only extract meaningful knowledge, skip opinions or personal experiences
- Return empty array if no meaningful knowledge found

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
你是心理陪伴场景的记忆提取器。你的核心任务是从用户与 AI 陪伴师的对话中，提取人际关系网络、时间节点和环境信息。

提取重点：
- **人际关系网络**：用户提到的人物之间的关系（如"用户的男朋友和妈妈关系不好"），分配到最相关的 category
- **关键时间节点**：截止日期、考试日期、约定时间等（如"考研初试时间12月23日"），分配到相关 events/* category
- **环境信息**：影响用户状态的环境因素（如"用户独居""用户宿舍四人间"），分配到最相关的 category

特别注意：
- 只提取用户明确说出的客观信息，不推测
- 人际关系只记录用户确认的事实关系，不记录 AI 的解读
"""

PROMPT_BLOCK_WORKFLOW = """
# Workflow
Read the full conversation to understand topics and meanings.
## Extract memories
Select turns that contain valuable Knowledge Information and extract knowledge memory items.
## Review & validate
Merge semantically similar items.
Resolve contradictions by keeping the latest / most certain item.
## Final output
Output Knowledge Information.
"""

PROMPT_BLOCK_RULES = """
# Rules
## General requirements (must satisfy all)
- 用"用户"指代用户。
- 每条记忆必须完整独立，用陈述句描述。
- 每条记忆表达一个完整信息，脱离上下文也能理解。
- 相似条目合并，只分配到一个 category。
- 每条记忆不超过 50 字（中文）。
- 使用中文输出（与对话语言一致）。
Important: 只提取用户明确说出的客观信息。不推测、不脑补。

## Special rules for Knowledge Information
- 用户的个人画像、事件、行为模式禁止出现在 knowledge 中（由其他 prompt 处理）。
- 聚焦客观的关系网络、时间节点、环境信息。
- 人际关系只记录用户确认的事实，不记录 AI 的解读或推测。

## Forbidden content
- AI 陪伴师的分析、建议、推测。
- 用户的个人观点和主观感受（由 profile prompt 处理）。
- 单次事件细节（由 event prompt 处理）。
- 危机相关敏感信息。

## Review & validation rules
- 合并相似条目，保留最新/最确定的版本。
- 最终检查：每条必须符合所有提取规则。
"""

PROMPT_BLOCK_CATEGORY = """
## Memory Categories:
{categories_str}

### 动态 Category 规则
除了上述预定义 category，你可以使用以下格式的动态 category：
- `people/{{人物称呼}}` — 如 people/妈妈、people/男朋友
- `events/{{事件名称}}` — 如 events/考研、events/求职
使用用户的原始称呼，事件用最简洁的名词。
"""

PROMPT_BLOCK_OUTPUT = """
# Output Format (XML)
Return all memories wrapped in a single <item> element:
<item>
    <memory>
        <content>Knowledge memory item content 1</content>
        <categories>
            <category>Category Name</category>
        </categories>
    </memory>
    <memory>
        <content>Knowledge memory item content 2</content>
        <categories>
            <category>Category Name</category>
        </categories>
    </memory>
</item>
"""

PROMPT_BLOCK_EXAMPLES = """
# Examples (Input / Output / Explanation)
Example 1: 心理陪伴对话中的关系网络和环境信息提取
## Input
user: 我妈又催我考研了，我爸倒是支持我工作
assistant: 听起来爸妈的想法不一样
user: 对，我妈和我爸在这件事上一直吵。男朋友也支持我工作，他在上海，我在北京
assistant: 异地也不容易
user: 嗯，考研初试12月23号，还有两个月
## Output
<item>
    <memory>
        <content>用户的妈妈和爸爸在考研问题上有分歧，妈妈支持考研，爸爸支持工作</content>
        <categories>
            <category>people/妈妈</category>
            <category>people/爸爸</category>
        </categories>
    </memory>
    <memory>
        <content>用户的男朋友在上海，用户在北京，处于异地恋状态</content>
        <categories>
            <category>people/男朋友</category>
        </categories>
    </memory>
    <memory>
        <content>考研初试时间为12月23号</content>
        <categories>
            <category>events/考研</category>
        </categories>
    </memory>
</item>
## Explanation
- 爸妈在考研问题上的分歧是客观的关系网络信息
- 异地恋是环境信息
- 考研初试时间是关键时间节点
- "催我考研"是事件，不在 knowledge 中提取
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
