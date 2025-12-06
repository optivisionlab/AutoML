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
            if df[col].nunique() > text_cardinality_threshold:
                text_cols.append(col)
            else:
                categorical_cols.append(col)
    return numeric_cols, categorical_cols, text_cols

def convert_to_string(x):
    return str(x) if x is not None else ""

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


# =========================================================================
def preprocess_data(list_feature: list, target: str, data: pd.DataFrame):    
    # Loại bỏ dòng mà target bị thiếu trước
    data = data.dropna(subset=[target]).copy()

    # Ép kiểu target sang số thực. 'coerce' biến chữ cái/lỗi thành NaN
    y_series = pd.to_numeric(data[target], errors='coerce')
    
    # Lọc bỏ các dòng bị NaN sau khi ép kiểu
    valid_indices = y_series.notna()
    data = data.loc[valid_indices]
    
    y_processed = y_series[valid_indices].values

    data_process = data[list_feature]
    numeric_cols, categorical_cols, text_cols = detect_column_types(data_process)

    transformers_list = [
        ('num', numeric_transformer, numeric_cols),
        ('cat', categorical_transformer, categorical_cols)
    ]
    
    # Thêm text transformer nếu có cột text (để tránh lỗi)
    if text_cols:
        transformers_list.append(('text', text_transformer, text_cols[0]))

    preprocessor = ColumnTransformer(
        transformers=transformers_list,
        remainder='drop' # Chỉ giữ lại các cột đã xử lý
    )

    X_processed = preprocessor.fit_transform(data_process)

    le_target = None

    return X_processed, y_processed, preprocessor, le_target
# =========================================================================
