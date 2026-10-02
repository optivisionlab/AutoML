# Standard Libraries
import logging
from typing import Any

# Third-party Libraries
import numpy as np
from sklearn.base import BaseEstimator
from sklearn.model_selection import BaseCrossValidator, ParameterGrid

# Local Libraries
from src.modules.hpo.base import BaseSearchCV, TrialPruned


# Logging
logger = logging.getLogger(__name__)


class RandomSearch(BaseSearchCV):
    """
    Randomized hyperparameter search over sampled configurations
    """

    def __init__(
        self,
        estimator: BaseEstimator,
        param_grid: list[dict[str, Any]] | dict[str, Any],
        n_iter: int = 20,
        patience: int | None = None,
        min_delta: float = 1e-4,
        enable_pruning: bool = False,
        cv: BaseCrossValidator | int = 5,
        scoring: dict[str, Any] | None = None,
        refit: str = "accuracy",
        random_state: int | None = 42,
        n_jobs: int = 1,
        verbose: int = 1,
    ):
        super().__init__(
            estimator=estimator,
            param_grid=param_grid,
            patience=patience,
            min_delta=min_delta,
            enable_pruning=enable_pruning,
            cv=cv,
            scoring=scoring,
            refit=refit,
            random_state=random_state,
            n_jobs=n_jobs,
            verbose=verbose,
        )
        self.n_iter = max(1, n_iter)

    def fit(self, X: np.ndarray, y: np.ndarray) -> "RandomSearch":
        """
        Samples n_iter random combinations from ParameterGrid and evaluates them
        """
        rng = np.random.default_rng(self.random_state)
        self._init_search(X, y)

        all_candidates = list(ParameterGrid(self.param_grid)) or [{}]
        n_samples = min(self.n_iter, len(all_candidates))
        sampled_indices = rng.choice(len(all_candidates), size=n_samples, replace=False)
        sampled_candidates = [all_candidates[i] for i in sampled_indices]

        if self.verbose > 0:
            logger.info(f"[RandomSearch] Sampling {n_samples} random candidate configurations...")

        for idx, candidate in enumerate(sampled_candidates, start=1):
            try:
                mean_scores, std_scores, fit_time, score_time = self._evaluate_candidate(
                    candidate_params=candidate,
                    X=X,
                    y=y,
                    trial_num=idx,
                    total_trials=n_samples,
                )
                self._record_trial(candidate, mean_scores, std_scores, fit_time, score_time, is_pruned=False)
                score = mean_scores.get(self.refit, 0.0)
                if self._check_early_stopping(score):
                    break
            except TrialPruned:
                self._record_trial(
                    candidate,
                    {m: 0.0 for m in self.scoring},
                    {m: 0.0 for m in self.scoring},
                    0.0,
                    0.0,
                    is_pruned=True,
                )

        self._finalize_search(X, y)
        return self
