import { describe, it, expect } from "vitest";
import { renderWithProviders, screen } from "@/test-utils";
import { MessageBubble } from "./MessageBubble";

describe("MessageBubble", () => {
  it("renders a user message as plain text", () => {
    renderWithProviders(<MessageBubble role="user" content="Where is Fukuoka?" />);
    expect(screen.getByText("Where is Fukuoka?")).toBeInTheDocument();
  });

  it("renders assistant markdown bold text as a real element, not literal asterisks", () => {
    renderWithProviders(<MessageBubble role="assistant" content="**bold** text" />);
    const strong = screen.getByText("bold");
    expect(strong.tagName).toBe("STRONG");
    expect(screen.queryByText(/\*\*bold\*\*/)).not.toBeInTheDocument();
  });

  it("renders assistant markdown headings as heading elements", () => {
    renderWithProviders(<MessageBubble role="assistant" content="# Riga" />);
    expect(screen.getByRole("heading", { name: "Riga" })).toBeInTheDocument();
  });

  it("renders assistant markdown lists as list elements", () => {
    renderWithProviders(<MessageBubble role="assistant" content={"- Lima\n- Abu Dhabi"} />);
    expect(screen.getByRole("list")).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });

  it("shows the intent label for an assistant message with an intent", () => {
    renderWithProviders(<MessageBubble role="assistant" intent="weather" content="Sunny today" />);
    expect(screen.getByText("weather")).toBeInTheDocument();
  });

  it("does not show an intent label for a user message", () => {
    renderWithProviders(
      <MessageBubble role="user" intent="weather" content="How's the weather?" />,
    );
    expect(screen.queryByText("weather")).not.toBeInTheDocument();
  });

  it("does not show an intent label when intent is absent", () => {
    renderWithProviders(<MessageBubble role="assistant" content="Hello there" />);
    expect(screen.queryByText(/^(weather|hotel|flight)$/)).not.toBeInTheDocument();
  });
});
