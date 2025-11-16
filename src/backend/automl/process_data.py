from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler, OneHotEncoder, LabelEncoder
from sklearn.feature_extraction.text import TfidfVectorizer
import pandas as pd

# =========================================================================
# PREPROCESS DATA
# =========================================================================
def detect_column_types(df: pd.DataFrame, text_cardinality_threshold: int = 50):
    numeric_cols = []
    categorical_cols = []
    text_cols = []
    
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            numeric_cols.append(col)
        elif pd.api.types.is_object_dtype(df[col]):
            unique_count = df[col].nunique()
            if unique_count > text_cardinality_threshold:
                text_cols.append(col)
            else:
                categorical_cols.append(col)

    return numeric_cols, categorical_cols, text_cols



def convert_to_string(x):
    return str(x)


# Pipeline
numeric_transformer = Pipeline(steps=[
    ('imputer', SimpleImputer(strategy='median')),
    ('scaler', StandardScaler())
])

categorical_transformer = Pipeline(steps=[
    ('imputer', SimpleImputer(strategy='most_frequent')),
    ('onehot', OneHotEncoder(handle_unknown='ignore', sparse_output=False))
])

text_transformer = Pipeline(steps=[
    ('imputer', SimpleImputer(strategy='constant', fill_value='')),
    ('tfidf', TfidfVectorizer(max_features=100, preprocessor=convert_to_string))
])


def preprocess_data(list_feature: list, target: str, data: pd.DataFrame):
    data_process = data[list_feature]
    numeric_cols, categorical_cols, text_cols = detect_column_types(data_process)

    preprocessor = ColumnTransformer(
        transformers=[
            ('num', numeric_transformer, numeric_cols),
            ('cat', categorical_transformer, categorical_cols),
            ('text', text_transformer, text_cols)
        ],
        remainder='passthrough'
    )

    X_processed = preprocessor.fit_transform(data_process)

    y_data = data[target]
    le_target = LabelEncoder()

    y_imputed_as_str = y_data.fillna('').astype(str)
    y_processed = le_target.fit_transform(y_imputed_as_str)

    return X_processed, y_processed, preprocessor, le_target
# =========================================================================
