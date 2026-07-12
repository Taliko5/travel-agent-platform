import { describe, it, expect } from "vitest";
import { renderWithProviders, screen } from "@/test-utils";
import { MessageList } from "./MessageList";
import type { Message } from "./ChatInterface";

describe("MessageList", () => {
  it("renders nothing for an empty message list", () => {
    // ChakraProvider injects a hidden `#__chakra_env` marker span, so the
    // container is never a literal empty DOM element under renderWithProviders
    // — assert on visible text content instead.
    const { container } = renderWithProviders(<MessageList messages={[]} />);
    expect(container).toHaveTextContent("");
  });

  it("renders one bubble per message, in order", () => {
    const messages: Message[] = [
      { role: "user", content: "Where should I go?" },
      { role: "assistant", intent: "chitchat", content: "How about Riga?" },
    ];
    renderWithProviders(<MessageList messages={messages} />);
    expect(screen.getByText("Where should I go?")).toBeInTheDocument();
    expect(screen.getByText("How about Riga?")).toBeInTheDocument();
    expect(screen.getByText("chitchat")).toBeInTheDocument();
  });
});
