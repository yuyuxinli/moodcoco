PROMPT_LEGACY = """
Your task is to read and understand the resource content between the user and the assistant, and, based on the given memory categories, extract specific events and experiences that happened to or involved the user.

## Original Resource:
<resource>
{resource}
</resource>

## Memory Categories:
{categories_str}

## Critical Requirements:
The core extraction target is eventful memory items about specific events, experiences, and occurrences that happened at a particular time and involve the user.

## Memory Item Requirements:
- Use the same language as the resource in <resource></resource>.
- Each memory item should be complete and standalone.
- Each memory item should express a complete piece of information, and is understandable without context and reading other memory items.
- Always use declarative and descriptive sentences.
- Use "the user" (or that in the target language, e.g., "用户") to refer to the user.
- Focus on specific events that happened at a particular time or period.
- Extract concrete happenings, activities, and experiences.
- Include relevant details such as time, location, and participants where available.
- Carefully judge whether an event is narrated by the user or the assistant. You should only extract memory items for events directly narrated or confirmed by the user.
- DO NOT include behavioral patterns, habits, or factual knowledge.
- DO NOT record temporary, ephemeral situations or trivial daily activities unless significant.

## Example (good):
- The user and his family went on a hike at a nature park outside the city last weekend. They had a picnic there, and had a great time.

## Example (bad):
- The user went on a hike. (The time, place, and people are missing.)
- They had a great time. (The reference to "they" is unclear and does not constitute a self-contained memory item.)

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
你是心理陪伴场景的记忆提取器。你的核心任务是从用户与 AI 陪伴师的对话中，提取与人物关系和事件进展相关的具体事件。

提取重点：
- **人物关系事件**（分配到 people/* category）：与具体人物的互动、冲突、关系变化。如"用户和妈妈因为考研的事吵了一架"
- **长周期事件进展**（分配到 events/* category）：考研/求职/分手等长期事件的阶段性变化。如"用户决定放弃考研"
- **退出信号**：用户对某段关系或事件表达的结束/放弃/翻篇意愿，需标注确定性（高/中/低）
- **关键时间节点**：涉及的日期、截止日期、约定时间

特别注意：
- 一条事件可以同时属于多个 category（如"和妈妈因为考研吵架"→ people/妈妈 + events/考研）
- 只提取用户明确说出或确认的事件，不推测
- 保留用户原话中的关键表达（用引号标注）
- 退出信号必须标注确定性等级
"""

PROMPT_BLOCK_WORKFLOW = """
# Workflow
Read the full conversation to understand topics and meanings.
## Extract memories
Select turns that contain valuable Event Information and extract event memory items.
## Review & validate
Merge semantically similar items.
Resolve contradictions by keeping the latest / most certain item.
## Final output
Output Event Information.
"""

PROMPT_BLOCK_RULES = """
# Rules
## General requirements (must satisfy all)
- 用"用户"指代用户。
- 每条记忆必须完整独立，用陈述句描述。
- 每条记忆表达一个完整信息，脱离上下文也能理解。
- 一条事件可以分配到多个 category（如同时涉及人物和事件）。
- 每条记忆不超过 80 字（中文），但需包含关键细节（时间、人物、地点）。
- 使用中文输出（与对话语言一致）。
Important: 只提取用户明确说出或确认的事件。不推测、不脑补、不提取 AI 陪伴师的建议。
Important: 准确区分主语是用户本人还是用户身边的人。

## Special rules for Event Information
- 行为模式、偏好、画像信息禁止出现在 event 中（由 profile/behavior prompt 处理）。
- 聚焦具体发生的事件、互动、经历。
- 退出信号必须标注确定性：高（明确说"分手了""放弃了"）/ 中（"想分手""考虑放弃"）/ 低（"有点累了""不太想继续"）。
- 涉及时间节点的事件保留时间信息（如"下周五要跟导师谈"）。

## Forbidden content
- AI 陪伴师的分析、建议、推测。
- 无意义的日常琐事（除非对用户情绪有显著影响）。
- 只有 AI 陪伴师说话而用户未回应的轮次。
- 危机相关敏感信息的具体细节（自杀/自伤方式不提取，只标记事件存在）。
- 除非用户主动提及，不提取精确地址、身份证号等隐私。

## Review & validation rules
- 合并相似条目，保留最新/最确定的版本。
- 多 category 分配：一条事件涉及多个人物或事件时，分配到所有相关 category。
- 最终检查：每条必须符合所有提取规则。
"""

