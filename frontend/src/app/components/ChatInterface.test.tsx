import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import userEvent from "@testing-library/user-event";
import { renderWithProviders, screen, waitFor } from "@/test-utils";
import { ChatInterface } from "./ChatInterface";

type FetchMock = ReturnType<typeof vi.fn>;

describe("ChatInterface", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends a POST request to /chat with the typed message and renders the response", async () => {
    const user = userEvent.setup();
    (fetch as FetchMock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ intent: "weather", response: "It's sunny in Tokyo." }),
    });

    renderWithProviders(<ChatInterface />);
    await user.type(
      screen.getByPlaceholderText(/ask about flights/i),
      "What's the weather in Tokyo?{Enter}",
    );

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/chat"),
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: "What's the weather in Tokyo?" }),
      }),
    );

    expect(await screen.findByText("It's sunny in Tokyo.")).toBeInTheDocument();
    expect(screen.getByText("weather")).toBeInTheDocument();
  });

  it("shows the thinking indicator while the request is in flight, then hides it", async () => {
    const user = userEvent.setup();
    let resolveFetch!: (value: unknown) => void;
    const pending = new Promise((resolve) => {
      resolveFetch = resolve;
    });
    (fetch as FetchMock).mockReturnValueOnce(pending);

    renderWithProviders(<ChatInterface />);
    await user.type(screen.getByPlaceholderText(/ask about flights/i), "Hi{Enter}");

    expect(await screen.findByText("...thinking")).toBeInTheDocument();

    resolveFetch({
      ok: true,
      json: async () => ({ intent: "chitchat", response: "Hello!" }),
    });

    await waitFor(() => {
      expect(screen.queryByText("...thinking")).not.toBeInTheDocument();
    });
  });

  it("renders an error message when the request fails", async () => {
    const user = userEvent.setup();
    (fetch as FetchMock).mockResolvedValueOnce({ ok: false, status: 500 });

    renderWithProviders(<ChatInterface />);
    await user.type(screen.getByPlaceholderText(/ask about flights/i), "Hi{Enter}");

    expect(await screen.findByText(/could not reach the backend/i)).toBeInTheDocument();
  });

  it("clears the input after submitting", async () => {
    const user = userEvent.setup();
    (fetch as FetchMock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ intent: "chitchat", response: "Hello!" }),
    });

    renderWithProviders(<ChatInterface />);
    const input = screen.getByPlaceholderText(/ask about flights/i);
    await user.type(input, "Hi{Enter}");

    await waitFor(() => {
      expect(input).toHaveValue("");
    });
  });
});
