from dataclasses import asdict, dataclass, field
from typing import List, Dict, Any, Optional, TypedDict
from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if value.__class__.__name__ == "ObjectId":
        return str(value)
    return value

class DatasetEntry(TypedDict, total=False):
    id: str
    name: str
    n_rows: int
    n_cols: int
    problem_type_inferred: Optional[str]
    last_seen: datetime

class JobEntry(TypedDict, total=False):
    id: str
    dataset_id: str
    config: Dict[str, Any]
    status: str
    metrics: Dict[str, float]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]

@dataclass
class WorldState:
    user_id: str
    datasets: Dict[str, DatasetEntry] = field(default_factory=dict)
    jobs: Dict[str, JobEntry] = field(default_factory=dict)
    goals: List[Dict[str, Any]] = field(default_factory=list)
    updated_at: datetime = field(default_factory=utc_now)
    created_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        return _json_ready(asdict(self))
