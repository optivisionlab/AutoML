# Third-party Libraries
from pydantic import BaseModel, Field


class CVStrategyConfig(BaseModel):
    """
    Configuration model for 3-Tier Cross-Validation Strategy
    """
    tier: int = Field(..., description="CV Tier level: 1 (Small), 2 (Medium), 3 (Large)")
    name: str = Field(..., description="Name of the cross-validation strategy")
    n_splits: int = Field(5, description="Number of folds/splits")
    n_repeats: int | None = Field(None, description="Number of repeats for RepeatedStratifiedKFold")
    has_holdout: bool = Field(False, description="Whether a separate holdout test set is extracted")
    test_size: float | None = Field(None, description="Ratio of holdout test set if Tier 3")
    description: str = Field(..., description="Human-readable description of the strategy")

    model_config = {
        "populate_by_name": True,
        "from_attributes": True
    }

class TimeSeriesConfig(CVStrategyConfig):
    """
    Cross-validation strategy of one-step time series forecasting, plus the feature settings chosen from the data
    """
    time_column: str = Field(..., description="Datetime column of a single, regularly sampled series")
    lags: list[int] = Field(..., description="Lags of the target used as features")
    rolling_windows: list[int] = Field(..., description="Windows of rolling mean/std over past target values")
    gap: int = Field(0, description="Samples skipped between train and validation of each chronological fold")
    max_train_size: int | None = Field(None, description="Maximum train window of a chronological fold")
    fold_test_size: int | None = Field(None, description="Validation window size of a chronological fold")
