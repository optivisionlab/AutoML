"""
Demonstration of BayesianSearchStrategy with both macro and weighted metrics support.

This script shows how the updated BayesianSearchStrategy can:
1. Compute both macro and weighted metrics simultaneously
2. Choose which metric to optimize based on data characteristics
3. Track and log both types of metrics for comparison
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

import numpy as np
from sklearn.datasets import make_classification
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import pandas as pd
from automl.search.strategies.bayesian_search import BayesianSearchStrategy


def demo_both_metrics():
    """Demonstrate computing both macro and weighted metrics."""
    print("\n" + "="*80)
    print("DEMO: Computing Both Macro and Weighted Metrics Simultaneously")
    print("="*80)
    
    # Create an imbalanced dataset
    X, y = make_classification(
        n_samples=1000, 
        n_features=20, 
        n_informative=15,
        n_classes=3, 
        weights=[0.6, 0.3, 0.1],  # Imbalanced classes
        random_state=42
    )
    
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    print("\nDataset characteristics:")
    unique, counts = np.unique(y_train, return_counts=True)
    for cls, count in zip(unique, counts):
        print(f"  Class {cls}: {count} samples ({count/len(y_train)*100:.1f}%)")
    
    # Configure BayesianSearchStrategy to compute both metrics
    print("\n" + "-"*60)
    print("Configuration 1: Both metrics, auto-optimize")
    print("-"*60)
    
    opt = BayesianSearchStrategy(
        n_calls=15,  # Reduced for demo
        cv=3,
        scoring='f1',  # The base metric to optimize
        averaging='both',  # Compute both macro and weighted
        optimize_for='auto',  # Auto-detect which to optimize
        random_state=42,
        save_log=True,
        log_dir='logs_demo',
        verbose=1
    )
    
    model = RandomForestClassifier(random_state=42)
    param_grid = {
        'n_estimators': [50, 100, 150],
        'max_depth': [5, 10, 15],
        'min_samples_split': [2, 5, 10]
    }
    
    best_params, best_score, result = opt.search(
        model, param_grid, X_train, y_train
    )
    
    print(f"\n✓ Best parameters found: {best_params}")
    print(f"✓ Best optimization score: {best_score:.4f}")
    
    # Compare with macro-only optimization
    print("\n" + "-"*60)
    print("Configuration 2: Both metrics, force macro optimization")
    print("-"*60)
    
    opt_macro = BayesianSearchStrategy(
        n_calls=15,
        cv=3,
        scoring='f1',
        averaging='both',
        optimize_for='macro',  # Force macro optimization
        random_state=42,
        save_log=False,
        verbose=0
    )
    
    best_params_macro, best_score_macro, _ = opt_macro.search(
        model, param_grid, X_train, y_train
    )
    
    print(f"\n✓ Best parameters (macro-optimized): {best_params_macro}")
    print(f"✓ Best macro F1 score: {best_score_macro:.4f}")
    
    # Compare with weighted-only optimization
    print("\n" + "-"*60)
    print("Configuration 3: Both metrics, force weighted optimization")
    print("-"*60)
    
    opt_weighted = BayesianSearchStrategy(
        n_calls=15,
        cv=3,
        scoring='f1',
        averaging='both',
        optimize_for='weighted',  # Force weighted optimization
        random_state=42,
        save_log=False,
        verbose=0
    )
    
    best_params_weighted, best_score_weighted, _ = opt_weighted.search(
        model, param_grid, X_train, y_train
    )
    
    print(f"\n✓ Best parameters (weighted-optimized): {best_params_weighted}")
    print(f"✓ Best weighted F1 score: {best_score_weighted:.4f}")
    
    # Load and analyze the search history
    print("\n" + "="*80)
    print("Analyzing Search History (from first optimization)")
    print("="*80)
    
    # Find the most recent log file
    import glob
    log_files = glob.glob('logs_demo/bayesian_search_RandomForestClassifier_*.csv')
    if log_files:
        latest_log = max(log_files, key=os.path.getctime)
        df = pd.read_csv(latest_log)
        
        if 'f1_macro' in df.columns and 'f1_weighted' in df.columns:
            print(f"\nLoaded search history from: {latest_log}")
            print(f"Total iterations: {len(df)}")
            
            print("\nMetric Statistics:")
            print("-" * 40)
            print(f"F1 Macro    - Min: {df['f1_macro'].min():.4f}, "
                  f"Max: {df['f1_macro'].max():.4f}, "
                  f"Mean: {df['f1_macro'].mean():.4f}")
            print(f"F1 Weighted - Min: {df['f1_weighted'].min():.4f}, "
                  f"Max: {df['f1_weighted'].max():.4f}, "
                  f"Mean: {df['f1_weighted'].mean():.4f}")
            
            print("\nTop 3 Configurations by Macro F1:")
            top_macro = df.nlargest(3, 'f1_macro')[['best_params', 'f1_macro', 'f1_weighted']]
            for idx, row in top_macro.iterrows():
                print(f"  {row['f1_macro']:.4f} (weighted: {row['f1_weighted']:.4f})")
            
            print("\nTop 3 Configurations by Weighted F1:")
            top_weighted = df.nlargest(3, 'f1_weighted')[['best_params', 'f1_macro', 'f1_weighted']]
            for idx, row in top_weighted.iterrows():
                print(f"  {row['f1_weighted']:.4f} (macro: {row['f1_macro']:.4f})")
    
    print("\n" + "="*80)
    print("Summary")
    print("="*80)
    print("""
The updated BayesianSearchStrategy now supports:

1. **Dual Metric Computation** (averaging='both'):
   - Computes both macro and weighted metrics in each iteration
   - Provides comprehensive view of model performance
   
2. **Flexible Optimization Target** (optimize_for parameter):
   - 'auto': Automatically chooses based on class balance
   - 'macro': Optimizes for macro-averaged metrics (better for minority classes)
   - 'weighted': Optimizes for weighted metrics (better overall accuracy)
   
3. **Complete Logging**:
   - Tracks both metric types in search history
   - Enables post-hoc analysis of trade-offs
   
Usage Example:
```python
optimizer = BayesianSearchStrategy(
    averaging='both',        # Compute both types
    optimize_for='auto',     # Let it decide what to optimize
    imbalance_threshold=0.3  # Threshold for auto-detection
)
```

This allows you to:
- See how different parameter choices affect both metrics
- Make informed decisions based on your specific needs
- Understand trade-offs between overall accuracy and minority class performance
    """)


if __name__ == "__main__":
    demo_both_metrics()
