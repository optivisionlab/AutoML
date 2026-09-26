# Standard Libraries
import logging
from typing import Any

# Third-party Libraries
import numpy as np
from sklearn.base import BaseEstimator
from sklearn.model_selection import BaseCrossValidator
from skopt import gp_minimize
from skopt.space import Categorical, Dimension
from skopt.utils import use_named_args

# Local Libraries
from src.modules.hpo.base import BaseSearchCV


# Logging
logger = logging.getLogger(__name__)


class BayesianSearch(BaseSearchCV):
    """
    Bayesian Optimization search over hyperparameters using Gaussian Process Regression (scikit-optimize).
    Learns a surrogate model of the objective function and uses an acquisition function to propose
    the next most promising hyperparameter combination.
    """

    def __init__(
        self,
        estimator: BaseEstimator,
        param_grid: list[dict[str, Any]] | dict[str, Any],
        n_calls: int = 25,
        n_initial_points: int = 5,
        acq_func: str = "EI",
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
        self.n_calls = n_calls
        self.n_initial_points = n_initial_points
        self.acq_func = acq_func
        self.random_state = random_state

    def _convert_grid_to_dimensions(self, grid: dict[str, Any]) -> list[Dimension]:
        """
        Converts a parameter grid dictionary into a list of skopt Dimension objects.
        """
        dimensions: list[Dimension] = []
        for k, v in grid.items():
            match v:
                case Dimension():
                    v.name = k
                    dimensions.append(v)
                case list() | tuple() | np.ndarray():
                    dimensions.append(Categorical(list(v), name=k))
                case _:
                    dimensions.append(Categorical([v], name=k))

        return dimensions

    def fit(self, X: np.ndarray, y: np.ndarray) -> "BayesianSearch":
        """
        Executes Bayesian Optimization search.
        """
        self._init_search(X, y)
        param_grids = self._normalize_param_grid()
        calls_per_grid = max(self.n_initial_points + 1, self.n_calls // len(param_grids))

        total_evaluated = 0
        cache: dict[tuple, tuple[dict[str, float], dict[str, float], float, float]] = {}

        for grid_idx, grid in enumerate(param_grids, start=1):
            dimensions = self._convert_grid_to_dimensions(grid) if grid else []

            if not dimensions:
                total_evaluated += 1
                mean_scores, std_scores, fit_time, score_time = self._evaluate_candidate(
                    candidate_params={},
                    X=X,
                    y=y,
                    trial_num=total_evaluated,
                    total_trials=self.n_calls,
                )
                self._record_trial({}, mean_scores, std_scores, fit_time, score_time)
                continue

            total_combos = np.prod([len(d.categories) for d in dimensions if hasattr(d, "categories")], dtype=int)
            effective_calls = min(calls_per_grid, int(total_combos)) if total_combos > 0 else calls_per_grid
            effective_initial = min(self.n_initial_points, max(1, effective_calls // 2))

            @use_named_args(dimensions)
            def objective(**params) -> float:
                nonlocal total_evaluated
                param_key = tuple(sorted((k, str(v)) for k, v in params.items()))

                if param_key not in cache:
                    total_evaluated += 1
                    mean_scores, std_scores, fit_time, score_time = self._evaluate_candidate(
                        candidate_params=params,
                        X=X,
                        y=y,
                        trial_num=total_evaluated,
                        total_trials=self.n_calls,
                    )
                    self._record_trial(params, mean_scores, std_scores, fit_time, score_time)
                    cache[param_key] = (mean_scores, std_scores, fit_time, score_time)

                return -float(cache[param_key][0].get(self.refit, 0.0))

            if self.verbose > 0:
                logger.info(
                    f"[BayesianSearch] Space {grid_idx}/{len(param_grids)}: Optimizing with {effective_calls} calls..."
                )

            try:
                gp_minimize(
                    func=objective,
                    dimensions=dimensions,
                    n_calls=effective_calls,
                    n_initial_points=effective_initial,
                    acq_func=self.acq_func,
                    random_state=self.random_state,
                    n_jobs=self.n_jobs,
                )
            except Exception as e:
                logger.warning(f"[BayesianSearch] gp_minimize execution notice: {e}")

        self._finalize_search(X, y)
        return self
