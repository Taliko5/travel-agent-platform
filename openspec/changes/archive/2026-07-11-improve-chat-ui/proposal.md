# Improve Chat UI Proposal

## What We Are Building

Three visual/UX improvements to the chat interface shipped in `add-chat-frontend`:

1. **Markdown rendering** — Gemini responses come back as markdown (`# headline`, `**bold**`, lists, etc.), but `MessageBubble` currently renders `content` as a flat `<Text whiteSpace="pre-wrap">`, so markup characters show up literally instead of being formatted.
2. **"...thinking" loading indicator** — a three-dot bounce animation with the text `...thinking`, shown in the message list while waiting for the backend response. Today the only loading feedback is the input field being disabled — no bubble appears until the real response lands.
3. **Chatbox outline + unicorn gradient page background** — the chat panel currently has no visible boundary from the page (both are flat white), so it doesn't read as a distinct surface. Add a visible outline/card treatment to the chat panel, and move the pastel unicorn gradient to the page background *outside* the chatbox.

## Why Now

| Problem | Impact |
|---|---|
| Markdown renders as literal text | `**bold**`, `# Headline`, and list markers show up as raw characters in every assistant response — reads as broken, not styled |
| No in-flight feedback in the message list | Users only see the input disable; on a slow LLM call there's no visible sign anything is happening in the conversation itself |
| Chat panel has no visible boundary | The pastel "unicorn" theme (`add-chat-frontend`) never actually reached the page — background and chatbox are both plain white, so the intended pastel visual identity isn't visible anywhere users look |

## Scope of This Change

**In scope:**
- `MessageBubble.tsx` — render `content` through a markdown renderer (headings, bold/italic, lists, inline code) instead of plain text, for assistant messages
- New `ThinkingIndicator.tsx` — three-dot bounce animation + `...thinking` text, shown in the message list while `loading` is true
- `ChatInterface.tsx` — outer chat panel gets a visible outline (border + rounded corner + subtle shadow), consistent with the existing `chatRadius` token
- Page/body background — apply the unicorn pastel gradient (pink → lavender → mint) at the page level, outside the chat panel
- New dependency: a markdown-rendering library (see design.md for choice)

**Out of scope (explicitly deferred):**
- Markdown for user-typed messages (users don't type markdown; only assistant responses need rendering)
- Syntax-highlighted code blocks (plain inline/`pre` code styling is enough for travel-agent responses — no code-heavy use case here)
- Customizing the three-dot animation's timing/easing beyond a simple bounce (no design requirement for anything fancier)
- Changing the send-button star motif or intent-label behavior (untouched, already shipped)

## Technology Choices (summary — see design.md for full rationale)

- **`react-markdown` + `remark-gfm`** for markdown rendering, with a custom Chakra-mapped `components` prop (not `chakra-ui-markdown-renderer`, which is unmaintained)
- **CSS `@keyframes` bounce** (via Chakra's `sx`/`animation` prop, same pattern as `SparkleHeader`'s existing `twinkle` keyframe) for the three-dot loader — no new animation library needed
- **Gradient moves from decorative-accent-only to page background** — a deliberate, narrow exception to the existing "pastel as accent, not background" rule from `add-chat-frontend`, scoped specifically to the area *outside* the chat panel (message bubbles stay white/neutral inside)

## Definition of Done

- An assistant response containing `# `, `**bold**`, and a bulleted list renders with real headings/bold/list formatting, not literal markdown characters
- While waiting for a response, a bubble showing a three-dot bounce animation and the text `...thinking` appears in the message list, and disappears once the real response (or error) arrives
- The chat panel has a visible outline/border distinguishing it from the page background
- The page background (outside the chat panel) shows the unicorn pastel gradient; message bubbles remain white/neutral and readable
