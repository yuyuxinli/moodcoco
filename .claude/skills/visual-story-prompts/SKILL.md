---
name: visual-story-prompts
description: Generate visually coherent Lovart/Nanobanana image prompts for multi-card WeChat story posts. Use when the user has a story plan document and needs to create AI image generation prompts that maintain visual continuity across different card styles (character-focused, panel/grid, text-focused). Also use when the user mentions 'out-image instructions,' 'Lovart prompts,' 'visual story,' 'card story,' 'image story continuity,' or 'carousel post prompts.'
---

# Visual Story Prompts

Generate visually coherent Lovart (Nanobanana) prompts for multi-card image stories, ensuring continuity across different card styles.

## Target Tool: Lovart + Nanobanana

**Lovart** is an AI design agent (not a simple image generator). Users interact through **chat-based dialogue**: describe what you want, Lovart generates it, then you refine through follow-up natural language instructions without rewriting the full prompt.

**Key capabilities that affect how we write prompts:**

| Capability | Implication for Prompt Writing |
|-----------|-------------------------------|
| **Conversational iteration** | First prompt establishes direction (composition, color, character position, text layout). Details (expression tweaks, light adjustments) are refined through follow-up dialogue. No need for a "perfect" first prompt. |
| **Touch Edit** | Lovart can modify selected regions while preserving the rest. Expression/layout changes don't require full regeneration. |
| **Reference images (up to 14)** | Screenshot-based cards: upload the original screenshot directly, mark with `【附加参考图】` in the prompt. Lovart interprets layout and content from the reference. |
| **Character consistency** | Nanobanana maintains consistent facial features, clothing, and character elements across multiple generations. Keep the character description prefix identical across all character-focused prompts. |
| **Natural language understanding** | Nanobanana responds to detailed natural language — no special syntax needed. But **physical/visible descriptions execute better than poetic/abstract ones** (see Step 5 Expression guidelines). |
| **Resolution** | Supports 2K/4K output. Default 3:4 vertical. |

## Theory Foundation

This skill draws from two sources. Read [references/shot-grammar.md](references/shot-grammar.md) for full theory.

**From "Understanding Comics" (Scott McCloud):**
- Panel-to-panel transitions: how adjacent images create narrative flow
- Closure: reader's brain fills gaps between panels — smaller gaps = smoother story
- Time-as-space: image size/layout controls perceived time passing

**From "Master Shots" (Christopher Kenworthy):**
- Shot size controls emotional distance (wide = context, close = intimacy)
- Camera angle conveys power dynamics and vulnerability
- Movement direction creates continuity between cuts

## 可可角色参考

**参考图**: [references/可可_角色参考.png](references/可可_角色参考.png)

给 Lovart 生成含可可的图时，务必附上这张参考图，并在 prompt 中包含以下角色描述前缀：

```
角色「可可」：圆脸小女孩，浅蓝色尖顶帽兜（帽兜连着衣服），金黄色及肩短发从帽兜两侧露出，
大黑眼睛，粉红脸颊，微笑。穿浅蓝色连帽长裙+同色打底裤+浅蓝靴子。
整体配色以浅蓝为主，风格圆润可爱，扁平插画风。
```

**跨卡一致性要点**：
- 帽兜形状（尖顶、贴合头部）和衣服是一体的，不是分开的帽子
- 头发金黄色，从帽兜两侧自然垂下
- 表情默认是温和微笑，根据场景调整（参考 Step 5 Expression 写法）
- 全身配色保持浅蓝色系，不同场景可微调明暗但不改色相

---

## Core Concept: Three Shot Types as a System

Each card style is a stable "shot type." The skill does NOT modify how individual card types are prompted — only how they connect.

| Shot Type | Video Analogy | Narrative Function | Lovart Output |
|-----------|---------------|-------------------|----------------|
| **Character-focused** (可可为主) | Main footage | Carry emotion, advance story | Full scene + character + text, 3:4 |
| **Panel/Grid** (分格) | Picture-in-picture / reaction shot | Show evidence + instant reaction | Full manga-style multi-panel page, 3:4 (Lovart generates the entire grid layout with panels, gutters, reactions in one prompt) |
| **Text-focused** (文字为主) | Title card / voiceover | Breathing room, topic pivot | Background frame or pure text layout, 3:4 |

**Default format**: All cards are 3:4 vertical. Panel/grid cards are NOT assembled in Canva — Lovart generates the complete multi-panel composition directly.

## Workflow

