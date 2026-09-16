/**
 * Visibility of hypotheses, datasets and experiments in the interface.
 *
 * Everything the API returns is shown unless it is listed here. Add an id or
 * dataset name to hide it from the lists and detail pages; direct URLs still
 * work for hidden items.
 */
export const HIDDEN_HYPOTHESIS_IDS: readonly string[] = [];
export const HIDDEN_DATASET_NAMES: readonly string[] = [];
export const HIDDEN_EXPERIMENT_IDS: readonly string[] = [];

export function isVisibleHypothesis(id: string) {
  return !HIDDEN_HYPOTHESIS_IDS.includes(id);
}

export function isVisibleDataset(name: string) {
  return !HIDDEN_DATASET_NAMES.some((hidden) => hidden.toLowerCase() === name.toLowerCase());
}

export function isVisibleExperiment(id: string) {
  return !HIDDEN_EXPERIMENT_IDS.includes(id);
}
