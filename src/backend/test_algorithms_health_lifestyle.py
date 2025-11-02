"""
Test script for comparing 3 search algorithms on Health and Lifestyle dataset
Dataset: https://www.kaggle.com/datasets/chik0di/health-and-lifestyle-dataset

Algorithms tested:
1. Genetic Algorithm
2. Grid Search
3. Bayesian Search
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.linear_model import LogisticRegression
import time
import warnings
warnings.filterwarnings('ignore')

from automl.search.strategy.genetic_algorithm import GeneticAlgorithm
from automl.search.strategy.grid_search import GridSearchStrategy
from automl.search.strategy.bayesian_search import BayesianSearchStrategy


def load_and_preprocess_data(file_path='health_and_lifestyle_dataset.csv'):
    """Load and preprocess the Health and Lifestyle dataset"""
    print("Loading dataset...")
    
    # Check if file exists
    import os
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        print("\nPlease download the dataset first:")
        print("  1. Run: pip install kaggle")
        print("  2. Configure Kaggle API (see README)")
        print("  3. Run: python download_dataset.py")
        print("\nOr download manually from:")
        print("  https://www.kaggle.com/datasets/chik0di/health-and-lifestyle-dataset")
        print("\nAlternatively, use test_algorithms_simple.py for testing without dataset")
        raise FileNotFoundError(f"Dataset file not found: {file_path}")
    
    df = pd.read_csv(file_path)
    
    print(f"Dataset shape: {df.shape}")
    print(f"Columns: {df.columns.tolist()}")
    
    # Encode categorical variables
    label_encoders = {}
    categorical_columns = df.select_dtypes(include=['object']).columns
    
    for col in categorical_columns:
        if col != 'Health_Status':  # Assuming this is the target
            le = LabelEncoder()
            df[col] = le.fit_transform(df[col].astype(str))
            label_encoders[col] = le
    
    # Separate features and target
    # Adjust target column name based on actual dataset
    target_col = 'Health_Status' if 'Health_Status' in df.columns else df.columns[-1]
    
    X = df.drop(columns=[target_col])
    y = df[target_col]
    
    # Encode target if categorical
    if y.dtype == 'object':
        le_target = LabelEncoder()
        y = le_target.fit_transform(y)
        print(f"Target classes: {le_target.classes_}")
    
    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    print(f"Features shape: {X_scaled.shape}")
    print(f"Target shape: {y.shape}")
    print(f"Target distribution: {np.bincount(y)}")
    
    return X_scaled, y


def test_genetic_algorithm(X_train, y_train, model, param_grid):
    """Test Genetic Algorithm"""
    print("\n" + "="*60)
    print("TESTING GENETIC ALGORITHM")
    print("="*60)
    
    ga = GeneticAlgorithm(
        population_size=15,
        generation=10,
        cv=3,
        n_jobs=-1,
        verbose=1
    )
    
    start_time = time.time()
    best_params, best_score, best_all_scores, cv_results = ga.search(
        model=model,
        param_grid=param_grid,
        X=X_train,
        y=y_train
    )
    elapsed_time = time.time() - start_time
    
    print(f"\nBest Parameters: {best_params}")
    print(f"Best Score: {best_score:.4f}")
    print(f"All Scores: {best_all_scores}")
    print(f"Time Elapsed: {elapsed_time:.2f} seconds")
    
    return {
        'algorithm': 'Genetic Algorithm',
        'best_params': best_params,
        'best_score': best_score,
        'all_scores': best_all_scores,
        'time': elapsed_time
    }


def test_grid_search(X_train, y_train, model, param_grid):
    """Test Grid Search"""
    print("\n" + "="*60)
    print("TESTING GRID SEARCH")
    print("="*60)
    
    grid = GridSearchStrategy(
        cv=3,
        n_jobs=-1,
        verbose=1
    )
    
    start_time = time.time()
    best_params, best_score, best_all_scores, cv_results = grid.search(
        model=model,
        param_grid=param_grid,
        X=X_train,
        y=y_train
    )
    elapsed_time = time.time() - start_time
    
    print(f"\nBest Parameters: {best_params}")
    print(f"Best Score: {best_score:.4f}")
    print(f"All Scores: {best_all_scores}")
    print(f"Time Elapsed: {elapsed_time:.2f} seconds")
    
    return {
        'algorithm': 'Grid Search',
        'best_params': best_params,
        'best_score': best_score,
        'all_scores': best_all_scores,
        'time': elapsed_time
    }


def test_bayesian_search(X_train, y_train, model, param_grid_bayesian):
    """Test Bayesian Search"""
    print("\n" + "="*60)
    print("TESTING BAYESIAN SEARCH")
    print("="*60)
    
    from skopt.space import Integer, Real, Categorical
    
    bayesian = BayesianSearchStrategy(
        n_calls=20,
        cv=3,
        n_jobs=-1,
        verbose=1
    )
    
    start_time = time.time()
    best_params, best_score, best_all_scores, cv_results = bayesian.search(
        model=model,
        param_grid=param_grid_bayesian,
        X=X_train,
        y=y_train
    )
    elapsed_time = time.time() - start_time
    
    print(f"\nBest Parameters: {best_params}")
    print(f"Best Score: {best_score:.4f}")
    print(f"All Scores: {best_all_scores}")
    print(f"Time Elapsed: {elapsed_time:.2f} seconds")
    
    return {
        'algorithm': 'Bayesian Search',
        'best_params': best_params,
        'best_score': best_score,
        'all_scores': best_all_scores,
        'time': elapsed_time
    }


def compare_results(results):
    """Compare and display results from all algorithms"""
    print("\n" + "="*60)
    print("COMPARISON RESULTS")
    print("="*60)
    
    df_results = pd.DataFrame([
        {
            'Algorithm': r['algorithm'],
            'Best Score': r['best_score'],
            'Accuracy': r['all_scores'].get('accuracy', 0),
            'Precision': r['all_scores'].get('precision', 0),
            'Recall': r['all_scores'].get('recall', 0),
            'F1': r['all_scores'].get('f1', 0),
            'Time (s)': r['time']
        }
        for r in results
    ])
    
    print("\n", df_results.to_string(index=False))
    
    # Find best algorithm
    best_idx = df_results['Best Score'].idxmax()
    print(f"\n🏆 Best Algorithm: {df_results.loc[best_idx, 'Algorithm']}")
    print(f"   Score: {df_results.loc[best_idx, 'Best Score']:.4f}")
    print(f"   Time: {df_results.loc[best_idx, 'Time (s)']:.2f}s")
    
    return df_results


def main():
    """Main function to run all tests"""
    print("="*60)
    print("HEALTH AND LIFESTYLE DATASET - ALGORITHM COMPARISON")
    print("="*60)
    
    # Load data
    X, y = load_and_preprocess_data()
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    print(f"\nTrain size: {X_train.shape[0]}")
    print(f"Test size: {X_test.shape[0]}")
    
    # Define model and parameter grids
    model = RandomForestClassifier(random_state=42)
    
    # Parameter grid for GA and Grid Search
    param_grid = {
        'n_estimators': [50, 100, 150],
        'max_depth': [5, 10, 15, None],
        'min_samples_split': [2, 5, 10]
    }
    
    # Parameter grid for Bayesian Search (using skopt dimensions)
    from skopt.space import Integer, Categorical
    param_grid_bayesian = {
        'n_estimators': Integer(50, 150),
        'max_depth': Categorical([5, 10, 15, None]),
        'min_samples_split': Integer(2, 10)
    }
    
    # Run all algorithms
    results = []
    
    # Test 1: Genetic Algorithm
    try:
        result_ga = test_genetic_algorithm(X_train, y_train, model, param_grid)
        results.append(result_ga)
    except Exception as e:
        print(f"Error in Genetic Algorithm: {e}")
    
    # Test 2: Grid Search
    try:
        result_grid = test_grid_search(X_train, y_train, model, param_grid)
        results.append(result_grid)
    except Exception as e:
        print(f"Error in Grid Search: {e}")
    
    # Test 3: Bayesian Search
    try:
        result_bayesian = test_bayesian_search(X_train, y_train, model, param_grid_bayesian)
        results.append(result_bayesian)
    except Exception as e:
        print(f"Error in Bayesian Search: {e}")
    
    # Compare results
    if results:
        df_comparison = compare_results(results)
        
        # Save results
        df_comparison.to_csv('algorithm_comparison_results.csv', index=False)
        print("\n✅ Results saved to 'algorithm_comparison_results.csv'")
    else:
        print("\n❌ No results to compare")


if __name__ == "__main__":
    main()
