# Standard Libraries
import time
import logging
import warnings
from abc import ABC, abstractmethod
from typing import Any

# Third-party Libraries
import numpy as np
from sklearn.base import BaseEstimator, clone, is_classifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.model_selection import BaseCrossValidator, check_cv

warnings.filterwarnings("ignore", category=ConvergenceWarning)
warnings.filterwarnings("ignore", category=UserWarning)


# Logging
logger = logging.getLogger(__name__)


class TrialPruned(Exception):
    """
    Exception raised when a hyperparameter candidate is pruned early
    """
    pass


def convert_numpy_types(obj: Any) -> Any:
    """
    Recursively converts numpy types to native Python types for JSON/BSON serialization
    """
    match obj:
        case np.integer():
            return int(obj)
        case np.floating():
            return float(obj)
        case np.bool_():
            return bool(obj)
        case np.ndarray():
            return [convert_numpy_types(x) for x in obj.tolist()]
        case dict():
            return {k: convert_numpy_types(v) for k, v in obj.items()}
        case list():
            return [convert_numpy_types(x) for x in obj]
        case tuple():
            return tuple(convert_numpy_types(x) for x in obj)
        case _:
            return obj


class BaseSearchCV(BaseEstimator, ABC):
    """
    Base class for Hyperparameter Optimization (HPO) algorithms with CV, pruning, and early stopping
    """

    def __init__(
        self,
        estimator: BaseEstimator,
        param_grid: list[dict[str, Any]] | dict[str, Any],
        patience: int | None = None,
        min_delta: float = 1e-4,
        enable_pruning: bool = False,
        pruning_startup_trials: int = 5,
        pruning_warmup_folds: int = 1,
        cv: BaseCrossValidator | int = 5,
        scoring: dict[str, Any] | None = None,
        refit: str = "accuracy",
        random_state: int | None = 42,
        n_jobs: int = 1,
        verbose: int = 1,
    ):
        self.estimator = estimator
        self.param_grid = param_grid
        self.patience = patience
        self.min_delta = min_delta
        self.enable_pruning = enable_pruning
        self.pruning_startup_trials = max(1, pruning_startup_trials)
        self.pruning_warmup_folds = max(0, pruning_warmup_folds)
        self.cv = cv
        self.scoring = scoring or {}
        self.refit = refit
        self.random_state = random_state
        self.n_jobs = n_jobs
        self.verbose = verbose

        # Fitted attributes
        self.best_estimator_: BaseEstimator | None = None
        self.best_params_: dict[str, Any] = {}
        self.best_score_: float = float("-inf")
        self.best_index_: int = 0
        self.cv_results_: dict[str, list[Any]] = {}
        self.trials_history_: list[dict[str, Any]] = []
        self.cv_splits_: list[tuple[np.ndarray, np.ndarray]] | None = None

        # Tracking state
        self.early_stopped_: bool = False
        self._best_tracked_score: float = float("-inf")
        self._stagnant_trials_count: int = 0
        self._fold_history_by_step: dict[int, list[float]] = {}

    def _normalize_param_grid(self) -> list[dict[str, Any]]:
        """
        Normalizes param_grid into a list of dictionaries
        """
        match self.param_grid:
            case dict() as d:
                return [d]
            case list() as l if len(l) > 0:
                return l
            case _:
                return [{}]

    def _init_cv_results(self) -> None:
        """
        Initializes cv_results_ dictionary structure
        """
        self.cv_results_ = {
            "params": [],
            "mean_test_score": [],
            "std_test_score": [],
            "rank_test_score": [],
            "mean_fit_time": [],
            "mean_score_time": [],
            **{f"mean_test_{m}": [] for m in self.scoring},
            **{f"std_test_{m}": [] for m in self.scoring},
            **{f"rank_test_{m}": [] for m in self.scoring},
        }
        self.trials_history_ = []
        self.early_stopped_ = False
        self._best_tracked_score = float("-inf")
        self._stagnant_trials_count = 0
        self._fold_history_by_step = {}

    def _init_search(self, X: np.ndarray, y: np.ndarray) -> None:
        """
        Initializes search state and precomputes CV fold splits
        """
        self._init_cv_results()
        cv_splitter = check_cv(self.cv, y, classifier=is_classifier(self.estimator))
        self.cv_splits_ = list(cv_splitter.split(X, y))
        self._fold_history_by_step = {step: [] for step in range(len(self.cv_splits_))}

    def _should_prune(self, step: int, current_mean_score: float) -> bool:
        """
        Determines if the candidate should be pruned at the current fold step
        """
        if not self.enable_pruning or not self.cv_splits_:
            return False

        n_splits = len(self.cv_splits_)
        if step < self.pruning_warmup_folds or step >= n_splits - 1:
            return False

        history_at_step = self._fold_history_by_step.get(step, [])
        if len(history_at_step) < self.pruning_startup_trials:
            return False

        median_score = float(np.median(history_at_step))
        return current_mean_score < median_score

    def _check_early_stopping(self, current_score: float) -> bool:
        """
        Checks and triggers early stopping if score improvement stagnates
        """
        if self.patience is None or self.patience <= 0:
            return False

        if current_score > self._best_tracked_score + self.min_delta:
            self._best_tracked_score = current_score
            self._stagnant_trials_count = 0
            return False
        else:
            self._stagnant_trials_count += 1
            if self._stagnant_trials_count >= self.patience:
                self.early_stopped_ = True
                if self.verbose > 0:
                    logger.info(
                        f"[{self.__class__.__name__}] Early stopping triggered: "
                        f"No improvement for {self.patience} consecutive trials "
                        f"(Best {self.refit}: {self._best_tracked_score:.4f})."
                    )
                return True
            return False

    def _evaluate_candidate(
        self,
        candidate_params: dict[str, Any],
        X: np.ndarray,
        y: np.ndarray,
        trial_num: int | None = None,
        total_trials: int | None = None,
    ) -> tuple[dict[str, float], dict[str, float], float, float]:
        """
        Evaluates a candidate across CV folds and prunes underperforming trials
        """
        start_time = time.time()
        cv_splits = self.cv_splits_ if self.cv_splits_ is not None else []
        n_splits = len(cv_splits)

        if not n_splits:
            model_instance = clone(self.estimator)
            if candidate_params:
                model_instance.set_params(**candidate_params)
            model_instance.fit(X, y)
            mean_scores = {m: 0.0 for m in self.scoring}
            std_scores = {m: 0.0 for m in self.scoring}
            return mean_scores, std_scores, 0.0, 0.0

        fold_scores: dict[str, list[float]] = {m: [] for m in self.scoring}
        step_intermediate_refit_scores: list[float] = []
        fit_times: list[float] = []
        score_times: list[float] = []

        model_name = self.estimator.__class__.__name__
        trial_tag = f"[{trial_num}/{total_trials}] " if trial_num and total_trials else ""

        # Fold-level evaluation
        for step, (train_idx, val_idx) in enumerate(cv_splits):
            fold_fit_start = time.time()
            model_fold = clone(self.estimator)
            if candidate_params:
                model_fold.set_params(**candidate_params)

            X_tr, y_tr = X[train_idx], y[train_idx]
            X_val, y_val = X[val_idx], y[val_idx]

            model_fold.fit(X_tr, y_tr)
            fit_times.append(time.time() - fold_fit_start)

            fold_eval_start = time.time()
            for metric, scorer_fn in self.scoring.items():
                try:
                    score_val = float(scorer_fn(model_fold, X_val, y_val))
                except Exception:
                    score_val = 0.0
                fold_scores[metric].append(score_val)
            score_times.append(time.time() - fold_eval_start)

            current_mean_refit = float(np.mean(fold_scores.get(self.refit, [0.0])))
            step_intermediate_refit_scores.append(current_mean_refit)

            # Fold-level median pruning check
            if self._should_prune(step, current_mean_refit):
                raise TrialPruned(
                    f"Candidate pruned at fold {step + 1}/{n_splits} (score: {current_mean_refit:.4f})"
                )

        # Update step history for completed trials
        for step, score in enumerate(step_intermediate_refit_scores):
            self._fold_history_by_step.setdefault(step, []).append(score)

        mean_scores = {m: float(np.mean(vals)) if vals else 0.0 for m, vals in fold_scores.items()}
        std_scores = {m: float(np.std(vals)) if vals else 0.0 for m, vals in fold_scores.items()}
        fit_time = float(np.mean(fit_times)) if fit_times else 0.0
        score_time = float(np.mean(score_times)) if score_times else 0.0
        elapsed = time.time() - start_time

        if self.verbose > 0:
            params_str = ", ".join(f"{k}: {repr(v)}" for k, v in candidate_params.items())
            logger.info(f"[{model_name}] {trial_tag}[{params_str}]")

        return mean_scores, std_scores, fit_time, score_time

    def _record_trial(
        self,
        candidate_params: dict[str, Any],
        mean_scores: dict[str, float],
        std_scores: dict[str, float],
        fit_time: float,
        score_time: float,
        is_pruned: bool = False,
    ) -> None:
        """
        Records evaluated trial metrics into trials_history_ and cv_results_
        """
        clean_params = convert_numpy_types(candidate_params)
        refit_score = mean_scores.get(self.refit, 0.0)

        self.cv_results_["params"].append(clean_params)
        self.cv_results_["mean_fit_time"].append(fit_time)
        self.cv_results_["mean_score_time"].append(score_time)
        self.cv_results_["mean_test_score"].append(refit_score)
        self.cv_results_["std_test_score"].append(std_scores.get(self.refit, 0.0))

        for metric in self.scoring:
            self.cv_results_[f"mean_test_{metric}"].append(mean_scores.get(metric, 0.0))
            self.cv_results_[f"std_test_{metric}"].append(std_scores.get(metric, 0.0))

        self.trials_history_.append({
            "trial_index": len(self.trials_history_),
            "params": clean_params,
            "scores": mean_scores,
            "std_scores": std_scores,
            "refit_score": refit_score,
            "fit_time": fit_time,
            "score_time": score_time,
            "is_pruned": is_pruned,
        })

    def _finalize_search(self, X: np.ndarray, y: np.ndarray) -> "BaseSearchCV":
        """
        Ranks results, selects best parameters, and refits champion estimator on full dataset
        """
        if not self.cv_results_["params"]:
            self.best_params_ = {}
            self.best_score_ = 0.0
            self.best_index_ = 0
            self.best_estimator_ = clone(self.estimator).fit(X, y)
            return self

        test_scores = np.array(self.cv_results_["mean_test_score"], dtype=float)
        self.cv_results_["rank_test_score"] = (np.argsort(np.argsort(-test_scores)) + 1).tolist()

        for metric in self.scoring:
            metric_scores = np.array(self.cv_results_[f"mean_test_{metric}"], dtype=float)
            self.cv_results_[f"rank_test_{metric}"] = (np.argsort(np.argsort(-metric_scores)) + 1).tolist()

        self.best_index_ = int(np.argmax(test_scores))
        self.best_score_ = float(test_scores[self.best_index_])
        self.best_params_ = self.cv_results_["params"][self.best_index_]

        self.best_estimator_ = clone(self.estimator)
        if self.best_params_:
            self.best_estimator_.set_params(**self.best_params_)
        self.best_estimator_.fit(X, y)

        return self

    @abstractmethod
    def fit(self, X: np.ndarray, y: np.ndarray) -> "BaseSearchCV":
        """
        Executes the hyperparameter search
        """
        pass

    def predict(self, X: np.ndarray) -> np.ndarray:
        if self.best_estimator_ is None:
            raise ValueError("This search instance is not fitted yet. Call 'fit' before using this estimator.")
        return self.best_estimator_.predict(X)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if self.best_estimator_ is None:
            raise ValueError("This search instance is not fitted yet. Call 'fit' before using this estimator.")
        if not hasattr(self.best_estimator_, "predict_proba"):
            raise AttributeError(f"Estimator {self.best_estimator_.__class__.__name__} has no predict_proba method.")
        return self.best_estimator_.predict_proba(X)
