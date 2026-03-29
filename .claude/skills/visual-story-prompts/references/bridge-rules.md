# Bridge Rules

Rules for fixing visual discontinuity at style-switching points.

## Rule 1: Color Bridge

### Problem

Panel and text cards default to a fixed background color regardless of where they sit in the story's color progression.

### Rule

Every card's dominant background color is a point on the story's color curve. Panel/text card backgrounds are interpolated from their neighboring character cards. Plot the color curve for all cards before writing any prompts — panel/text cards derive their color by interpolating between their adjacent character cards.

## Rule 2: Element Traversal

### Problem

When style switches, no visual element carries over, making the cards feel like separate projects.

### Rule

At least one visual element "crosses" the style boundary. The element should be narratively motivated (not random decoration).

### Traversal Types

| Element | How It Crosses |
|---------|---------------|
| **Prop** | Object appears in both styles |
| **Light** | Same directional warmth |
| **Particle** | Floating decorative elements carry over |
| **Texture** | Surface quality carries over |
| **Frame element** | Decorative framing consistent |

## Rule 3: Gaze Direction

### Problem

Character's gaze direction in one card has no relationship to the next card's content placement, breaking visual flow.

### Rule

Character's gaze/body orientation → next card's visual weight position. This creates a "look, then see" rhythm.

### Gaze-to-Layout Mapping

| Character Gaze | Next Card Layout |
|---------------|-----------------|
| Looking down at hands/phone | Next card's main content in center or upper area |
| Looking right/off to side | Next card's main content on the right side |
| Looking left | Next card's main content on the left side |
| Facing reader directly | Next card's content centered symmetrically |
| Looking up/toward window | Next card has open/airy composition with top emphasis |

## Rule 4: Return Signal

### Problem

After a panel or text card, reader loses sense of "where we are" when returning to character card.

### Rule

First character card after a cross-style excursion must include a spatial anchor proving we're in the same world, plus a subtle progression signal showing time passed.

### Return Signal Components

| Component | Purpose | How |
|-----------|---------|-----|
| **Spatial anchor** | "We're back" | Same room, same window, same furniture piece. Not a new location. |
| **Progression** | "Time moved" | Light changed slightly, posture different, small environmental detail shifted |
| **Emotional bridge** | "The feeling continues" | Expression shows effect of what was just shown in the panel card |

## Rule 5: Narrative Thread

### Problem

Adjacent cards' on-image text has no semantic connection. When the reader swipes from one card to the next, the text feels like isolated captions rather than a continuous narrative.

### Rule

At **cross-style transitions** and **emotional turning points**, the text on adjacent cards should have a semantic connection — the reader should feel the two cards are "in dialogue." The specific connection technique is flexible; choose what fits the narrative naturally.

### Available Techniques (non-exhaustive)

| Technique | How It Works |
|-----------|-------------|
| **Keyword passing** | A core word from Card N reappears (as variant or echo) in Card N+1 |
| **Emotional echo** | Card N's emotional state is received or advanced by Card N+1's text |
| **Question-answer** | Card N poses an implicit question; Card N+1 responds |
| **Perspective shift** | Same theme pivots from "I" to "you" |
| **Gap-and-fill** | Card N deliberately leaves something incomplete; Card N+1 completes it |
| **...** | New techniques can be added as they emerge in production |

### Usage Principles

- **Not every pair needs a thread.** Apply at cross-style transitions and emotional turning points. Same-style sequential cards with smooth emotional progression may not need explicit text threading.
- **Mix techniques.** A single story can use keyword passing at one transition, perspective shift at another, and emotional echo at a third. Variety keeps the connections from feeling formulaic.
- **Natural over forced.** If a thread feels contrived, drop it. A natural-flowing story beats a perfectly threaded one.

---

## Rhythm Templates

### Standard Emotional Arc (10-14 cards)

```
Opening:    Character × 2-3  (establish world)
Build-up:   Character → Panel → Character  (evidence + reaction cycle)
Peak:       Character × 2  (uninterrupted emotional climax)
Breathing:  Text × 1  (reader digests)
Resolution: Character × 2-3  (invitation + close)
```

### Quick Punch (6-8 cards)

```
Hook:       Character × 1  (strong opening)
Evidence:   Panel → Character  (one evidence-reaction pair)
Turn:       Text × 1  (pivot)
Close:      Character × 2  (invitation + CTA)
```

### Evidence-Heavy (12-16 cards)

```
Opening:    Character × 2  (establish)
Cycle 1:    Character → Panel → Character  (first evidence)
Cycle 2:    Panel → Character  (second evidence, skip re-entry setup)
Cycle 3:    Panel  (third evidence, rapid fire)
Breathing:  Character × 1 or Text × 1  (digest)
Close:      Character × 2-3  (resolution)
```

## Diagnostic Checklist

When reviewing generated prompts, check each transition point:

| Check | Pass | Fail → Fix |
|-------|------|-----------|
| Color smooth between adjacent cards? | Gradient is drawable | Adjust panel/text bg to interpolate from neighbors |
| Element crosses style boundary? | At least 1 shared element | Add prop/light/particle to panel/text prompt |
| Gaze flows to next card? | Visual weight follows look direction | Adjust gaze or next card's layout |
| Return card feels "same world"? | Spatial anchor present | Add room/furniture/window reference |
| Shot sizes vary? | No 3+ same-size consecutive | Change at least one to different size |
| Light direction consistent? | Same side throughout | Fix prompt to match global light source |
| Adjacent text semantically connected at transitions? | Cross-style and emotional turning points have narrative thread | Apply Rule 5 technique (keyword passing, emotional echo, etc.) |
| Expressions use physical markers? | Eyes, mouth, brows, posture described concretely | Replace poetic descriptions with visible physical details |
