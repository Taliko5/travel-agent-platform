# Step 6: Frontend (Next.js 14 / TypeScript)

## Goal

Build a chat UI that connects to the FastAPI backend. Users type a travel question, see the classified intent and AI-generated response.

## Decisions

**Next.js 14 App Router** — current default; no reason to use Pages Router for a new project.

**Client-side fetch** — the chat call is user-triggered, not server-rendered. `fetch` to `NEXT_PUBLIC_API_URL/chat` from the browser. No additional HTTP library needed.

**`NEXT_PUBLIC_API_URL` env var** — defaults to `http://localhost:8000` for local dev. docker-compose sets it to `http://backend:8000` for server-side calls (not applicable here since fetch is client-side — browser always uses `localhost:8000`).

**Node 20 Alpine in Dockerfile** — smallest viable image for Next.js. Multi-stage not needed yet; build + serve in one stage is fine at this scale.

**`depends_on: backend`** in docker-compose — ensures backend starts before frontend, though frontend is a static SPA once built so the dependency is soft.

## File Structure

```
frontend/
├── package.json
├── tsconfig.json
├── next.config.ts
├── Dockerfile
├── .env.local.example
└── src/
    └── app/
        ├── layout.tsx
        ├── page.tsx
        ├── globals.css
        └── components/
            └── ChatInterface.tsx
```

## Specs

### `frontend/Dockerfile`

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

### `frontend/.env.local.example`

```
# Copy to .env.local for local development
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### `docker-compose.yaml` — add frontend service

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

### `ChatInterface.tsx`

State shape:
```ts
interface Message {
  role: "user" | "assistant";
  intent?: string;   // from API response, shown as a label on assistant messages
  content: string;
}

// useState: messages: Message[], input: string, loading: boolean
```

Fetch contract:
```ts
// POST ${process.env.NEXT_PUBLIC_API_URL}/chat
// body:    { message: string }
// response: { intent: string, response: string }
// on error: push assistant message "Error: could not reach the backend."
```

Behaviour:
- Submit on Enter key or Send button
- Disable input while loading
- Show `[intent]` label above each assistant message

## Tasks

- [ ] 6.1 Init Next.js 14 TypeScript project: `npx create-next-app@14 frontend --typescript --app --no-tailwind --no-eslint`
- [ ] 6.2 Create `src/app/components/ChatInterface.tsx`
- [ ] 6.3 Update `src/app/page.tsx` to render `ChatInterface`
- [ ] 6.4 Create `frontend/.env.local.example`
- [ ] 6.5 Copy `.env.local.example` to `.env.local`, set `NEXT_PUBLIC_API_URL=http://localhost:8000`
- [ ] 6.6 Test locally: `npm run dev` at `localhost:3000`, chat with backend running
- [ ] 6.7 Create `frontend/Dockerfile`
- [ ] 6.8 Add frontend service to `docker-compose.yaml`
- [ ] 6.9 Test: `docker-compose up --build`, both services start, chat works at `localhost:3000`
- [ ] 6.10 Update `docs/plan.md` Step 6 to Done

## Definition of Done

- [ ] `npm run dev` starts at `localhost:3000`
- [ ] Chat sends to `POST /chat` and displays intent + response
- [ ] `docker-compose up --build` starts frontend and backend
- [ ] Chat works end-to-end through docker-compose
- [ ] `frontend/Dockerfile` builds without errors
- [ ] `.env.local.example` committed; real `.env.local` is not
