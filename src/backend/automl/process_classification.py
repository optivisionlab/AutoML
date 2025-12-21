from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler, OneHotEncoder, LabelEncoder, FunctionTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
import pandas as pd
import numpy as np


# helper function
def detect_column_types(df: pd.DataFrame, text_cardinality_threshold: int = 50):
    numeric_cols = []
    categorical_cols = []
    text_cols = []
    
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            numeric_cols.append(col)
        elif pd.api.types.is_object_dtype(df[col]) or isinstance(df[col].dtype, pd.CategoricalDtype):
            if df[col].nunique() > text_cardinality_threshold:
                text_cols.append(col)
            else:
                categorical_cols.append(col)

    return numeric_cols, categorical_cols, text_cols


def to_1d_array(x):
    if hasattr(x, 'values'):
        return x.values.ravel()
    if isinstance(x, np.ndarray):
        return x.ravel()
    return np.array(x).ravel()

def convert_to_string(x):
    return str(x)


# pipeline definitions
numeric_transformer = Pipeline(steps=[
    ('imputer', SimpleImputer(strategy='median')),
    ('scaler', StandardScaler())
])

categorical_transformer = Pipeline(steps=[
    ('imputer', SimpleImputer(strategy='most_frequent')),
    ('onehot', OneHotEncoder(handle_unknown='ignore', sparse_output=True))
])

text_transformer = Pipeline(steps=[
    ('imputer', SimpleImputer(strategy='constant', fill_value='')),
    ('reshape', FunctionTransformer(to_1d_array, validate=False)),
    ('tfidf', TfidfVectorizer(max_features=50, preprocessor=convert_to_string))
])


# main function
def preprocess_data(list_feature: list, target: str, data: pd.DataFrame):
    try:
        data_process = data[list_feature].copy()
    except KeyError as ke:
        raise KeyError(f"Not found feature {str(ke)}")
    
    numeric_cols, categorical_cols, text_cols = detect_column_types(data_process)

    transformers = []

    if numeric_cols:
        transformers.append(('num', numeric_transformer, numeric_cols))

    if categorical_cols:
        transformers.append(('cat', categorical_transformer, categorical_cols))

    if text_cols:
        for col in text_cols:
            transformers.append((f"text_{col}", text_transformer, [col]))

    if not transformers:
        X_processed = data_process.values
        preprocessor = None
    else:
        preprocessor = ColumnTransformer(
            transformers=transformers,
            remainder='passthrough',
            sparse_threshold=0.3
        )
        X_processed = preprocessor.fit_transform(data_process)

    if hasattr(X_processed, "toarray"):
            X_processed = X_processed.toarray()

    if target in data.columns:
        le_target = LabelEncoder()
        y_imputed_as_str = data[target].fillna('').astype(str)
        y_processed = le_target.fit_transform(y_imputed_as_str)
    else:
        raise KeyError(f"Target '{target}' not exsist")

    return X_processed, y_processed, preprocessor, le_target
