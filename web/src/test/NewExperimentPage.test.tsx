import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NewExperimentPage } from "../pages/NewExperimentPage";

const config = {
  plans: { k: 5, model: null, temperature: 0.9 },
  decisions: { mode: "sample_plans", models: [], critique: false, max_decisions: 6 },
  universes: { cap: 24, include: [], exclude: [] },
  execute: { agent: "terminus-2", models: [], dry_run: false },
  surprisal: { model: null, n_samples: 5 },
  through: "universes",
};

beforeEach(() => {
  window.history.replaceState({}, "", "/experiments/new");
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      const payload = url.endsWith("/settings")
        ? {
            default_experiment: config,
            review_before_execute: true,
            providers: { openai: true, gemini: false, harbor: true },
          }
        : url.endsWith("/datasets")
          ? [
              {
                name: "hurricane",
                path: "/data/hurricane",
                n_rows: 94,
                n_columns: 12,
                description: "Atlantic hurricanes",
              },
            ]
          : url.endsWith("/extraction-modes")
            ? [
                { id: "sample_plans", description: "Compare sampled plans.", needs_plans: true },
                { id: "audit_plan", description: "Audit one plan.", needs_plans: true },
                { id: "direct", description: "Extract directly.", needs_plans: false },
              ]
            : {
                run: "astaverse run <experiment-id> --decisions.mode sample_plans",
                stages: {},
                planned_stages: ["study", "plans", "decisions", "universes"],
              };
      return new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("NewExperimentPage", () => {
  it("shows settings conditional on the extraction method", async () => {
    render(<NewExperimentPage />);
    await screen.findByText("Choose a method");

    expect(screen.getByText("Plans to sample")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Audit one plan/ }));
    expect(
      screen.getByText(/AstaVerse will generate one plan/),
    ).toBeInTheDocument();
    expect(screen.queryByText("Plans to sample")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Direct extraction/ }));
    await waitFor(() =>
      expect(screen.queryByText(/AstaVerse will generate one plan/)).not.toBeInTheDocument(),
    );
  });

  it("renders the live CLI preview returned by the API", async () => {
    render(<NewExperimentPage />);
    await screen.findByText("CLI equivalent");
    expect(screen.getByText(/astaverse run <experiment-id>/)).toBeInTheDocument();
  });
});
