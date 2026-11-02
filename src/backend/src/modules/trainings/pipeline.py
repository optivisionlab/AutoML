# Standard Libraries
import json
import math
from datetime import datetime, timezone
from typing import Any

# Local Libraries
from src.core import constants


PIPELINE_VERSION = "2.0.0"

# Score recorded by BaseSearchCV when a metric cannot be computed or a trial is pruned
FAILED_SCORE_SENTINEL = -1e6

TERMINAL_STATUSES = frozenset({"succeeded", "failed", "skipped", "cancelled"})

# Node key -> (display name, kind, depends_on)
PIPELINE_NODES: dict[str, tuple[str, str, list[str]]] = {
    "read_dataset": ("Read dataset", "data_loading", []),
    "split_holdout_data": ("Split holdout data", "data_splitting", ["read_dataset"]),
    "preprocessing": ("Preprocessing", "preprocessing", ["split_holdout_data"]),
    "model_selection": ("Model selection", "model_selection", ["preprocessing"]),
    "train": ("Train models", "model_training", ["model_selection"]),
    "select_best": ("Select best model", "model_selection", ["train"]),
    "save_result": ("Save result", "result_storage", ["select_best"]),
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def metric_direction(metric: str) -> str:
    return "minimize" if metric in constants.LOWER_IS_BETTER_METRICS else "maximize"


def normalize_score(metric: str, raw: Any) -> float | None:
    """
    Converts a raw scorer value to its natural scale: error metrics are stored negated by sklearn scorers.
    Returns None for missing, non-finite or sentinel (failed) values.
    """
    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value) or value == FAILED_SCORE_SENTINEL:
        return None
    return abs(value) if metric in constants.LOWER_IS_BETTER_METRICS else value


def build_trials(
    trials_history: list[dict[str, Any]],
    best_index: int | None,
    metric_list: list[str],
    clean_params: Any = None,
) -> tuple[list[dict[str, Any]], int | None]:
    """
    Converts BaseSearchCV.trials_history_ into pipeline trials (one entry per distinct parameter set,
    in first-evaluation order) and remaps the search's best_index_ onto the de-duplicated list.
    """
    metrics = [m.lower().strip().replace(" ", "_") for m in metric_list]
    trials: list[dict[str, Any]] = []
    position_by_key: dict[str, int] = {}
    best_key: str | None = None

    for index, record in enumerate(trials_history):
        params = record.get("params") or {}
        if clean_params is not None:
            params = clean_params(params)
        key = json.dumps(params, sort_keys=True, default=str)
        if index == best_index:
            best_key = key
        if key in position_by_key:
            continue

        is_pruned = bool(record.get("is_pruned", False))
        raw_scores = record.get("scores") or {}
        position_by_key[key] = len(trials)
        trials.append({
            "params": params,
            "status": "pruned" if is_pruned else "succeeded",
            "scores": {
                m: None if is_pruned else normalize_score(m, raw_scores.get(m))
                for m in metrics
            },
        })

    best_trial = position_by_key.get(best_key) if best_key is not None else None
    return trials, best_trial


class PipelineTracker:
    """
    Builds the training pipeline JSON stored in tbl_Job.pipeline: job-level fields plus one entry per node,
    each with the same common keys (name, kind, depends_on, status, started_at, finished_at, error, params, output).
    """

    def __init__(
        self,
        job_id: str,
        dataset_id: str,
        problem_type: str,
        search_algorithm: str,
        metric_sort: str | None,
        target: str | None,
        feature_cols: list[str] | None,
        timeout: int | None,
    ):
        self.data: dict[str, Any] = {
            "job_id": job_id,
            "version": PIPELINE_VERSION,
            "mode": "automl",
            "source": "tracked",
            "status": "running",
            "error": None,
            "updated_at": _now_iso(),
        }
        for key, (name, kind, depends_on) in PIPELINE_NODES.items():
            self.data[key] = {
                "name": name,
                "kind": kind,
                "depends_on": list(depends_on),
                "status": "queued",
                "started_at": None,
                "finished_at": None,
                "error": None,
                "params": {},
                "output": {},
            }

        self.data["read_dataset"]["params"] = {"id_data": dataset_id, "format": "parquet"}
        self.data["preprocessing"]["params"] = {"target": target, "list_feature": feature_cols or []}
        self.data["model_selection"]["params"] = {
            "problem_type": problem_type,
            "search_algorithm": search_algorithm,
            "metric_sort": metric_sort,
            "timeout": timeout,
        }
        self.data["save_result"]["params"] = {"bucket_name": "models"}
        self.data["train"]["output"] = {"models": {}}

    def node(self, key: str) -> dict[str, Any]:
        return self.data[key]

    def start(self, key: str) -> None:
        node = self.data[key]
        node["status"] = "running"
        node["started_at"] = _now_iso()
        self._touch()

    def finish(self, key: str, output: dict[str, Any] | None = None, status: str = "succeeded") -> None:
        node = self.data[key]
        if node["started_at"] is None:
            node["started_at"] = _now_iso()
        node["status"] = status
        node["finished_at"] = _now_iso()
        if output:
            node["output"].update(output)
        self._touch()

    def skip(self, key: str, output: dict[str, Any] | None = None) -> None:
        node = self.data[key]
        node["status"] = "skipped"
        if node["started_at"] is not None:
            node["finished_at"] = _now_iso()
        if output:
            node["output"].update(output)
        self._touch()

    def set_models(self, metric_list: list[str], model_names: list[str], metric_sort: str) -> None:
        """
        Declares candidate models and metrics; every model starts queued with empty results.
        """
        params = self.data["model_selection"]["params"]
        params["metric_sort"] = metric_sort
        params["model_names"] = list(model_names)
        params["metrics"] = {m: metric_direction(m) for m in metric_list}
        self.data["train"]["output"]["models"] = {
            name: {"status": "queued", "error": None, "best_trial": None, "trials": None, "holdout_scores": None}
            for name in model_names
        }

    def set_model_status(self, model_name: str, status: str) -> None:
        self.data["train"]["output"]["models"][model_name]["status"] = status

    def set_model_result(
        self,
        model_name: str,
        trials: list[dict[str, Any]] | None,
        best_trial: int | None,
        holdout_scores: dict[str, float] | None = None,
    ) -> None:
        self.data["train"]["output"]["models"][model_name].update({
            "status": "succeeded",
            "error": None,
            "best_trial": best_trial,
            "trials": trials,
            "holdout_scores": holdout_scores,
        })

    def set_model_error(self, model_name: str, message: str) -> None:
        self.data["train"]["output"]["models"][model_name].update({
            "status": "failed",
            "error": {"message": message},
        })

    def complete(self) -> None:
        self.data["status"] = "succeeded"
        self._touch()

    def abort(self, message: str, status: str = "failed") -> None:
        """
        Marks the running node (and the job) as failed or cancelled; nodes that never started are skipped.
        """
        for key in PIPELINE_NODES:
            node = self.data[key]
            if node["status"] == "running":
                node["status"] = status
                node["finished_at"] = _now_iso()
                node["error"] = {"message": message}
            elif node["status"] == "queued":
                node["status"] = "skipped"
        for model in self.data["train"]["output"]["models"].values():
            if model["status"] in ("queued", "running"):
                model["status"] = status
        self.data["status"] = status
        self.data["error"] = {"message": message}
        self._touch()

    def to_dict(self) -> dict[str, Any]:
        return self.data

    def _touch(self) -> None:
        self.data["updated_at"] = _now_iso()


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _legacy_job_status(job_doc: dict[str, Any]) -> int:
    """
    Job status as JobStatus; older documents may store it as a string or omit it (the old engine only saved
    finished jobs).
    """
    try:
        return int(job_doc["status"])
    except (KeyError, TypeError, ValueError):
        return constants.JobStatus.SUCCESS if job_doc.get("orther_model_scores") else constants.JobStatus.RUNNING


