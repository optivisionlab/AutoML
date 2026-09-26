# Standard Libraries
import logging
from typing import Any

# Third-party Libraries
import numpy as np
from sklearn.base import BaseEstimator
from sklearn.model_selection import BaseCrossValidator, ParameterGrid

# Local Libraries
from src.modules.hpo.base import BaseSearchCV


# Logging
logger = logging.getLogger(__name__)


class GridSearch(BaseSearchCV):
    """
    Exhaustive search over specified parameter values for an estimator.
    Evaluates all combinations in the parameter grid and logs each trial result in real-time.
    """

    def __init__(
        self,
        estimator: BaseEstimator,
        param_grid: list[dict[str, Any]] | dict[str, Any],
        cv: BaseCrossValidator | int = 5,
        scoring: dict[str, Any] | None = None,
        refit: str = "accuracy",
        n_jobs: int = 1,
        verbose: int = 1,
    ):
        super().__init__(
            estimator=estimator,
            param_grid=param_grid,
            cv=cv,
            scoring=scoring,
            refit=refit,
            n_jobs=n_jobs,
            verbose=verbose,
        )

    def fit(self, X: np.ndarray, y: np.ndarray) -> "GridSearch":
        """
        Executes Grid Search over all configurations in ParameterGrid.
        """
        self._init_search(X, y)
        candidates = list(ParameterGrid(self.param_grid)) or [{}]
        total_trials = len(candidates)

        if self.verbose > 0:
            logger.info(f"[GridSearch] Evaluating {total_trials} candidate configurations...")

        for idx, candidate in enumerate(candidates, start=1):
            mean_scores, std_scores, fit_time, score_time = self._evaluate_candidate(
                candidate_params=candidate,
                X=X,
                y=y,
                trial_num=idx,
                total_trials=total_trials,
            )
            self._record_trial(candidate, mean_scores, std_scores, fit_time, score_time)

        self._finalize_search(X, y)
        return self
