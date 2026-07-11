# Improve Chat UI — Design

## Markdown rendering: `react-markdown` + `remark-gfm`

**Decision:** add `react-markdown` (v9) and `remark-gfm` as dependencies. Render `MessageBubble`'s `content` through `<ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>`, where `mdComponents` maps markdown elements to Chakra primitives so headings/bold/lists pick up the existing theme (font, color, `chatRadius` where relevant) instead of browser-default styling:

```tsx
const mdComponents = {
  h1: (props) => <Heading as="h3" size="md" mt={2} mb={1} {...props} />,
  h2: (props) => <Heading as="h4" size="sm" mt={2} mb={1} {...props} />,
  h3: (props) => <Heading as="h5" size="xs" mt={2} mb={1} {...props} />,
  p: (props) => <Text mb={2} {...props} />,
  strong: (props) => <Text as="strong" fontWeight="bold" {...props} />,
  em: (props) => <Text as="em" fontStyle="italic" {...props} />,
  ul: (props) => <UnorderedList mb={2} {...props} />,
  ol: (props) => <OrderedList mb={2} {...props} />,
  li: (props) => <ListItem {...props} />,
  code: (props) => <Code {...props} />,
};
```

**Alternative considered — `chakra-ui-markdown-renderer`:** rejected. It wraps `react-markdown` with a similar `components` map, but the package has had no release in several years and pins an old `react-markdown` major; hand-rolling the (small) `components` map keeps us on current `react-markdown` without an unmaintained middle dependency.

**Alternative considered — `dangerouslySetInnerHTML` with a markdown-to-HTML string (e.g. `marked`):** rejected. Requires manual sanitization (XSS risk) since the content is model-generated text rendered directly into the DOM; `react-markdown` parses to a React element tree and never touches `innerHTML`, so there's no sanitization step to get wrong.

**Scope of markdown support:** headings (h1–h3), bold/italic, ordered/unordered lists, inline code and code blocks (via `remark-gfm` — also picks up tables/strikethrough if a response ever includes them, at no extra cost). No syntax highlighting — out of scope per proposal.md, and travel-agent responses aren't code-heavy.

**Applies to assistant messages only.** `MessageBubble` already receives `role` as a prop; the markdown renderer wraps `content` only when `role === "assistant"`. User-typed messages continue rendering as plain text — users don't type markdown, and escaping their literal `*`/`#` characters as user input would be surprising.

## Loading indicator: new `ThinkingIndicator` component, not a state field on `ChatInterface`

**Decision:** add `ThinkingIndicator.tsx` — a self-contained component with no props, showing three small dots with a staggered CSS bounce (`@keyframes bounce`, same pattern `SparkleHeader.tsx` already uses for `twinkle`) plus the text `...thinking`. `ChatInterface` renders it conditionally after `MessageList` when `loading` is true:

```tsx
<MessageList messages={messages} />
{loading && <ThinkingIndicator />}
```

This keeps the one-component-per-concern split from `add-chat-frontend`'s design intact — the loading visual is swappable independently, and `MessageList`/`MessageBubble` don't need to know about a "pending" message that isn't really part of `messages[]`.

**Alternative considered — push a placeholder message into `messages[]` and remove it on response:** rejected. Would require `MessageBubble` to handle a "pending" variant (or a new prop), coupling the loading UI to the message-rendering component the proposal explicitly wants to keep swappable. Rendering `ThinkingIndicator` as a sibling after the list, driven directly by the existing `loading` state `ChatInterface` already owns, needs no new state and no changes to `Message`/`MessageBubble`.

**Bubble styling:** matches the assistant bubble style (white background, `chatRadius`, left-aligned) so it reads as "the assistant's turn is in progress" in the same visual slot a real assistant bubble would occupy next.

## Chatbox outline + page-level gradient background

Two things were previously flat white with no visual separation: the page `body` background and the chat panel itself. Two options were on the table for where the pastel gradient should live now that it needs to become visible somewhere:

| Option | Verdict |
|---|---|
| Keep gradient accent-only (buttons/header), add a plain gray/border outline to the chat panel | Rejected — doesn't address "the pastel theme isn't visible on the page" |
| Move gradient to page background, add visible outline to the chat panel, keep bubbles/panel interior white | **Chosen** |

**Decision:**
- `globals.css` (or the theme's `styles.global`): `body` background becomes `linear-gradient(135deg, unicorn.pink.50, unicorn.lavender.50, unicorn.mint.50)` (soft, low-saturation — same three color scales already defined in `theme/index.ts`, just applied at a different layer, not new colors).
- `ChatInterface.tsx`'s outer `Box` gets `bg="white"`, `borderWidth="1px"`, `borderColor="unicorn.lavender.100"`, `borderRadius="chatRadius"`, and a subtle `boxShadow` — so it reads as a card floating on the gradient page.

This is a narrow, deliberate exception to `add-chat-frontend`'s "pastel is accent-only, not background" rule — but that rule was scoped to *message bubble backgrounds* specifically (to keep long AI text readable), not the page chrome outside the chat panel. Message bubbles and the chat panel interior stay white/neutral; only the area outside the card changes. Existing spec scenario "Palette stays readable for long responses" is unaffected — see `specs/chat-frontend/spec.md` for the exact wording being modified.

## File structure (changed/added files)

```
frontend/src/
├── theme/index.ts                     ← body gradient added to styles.global (or globals.css, see below)
└── app/
    ├── globals.css                    ← alternative location for the body gradient if simpler than theme styles.global
    └── components/
        ├── MessageBubble.tsx          ← renders content via ReactMarkdown (assistant only) instead of <Text>
        ├── ThinkingIndicator.tsx      ← NEW: three-dot bounce + "...thinking"
        └── ChatInterface.tsx          ← outer Box gets border/shadow; renders <ThinkingIndicator /> when loading
```

## New dependencies

```bash
npm install react-markdown remark-gfm
```

Both are pure ESM, which Next.js 14's bundler supports natively — no transpile config changes needed.
