## ADDED Requirements

### Requirement: Markdown Response Rendering
The system SHALL render assistant message content as formatted markdown (headings, bold/italic text, ordered and unordered lists, inline code) instead of plain text. User-typed messages SHALL continue to render as plain text.

#### Scenario: Assistant response contains markdown formatting
- **WHEN** an assistant response contains markdown syntax (e.g. `# Heading`, `**bold**`, `- list item`)
- **THEN** the message SHALL render with real headings, bold/italic styling, and list formatting — not literal markdown characters

#### Scenario: User message is not treated as markdown
- **WHEN** a user-typed message contains characters that look like markdown syntax (e.g. `*` or `#`)
- **THEN** the message SHALL render as plain text, unchanged

### Requirement: Assistant Thinking Indicator
The system SHALL display a loading indicator in the message list while waiting for a response from the backend, distinct from the existing input-disable behavior.

#### Scenario: Request in flight
- **WHEN** a request to `/chat` is in flight
- **THEN** a bubble showing a three-dot bounce animation and the text "...thinking" SHALL appear in the message list, in the position the next assistant message will occupy

#### Scenario: Response or error arrives
- **WHEN** the `/chat` response (or an error) is received
- **THEN** the thinking indicator SHALL be removed and replaced by the real assistant message (or the error fallback message)

## MODIFIED Requirements

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
