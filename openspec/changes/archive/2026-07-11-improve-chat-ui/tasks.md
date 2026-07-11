# Improve Chat UI — Tasks

## 1. Markdown rendering

- [x] 1.1 Install `react-markdown` + `remark-gfm` (`frontend/package.json`)
- [x] 1.2 Build Chakra-mapped `components` map — h1–h3, p, strong, em, ul/ol/li, code (`frontend/src/app/components/MessageBubble.tsx`)
- [x] 1.3 Wire `ReactMarkdown` into `MessageBubble` for `role === "assistant"` only; user messages stay plain text (`frontend/src/app/components/MessageBubble.tsx`)
- [x] 1.4 Manual check: send a query that returns headings/bold/lists, confirm real formatting (not literal `#`/`**`)

## 2. Thinking indicator

- [x] 2.1 Build `ThinkingIndicator`: three dots with staggered bounce `@keyframes`, `...thinking` text (`frontend/src/app/components/ThinkingIndicator.tsx`)
- [x] 2.2 Render `<ThinkingIndicator />` in `ChatInterface` after `MessageList` when `loading` is true (`frontend/src/app/components/ChatInterface.tsx`)
- [x] 2.3 Manual check: indicator appears on submit, disappears once the response (or error) lands

## 3. Chatbox outline + gradient background

- [x] 3.1 Add unicorn pastel gradient to `body` background (`frontend/src/app/globals.css`)
- [x] 3.2 Add border/shadow/`chatRadius` outline to `ChatInterface`'s outer `Box` (`frontend/src/app/components/ChatInterface.tsx`)
- [x] 3.3 Manual check: chat panel reads as a distinct white card on the gradient page; message bubbles still readable

## 4. Wrap-up

- [x] 4.1 `npm run build` / `tsc --noEmit` clean
- [x] 4.2 Note UI polish under Step 6 in `docs/plan.md` (no new roadmap step — this layers on the already-Done step)
- [ ] 4.3 Archive `improve-chat-ui`, sync spec into `openspec/specs/chat-frontend/`

---

## Task Detail

### 1.2 — Chakra-mapped markdown components

See `design.md` "Markdown rendering" for the exact `components` map. Keep it in `MessageBubble.tsx` (or a co-located `mdComponents.ts` if it grows) — no need for a shared/exported util unless a second consumer appears.

### 1.3 — MessageBubble wiring

```tsx
{isUser ? (
  <Text whiteSpace="pre-wrap">{content}</Text>
) : (
  <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
    {content}
  </ReactMarkdown>
)}
```

### 2.1 — ThinkingIndicator

Three `Box` dots (`Box w={2} h={2} borderRadius="full" bg="unicorn.lavender.300"`), each with `animation` delay staggered by ~0.15s via the `sx` prop, same `keyframes` import pattern as `SparkleHeader.tsx`. Bubble wrapper matches the assistant `MessageBubble` styling (white bg, `chatRadius`, left-aligned) so it visually sits in the same slot as an incoming assistant message.

### 3.1 — Page gradient

```css
body {
  background: linear-gradient(135deg, var(--chakra-colors-unicorn-pink-50), var(--chakra-colors-unicorn-lavender-50), var(--chakra-colors-unicorn-mint-50));
  min-height: 100vh;
}
```

Uses Chakra's generated CSS variables for the existing `unicorn.*` scales — no new colors. If Chakra's CSS-variable emission for these tokens is unavailable in `globals.css`'s plain-CSS context, fall back to the same hex values already defined in `theme/index.ts` (`pink.50 #fff5f8`, `lavender.50 #f7f4ff`, `mint.50 #f2fffb`).

### 3.2 — Chatbox outline

```tsx
<Box
  maxW="2xl" mx="auto" h="100vh" display="flex" flexDirection="column"
  bg="white"
  borderWidth="1px"
  borderColor="unicorn.lavender.100"
  borderRadius="chatRadius"
  boxShadow="md"
  my={{ base: 0, md: 6 }}
>
```

`my={{ base: 0, md: 6 }}` gives the card breathing room from the viewport edge on larger screens so the gradient is actually visible around it, while staying edge-to-edge on mobile.
