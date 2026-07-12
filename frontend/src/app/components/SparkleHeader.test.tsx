import { describe, it, expect } from "vitest";
import { renderWithProviders, screen } from "@/test-utils";
import { SparkleHeader } from "./SparkleHeader";

// Smoke test only — SparkleHeader is decorative with no props/state (see CLAUDE.md),
// so asserting anything beyond "it renders" would pin implementation detail (sparkle
// positions, animation) rather than behavior.
describe("SparkleHeader", () => {
  it("renders without crashing", () => {
    renderWithProviders(<SparkleHeader />);
    expect(screen.getByText("Travel Agent")).toBeInTheDocument();
  });
});
