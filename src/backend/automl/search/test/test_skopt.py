import sys
import os

from skopt.space import Real, Categorical

sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import cross_validate
from datasets import load_dataset

from automl.search.strategies.bayesian_search import BayesianSearchStrategy
from ucimlrepo import fetch_ucirepo

def load_iris_data():
    """Load and prepare the iris dataset."""
    # Construct the path to the data file relative to this script's location
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(base_dir, '../../../assets/iris.data.csv')

    # Load the iris dataset
    df = pd.read_csv(data_path)

    # Separate features and target
    X = df.drop('class', axis=1).values
    y = df['class'].values

    # Encode the target labels
    le = LabelEncoder()
    y = le.fit_transform(y)

    return X, y

def load_shopping_data():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(base_dir, '../../../assets/online_shoppers/online_shoppers_intention.csv')

    df = pd.read_csv(data_path)

    X = df.drop('Revenue', axis=1)
    y = df['Revenue'].values

    categorical_cols = ['Month', 'OperatingSystems', 'Browser', 'Region',
                        'TrafficType', 'VisitorType', 'Weekend']
    X = pd.get_dummies(X, columns=categorical_cols, drop_first=True)

    X = X.values

    # Encode target (if not already 0/1)
    le = LabelEncoder()
    y = le.fit_transform(y)

    return X, y

def load_glass_data():
    # fetch dataset
    glass_identification = fetch_ucirepo(id=42)

    # data (as pandas dataframes)
    X = glass_identification.data.features
    y = glass_identification.data.targets

    X = X.values
    y = y.values.ravel()

    return X, y


def run_test():
    """Run the genetic algorithm test with iris dataset."""
    # Load the data
    X, y = load_glass_data()

    # Initialize the genetic algorithm
    opt = BayesianSearchStrategy(
        n_calls=30,
        cv=5,
        scoring='roc_auc',
        n_jobs=-1,
        verbose=1,
        random_state=42,
        save_log=True,
        log_dir='logs'
    )

    # Define different models and their parameter grids to test
    test_cases = [
        {
            'model': RandomForestClassifier(random_state=42),
            'param_grid': {
                'n_estimators': [10, 50, 100, 200],
                'max_depth': [3, 5, 7, 10, None],
                'min_samples_split': [2, 5, 10],
                'min_samples_leaf': [1, 2, 4]
            }
        },
        {
            'model': SVC(random_state=42, probability=True),
            'param_grid': {
                'C': Real(0.01, 100.0, prior='log-uniform'),  # Remove name parameter
                'gamma': Categorical(['scale', 'auto']),
                'kernel': Categorical(['rbf', 'linear', 'poly'])
            }
        },
        {
            'model': DecisionTreeClassifier(random_state=42),
            'param_grid': {
                'max_depth': [3, 5, 7, 10, 15],
                'min_samples_split': [2, 5, 10, 20],
                'min_samples_leaf': [1, 2, 4, 8],
                'criterion': ['gini', 'entropy']
            }
        }
    ]

    all_results = []
    scoring_metrics = ['accuracy', 'precision_macro', 'recall_macro', 'f1_macro']
    output_file = 'opt_test_results.csv'

    # Run tests for each model
    for i, test_case in enumerate(test_cases, 1):
        model_name = test_case['model'].__class__.__name__
        print(f"\n{'=' * 60}")
        print(f"Running Test {i}: {model_name}")
        print(f"{'=' * 60}")

        try:
            # Run the genetic algorithm search
            best_params, best_f1_score, _ = opt.search(
                model=test_case['model'],
                param_grid=test_case['param_grid'],
                X=X,
                y=y)

            best_model = test_case['model'].set_params(**best_params)

            cv_scores = cross_validate(best_model, X, y, cv=opt.config['cv'], scoring=scoring_metrics,
                                       n_jobs=opt.config['n_jobs'])

            # Store results
            result_row = {
                'model': model_name,
                'run_type': 'genetic_algorithm',
                'best_params': str(best_params),
                'accuracy': cv_scores['test_accuracy'].mean(),
                'precision': cv_scores['test_precision_macro'].mean(),
                'recall': cv_scores['test_recall_macro'].mean(),
                'f1': cv_scores['test_f1_macro'].mean()
            }

            all_results.append(result_row)

            print(f"\nResults for {model_name}:")
            print(f"Best Parameters: {best_params}")
            print(f"Best F1 Score (from search): {best_f1_score:.4f}")
            print(f"Cross-validated Accuracy: {result_row['accuracy']:.4f}")
            print(f"Cross-validated F1: {result_row['f1']:.4f}")

        except Exception as e:
            print(f"Error occurred during test {i}: {e}")

    # Save all results to a CSV file
    if all_results:
        df = pd.DataFrame(all_results)
        df.to_csv(output_file, index=False)
        print(f"\nAll results saved to: {output_file}")
    else:
        print("\nNo results to save.")

# Main execution
if __name__ == "__main__":
    run_test()
