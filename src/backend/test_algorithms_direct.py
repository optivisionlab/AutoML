"""
Test 3 search algorithms DIRECTLY (not via API) with Health and Lifestyle dataset
Dataset: https://www.kaggle.com/datasets/chik0di/health-and-lifestyle-dataset

This script tests algorithms directly without API to have full control over search strategies.
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier
import time
import warnings
warnings.filterwarnings('ignore')

from automl.search.strategy.genetic_algorithm import GeneticAlgorithm
from automl.search.strategy.grid_search import GridSearchStrategy
from automl.search.strategy.bayesian_search import BayesianSearchStrategy


def load_dataset(file_path='health_lifestyle_dataset.csv'):
    """Load and preprocess the Health and Lifestyle dataset"""
    print("="*70)
    print("LOADING HEALTH AND LIFESTYLE DATASET")
    print("="*70)
    
    df = pd.read_csv(file_path)
    print(f"Original shape: {df.shape}")
    print(f"Columns: {df.columns.tolist()}")
    
    # Drop ID column
    if 'id' in df.columns:
        df = df.drop(columns=['id'])
    
    # Target column
    target_col = 'disease_risk'
    
    # Encode categorical variables
    for col in df.select_dtypes(include=['object']).columns:
        if col != target_col:
            le = LabelEncoder()
            df[col] = le.fit_transform(df[col].astype(str))
            print(f"Encoded column: {col}")
    
    # Separate features and target
    X = df.drop(columns=[target_col])
    y = df[target_col]
    
    print(f"\nFeatures shape: {X.shape}")
    print(f"Target shape: {y.shape}")
    print(f"Target distribution: {np.bincount(y)}")
    print(f"  Class 0 (No disease): {np.sum(y==0)} ({np.sum(y==0)/len(y)*100:.1f}%)")
    print(f"  Class 1 (Disease): {np.sum(y==1)} ({np.sum(y==1)/len(y)*100:.1f}%)")
    
    # Sample for faster testing
    sample_size = 2000
    if len(df) > sample_size:
        X_sample, _, y_sample, _ = train_test_split(
            X, y, train_size=sample_size, random_state=42, stratify=y
        )
        print(f"\nSampled to {sample_size} rows for faster testing")
        return X_sample, y_sample
    
    return X, y


def test_genetic_algorithm(X, y):
    """Test Genetic Algorithm"""
    print("\n" + "="*70)
    print("1. GENETIC ALGORITHM")
    print("="*70)
    
    model = RandomForestClassifier(random_state=42)
    param_grid = {
        'n_estimators': [50, 100, 150],
        'max_depth': [5, 10, 15, None],
        'min_samples_split': [2, 5, 10]
    }
    
    ga = GeneticAlgorithm(
        population_size=12,
        generation=10,
        cv=3,
        n_jobs=-1,
        verbose=1
    )
    
    print(f"Config: population={ga.config['population_size']}, generations={ga.config['generation']}")
    
    start_time = time.time()
    best_params, best_score, best_all_scores, cv_results = ga.search(
        model=model,
        param_grid=param_grid,
        X=X,
        y=y
    )
    elapsed_time = time.time() - start_time
    
    print(f"\n✅ Results:")
    print(f"   Best Score: {best_score:.4f}")
    print(f"   Best Params: {best_params}")
    print(f"   All Scores: {best_all_scores}")
    print(f"   Time: {elapsed_time:.2f}s")
    
    return {
        'algorithm': 'Genetic Algorithm',
        'best_score': best_score,
        'best_params': best_params,
        'all_scores': best_all_scores,
        'time': elapsed_time
    }


def test_grid_search(X, y):
    """Test Grid Search"""
    print("\n" + "="*70)
    print("2. GRID SEARCH")
    print("="*70)
    
    model = RandomForestClassifier(random_state=42)
    param_grid = {
        'n_estimators': [50, 100, 150],
        'max_depth': [5, 10, None],
        'min_samples_split': [2, 5]
    }
    
    grid = GridSearchStrategy(
        cv=3,
        n_jobs=-1,
        verbose=1
    )
    
    # Calculate total combinations
    total_combinations = 1
    for values in param_grid.values():
        total_combinations *= len(values)
    print(f"Total combinations to test: {total_combinations}")
    
    start_time = time.time()
    best_params, best_score, best_all_scores, cv_results = grid.search(
        model=model,
        param_grid=param_grid,
        X=X,
        y=y
    )
    elapsed_time = time.time() - start_time
    
    print(f"\n✅ Results:")
    print(f"   Best Score: {best_score:.4f}")
    print(f"   Best Params: {best_params}")
    print(f"   All Scores: {best_all_scores}")
    print(f"   Time: {elapsed_time:.2f}s")
    
    return {
        'algorithm': 'Grid Search',
        'best_score': best_score,
        'best_params': best_params,
        'all_scores': best_all_scores,
        'time': elapsed_time
    }


def test_bayesian_search(X, y):
    """Test Bayesian Search"""
    print("\n" + "="*70)
    print("3. BAYESIAN SEARCH")
    print("="*70)
    
    from skopt.space import Integer, Categorical
    
    model = RandomForestClassifier(random_state=42)
    param_grid = {
        'n_estimators': Integer(50, 150),
        'max_depth': Categorical([5, 10, 15, None]),
        'min_samples_split': Integer(2, 10)
    }
    
    bayesian = BayesianSearchStrategy(
        n_calls=20,
        cv=3,
        n_jobs=-1,
        verbose=1
    )
    
    print(f"Config: n_calls={bayesian.config['n_calls']}")
    
    start_time = time.time()
    best_params, best_score, best_all_scores, cv_results = bayesian.search(
        model=model,
        param_grid=param_grid,
        X=X,
        y=y
    )
    elapsed_time = time.time() - start_time
    
    print(f"\n✅ Results:")
    print(f"   Best Score: {best_score:.4f}")
    print(f"   Best Params: {best_params}")
    print(f"   All Scores: {best_all_scores}")
    print(f"   Time: {elapsed_time:.2f}s")
    
    return {
        'algorithm': 'Bayesian Search',
        'best_score': best_score,
        'best_params': best_params,
        'all_scores': best_all_scores,
        'time': elapsed_time
    }


def compare_results(results):
    """Compare and display results"""
    print("\n" + "="*70)
    print("FINAL COMPARISON")
    print("="*70)
    
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
    
    # Find winner
    best_idx = df_results['Best Score'].idxmax()
    print(f"\n🏆 Winner: {df_results.loc[best_idx, 'Algorithm']}")
    print(f"   Score: {df_results.loc[best_idx, 'Best Score']:.4f}")
    print(f"   Time: {df_results.loc[best_idx, 'Time (s)']:.2f}s")
    
    # Speed comparison
    fastest_idx = df_results['Time (s)'].idxmin()
    print(f"\n⚡ Fastest: {df_results.loc[fastest_idx, 'Algorithm']}")
    print(f"   Time: {df_results.loc[fastest_idx, 'Time (s)']:.2f}s")
    
    return df_results


def main():
    """Main function"""
    print("="*70)
    print("HEALTH AND LIFESTYLE DATASET - ALGORITHM COMPARISON")
    print("Direct Testing (Not via API)")
    print("="*70)
    
    # Load dataset
    X, y = load_dataset()
    
    # Test all algorithms
    results = []
    
    try:
        result_ga = test_genetic_algorithm(X, y)
        results.append(result_ga)
    except Exception as e:
        print(f"\n❌ Error in Genetic Algorithm: {e}")
    
    try:
        result_grid = test_grid_search(X, y)
        results.append(result_grid)
    except Exception as e:
        print(f"\n❌ Error in Grid Search: {e}")
    
    try:
        result_bayesian = test_bayesian_search(X, y)
        results.append(result_bayesian)
    except Exception as e:
        print(f"\n❌ Error in Bayesian Search: {e}")
    
    # Compare results
    if results:
        df_comparison = compare_results(results)
        
        # Save results
        df_comparison.to_csv('health_lifestyle_comparison_results.csv', index=False)
        print(f"\n💾 Results saved to 'health_lifestyle_comparison_results.csv'")
    else:
        print("\n❌ No results to compare")


if __name__ == "__main__":
    main()
