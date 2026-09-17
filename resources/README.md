# Resources

Background reading for AstaVerse, kept alongside the code so a reference in a
findings doc resolves to something.

## Papers

**Many AI Analysts, One Dataset: Navigating the Agentic Data Science Multiverse**
`many-ai-analysts-one-dataset-2602.18710.pdf` · [arXiv:2602.18710](https://arxiv.org/abs/2602.18710)
The question this repository exists to answer: what happens to the multiverse
when the analysts are agents.

**Boba: Authoring and Visualizing Multiverse Analyses**
`boba-multiverse-2007.05551.pdf` · [arXiv:2007.05551](https://arxiv.org/abs/2007.05551)
Liu, Kale, Althoff & Heer. The authoring language and the visual grammar for
multiverse results — the specification curve with its decision matrix below it,
which is the shape `ResultsView` draws.

**Automated Hypothesis Validation with Agentic Sequential Falsifications**
`popper-sequential-falsification-2502.09858.pdf` · [arXiv:2502.09858](https://arxiv.org/abs/2502.09858)
POPPER. Sequential falsification as the loop an agent runs against a claim —
the closest relative to the refinement stage, which splits a claim that turned
out to be several.

## Prior art the pipeline is measured against

Not included as files; both are public and the data is documented in the
relevant `data/datasets/*/info.json`.

- **Silberzahn et al. (2018), Many Analysts, One Data Set** —
  [journal](https://journals.sagepub.com/doi/10.1177/2515245917747646).
  29 teams, one dataset, odds ratios 0.89–2.93. The only benchmark here with a
  human-measured analytic spread; `runs/20260916-214343__referees-*` is the
  AstaVerse reproduction.
- **Steegen, Tuerlinckx, Gelman & Vanpaemel (2016), Increasing Transparency
  Through a Multiverse Analysis** — [journal](https://journals.sagepub.com/doi/10.1177/1745691616658637),
  [materials](https://osf.io/zj68b/). The paper that named multiverse analysis,
  reanalysing Durante et al. (2013).
- **Pierson et al. (2020), A large-scale analysis of racial disparities in
  police stops** — [Nature Human Behaviour](https://www.nature.com/articles/s41562-020-0858-1),
  [data](https://openpolicing.stanford.edu/data/). Source of the Durham stops.
