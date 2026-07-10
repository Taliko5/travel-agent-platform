# Add Chat Frontend — Design

## Chakra UI over plain CSS / Tailwind

`docs/step6.md` originally planned `create-next-app --no-tailwind` with hand-rolled CSS. That's fine for a plain interface but painful for a themed, gradient-heavy "pop" style — every component would hand-duplicate color/radius values in `globals.css` with no central theming.

**Decision:** use Chakra UI. Define the palette once as theme tokens (`theme/index.ts`); every component (`Box`, `VStack`, `Input`, `IconButton`) references the tokens. Also gets accessible focus states and keyboard handling for free, which matters for an Enter-to-submit chat input.

**Alternative considered — Tailwind + custom components:** rejected. Tailwind gives utility classes, not a theming object; the pastel palette + rounded "pop" component style would need to be re-specified per component via class strings rather than defined once.

**New dependencies:** `@chakra-ui/react`, `@emotion/react`, `@emotion/styled`, `framer-motion` (Chakra peer deps). Chakra ships no icon set, so an icon package is also needed for the star glyph: `react-icons` (`FaStar`) — chosen over `lucide-react` only because it's the more common Chakra pairing; either would work.

---

## Next.js App Router constraint: provider wrapper

`ChakraProvider` needs client-side React context (Emotion's `CacheProvider`, color mode context). `app/layout.tsx` is a server component by default in the App Router — `ChakraProvider` cannot be used there directly.

**Decision:** add `frontend/src/app/providers.tsx` as a dedicated `"use client"` component:

```tsx
"use client";
import { ChakraProvider } from "@chakra-ui/react";
import theme from "@/theme";

export function Providers({ children }: { children: React.ReactNode }) {
  return <ChakraProvider theme={theme}>{children}</ChakraProvider>;
}
```

`layout.tsx` stays a server component and wraps `{children}` in `<Providers>`.

---

## "Unicorn" color palette — pastel, not saturated or iridescent

Three options were considered for palette intensity:

| Option | Verdict |
|---|---|
| Saturated candy-pop (hot pink, electric purple, vivid cyan) | Rejected — clashes with long blocks of AI-generated response text |
| Iridescent/holographic gradient everywhere | Rejected — too much visual noise for a text-heavy chat surface |
| **Pastel unicorn (soft, low-saturation)** | **Chosen** — playful without fighting readability |

**Decision:** custom Chakra theme color scales (50–900 shades each):
- `unicorn.pink` — blush → berry
- `unicorn.lavender` — pale lilac → violet
- `unicorn.mint` — seafoam → teal

Base surfaces (page background, message bubble backgrounds) stay white/neutral gray. Pastel gradients are used as *accents* — header bar, send button — not as the dominant surface color. This is what keeps a long assistant response readable instead of sitting on a loud background.

---

## Typography

Rounded display font (`Baloo 2` or `Fredoka`, loaded via `next/font/google`) for the header/logo text only — gives the "pop" feel in the one place it doesn't compete with reading. Body and chat message text use a normal readable font (Chakra default stack / system font) — long AI responses should not be set in a novelty typeface.

---

## Border radius

`radii.chatRadius = "2xl"` set as the default radius for chat bubbles, the input field, and the send button. This is the single token responsible for the "poppy" rounded look; changing it in one place re-shapes the whole UI.

---

## Star motif — scope drawn deliberately narrow

Two options were on the table for how far the star motif should reach: purely decorative, or attached to a real feature (favoriting a response, a custom loading spinner). Confirmed with the user to keep it narrow:

- **Functional:** the send button is an `IconButton` using `FaStar`, with a pastel gradient background (`linear-gradient(to-r, pink.300, lavender.300)`), replacing the usual paper-plane/arrow icon.
- **Decorative only:** small `✦` sparkle glyphs placed in the header/background area. Optionally a subtle CSS `@keyframes twinkle` opacity animation. No state, no interactivity.
- **Explicitly not built:** favoriting/saving a response, a star-shaped loading spinner. Both would be genuine new features, not styling — out of scope for this change. If wanted later, they'd be a separate change against the `chat-frontend` capability.

---

## Component granularity: split components, not one file

Two options were on the table: one `ChatInterface.tsx` file owning state, fetch, header decoration, message rendering, and the input control; or splitting along those natural seams into separate small components.

**Decision:** split into five components. The deciding factor isn't reuse (there's only one consumer, `page.tsx`) — it's swap-ability. The proposal already flags likely near-future changes scoped to a single concern (favoriting a response → touches only message rendering; a custom star-shaped loading spinner → touches only the input control). With a single file, either change means editing a file that also holds fetch/state logic, risking unrelated breakage. With the split below, each future change touches exactly one component:

