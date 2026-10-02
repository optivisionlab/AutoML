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


class GridSearch(BaseSearchCV):
    """
    Exhaustive Grid Search over specified hyperparameter values
    """

    def __init__(
        self,
        estimator: BaseEstimator,
        param_grid: list[dict[str, Any]] | dict[str, Any],
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

    def fit(self, X: np.ndarray, y: np.ndarray) -> "GridSearch":
        """
        Evaluates all combinations in ParameterGrid
        """
        self._init_search(X, y)
        candidates = list(ParameterGrid(self.param_grid)) or [{}]
        total_trials = len(candidates)

        if self.verbose > 0:
            logger.info(f"[GridSearch] Evaluating {total_trials} candidate configurations...")

        for idx, candidate in enumerate(candidates, start=1):
            try:
                mean_scores, std_scores, fit_time, score_time = self._evaluate_candidate(
                    candidate_params=candidate,
                    X=X,
                    y=y,
                    trial_num=idx,
                    total_trials=total_trials,
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