```
Input: Story plan document (with card sequence, content, emotions, style types)
                              ↓
Step 1   — EXTRACT: Parse card sequence into structured list
Step 1.5 — ASSESS: Evaluate trimmability, pacing, and reorder opportunities
Step 2   — ANCHOR LINE: Define visual continuity thread (color curve + recurring props + lighting)
Step 3   — TRANSITIONS: Tag each card-to-card transition and apply bridge rules
Step 4   — SHOT PLAN: Assign shot size + angle per card for rhythm
Step 5   — GENERATE: Write Lovart prompts with bridge annotations
Step 6   — VERIFY: Check adjacent pairs for continuity
```

### Step 1: Extract Card Sequence

Parse the story plan into a table:

| # | Style | Content Summary | Emotion | Notes |
|---|-------|----------------|---------|-------|
| ... | ... | ... | ... | ... |

### Step 1.5: Coherence Pre-Assessment

Before defining visual anchors, evaluate the extracted card sequence for trimmability, pacing, and reorder opportunities. This prevents generating prompts for cards that will be cut during production.

**1. Trimmability Rating** — Add a column to the Step 1 table:

| Rating | Meaning | Criteria |
|--------|---------|----------|
| **Essential** | Cannot be removed | Carries unique narrative function (opening, climax, CTA) |
| **Trimmable** | Could be removed if needed | Narrative pattern overlaps with an adjacent card, or serves a pure transition function that neighbors could absorb |
| **Recommend trim** | Should probably be removed | Duplicates an adjacent card's style AND content pattern (e.g., two consecutive panel cards showing similar feedback types) |

**2. Pacing Review** — Check the overall rhythm:

- Are there 3+ consecutive same-style cards? If so, consider inserting a breathing card or trimming one.
- After evidence-dense sections (multiple panel/text cards), is there a digestion space (character card)?
- Would reordering improve momentum? (e.g., moving a group-evidence card earlier to establish breadth before individual evidence)
- After any proposed reorder, **re-derive the color curve** — reordering invalidates the original color interpolation.

**3. Style Switch Frequency** — Check transitions are neither too dense nor too sparse:

- 2+ consecutive cross-style switches (e.g., Character→Panel→Text) need enough bridging space between them
- Long same-style runs (4+ character cards in a row) may lose visual variety — consider if a style switch would improve rhythm

**Output**: Updated Step 1 table with "Trimmability" column + a brief assessment paragraph noting any recommended trims, reorders, or pacing adjustments. Present to user for decision before proceeding to Step 2.

### Step 2: Define the Visual Anchor Line

Three continuity threads that run through ALL cards regardless of style:

**Color Curve** — Plot the entire story's color progression as a continuous gradient. Each card is a point on this curve. When style switches happen, the new card's background color must be derivable from the curve, not an arbitrary default.

**Recurring Props** — Choose 2-3 small props that appear across card types:
- Primary prop (appears in most cards)
- Secondary prop (appears occasionally)
- Micro-detail (subtle)

**Lighting Direction** — Maintain consistent light source direction throughout. If character cards have warm light from the upper-left window, panel cards should show the same directional warmth as edge glow.

### Step 3: Tag Transitions and Apply Bridge Rules

For each adjacent card pair, determine the transition type and apply matching bridge rules.

**Transition Types:**

| Transition | When | Bridge Required |
|-----------|------|----------------|
| Same-style | Character → Character | Light (color + emotion progression) |
| Cross-style entry | Character → Panel/Text | Heavy (color bridge + element traversal + gaze link) |
| Cross-style return | Panel/Text → Character | Heavy (return signal + spatial anchor) |
| Breathing | Any → Text | Medium (color bridge + breathing space) |

**Bridge Rules — Read [references/bridge-rules.md](references/bridge-rules.md) for full examples.**

Core rules summary:

1. **Color Bridge**: Next card's dominant color = transition point on the color curve. Panel/text card backgrounds derive from adjacent character card colors, never from an independent default palette.

2. **Element Traversal**: When switching styles, at least one visual element "crosses over" — props, light, particles, texture, or frame elements.

3. **Gaze Direction**: Character's gaze/body orientation in the current card points toward the next card's visual center of gravity.

4. **Return Signal**: When returning from Panel/Text back to Character, include a spatial anchor proving we're in the same world, plus a progression signal showing time passed.

### Step 4: Shot Size Planning

Vary shot sizes across character-focused cards for emotional rhythm. Do NOT use the same shot size for every card.

