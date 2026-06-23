from typing import Dict, Any

from .schema import WorldState, DatasetEntry, JobEntry, utc_now

def apply_tool_output(state: WorldState, tool_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Parse tool output và trả về một patch cho world state."""
    patch = {}
    now = utc_now()

    if tool_name == "list_datasets" and "datasets" in payload:
        datasets_patch = state.datasets.copy()
        for ds in payload["datasets"]:
            if "id" in ds:
                datasets_patch[ds["id"]] = DatasetEntry(
                    id=ds["id"],
                    name=ds.get("name"),
                    n_rows=ds.get("n_rows"),
                    n_cols=ds.get("n_cols"),
                    last_seen=now
                )
        patch["datasets"] = datasets_patch

    elif tool_name == "get_dataset_info" and "id" in payload:
        dataset_id = payload["id"]
        if dataset_id in state.datasets:
            datasets_patch = state.datasets.copy()
            datasets_patch[dataset_id].update(payload)
            datasets_patch[dataset_id]["last_seen"] = now
            patch["datasets"] = datasets_patch

    elif tool_name == "list_jobs" and "jobs" in payload:
        jobs_patch = state.jobs.copy()
        for job in payload["jobs"]:
            if "id" in job:
                jobs_patch[job["id"]] = JobEntry(
                    id=job["id"],
                    dataset_id=job.get("dataset_id"),
                    status=job.get("status"),
                    started_at=job.get("started_at"),
                )
        patch["jobs"] = jobs_patch

    elif tool_name == "get_job_info" and "id" in payload:
        job_id = payload["id"]
        if job_id in state.jobs:
            jobs_patch = state.jobs.copy()
            jobs_patch[job_id].update(payload)
            patch["jobs"] = jobs_patch

    elif tool_name == "start_training" and "job_id" in payload:
        job_id = payload["job_id"]
        jobs_patch = state.jobs.copy()
        jobs_patch[job_id] = JobEntry(
            id=job_id,
            dataset_id=payload.get("dataset_id"),
            config=payload.get("config"),
            status="starting",
            started_at=now
        )
        patch["jobs"] = jobs_patch

    return patch
