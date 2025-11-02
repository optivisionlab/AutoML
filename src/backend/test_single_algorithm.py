"""
Test a single algorithm - useful for debugging
Usage: python test_single_algorithm.py [grid|bayesian|genetic]
"""
import sys
import pandas as pd
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import accuracy_score, classification_report

from automl.search.strategy.grid_search import GridSearchStrategy
from automl.search.strategy.bayesian_search import BayesianSearchStrategy
from automl.search.strategy.genetic_algorithm import GeneticAlgorithm


def load_data():
    """Load and prepare data."""
    train_csv = 'assets/online_shoppers/online_shoppers_intention.csv'
    test_csv = 'assets/online_shoppers/online_Shoppers_testing.csv'
    
    # Load training data
    df_train = pd.read_csv(train_csv)
    df_test = pd.read_csv(test_csv)
    
    # Encode categorical variables
    label_encoders = {}
    categorical_cols = ['Month', 'VisitorType', 'Weekend', 'Revenue']
    
    for col in categorical_cols:
        if col in df_train.columns:
            le = LabelEncoder()
            df_train[col] = le.fit_transform(df_train[col].astype(str))
            df_test[col] = le.transform(df_test[col].astype(str))
            label_encoders[col] = le
    
    X_train = df_train.drop('Revenue', axis=1)
    y_train = df_train['Revenue']
    X_test = df_test.drop('Revenue', axis=1)
    y_test = df_test['Revenue']
    
    # Use subset for faster testing
    X_train, _, y_train, _ = train_test_split(
        X_train, y_train, train_size=0.1, random_state=42, stratify=y_train
    )
    
    return X_train.values, y_train.values, X_test.values, y_test.values


def test_grid_search(X_train, y_train, X_test, y_test):
    """Test Grid Search."""
    print("Testing Grid Search...")
    
    model = DecisionTreeClassifier(random_state=42)
    param_grid = {
        'max_depth': [3, 5, 7],
        'min_samples_split': [2, 5]
    }
    
    strategy = GridSearchStrategy(cv=3, scoring='accuracy', n_jobs=-1, verbose=1)
    best_params, best_score, _, _ = strategy.search(model, param_grid, X_train, y_train)
    
    # Train and test
    final_model = DecisionTreeClassifier(random_state=42, **best_params)
    final_model.fit(X_train, y_train)
    y_pred = final_model.predict(X_test)
    
    print(f"\nBest Params: {best_params}")
    print(f"CV Score: {best_score:.4f}")
    print(f"Test Accuracy: {accuracy_score(y_test, y_pred):.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, zero_division=0))


def test_bayesian_search(X_train, y_train, X_test, y_test):
    """Test Bayesian Search."""
    print("Testing Bayesian Search...")
    
    from skopt.space import Integer
    
    model = DecisionTreeClassifier(random_state=42)
    param_grid = {
        'max_depth': Integer(3, 10, name='max_depth'),
        'min_samples_split': Integer(2, 10, name='min_samples_split')
    }
    
    strategy = BayesianSearchStrategy(
        n_calls=10, cv=3, scoring='accuracy', n_jobs=-1, verbose=1, random_state=42
    )
    best_params, best_score, _, _ = strategy.search(model, param_grid, X_train, y_train)
    
    # Train and test
    final_model = DecisionTreeClassifier(random_state=42, **best_params)
    final_model.fit(X_train, y_train)
    y_pred = final_model.predict(X_test)
    
    print(f"\nBest Params: {best_params}")
    print(f"CV Score: {best_score:.4f}")
    print(f"Test Accuracy: {accuracy_score(y_test, y_pred):.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, zero_division=0))


def test_genetic_algorithm(X_train, y_train, X_test, y_test):
    """Test Genetic Algorithm."""
    print("Testing Genetic Algorithm...")
    
    model = DecisionTreeClassifier(random_state=42)
    param_grid = {
        'max_depth': [3, 5, 7, 10],
        'min_samples_split': (2, 10)
    }
    
    strategy = GeneticAlgorithm(
        population_size=8, generation=5, cv=3, scoring='accuracy',
        n_jobs=-1, verbose=1, random_state=42
    )
    best_params, best_score, _, _ = strategy.search(model, param_grid, X_train, y_train)
    
    # Train and test
    final_model = DecisionTreeClassifier(random_state=42, **best_params)
    final_model.fit(X_train, y_train)
    y_pred = final_model.predict(X_test)
    
    print(f"\nBest Params: {best_params}")
    print(f"CV Score: {best_score:.4f}")
    print(f"Test Accuracy: {accuracy_score(y_test, y_pred):.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, zero_division=0))


def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage: python test_single_algorithm.py [grid|bayesian|genetic]")
        sys.exit(1)
    
    algorithm = sys.argv[1].lower()
    
    print("Loading data...")
    X_train, y_train, X_test, y_test = load_data()
    print(f"Train: {X_train.shape}, Test: {X_test.shape}\n")
    
    if algorithm == 'grid':
        test_grid_search(X_train, y_train, X_test, y_test)
    elif algorithm == 'bayesian':
        test_bayesian_search(X_train, y_train, X_test, y_test)
    elif algorithm == 'genetic':
        test_genetic_algorithm(X_train, y_train, X_test, y_test)
    else:
        print(f"Unknown algorithm: {algorithm}")
        print("Available: grid, bayesian, genetic")
        sys.exit(1)


if __name__ == "__main__":
    main()