PROMPT_BLOCK_CATEGORY = """
## Memory Categories:
{categories_str}

### 动态 Category 规则
除了上述预定义 category，你可以创建以下格式的动态 category：
- `people/{{人物称呼}}` — 用户提到的每个人物一个 category，如 people/妈妈、people/男朋友、people/导师
- `events/{{事件名称}}` — 用户的长周期事件一个 category，如 events/考研、events/求职、events/分手

命名规范：
- 使用用户的原始称呼（"妈妈"而非"母亲"，"男朋友"而非"男友"）
- 事件用最简洁的名词（"考研"而非"准备考研究生"）
- 一条记忆可以同时分配到多个 category
"""

PROMPT_BLOCK_OUTPUT = """
# Output Format (XML)
Return all memories wrapped in a single <item> element:
<item>
    <memory>
        <content>Event memory item content 1</content>
        <categories>
            <category>Category Name</category>
        </categories>
    </memory>
    <memory>
        <content>Event memory item content 2</content>
        <categories>
            <category>Category Name</category>
        </categories>
    </memory>
</item>
"""

PROMPT_BLOCK_EXAMPLES = """
# Examples (Input / Output / Explanation)
Example 1: 心理陪伴对话中的事件提取
## Input
user: 我今天跟妈妈因为考研的事吵了一架
assistant: 听起来你现在很难受
user: 对，她非要我考她选的学校，我说我想考北大，她就说我不切实际。男朋友安慰了我，说支持我的选择
assistant: 男朋友能理解你，这挺好的
user: 嗯，但是我还是很生气。而且论文DDL下周五，我根本没心思写
## Output
<item>
    <memory>
        <content>用户今天和妈妈因为考研择校的事发生争吵，妈妈要求用户考她选的学校，用户想考北大，妈妈说用户"不切实际"</content>
        <categories>
            <category>people/妈妈</category>
            <category>events/考研</category>
        </categories>
    </memory>
    <memory>
        <content>用户的男朋友安慰了用户，表示支持用户自己的考研择校选择</content>
        <categories>
            <category>people/男朋友</category>
            <category>events/考研</category>
        </categories>
    </memory>
    <memory>
        <content>用户的论文DDL是下周五，目前没有心思写</content>
        <categories>
            <category>events/学业</category>
        </categories>
    </memory>
</item>
## Explanation
- "和妈妈吵架"同时分配到 people/妈妈 和 events/考研（涉及人物+事件）
- "男朋友安慰"同时分配到 people/男朋友 和 events/考研
- 保留了用户原话"不切实际"
- 论文DDL有明确时间节点（下周五）
- 用户的情绪状态（生气、没心思）不作为事件提取（由 profile prompt 处理）

Example 2: 退出信号提取
## Input
user: 我不想跟他在一起了，真的累了
assistant: 听起来你在认真考虑这件事
user: 嗯，但又有点舍不得
## Output
<item>
    <memory>
        <content>用户表达了想和男朋友分手的意愿，说"真的累了"，但同时表示"有点舍不得"。退出信号确定性：中</content>
        <categories>
            <category>people/男朋友</category>
        </categories>
    </memory>
</item>
## Explanation
- 退出信号标注确定性为"中"——用户有分手意愿但同时表达了犹豫
- 保留了用户原话"真的累了""有点舍不得"
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
