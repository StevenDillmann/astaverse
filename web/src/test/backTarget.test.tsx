import { renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { navigate, routeLabel, useBackTarget } from "../hooks";

afterEach(() => {
  window.history.replaceState(null, "", "/");
});

describe("routeLabel", () => {
  it("names list routes and self-describing detail routes", () => {
    expect(routeLabel("/")).toBe("Overview");
    expect(routeLabel("/experiments")).toBe("Experiments");
    expect(routeLabel("/experiments?status=complete")).toBe("Experiments");
    expect(routeLabel("/hypotheses")).toBe("Hypotheses");
    // A dataset is addressed by name, so it can label itself.
    expect(routeLabel("/datasets/ucb-admissions")).toBe("ucb-admissions");
    // Ids cannot, so they get the entity name.
    expect(routeLabel("/hypotheses/60fff5159571")).toBe("Hypothesis");
    expect(routeLabel("/experiments/20260909-061016__x")).toBe("Experiment");
  });
});

describe("useBackTarget", () => {
  it("has no origin on a cold load, so the caller names the fallback", () => {
    window.history.replaceState(null, "", "/experiments/abc");
    const { result } = renderHook(() => useBackTarget());
    expect(result.current.label).toBeNull();
  });

  it("reports the page navigated from, not the semantic parent", () => {
    window.history.replaceState(null, "", "/experiments?status=complete");
    navigate("/experiments/abc");
    const { result } = renderHook(() => useBackTarget());
    expect(result.current.label).toBe("Experiments");
  });

  it("distinguishes arriving from a hypothesis versus from the list", () => {
    window.history.replaceState(null, "", "/hypotheses/60fff5159571");
    navigate("/experiments/abc");
    const { result } = renderHook(() => useBackTarget());
    expect(result.current.label).toBe("Hypothesis");
  });

  it("returns to the previous entry rather than pushing a new one", () => {
    window.history.replaceState(null, "", "/experiments");
    navigate("/experiments/abc");
    const before = window.history.length;
    const { result } = renderHook(() => useBackTarget());
    result.current.go("/hypotheses/unused");
    expect(window.history.length).toBe(before);
  });
});
