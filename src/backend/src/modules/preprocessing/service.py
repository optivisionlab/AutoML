# Standard Libraries
import logging

# Third-party Libraries
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

# Local Libraries
from src.modules.preprocessing.schemas import CVStrategyConfig


# Logging
logger = logging.getLogger(__name__)


class TabularPreprocessor:
    """
    Service for tabular data cleaning, encoding, scaling, and 3-Tier CV strategy preparation
    """
    @staticmethod
    def determine_cv_tier(n_rows: int, min_class_count: int = 5) -> CVStrategyConfig:
        """
        Determine the Cross-Validation tier and configuration based on row count and class balance

        Tier 1 (30 - 500 rows): RepeatedStratifiedKFold (5 splits, 5 repeats)
        Tier 2 (501 - 10,000 rows): StratifiedKFold (5 splits)
        Tier 3 (> 10,000 rows): Train/Test Split (80/20) + StratifiedKFold on Train
        """
        # Ensure n_splits does not exceed smallest class sample count
        safe_splits = max(2, min(5, min_class_count))

        if n_rows <= 500:
            return CVStrategyConfig(
                tier=1,
                name="RepeatedStratifiedKFold",
                n_splits=safe_splits,
                n_repeats=5,
                has_holdout=False,
                description=f"Tier 1 (30 - 500 rows): RepeatedStratifiedKFold ({safe_splits} splits, 5 repeats)"
            )
        elif n_rows <= 10000:
            return CVStrategyConfig(
                tier=2,
                name="StratifiedKFold",
                n_splits=safe_splits,
                has_holdout=False,
                description=f"Tier 2 (501 - 10,000 rows): StratifiedKFold ({safe_splits} splits)"
            )
        else:
            return CVStrategyConfig(
                tier=3,
                name="TrainTestSplit+StratifiedKFold",
                test_size=0.2,
                n_splits=safe_splits,
                has_holdout=True,
                description=f"Tier 3 (> 10,000 rows): Train-Test Split (80/20) + StratifiedKFold ({safe_splits} splits)"
            )

    @classmethod
    def prepare_data(
        cls,
        df: pd.DataFrame,
        target_col: str,
        feature_cols: list[str] | None = None,
        random_state: int = 42
    ) -> tuple[tuple[np.ndarray, np.ndarray], tuple[np.ndarray, np.ndarray] | None, CVStrategyConfig, list[str]]:
        """
        Cleans data, encodes categorical features/target, performs scaling, 
        and prepares train/test splits based on the 3-Tier CV strategy
        """
        data = df.copy()

        if target_col not in data.columns:
            raise ValueError(f"Target column '{target_col}' not found in dataset columns: {list(data.columns)}")

        # Determine feature columns
        if not feature_cols:
            feature_cols = [col for col in data.columns if col != target_col]
        else:
            feature_cols = [col for col in feature_cols if col in data.columns and col != target_col]

        if not feature_cols:
            raise ValueError("No valid feature columns specified for training.")

        # Encode Target variable cleanly with LabelEncoder
        y_raw = data[target_col]
        valid_mask = ~y_raw.isna()
        if not valid_mask.all():
            data = data[valid_mask].reset_index(drop=True)
            y_raw = data[target_col]

        target_encoder = LabelEncoder()
        y = target_encoder.fit_transform(y_raw)

        # Check minimum class count
        unique_classes, class_counts = np.unique(y, return_counts=True)
        min_class_count = int(np.min(class_counts)) if len(class_counts) > 0 else 5

        # Encode categorical feature columns & handle missing values
        X_df = data[feature_cols].copy()
        for col in feature_cols:
            if X_df[col].dtype == "object" or X_df[col].dtype.name == "category":
                # Handle categorical missing values with mode
                mode_val = X_df[col].mode()
                fill_val = mode_val.iloc[0] if not mode_val.empty else "missing"
                X_df[col] = X_df[col].fillna(fill_val)
                le = LabelEncoder()
                X_df[col] = le.fit_transform(X_df[col].astype(str))
            else:
                # Handle numerical missing values with median
                median_val = X_df[col].median()
                X_df[col] = X_df[col].fillna(median_val if not pd.isna(median_val) else 0)

        # Determine CV Tier
        n_rows = len(data)
        cv_config = cls.determine_cv_tier(n_rows, min_class_count)

        # Split and Scale features
        if cv_config.has_holdout:
            # Tier 3: Train-Test Split with stratification
            test_size = cv_config.test_size or 0.2
            try:
                X_train_df, X_test_df, y_train, y_test = train_test_split(
                    X_df, y,
                    test_size=test_size,
                    stratify=y,
                    random_state=random_state
                )
            except ValueError:
                # Fallback without stratification if rare classes prevent stratified split
                X_train_df, X_test_df, y_train, y_test = train_test_split(
                    X_df, y,
                    test_size=test_size,
                    random_state=random_state
                )

            scaler = StandardScaler()
            X_train = scaler.fit_transform(X_train_df)
            X_test = scaler.transform(X_test_df)

            return (X_train, y_train), (X_test, y_test), cv_config, feature_cols
        else:
            # Tier 1 & Tier 2: Fit scaler on full dataset, CV handles validation
            scaler = StandardScaler()
            X_train = scaler.fit_transform(X_df)

            return (X_train, y), None, cv_config, feature_cols
