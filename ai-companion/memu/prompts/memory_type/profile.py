PROMPT_LEGACY = """
Your task is to read and understand the resource content between the user and the assistant, and, based on the given memory categories, extract memory items about the user.

## Original Resource:
<resource>
{resource}
</resource>

## Memory Categories:
{categories_str}

## Critical Requirements:
The core extraction target is self-contained memory items about the user.

## Memory Item Requirements:
- Use the same language as the resource in <resource></resource>.
- Each memory item should be complete and standalone.
- Each memory item should express a complete piece of information, and is understandable without context and reading other memory items.
- Always use declarative and descriptive sentences.
- Use "the user" (or that in the target language, e.g., "用户") to refer to the user.
- You can cluster multiple events that are closely related or under a single topic into a single memory item, but avoid making each single memory item too long (over 100 words).
- **Important** Carefully judge whether an event/fact/information is narrated by the user or the assistant. You should only extract memory items for the event/fact/information directly narrated or confirmed by the user. DO NOT include any groundless conjectures, advice, suggestions, or any content provided by the assistant.
- **Important** Carefully judge whether the subject of an event/fact/information is the user themselves or some person around the user (e.g., the user's family, friend, or the assistant), and reflect the subject correctly in the memory items.
- **Important** DO NOT record temporary, ephemeral, or one-time situational information such as weather conditions (e.g., "today is raining"), current mood states, temporary technical issues, or any short-lived circumstances that are unlikely to be relevant for the user profile. Focus on meaningful, persistent information about the user's characteristics, preferences, relationships, ongoing situations, and significant events.

## Example (good):
- The user and his family went on a hike at a nature park outside the city last weekend. They had a picnic there, and had a great time.

## Example (bad):
- The user went on a hike. (The time, place, and people are missing.)
- They had a great time. (The reference to "they" is unclear and does not constitute a self-contained memory item.)
- The user and his family went on a hike at a nature park outside the city last weekend. The user and his family had a picnic at a nature park outside the city last weekend. (Should be merged.)

## About Memory Categories:
- You can put identical or similar memory items into multiple memory categories. For example, "The user and his family went on a hike at a nature park outside the city last weekend." can be put into all of "hiking", "weekend activities", and "family activities" categories (if they exist). Nevertheless, Memory items put to each category can have different focuses.
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
你是心理陪伴场景的记忆提取器。你的核心任务是从用户与 AI 陪伴师的对话中，提取用户的个人画像信息。

提取重点（分配到 self/* category）：
- 基本信息：称呼、年龄、身份（学生/职场人）、所在城市
- 沟通偏好：喜欢被怎么称呼、偏好的对话方式（直接/委婉）、讨厌的回应方式
- 核心信念：用户关于自己的稳定看法（如"我不值得被爱""我总是不够好"）
- 价值观：什么对用户重要（如独立、被认可、安全感）
- 情绪触发点：什么情境容易触发强烈情绪（如被忽视、被比较、被催促）

特别注意：
- 只提取用户明确说出或确认的信息，不推测
- 保留用户原话（用引号标注）
- 自我评价性语句是重点（如"我就是讨好型人格"→ 提取为核心信念）
"""

PROMPT_BLOCK_WORKFLOW = """
# Workflow
Read the full conversation to understand topics and meanings.
## Extract memories
Select turns that contain valuable User Information and extract user info memory items.
## Review & validate
Merge semantically similar items.
Resolve contradictions by keeping the latest / most certain item.
## Final output
Output User Information.
"""

PROMPT_BLOCK_RULES = """
# Rules
## General requirements (must satisfy all)
- 用”用户”指代用户。
- 每条记忆必须完整独立，用陈述句描述。
- 每条记忆表达一个完整信息，脱离上下文也能理解。
- 相似条目合并，只分配到一个 category。
- 每条记忆不超过 50 字（中文）。
- 不包含时间戳。
- 使用中文输出（与对话语言一致）。
Important: 只提取用户明确说出或确认的信息。不推测、不脑补、不提取 AI 陪伴师的建议。
Important: 准确区分主语是用户本人还是用户身边的人。
Important: 不记录临时/一次性状态；聚焦有意义的持久信息。

## Special rules for User Information
- 事件类条目禁止出现在 profile 中（事件由 event prompt 处理）。
- 保留用户原话中的关键表达（用引号标注）。
- 自我评价性语句（如”我就是这样的人””我不够好”）必须提取为核心信念。

## Forbidden content
- AI 陪伴师的分析、建议、推测。
- 无意义的细微更新。
- 只有 AI 陪伴师说话而用户未回应的轮次。
- 危机相关敏感信息（自杀/自伤细节不作为 profile 提取，由 crisis 模块处理）。
- 除非用户主动提及，不提取精确地址、身份证号等隐私。

## Review & validation rules
- 合并相似条目，保留最新/最确定的版本。
- 最终检查：每条必须符合所有提取规则。
"""

PROMPT_BLOCK_CATEGORY = """
## Memory Categories:
{categories_str}

### Category 说明
profile 提取的记忆主要分配到 self/* 系列 category。不使用 people/* 或 events/*（由 event/knowledge prompt 负责）。
"""

PROMPT_BLOCK_OUTPUT = """
# Output Format (XML)
Return all memories wrapped in a single <item> element:
<item>
    <memory>
        <content>User memory item content 1</content>
        <categories>
            <category>Category Name</category>
        </categories>
    </memory>
    <memory>
        <content>User memory item content 2</content>
        <categories>
            <category>Category Name</category>
        </categories>
    </memory>
</item>
"""

PROMPT_BLOCK_EXAMPLES = """
# Examples (Input / Output / Explanation)
Example 1: 心理陪伴对话中的个人画像提取
## Input
user: 我妈又催我考研了，烦死了
assistant: 听起来你现在很烦
user: 对，她每次打电话都要提，我都不想接电话了。我叫小雨，大四，在北京。每次她一催我就觉得自己不够好，好像什么都做不好
assistant: "觉得自己不够好"——这个感觉出现很多次吗？
user: 嗯，从小就这样，她总拿我跟别人比
## Output
<item>
    <memory>
        <content>用户叫小雨，大四学生，在北京</content>
        <categories>
            <category>self/核心信念</category>
        </categories>
    </memory>
    <memory>
        <content>用户的核心信念："觉得自己不够好""什么都做不好"，从小就有这种感觉</content>
        <categories>
            <category>self/核心信念</category>
        </categories>
    </memory>
    <memory>
        <content>用户的情绪触发点：被妈妈催促/拿来跟别人比较时容易触发"不够好"的感觉</content>
        <categories>
            <category>self/情绪触发点</category>
        </categories>
    </memory>
</item>
## Explanation
- 提取了稳定的个人信息（姓名、年级、城市）
- "觉得自己不够好"是用户原话，属于核心信念
- "被催促/被比较"是情绪触发点
- "妈妈催考研"是事件，不在 profile 中提取（由 event prompt 处理）
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
