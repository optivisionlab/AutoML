import pandas as pd
import numpy as np
from sklearn.svm import SVC
from sklearn.model_selection import GridSearchCV
from sklearn.datasets import make_classification
from sklearn.preprocessing import StandardScaler, scale
from search_algorithms import grid_search

X, y = make_classification(n_samples=1000, n_features= 20, n_classes=2, random_state=42)
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

param_grid = {
    'C': [0.1, 1, 10],
    'kernel': ['linear', 'rbf'],
    'gamma': ['scale', 'auto']
}

print("Running Custom Grid Search...")
best_params_custom, best_score_custom, best_all_scores_custom, cv_results_custom = grid_search(
    param_grid=param_grid,
    model_func=SVC,
    data=X_scaled,
    targets=y,
    cv=5,
    metric_sort='accuracy'
)

print("Running Sklearn GridSearchCV...")
grid_search_sklearn = GridSearchCV (
    SVC(random_state=42),
    param_grid=param_grid,
    cv=5,
    scoring=['accuracy', 'precision_macro', 'recall_macro', 'f1_macro'],
    refit='accuracy'
)
grid_search_sklearn.fit(X_scaled, y)

sklearn_results = []
custom_results = []

print("Processing Custom Grid Search results...")
for i, params in enumerate(grid_search_sklearn.cv_results_['params']):
    row = {
        "Method" : "GridSearchCV",
        'C': params['C'],
        'kernel': params['kernel'],
        'gamma': params['gamma'],
        'Accuracy': round(grid_search_sklearn.cv_results_['mean_test_accuracy'][i], 4),
        'Precision': round(grid_search_sklearn.cv_results_['mean_test_precision_macro'][i], 4),
        'Recall': round(grid_search_sklearn.cv_results_['mean_test_recall_macro'][i], 4),
        'F1-Score': round(grid_search_sklearn.cv_results_['mean_test_f1_macro'][i], 4)
    }
    custom_results.append(row)

print("Processing Sklean Library results...")
for i, params in enumerate(grid_search_sklearn.cv_results_['params']):
    row = {
        "Method" : "Custom Grid Search",
        'C': params['C'],
        'kernel': params['kernel'],
        'gamma': params['gamma'],
        'Accuracy': round(grid_search_sklearn.cv_results_['mean_test_accuracy'][i], 4),
        'Precision': round(grid_search_sklearn.cv_results_['mean_test_precision_macro'][i], 4),
        'Recall': round(grid_search_sklearn.cv_results_['mean_test_recall_macro'][i], 4),
        'F1-Score': round(grid_search_sklearn.cv_results_['mean_test_f1_macro'][i], 4)
    }
    sklearn_results.append(row)

df_custom = pd.DataFrame(custom_results)
df_sklearn = pd.DataFrame(sklearn_results)

df_custom = df_custom.sort_values(['C', 'kernel', 'gamma'])
df_sklearn = df_sklearn.sort_values(['C', 'kernel', 'gamma'])

df_custom.to_csv('custom_grid_search.csv', index=False)
df_sklearn.to_csv('sklearn_grid_search.csv', index=False)

print("="*60)
print("RESULTS SAVED TO SEPARATE FILES")
print("="*60)
print("🔧 CUSTOM GRID SEARCH RESULTS")
print("   File: custom_grid_search_results.csv")
print(df_custom)

print("\n" + "="*60)
print("📚 SKLEARN GRID_SEARCH_CV RESULTS")
print("   File: sklearn_grid_search_cv_results.csv")
print(df_sklearn)

print("\n" + "="*60)
print("BEST SCORES COMPARISON")
print("="*60)
print(f"🔧 CUSTOM Grid Search Best Score: {best_score_custom:.4f}")
print(f"📚 SKLEARN GridSearchCV Best Score: {grid_search_sklearn.best_score_:.4f}")
print("="*60)