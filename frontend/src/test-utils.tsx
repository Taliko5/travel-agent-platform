import type { ReactElement } from "react";
import { render, type RenderOptions } from "@testing-library/react";
import { Providers } from "@/app/providers";

function renderWithProviders(ui: ReactElement, options?: Omit<RenderOptions, "wrapper">) {
  return render(ui, { wrapper: Providers, ...options });
}

export * from "@testing-library/react";
export { renderWithProviders };
