"""Wire format between pipeline stages.

Every stage reads one artifact and writes another; these are those artifacts.

The decision-spec models deliberately mirror the field names of the ASTRA
specification (https://astra-spec.org, LightconeResearch/astra-spec) so that
emitted YAML is ASTRA-*shaped* without taking a dependency on `astra-tools`
while the prototype is still finding its shape. Adopting the real validator
later should be a matter of running `astra validate` and fixing what it flags,
not a redesign. Names that come from ASTRA are marked [ASTRA].
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# The ASTRA schema version whose shape we are mirroring. Recorded in emitted
# YAML so a later conformance pass knows what it is comparing against. Note
# that the schema (astra-spec, v0.0.x) and the CLI (astra-tools, PyPI 0.2.x)
# are separate repos on separate version lines.
ASTRA_SCHEMA_SHAPE = "0.0.13"


# --------------------------------------------------------------------------
# s1 — study
# --------------------------------------------------------------------------


class Column(BaseModel):
    """One dataset column, as described to the plan-generating model."""

    name: str
    dtype: str
    description: str | None = None
    n_missing: int | None = None
    min: float | None = None
    max: float | None = None
    samples: list[Any] = Field(default_factory=list)


class StudySpec(BaseModel):
    """The input to the whole pipeline: a hypothesis and the data to test it on."""

    hypothesis: str
    dataset_path: str
    dataset_name: str
    dataset_description: str | None = None
    n_rows: int | None = None
    columns: list[Column] = Field(default_factory=list)
    research_questions: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------
# s2 — plans
# --------------------------------------------------------------------------


class Plan(BaseModel):
    """One sampled analysis plan.

    Mirrors `ExperimentPlan` in asta-autodiscovery (objective / steps /
    deliverables) so plans round-trip with the existing `query` convention.
    """

    id: str
    objective: str
    steps: str
    deliverables: str
    rationale: str | None = None
    # True when the plan was supplied rather than sampled — the plan under
    # evaluation. Extraction audits it for under-specification, not just for
    # disagreement with the others.
    seeded: bool = False

    def to_query(self) -> str:
        """Render in the `query` format used by asta-autodiscovery's plan records."""
        return (
            f"Experiment objective: {self.objective}\n\n"
            f"Steps for the programmer:\n{self.steps}\n\n"
            f"Deliverables:\n{self.deliverables}"
        )


class PlanSet(BaseModel):
    plans: list[Plan]
    model: str
    temperature: float


# --------------------------------------------------------------------------
# s3 — decision space / decision spec  [ASTRA-shaped]
# --------------------------------------------------------------------------


class DecisionKind(str, Enum):
    """What sort of fork this is.

    `verdict_rule` is first-class on purpose: the experiments repo found that
    the *verdict decision rule* is an under-specification that never gets
    resolved, distinct from under-specified computation.
    """

    preprocessing = "preprocessing"
    variable_choice = "variable_choice"
    model = "model"
    inference = "inference"
    verdict_rule = "verdict_rule"


class Option(BaseModel):
    """One option of a decision. [ASTRA] label / description / requires / incompatible_with."""

    label: str
    description: str | None = None
    # Cross-decision constraints, in ASTRA's "<decision_id>.<option_id>" form.
    requires: list[str] = Field(default_factory=list)
    incompatible_with: list[str] = Field(default_factory=list)
    # Astaverse extension, kept out of the ASTRA block on emit: which sampled
    # plans supported this option. Recorded for provenance, never used to filter.
    supported_by: list[str] = Field(default_factory=list)


class Decision(BaseModel):
    """One analytic fork. [ASTRA] label / rationale / default / options."""

    label: str
    rationale: str | None = None
    default: str
    options: dict[str, Option]
    kind: DecisionKind = DecisionKind.preprocessing
    # True if this decision is resolved by astaverse from the reported numbers
    # rather than by executing code (verdict rules are the motivating case).
    post_hoc: bool = False


