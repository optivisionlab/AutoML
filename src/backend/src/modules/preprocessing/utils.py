# Third-party Libraries
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler, OneHotEncoder, FunctionTransformer
from sklearn.feature_extraction.text import TfidfVectorizer


def detect_column_types(df: pd.DataFrame, text_cardinality_threshold: int = 50) -> tuple[list[str], list[str], list[str]]:
    numeric_cols: list[str] = []
    categorical_cols: list[str] = []
    text_cols: list[str] = []

    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            numeric_cols.append(col)
        elif pd.api.types.is_object_dtype(df[col]) or isinstance(df[col].dtype, pd.CategoricalDtype) or pd.api.types.is_string_dtype(df[col]):
            if df[col].nunique() > text_cardinality_threshold:
                text_cols.append(col)
            else:
                categorical_cols.append(col)

    return numeric_cols, categorical_cols, text_cols


def to_1d_array(x):
    if hasattr(x, "values"):
        return x.values.ravel()
    if isinstance(x, np.ndarray):
        return x.ravel()
    return np.array(x).ravel()


def convert_to_string(x):
    return str(x) if x is not None else ""


def build_feature_column_transformer(
    numeric_cols: list[str],
    categorical_cols: list[str],
    text_cols: list[str],
) -> ColumnTransformer | None:
    transformers = []

    if numeric_cols:
        numeric_transformer = Pipeline(steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ])
        transformers.append(("num", numeric_transformer, numeric_cols))

    if categorical_cols:
        categorical_transformer = Pipeline(steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=True)),
        ])
        transformers.append(("cat", categorical_transformer, categorical_cols))

    if text_cols:
        for col in text_cols:
            text_transformer = Pipeline(steps=[
                ("imputer", SimpleImputer(strategy="constant", fill_value="")),
                ("reshape", FunctionTransformer(to_1d_array, validate=False)),
                ("tfidf", TfidfVectorizer(max_features=50, preprocessor=convert_to_string)),
            ])
            transformers.append((f"text_{col}", text_transformer, [col]))

    if not transformers:
        return None

    return ColumnTransformer(
        transformers=transformers,
        remainder="passthrough",
        sparse_threshold=0.3,
    )
