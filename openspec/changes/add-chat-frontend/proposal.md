# Add Chat Frontend Proposal

## What We Are Building

A Next.js 14 (App Router, TypeScript) chat interface that talks to the existing FastAPI backend's `POST /chat` endpoint, styled with Chakra UI in a pastel "unicorn" theme with a star motif. This is Step 6 of the project roadmap (`docs/plan.md`) and supersedes the older, never-implemented plan in `docs/step6.md`.

`frontend/` is currently empty — nothing has been built for this capability yet. This proposal covers the full first implementation, not an iteration on existing code.

---

## Why Now

The backend (intent classification, weather/flight/hotel tools, RAG) has been usable only via raw `POST /chat` calls (curl, tests). There is no way for a person to actually use the travel agent. Step 6 closes that gap.

| Problem | Impact |
|---|---|
| No UI exists | The agent is only reachable via API calls — not demoable, not usable by a non-technical person |
| `docker-compose.yaml` has no frontend service | The "full stack" in `docker-compose up --build` is backend-only |
| Step 7 (CI) and Step 9 (AWS) assume a frontend eventually exists | Roadmap steps reference a frontend build/deploy step that has nothing to build yet |

---

## Scope of This Change

**In scope:**
- `frontend/` — Next.js 14 App Router project, TypeScript
- Chakra UI integration: theme, provider wrapper, themed chat components
- `ChatInterface.tsx` — message list, input, send button, intent label, loading/error states
- `frontend/Dockerfile` + `docker-compose.yaml` frontend service
- `frontend/.env.local.example`
- Pastel "unicorn" visual theme with a star-icon send button and decorative sparkle accents

**Out of scope (explicitly deferred):**
- Favoriting/saving individual assistant responses (a real feature, not styling — deferred, not requested)
- Custom star-shaped loading indicator (deferred — a plain loading state is sufficient for this change)
- Multi-conversation / chat history persistence
- Auth / user accounts
- Dark mode
- Server-side rendering of chat state (fetch is client-side only, matching backend's stateless `/chat` contract)

---

## Technology Choices (summary — see design.md for full rationale)

- **Chakra UI** (not Tailwind, not hand-rolled CSS as originally planned in `docs/step6.md`) — theming system + accessible primitives
- **Pastel palette**, not saturated candy-pop or iridescent — chosen to keep long AI-response text readable
- **Star icon as the send button**, sparkle accents as decoration only — no new interactive features attached to the star motif

---

## Definition of Done

- `npm run dev` starts at `localhost:3000` with the themed chat UI
- Chat sends to `POST /chat` and displays intent + response
- Backend-unreachable case shows the fallback error message
- `docker-compose up --build` starts frontend and backend together, chat works end-to-end
- `frontend/Dockerfile` builds without errors
- `.env.local.example` committed; real `.env.local` is not