- `ChatInterface.tsx` — orchestrator only: `messages`/`input`/`loading` state, the `POST /chat` fetch + error handling. Composes the four components below and passes state/handlers down as props. No JSX beyond composition.
- `SparkleHeader.tsx` — decorative `✦` accents, optional `twinkle` animation. No state, no props needed beyond static config.
- `MessageList.tsx` — maps `messages[]` → `MessageBubble`. Thin — exists so the list-rendering seam is separate from the bubble's own render logic.
- `MessageBubble.tsx` — single message: role-based bubble styling + conditional intent label. This is the one most likely to change first (favoriting, richer content) — isolating it now means that change won't touch `ChatInterface`'s fetch logic at all.
- `ChatInput.tsx` — `Input` + star `IconButton`, Enter-to-submit, disabled while `loading`. Swappable independently (e.g. a different send-control style or the deferred star loading indicator) without touching message rendering.

**Alternative considered — single file:** rejected. Simpler for a one-time build, but every future change (even a narrowly-scoped one like the deferred favoriting feature) would require editing the same file that owns network/state logic, increasing the chance of an unrelated regression.

## File structure

```
frontend/
├── package.json
├── tsconfig.json
├── next.config.ts
├── Dockerfile
├── .env.local.example
└── src/
    ├── theme/
    │   └── index.ts            ← extendTheme(): unicorn color scales, chatRadius, fonts
    └── app/
        ├── layout.tsx           ← server component, wraps children in <Providers>
        ├── providers.tsx        ← "use client", <ChakraProvider theme={theme}>
        ├── page.tsx              ← renders <ChatInterface />
        ├── globals.css           ← minimal: font-face fallback only, styling lives in theme
        └── components/
            ├── ChatInterface.tsx ← orchestrator: state + POST /chat fetch, composes the four below
            ├── SparkleHeader.tsx ← decorative ✦ accents, optional twinkle animation — no state
            ├── MessageList.tsx   ← maps messages[] → MessageBubble
            ├── MessageBubble.tsx ← single message: role-based style + conditional intent label
            └── ChatInput.tsx     ← Input + star IconButton, Enter-to-submit, disabled while loading
```

---

## Fetch contract (unchanged from original `docs/step6.md` plan)

```ts
// POST ${process.env.NEXT_PUBLIC_API_URL}/chat
// body:    { message: string }
// response: { intent: string, response: string }
// on error: push assistant message "Error: could not reach the backend."
```

Client-side fetch only — the chat call is user-triggered, not server-rendered, so no additional HTTP library or server action is needed.

`NEXT_PUBLIC_API_URL` defaults to `http://localhost:8000` for local dev; docker-compose does not need to override it for browser-side calls (the browser always reaches the backend via `localhost:8000`, not the compose service name).

---

## Docker

Single-stage `node:20-alpine` build (`npm ci` → `npm run build` → `npm start`), matching the original step6.md plan — multi-stage isn't justified at this scale. `docker-compose.yaml` gets a `frontend` service with `depends_on: backend` (soft dependency — the frontend is a static SPA once built, so this only affects startup order, not runtime behavior).