class DecisionSpec(BaseModel):
    """The decision space, plus enough context to execute it. [ASTRA] astra.yaml."""

    id: str
    name: str
    description: str | None = None
    hypothesis: str
    dataset_path: str
    decisions: dict[str, Decision]
    astra_schema_shape: str = ASTRA_SCHEMA_SHAPE

    def execution_decisions(self) -> dict[str, Decision]:
        """Decisions the analysis code must actually branch on."""
        return {k: v for k, v in self.decisions.items() if not v.post_hoc}

    def post_hoc_decisions(self) -> dict[str, Decision]:
        """Decisions applied to the reported numbers after execution, at zero exec cost."""
        return {k: v for k, v in self.decisions.items() if v.post_hoc}


# --------------------------------------------------------------------------
# s4 — universes  [ASTRA-shaped]
# --------------------------------------------------------------------------


class Universe(BaseModel):
    """One point in the decision grid. [ASTRA] UniverseNode / DecisionSelection."""

    id: str
    # decision_id -> option_id  [ASTRA] DecisionSelection
    decisions: dict[str, str]
    is_default: bool = False

    def label(self) -> str:
        return ", ".join(f"{k}={v}" for k, v in sorted(self.decisions.items()))


class UniverseSet(BaseModel):
    universes: list[Universe]
    n_total_grid: int
    n_dropped_constraints: int = 0
    n_dropped_cap: int = 0
    cap: int | None = None

    @property
    def truncated(self) -> bool:
        return self.n_dropped_cap > 0


# --------------------------------------------------------------------------
# s6/s7 — execution results and verdicts
# --------------------------------------------------------------------------


class UniverseStats(BaseModel):
    """Numbers reported by the analysis for one universe.

    Deliberately contains no verdict: the agent reports statistics, astaverse
    assigns the verdict (bias control 2).
    """

    universe_id: str
    decisions: dict[str, str] = Field(default_factory=dict)
    estimate: float | None = None
    # The comparable estimand. `estimate` is on the natural scale of whatever
    # model the universe fitted, so it is NOT comparable across universes that
    # transform the outcome or change model family — plotting those together
    # yields a spread made of unit changes rather than analytic disagreement.
    estimate_standardized: float | None = None
    std_error: float | None = None
    p_value: float | None = None
    n: int | None = None
    direction: str | None = None  # "positive" | "negative" | "none"
    converged: bool = True
    notes: str | None = None


class Verdict(str, Enum):
    supported = "supported"
    not_supported = "not_supported"
    mixed = "mixed"
    failed = "failed"


class UniverseResult(BaseModel):
    """A universe's numbers plus the verdict astaverse derived from them."""

    universe_id: str
    decisions: dict[str, str]
    stats: UniverseStats
    verdict: Verdict
    verdict_rule: str
    agent: str | None = None
    is_default: bool = False


# --------------------------------------------------------------------------
# s8 — robust surprisal
# --------------------------------------------------------------------------


class BeliefDistribution(BaseModel):
    """A Beta belief over the hypothesis, from categorical LLM draws."""

    alpha: float
    beta: float
    counts: dict[str, int] = Field(default_factory=dict)
    n_samples: int = 0

    @property
    def mean(self) -> float:
        return self.alpha / (self.alpha + self.beta)


class UniverseSurprisal(BaseModel):
    universe_id: str
    decisions: dict[str, str]
    verdict: Verdict
    posterior_mean: float
    surprisal: float
    is_default: bool = False
    agent: str | None = None


class DecisionSensitivity(BaseModel):
    """How much a single decision moved the result, marginalizing the others."""

    decision_id: str
    label: str
    kind: DecisionKind
    option_means: dict[str, float]
    spread: float
    predicted_consequential: bool | None = None


class RobustSurprisal(BaseModel):
    """The headline artifact: surprisal as a distribution, not a point."""

    prior_mean: float
    n_universes: int
    per_universe: list[UniverseSurprisal]

    median: float
    mean: float
    iqr: float
    sign_consistency: float
    frac_surprising: float
    verdict_distribution: dict[str, int]

    single_universe_surprisal: float | None = None
    fragility_index: float | None = None

    decision_sensitivity: list[DecisionSensitivity] = Field(default_factory=list)
    between_agent_spread: float | None = None
