# Standard Libraries
import time
import logging
from abc import ABC, abstractmethod
from typing import Any

# Third-party Libraries
import numpy as np
from sklearn.base import BaseEstimator, clone, is_classifier
from sklearn.model_selection import BaseCrossValidator, check_cv, cross_validate


# Logging
logger = logging.getLogger(__name__)


def convert_numpy_types(obj: Any) -> Any:
    """
    Recursively converts numpy data types to native Python types for JSON/BSON serialization.
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
    Base class for custom Hyperparameter Optimization (HPO) search algorithms.
    Provides standardized Cross-Validation evaluation, trial recording, real-time logging,
    and best estimator refitting compatible with Scikit-learn SearchCV interface.
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
        self.estimator = estimator
        self.param_grid = param_grid
        self.cv = cv
        self.scoring = scoring or {}
        self.refit = refit
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

    def _normalize_param_grid(self) -> list[dict[str, Any]]:
        """
        Normalizes param_grid input into a list of parameter dictionaries.
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
        Initializes the structure of cv_results_ dictionary.
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

    def _init_search(self, X: np.ndarray, y: np.ndarray) -> None:
        """
        Initializes the CV results structure and precomputes CV fold splits once
        to ensure identical, deterministic fold splits and maximum execution speed
        across all candidate evaluations.
        """
        self._init_cv_results()
        cv_splitter = check_cv(self.cv, y, classifier=is_classifier(self.estimator))
        self.cv_splits_ = list(cv_splitter.split(X, y))

    def _evaluate_candidate(
        self,
        candidate_params: dict[str, Any],
        X: np.ndarray,
        y: np.ndarray,
        trial_num: int | None = None,
        total_trials: int | None = None,
    ) -> tuple[dict[str, float], dict[str, float], float, float]:
        """
        Evaluates a single hyperparameter configuration using Cross-Validation,
        prints trial results in real-time, and returns computed metrics and execution times.
        """
        start_time = time.time()
        model_instance = clone(self.estimator)
        if candidate_params:
            model_instance.set_params(**candidate_params)

        cv_splits = self.cv_splits_ if self.cv_splits_ is not None else self.cv
        cv_output = cross_validate(
            estimator=model_instance,
            X=X,
            y=y,
            cv=cv_splits,
            scoring=self.scoring,
            n_jobs=self.n_jobs,
            error_score=0.0,
            return_train_score=False,
        )

        mean_scores = {
            metric: float(np.mean(cv_output[f"test_{metric}"])) if f"test_{metric}" in cv_output else 0.0
            for metric in self.scoring
        }
        std_scores = {
            metric: float(np.std(cv_output[f"test_{metric}"])) if f"test_{metric}" in cv_output else 0.0
            for metric in self.scoring
        }

        fit_time = float(np.mean(cv_output.get("fit_time", [0.0])))
        score_time = float(np.mean(cv_output.get("score_time", [0.0])))
        elapsed = time.time() - start_time

        if self.verbose > 0:
            trial_tag = f"[{trial_num}/{total_trials}] " if trial_num and total_trials else ""
            metrics_display = ", ".join(f"{k}: {v:.4f}" for k, v in mean_scores.items())
            logger.info(
                f"[{self.__class__.__name__}] {trial_tag}Params: {candidate_params} -> {metrics_display} (time: {elapsed:.2f}s)"
            )

        return mean_scores, std_scores, fit_time, score_time

    def _record_trial(
        self,
        candidate_params: dict[str, Any],
        mean_scores: dict[str, float],
        std_scores: dict[str, float],
        fit_time: float,
        score_time: float,
    ) -> None:
        """
        Records the evaluated trial metrics and parameters into trials_history_ and cv_results_.
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
        })

    def _finalize_search(self, X: np.ndarray, y: np.ndarray) -> "BaseSearchCV":
        """
        Computes metric ranks, identifies the best hyperparameter configuration,
        and refits the best estimator on the entire dataset.
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

        if self.verbose > 0:
            logger.info(
                f"[{self.__class__.__name__}] Best {self.refit}: {self.best_score_:.4f} with Params: {self.best_params_}"
            )

        return self

    @abstractmethod
    def fit(self, X: np.ndarray, y: np.ndarray) -> "BaseSearchCV":
        """
        Runs the search algorithm to find the optimal hyperparameters.
        """
        ...

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