def _legacy_model_name(value: Any) -> str | None:
    """
    Model class name; the old engine stored str(estimator), e.g. "RandomForestClassifier(max_depth=5)".
    """
    return str(value).split("(", 1)[0].strip() or None if value else None


def pipeline_from_job(job_doc: dict[str, Any]) -> dict[str, Any]:
    """
    Builds the pipeline JSON for a job without a stored one: a job still waiting for a worker (all nodes queued),
    or a job trained before pipeline tracking (source "legacy"), whose results only hold each model's best
    parameter set, so every model has a single trial. Tolerates documents written by older backends
    (model bytes stored inline, estimator repr as best_model, string status).
    """
    config = _as_dict(job_doc.get("config"))
    if isinstance(config.get("config"), dict):
        config = config["config"]

    tracker = PipelineTracker(
        job_id=str(job_doc.get("_id", "")),
        dataset_id=_as_dict(job_doc.get("data")).get("id"),
        problem_type=config.get("problem_type"),
        search_algorithm=config.get("search_algorithm"),
        metric_sort=config.get("metric_sort"),
        target=config.get("target"),
        feature_cols=config.get("list_feature"),
        timeout=config.get("timeout") or None,
    )
    data = tracker.data
    job_status = _legacy_job_status(job_doc)

    if job_status == constants.JobStatus.RUNNING:
        data["status"] = "queued"
        return data

    data["source"] = "legacy"
    if job_status in (constants.JobStatus.FAILED, constants.JobStatus.CANCELLED):
        # The failing step was not recorded, so no node is marked as the cause
        status = "failed" if job_status == constants.JobStatus.FAILED else "cancelled"
        for key in PIPELINE_NODES:
            data[key]["status"] = "skipped"
        data["status"] = status
        data["error"] = {"message": job_doc.get("infor") or f"Training job {status}."}
        return data

    model_scores = [m for m in job_doc.get("orther_model_scores") or [] if isinstance(m, dict) and m.get("model_name")]
    metric_list = list(dict.fromkeys(metric for m in model_scores for metric in _as_dict(m.get("scores"))))
    metric_sort = config.get("metric_sort") or (metric_list[0] if metric_list else None)
    tracker.set_models(metric_list, [m["model_name"] for m in model_scores], metric_sort)
    for m in model_scores:
        scores = _as_dict(m.get("scores"))
        trial = {
            "params": _as_dict(m.get("best_params")),
            "status": "succeeded",
            "scores": {metric: normalize_score(metric, scores.get(metric)) for metric in metric_list},
        }
        tracker.set_model_result(m["model_name"], trials=[trial], best_trial=0)

    for key in PIPELINE_NODES:
        data[key]["status"] = "succeeded"
    # Whether the scores came from a holdout split was not recorded
    data["select_best"]["output"] = {"best_model": _legacy_model_name(job_doc.get("best_model")), "score_source": None}
    # The old engine kept the pickled model inline (bytes) instead of a storage reference
    data["save_result"]["output"] = {"object_name": _as_dict(job_doc.get("model")).get("object_name")}
    data["status"] = "succeeded"
    return data
