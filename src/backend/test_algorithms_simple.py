"""
Simple test script for 3 search algorithms using synthetic data
No need to download dataset - generates sample data automatically
"""

import numpy as np
import pandas as pd
from sklearn.datasets import make_classification
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import time
import warnings
warnings.filterwarnings('ignore')

from automl.search.strategy.genetic_algorithm import GeneticAlgorithm
from automl.search.strategy.grid_search import GridSearchStrategy
from automl.search.strategy.bayesian_search import BayesianSearchStrategy


def generate_sample_data(n_samples=1000, n_features=20, n_classes=3):
    """Generate synthetic classification dataset"""
    print(f"Generating synthetic dataset...")
    print(f"  Samples: {n_samples}")
    print(f"  Features: {n_features}")
    print(f"  Classes: {n_classes}")
    
    # Calculate informative and redundant features
    n_informative = max(2, int(n_features * 0.7))
    n_redundant = max(0, n_features - n_informative)
    
    X, y = make_classification(
        n_samples=n_samples,
        n_features=n_features,
        n_informative=n_informative,
        n_redundant=n_redundant,
        n_classes=n_classes,
        random_state=42,
        class_sep=0.8
    )
    
    print(f"  Target distribution: {np.bincount(y)}")
    return X, y


def run_comparison():
    """Run comparison of all 3 algorithms"""
    print("="*70)
    print("AUTOML ALGORITHM COMPARISON - SIMPLE TEST")
    print("="*70)
    
    # Generate data
    X, y = generate_sample_data(n_samples=800, n_features=15, n_classes=3)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    print(f"\nTrain size: {X_train.shape[0]}, Test size: {X_test.shape[0]}")
    
    # Model and parameters
    model = RandomForestClassifier(random_state=42)
    
    param_grid = {
        'n_estimators': [50, 100, 150],
        'max_depth': [5, 10, None],
        'min_samples_split': [2, 5]
    }
    
    results = []
    
    # Test 1: Genetic Algorithm
    print("\n" + "="*70)
    print("1. GENETIC ALGORITHM")
    print("="*70)
    try:
        ga = GeneticAlgorithm(
            population_size=10,
            generation=8,
            cv=3,
            n_jobs=-1,
            verbose=1
        )
        
        start = time.time()
        best_params, best_score, best_all_scores, _ = ga.search(
            model=model,
            param_grid=param_grid,
            X=X_train,
            y=y_train
        )
        elapsed = time.time() - start
        
        results.append({
            'Algorithm': 'Genetic Algorithm',
            'Best Score': best_score,
            'Accuracy': best_all_scores.get('accuracy', 0),
            'F1': best_all_scores.get('f1', 0),
            'Time (s)': elapsed,
            'Best Params': str(best_params)
        })
        
        print(f"\n✅ Best Score: {best_score:.4f}")
        print(f"   Time: {elapsed:.2f}s")
        print(f"   Params: {best_params}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 2: Grid Search
    print("\n" + "="*70)
    print("2. GRID SEARCH")
    print("="*70)
    try:
        grid = GridSearchStrategy(
            cv=3,
            n_jobs=-1,
            verbose=1
        )
        
        start = time.time()
        best_params, best_score, best_all_scores, _ = grid.search(
            model=model,
            param_grid=param_grid,
            X=X_train,
            y=y_train
        )
        elapsed = time.time() - start
        
        results.append({
            'Algorithm': 'Grid Search',
            'Best Score': best_score,
            'Accuracy': best_all_scores.get('accuracy', 0),
            'F1': best_all_scores.get('f1', 0),
            'Time (s)': elapsed,
            'Best Params': str(best_params)
        })
        
        print(f"\n✅ Best Score: {best_score:.4f}")
        print(f"   Time: {elapsed:.2f}s")
        print(f"   Params: {best_params}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 3: Bayesian Search
    print("\n" + "="*70)
    print("3. BAYESIAN SEARCH")
    print("="*70)
    try:
        from skopt.space import Integer, Categorical
        
        param_grid_bayesian = {
            'n_estimators': Integer(50, 150),
            'max_depth': Categorical([5, 10, None]),
            'min_samples_split': Integer(2, 5)
        }
        
        bayesian = BayesianSearchStrategy(
            n_calls=15,
            cv=3,
            n_jobs=-1,
            verbose=1
        )
        
        start = time.time()
        best_params, best_score, best_all_scores, _ = bayesian.search(
            model=model,
            param_grid=param_grid_bayesian,
            X=X_train,
            y=y_train
        )
        elapsed = time.time() - start
        
        results.append({
            'Algorithm': 'Bayesian Search',
            'Best Score': best_score,
            'Accuracy': best_all_scores.get('accuracy', 0),
            'F1': best_all_scores.get('f1', 0),
            'Time (s)': elapsed,
            'Best Params': str(best_params)
        })
        
        print(f"\n✅ Best Score: {best_score:.4f}")
        print(f"   Time: {elapsed:.2f}s")
        print(f"   Params: {best_params}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Display comparison
    if results:
        print("\n" + "="*70)
        print("FINAL COMPARISON")
        print("="*70)
        
        df = pd.DataFrame(results)
        print("\n", df[['Algorithm', 'Best Score', 'Accuracy', 'F1', 'Time (s)']].to_string(index=False))
        
        # Find winner
        best_idx = df['Best Score'].idxmax()
        print(f"\n🏆 Winner: {df.loc[best_idx, 'Algorithm']}")
        print(f"   Score: {df.loc[best_idx, 'Best Score']:.4f}")
        print(f"   Time: {df.loc[best_idx, 'Time (s)']:.2f}s")
        
        # Save results
        df.to_csv('simple_test_results.csv', index=False)
        print("\n💾 Results saved to 'simple_test_results.csv'")
    else:
        print("\n❌ No results to compare")


if __name__ == "__main__":
    run_comparison()
