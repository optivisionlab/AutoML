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


class RandomSearch(BaseSearchCV):
    """
    Randomized search on hyperparameters.
    Samples a fixed number of parameter settings (n_iter) from the specified parameter space
    and evaluates each trial in real-time.
    """

    def __init__(
        self,
        estimator: BaseEstimator,
        param_grid: list[dict[str, Any]] | dict[str, Any],
        n_iter: int = 20,
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
            cv=cv,
            scoring=scoring,
            refit=refit,
            n_jobs=n_jobs,
            verbose=verbose,
        )
        self.n_iter = n_iter
        self.random_state = random_state

    def fit(self, X: np.ndarray, y: np.ndarray) -> "RandomSearch":
        """
        Executes Random Search by sampling n_iter combinations from ParameterGrid.
        """
        rng = np.random.default_rng(self.random_state)
        self._init_search(X, y)

        all_candidates = list(ParameterGrid(self.param_grid)) or [{}]
        n_samples = min(self.n_iter, len(all_candidates))
        sampled_indices = rng.choice(len(all_candidates), size=n_samples, replace=False)
        sampled_candidates = [all_candidates[i] for i in sampled_indices]

        if self.verbose > 0:
            logger.info(
                f"[RandomSearch] Sampled {n_samples} candidate configurations (out of {len(all_candidates)} total)..."
            )

        for idx, candidate in enumerate(sampled_candidates, start=1):
            mean_scores, std_scores, fit_time, score_time = self._evaluate_candidate(
                candidate_params=candidate,
                X=X,
                y=y,
                trial_num=idx,
                total_trials=n_samples,
            )
            self._record_trial(candidate, mean_scores, std_scores, fit_time, score_time)

        self._finalize_search(X, y)
        return self
