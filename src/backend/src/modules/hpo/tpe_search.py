# Standard Libraries
import logging
from typing import Any

# Third-party Libraries
import numpy as np
import optuna
from sklearn.base import BaseEstimator
from optuna.pruners import MedianPruner, NopPruner
from optuna.samplers import TPESampler
from sklearn.model_selection import BaseCrossValidator, ParameterGrid

# Local Libraries
from src.modules.hpo.base import BaseSearchCV, TrialPruned


# Logging
logger = logging.getLogger(__name__)


class TPESearch(BaseSearchCV):
    """
    Hyperparameter optimization using Tree-structured Parzen Estimator (TPE) via Optuna
    """

    def __init__(
        self,
        estimator: BaseEstimator,
        param_grid: list[dict[str, Any]] | dict[str, Any],
        n_trials: int = 30,
        patience: int | None = 10,
        min_delta: float = 1e-4,
        enable_pruning: bool = True,
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
        self.n_trials = max(1, n_trials)

    def fit(self, X: np.ndarray, y: np.ndarray) -> "TPESearch":
        """
        Executes TPE hyperparameter optimization
        """
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        self._init_search(X, y)
        param_grids = self._normalize_param_grid()
        total_possible_combos = len(list(ParameterGrid(self.param_grid))) or 1
        total_trials = min(self.n_trials, total_possible_combos)

        total_evaluated = 0
        cache: dict[tuple, tuple[dict[str, float], dict[str, float], float, float]] = {}

        for grid_idx, grid in enumerate(param_grids, start=1):
            combos_in_grid = len(list(ParameterGrid(grid))) or 1
            trials_per_grid = min(max(1, self.n_trials // len(param_grids)), combos_in_grid)

            if not grid:
                total_evaluated += 1
                try:
                    mean_scores, std_scores, fit_time, score_time = self._evaluate_candidate(
                        candidate_params={},
                        X=X,
                        y=y,
                        trial_num=total_evaluated,
                        total_trials=total_trials,
                    )
                    self._record_trial({}, mean_scores, std_scores, fit_time, score_time, is_pruned=False)
                except TrialPruned:
                    self._record_trial({}, {m: 0.0 for m in self.scoring}, {m: 0.0 for m in self.scoring}, 0.0, 0.0, is_pruned=True)
                continue

            sampler = TPESampler(
                seed=self.random_state,
                multivariate=True,
            )
            pruner = (
                MedianPruner(n_startup_trials=self.pruning_startup_trials, n_warmup_steps=self.pruning_warmup_folds, interval_steps=1)
                if self.enable_pruning
                else NopPruner()
            )
            study = optuna.create_study(direction="maximize", sampler=sampler, pruner=pruner)

            def objective(trial: optuna.Trial) -> float:
                nonlocal total_evaluated

                sampled_params: dict[str, Any] = {}
                for param_name, values in grid.items():
                    if isinstance(values, (list, tuple, np.ndarray)) and len(values) > 0:
                        sampled_params[param_name] = trial.suggest_categorical(param_name, list(values))
                    else:
                        sampled_params[param_name] = values

                param_key = tuple(sorted((k, str(v)) for k, v in sampled_params.items()))

                if param_key in cache:
                    cached_mean_scores, _, _, _ = cache[param_key]
                    return float(cached_mean_scores.get(self.refit, 0.0))

                total_evaluated += 1
                try:
                    mean_scores, std_scores, fit_time, score_time = self._evaluate_candidate(
                        candidate_params=sampled_params,
                        X=X,
                        y=y,
                        trial_num=total_evaluated,
                        total_trials=total_trials,
                    )
                    self._record_trial(sampled_params, mean_scores, std_scores, fit_time, score_time, is_pruned=False)
                    cache[param_key] = (mean_scores, std_scores, fit_time, score_time)
                except TrialPruned as prune_exc:
                    zero_scores = {m: 0.0 for m in self.scoring}
                    self._record_trial(sampled_params, zero_scores, zero_scores, 0.0, 0.0, is_pruned=True)
                    cache[param_key] = (zero_scores, zero_scores, 0.0, 0.0)
                    raise optuna.TrialPruned(str(prune_exc))

                current_score = float(mean_scores.get(self.refit, 0.0))

                # Check centralized early stopping
                if self._check_early_stopping(current_score):
                    study.stop()

                return current_score

            try:
                study.optimize(objective, n_trials=trials_per_grid, n_jobs=self.n_jobs)
            except Exception as e:
                logger.warning(f"[TPESearch] Optuna notice: {e}")

        self._finalize_search(X, y)
        return self
