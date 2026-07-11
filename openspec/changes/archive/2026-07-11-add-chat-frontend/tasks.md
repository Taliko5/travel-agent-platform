# Add Chat Frontend — Tasks

## Task List

### Project setup

| # | Status | Task | File(s) | Depends On |
|---|---|---|---|---|
| 1.1 | ✓ | Init Next.js 14 TypeScript project (App Router, no Tailwind — Chakra handles styling) | `frontend/` | — |
| 1.2 | ✓ | Install Chakra UI + peer deps + icon package | `frontend/package.json` | 1.1 |
| 1.3 | ✓ | Create unicorn theme (color scales, radii, fonts) | `frontend/src/theme/index.ts` | 1.2 |
| 1.4 | ✓ | Create client provider wrapper | `frontend/src/app/providers.tsx` | 1.3 |
| 1.5 | ✓ | Wire provider into layout | `frontend/src/app/layout.tsx` | 1.4 |

### Chat UI

| # | Status | Task | File(s) | Depends On |
|---|---|---|---|---|
| 2.1 | ✓ | Build `ChatInterface` orchestrator: `messages`/`input`/`loading` state, `POST /chat` fetch + error handling | `frontend/src/app/components/ChatInterface.tsx` | 1.5 |
| 2.2 | ✓ | Build `MessageBubble`: single message render, role-based styling, conditional intent label | `frontend/src/app/components/MessageBubble.tsx` | 1.5 |
| 2.3 | ✓ | Build `MessageList`: maps `messages[]` → `MessageBubble` | `frontend/src/app/components/MessageList.tsx` | 2.2 |
| 2.4 | ✓ | Build `ChatInput`: `Input` + star `IconButton` send control, Enter-to-submit, disabled while loading | `frontend/src/app/components/ChatInput.tsx` | 1.5 |
| 2.5 | ✓ | Build `SparkleHeader`: decorative sparkle accents, optional twinkle animation | `frontend/src/app/components/SparkleHeader.tsx` | 1.5 |
| 2.6 | ✓ | Compose `ChatInterface`: wire `SparkleHeader` + `MessageList` + `ChatInput` together, pass state/handlers as props | `frontend/src/app/components/ChatInterface.tsx` | 2.1, 2.3, 2.4, 2.5 |
| 2.7 | ✓ | Render `ChatInterface` from the page | `frontend/src/app/page.tsx` | 2.6 |
| 2.8 | ✓ | Create env example, verify local dev run | `frontend/.env.local.example` | 2.7 |

### Containerization

| # | Status | Task | File(s) | Depends On |
|---|---|---|---|---|
| 3.1 | ✓ | Create `frontend/Dockerfile` | `frontend/Dockerfile` | 2.8 |
| 3.2 | ✓ | Add `frontend` service to `docker-compose.yaml` | `docker-compose.yaml` | 3.1 |
| 3.3 | ✓ | Smoke test: `docker-compose up --build`, chat works at `localhost:3000` | — | 3.2 |

### Wrap-up

| # | Status | Task | File(s) | Depends On |
|---|---|---|---|---|
| 4.1 | ✓ | Update `docs/plan.md` Step 6 to Done | `docs/plan.md` | 3.3 |
| 4.2 | | Archive `add-chat-frontend` change, sync spec into `openspec/specs/chat-frontend/` | — | 4.1 |

---

## Task Detail

### 1.1 — Init Next.js project

```bash
npx create-next-app@14 frontend --typescript --app --no-tailwind --no-eslint
```
(`--no-tailwind` is intentional — Chakra UI is the styling system for this change, not Tailwind.)

### 1.2 — Install Chakra UI + deps

```bash
cd frontend
npm install @chakra-ui/react @emotion/react @emotion/styled framer-motion react-icons
```

### 1.3 — Unicorn theme

`frontend/src/theme/index.ts` — `extendTheme({ colors: { unicorn: { pink: {...}, lavender: {...}, mint: {...} } }, radii: { chatRadius: "2xl" }, fonts: { heading: "'Baloo 2', sans-serif" } })`. See design.md for the full rationale on palette intensity and font pairing.

### 1.4 / 1.5 — Provider wrapper

See design.md "Next.js App Router constraint" for why this file exists and its exact shape.

### 2.1 — ChatInterface (orchestrator)

State shape (unchanged from original plan):
```ts
interface Message {
  role: "user" | "assistant";
  intent?: string;
  content: string;
}
// useState: messages: Message[], input: string, loading: boolean
```

Owns `handleSubmit` (POST `/chat`, error handling) only. No message-rendering or input JSX lives here — see 2.2–2.5. On fetch failure, push `{ role: "assistant", content: "Error: could not reach the backend." }`.

### 2.2 — MessageBubble

Props: `{ role: "user" | "assistant"; intent?: string; content: string }`. Role-based bubble styling (`chatRadius` token, background color). Shows `[intent]` label above the message only when `role === "assistant" && intent` is present.

### 2.3 — MessageList

Props: `{ messages: Message[] }`. Thin — maps and renders `MessageBubble` per message. No local state.

### 2.4 — ChatInput

Props: `{ value: string; onChange, onSubmit; disabled: boolean }`. Submit on Enter key or the star `IconButton`. `disabled` (driven by `ChatInterface`'s `loading` state) disables both the input and the send button.

### 2.5 — SparkleHeader

Small `✦` glyphs, absolutely positioned, optional subtle `@keyframes twinkle` opacity animation via Chakra's `sx` prop or a `framer-motion` `motion.div`. No props, no component state — purely visual, safe to swap or remove independently.

### 2.6 — Compose ChatInterface

Wire `SparkleHeader`, `MessageList`, and `ChatInput` together inside `ChatInterface`, passing `messages`, `input`/`onChange`, `handleSubmit`, and `loading` down as props.

### 3.1 — Dockerfile

```dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npm", "start"]
```

### 3.2 — docker-compose frontend service

```yaml
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
    depends_on:
      - backend
```
