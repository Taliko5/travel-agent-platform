import { describe, it, expect } from "vitest";
import { renderWithProviders, screen } from "@/test-utils";
import { ThinkingIndicator } from "./ThinkingIndicator";

describe("ThinkingIndicator", () => {
  it("renders the thinking label", () => {
    renderWithProviders(<ThinkingIndicator />);
    expect(screen.getByText("...thinking")).toBeInTheDocument();
  });
});