| Shot Size | Emotion | Use For |
|-----------|---------|---------|
| Wide/Full | Establishing, calm, context | Opening, breathing moments, scene transitions |
| Medium | Following, narrative | Most story-telling cards, default |
| Close-up | Intensity, intimacy, impact | Emotional peaks, key reactions |
| Detail | Emphasis, symbolic | Props, hands, specific objects |

**Rhythm Rule**: Alternate between at least 2 shot sizes. Never use 3+ consecutive same-size shots.

### Step 5: Generate Lovart Prompts

For each card, generate the prompt following its style-specific template. The templates below are structural guides — adapt the content to match the story.

**Character-focused prompt structure:**
```
[Art style base]. [Character description].
Scene: [Scene description with spatial anchors from Step 2].
[Bridge annotation]: [Color from curve], [recurring prop placement], [lighting direction].

Expression (physical): [REQUIRED. Physically visible markers that Lovart can directly execute:
  eyes (open/closed/half-closed, pupil size, gaze direction),
  mouth (corners up/down, lips parted/pressed, teeth showing),
  eyebrows (raised/furrowed/relaxed),
  cheeks (blush intensity),
  body language (posture, hand position, shoulder tension)]
Expression (mood note): [OPTIONAL. Poetic/atmospheric supplement for intent, not execution.
  e.g., "the quiet of digesting something heavy" — helps convey mood direction
  but Lovart's rendering relies on the physical field above.]

Color palette: [Exact colors from color curve position].
Shot: [Shot size from Step 4], [angle].

Hand-drawn text:
[Text content with position, size, color, emphasis marks]

[Style closing]. [Aspect ratio]
```

> **Expression Writing Guidelines**: Physical descriptions execute far better than poetic ones in Nanobanana. "Eyes wide open, pupils slightly dilated, mouth slightly ajar" produces a consistent shocked expression. "Struck by something she hasn't processed yet" produces unpredictable results. Always lead with physical markers; add mood notes only when the emotional intent isn't obvious from the physical description alone.

**Panel/Grid prompt structure** (Lovart generates entire multi-panel page):
```
Make a [art style] page of manga/comic panels, 3:4 vertical format.
Layout: [Panel arrangement description — e.g., "left large panel (2/3) with right column split into two smaller panels"].
Large panel: [Content description — screenshot placeholder area, or main scene].
Small panel 1: [Character reaction — specific expression and pose].
Small panel 2: [Character reaction — specific expression and pose].
Background color: [Color derived from color curve, NOT arbitrary default].
Panel borders: [Style — e.g., white gutters, rounded corners].
[Bridge annotation]: [Shared elements with adjacent character cards — edge glow, particles, props].
[Style closing]. 3:4 vertical.
```

Lovart's agent (Nanobanana) handles the panel composition internally. Describe the layout in natural language and let the agent interpret it. Include specific panel ratios (e.g., "left 2/3, right 1/3 split top/bottom") for consistency.

**Text-focused prompt structure:**
```
[Layout style]. [Aspect ratio]. Hand-drawn text, [background color from curve].
[Layout description with text zones].
[Bridge annotation]: [Corner decorations matching recurring props], [directional light matching character cards].
[Style closing].
```

### Step 6: Continuity Verification

After generating all prompts, verify each adjacent pair:

- [ ] Color: Can you draw a smooth gradient through all cards' dominant colors?
- [ ] Props: Do recurring props appear in at least 60% of cards?
- [ ] Gaze: Does each card's visual weight flow naturally to the next?
- [ ] Return: After every cross-style excursion, is there a clear "back in the room" signal?
- [ ] Rhythm: Are shot sizes varied (no 3+ consecutive same-size)?
- [ ] Lighting: Is light direction consistent throughout?
- [ ] Narrative: At cross-style transitions and emotional turning points, do adjacent cards' text have semantic connection? (See [bridge-rules.md Rule 5](references/bridge-rules.md) for techniques.)
- [ ] Expression: Are all character card expressions described with physical visible markers (not just poetic descriptions)?

If any check fails, revise the specific prompt with the bridge rule annotation.

## Resources

### references/
- [可可_角色参考.png](references/可可_角色参考.png) — 可可角色设计参考图（生成含可可的图时必须附上）
- [shot-grammar.md](references/shot-grammar.md) — Theory from "Understanding Comics" and "Master Shots" adapted for card stories
- [bridge-rules.md](references/bridge-rules.md) — Detailed bridge rules with before/after prompt examples
