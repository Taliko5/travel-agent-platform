import { describe, it, expect, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { renderWithProviders, screen, fireEvent } from "@/test-utils";
import { ChatInput } from "./ChatInput";

describe("ChatInput", () => {
  it("renders the current value", () => {
    renderWithProviders(
      <ChatInput value="hello" onChange={vi.fn()} onSubmit={vi.fn()} disabled={false} />,
    );
    expect(screen.getByPlaceholderText(/ask about flights/i)).toHaveValue("hello");
  });

  it("calls onChange when typing", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    renderWithProviders(
      <ChatInput value="" onChange={onChange} onSubmit={vi.fn()} disabled={false} />,
    );
    await user.type(screen.getByPlaceholderText(/ask about flights/i), "hi");
    expect(onChange).toHaveBeenCalled();
  });

  it("calls onSubmit when Enter is pressed and not disabled", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    renderWithProviders(
      <ChatInput value="hi" onChange={vi.fn()} onSubmit={onSubmit} disabled={false} />,
    );
    await user.type(screen.getByPlaceholderText(/ask about flights/i), "{Enter}");
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("does not call onSubmit on Enter when disabled", () => {
    // fireEvent (not userEvent) — a disabled input blocks userEvent's own
    // pointer/keyboard interaction, but this test targets the component's
    // own `!disabled` guard in handleKeyDown, not the browser's native block.
    const onSubmit = vi.fn();
    renderWithProviders(
      <ChatInput value="hi" onChange={vi.fn()} onSubmit={onSubmit} disabled={true} />,
    );
    fireEvent.keyDown(screen.getByPlaceholderText(/ask about flights/i), { key: "Enter" });
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("calls onSubmit when the send button is clicked", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    renderWithProviders(
      <ChatInput value="hi" onChange={vi.fn()} onSubmit={onSubmit} disabled={false} />,
    );
    await user.click(screen.getByRole("button", { name: /send message/i }));
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("disables the input and send button when disabled is true", () => {
    renderWithProviders(
      <ChatInput value="hi" onChange={vi.fn()} onSubmit={vi.fn()} disabled={true} />,
    );
    expect(screen.getByPlaceholderText(/ask about flights/i)).toBeDisabled();
    expect(screen.getByRole("button", { name: /send message/i })).toBeDisabled();
  });
});
