import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { Headline } from "../pages/ExperimentDetailPage";
import type { ExperimentDetail } from "../types";

afterEach(cleanup);

describe("experiment headline", () => {
  it("uses free summary space for the conclusion and classification", () => {
    const experiment = {
      artifacts: {
        verdicts: {
          results: [
            {
              universe_id: "universe_000",
              verdict_rule: "alpha_05_directional",
              stats: {
                estimate_standardized: 0.4,
                p_value: 0.01,
                converged: true,
              },
            },
          ],
          curve_summary: { median: 0.4 },
          decision_sensitivity: [
            {
              decision_id: "outcome",
              n_pairs: 2,
              normalized_effect_change: 0.5,
            },
          ],
        },
        conclusion: {
          evidence_status: "partially_supported",
          answer: "The positive result depends on which outcome is analyzed.",
        },
      },
    } as unknown as ExperimentDetail;

    render(<Headline experiment={experiment} />);

    expect(screen.getByText("partially supported")).toBeInTheDocument();
    expect(
      screen.getByText("The positive result depends on which outcome is analyzed."),
    ).toBeInTheDocument();
    expect(screen.getByText("Most sensitive decisions").querySelector("br")).toBeNull();
  });
});
