# chat-frontend

## Purpose

Browser-based chat UI (Next.js 14 App Router, TypeScript) that lets a user converse with the travel agent backend's `POST /chat` endpoint, displaying the classified intent and assistant response.

## Requirements

### Requirement: Chat Message Exchange
The system SHALL provide a browser-based chat interface that sends the user's message to the backend `/chat` endpoint and displays the returned response.

#### Scenario: User submits a message
- **WHEN** the user types a message and presses Enter or clicks the send button
- **THEN** the system SHALL POST `{ message: string }` to `${NEXT_PUBLIC_API_URL}/chat`
- **AND** display the returned `response` as a new assistant message in the conversation

#### Scenario: Input disabled while waiting for a response
- **WHEN** a request to `/chat` is in flight
- **THEN** the message input SHALL be disabled until the response (or error) is received

### Requirement: Assistant Thinking Indicator
The system SHALL display a loading indicator in the message list while waiting for a response from the backend, distinct from the existing input-disable behavior.

#### Scenario: Request in flight
- **WHEN** a request to `/chat` is in flight
- **THEN** a bubble showing a three-dot bounce animation and the text "...thinking" SHALL appear in the message list, in the position the next assistant message will occupy

#### Scenario: Response or error arrives
- **WHEN** the `/chat` response (or an error) is received
- **THEN** the thinking indicator SHALL be removed and replaced by the real assistant message (or the error fallback message)

### Requirement: Backend Unreachable Fallback
The system SHALL display a fallback message when the backend cannot be reached, instead of failing silently.

#### Scenario: Fetch to /chat fails
- **WHEN** the fetch request to `/chat` throws or rejects
- **THEN** the system SHALL append an assistant message with the exact content "Error: could not reach the backend."

### Requirement: Intent Label Display
The system SHALL surface the classified intent alongside each assistant response.

#### Scenario: Assistant message includes intent
- **WHEN** a `/chat` response is received containing an `intent` field
- **THEN** the system SHALL display the intent as a label above the corresponding assistant message

### Requirement: Markdown Response Rendering
The system SHALL render assistant message content as formatted markdown (headings, bold/italic text, ordered and unordered lists, inline code) instead of plain text. User-typed messages SHALL continue to render as plain text.

#### Scenario: Assistant response contains markdown formatting
- **WHEN** an assistant response contains markdown syntax (e.g. `# Heading`, `**bold**`, `- list item`)
- **THEN** the message SHALL render with real headings, bold/italic styling, and list formatting — not literal markdown characters

#### Scenario: User message is not treated as markdown
- **WHEN** a user-typed message contains characters that look like markdown syntax (e.g. `*` or `#`)
- **THEN** the message SHALL render as plain text, unchanged

### Requirement: Unicorn Pop Visual Theme
The system SHALL present the chat interface using a pastel "unicorn" color theme with rounded, poppy component styling, implemented via a Chakra UI theme. The pastel gradient SHALL be visible on the page background outside the chat panel; the chat panel interior and message bubbles SHALL remain white/neutral for readability.

#### Scenario: Palette stays readable for long responses
- **WHEN** an assistant message contains a long block of generated text
- **THEN** the message SHALL render on a neutral/white background, with pastel colors (pink, lavender, mint) used only as accents (header, buttons) or as the page background outside the chat panel — not as the message bubble background

#### Scenario: Rounded component styling
- **WHEN** chat bubbles, the input field, or the send button are rendered
- **THEN** they SHALL use the theme's rounded corner token (`2xl`), consistent across all three

#### Scenario: Page background shows the pastel gradient
- **WHEN** the chat page is rendered
- **THEN** the page background (outside the chat panel) SHALL display the unicorn pastel gradient (pink → lavender → mint)

#### Scenario: Chat panel is visually distinct from the page
- **WHEN** the chat page is rendered
- **THEN** the chat panel SHALL have a visible outline (border and rounded corner) distinguishing it from the gradient page background behind it

### Requirement: Star-Icon Send Action
The system SHALL use a star icon as the visual affordance for sending a message, styled with the theme's pastel gradient. This is the only functional use of the star motif in this change — no favoriting or star-based loading indicator is included.

#### Scenario: Send button rendering
- **WHEN** the chat input is rendered
- **THEN** the send control SHALL be an icon button showing a star glyph with a pastel gradient background

### Requirement: Containerized Frontend Delivery
The system SHALL be packaged as a Docker image and included as a service in the project's docker-compose stack, startable alongside the backend.

#### Scenario: Full stack startup
- **WHEN** `docker-compose up --build` is run
- **THEN** both the `backend` and `frontend` services SHALL start
- **AND** the chat UI at `localhost:3000` SHALL successfully exchange messages with the backend
