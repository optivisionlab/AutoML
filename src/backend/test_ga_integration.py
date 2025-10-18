#!/usr/bin/env python3
"""
Test script to verify that the Genetic Algorithm works with the updated engine.py
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

import numpy as np
import pandas as pd
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split

# Import the engine functions
from automl.engine import training
from automl.engine import get_model

def test_ga_integration():
    """Test the GA integration with the training function."""
    
    print("=" * 80)
    print("Testing Genetic Algorithm Integration with engine.py")
    print("=" * 80)
    
    # Load a simple dataset
    iris = load_iris()
    X = iris.data
    y = iris.target
    
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    # Get models and metrics
    models, metric_list = get_model()
    
    # Use only first 2 models for faster testing
    test_models = {0: models[0], 1: models[1]}
    
    # Define metrics to use
    metric_list = ['accuracy', 'precision', 'recall', 'f1']
    metric_sort = 'accuracy'
    
    # Test with GA algorithm
    print("\nTesting with Genetic Algorithm...")
    print("-" * 60)
    
    try:
        best_model_id, best_model, best_score, best_params, model_scores = training(
            models=test_models,  # Test with first 2 models
            metric_list=metric_list,
            metric_sort=metric_sort,
            X_train=X_train,
            y_train=y_train,
            search_algorithm='GA'
        )
        
        print(f"✓ GA Training Successful!")
        print(f"  Best Model ID: {best_model_id}")
        print(f"  Best Score: {best_score:.4f}")
        print(f"  Best Parameters: {best_params}")
        print(f"  All Model Scores: {model_scores}")
        
    except Exception as e:
        print(f"✗ GA Training Failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Test with Bayesian Search
    print("\n\nTesting with Bayesian Search...")
    print("-" * 60)
    
    try:
        best_model_id, best_model, best_score, best_params, model_scores = training(
            models=test_models,  # Test with first 2 models
            metric_list=metric_list,
            metric_sort=metric_sort,
            X_train=X_train,
            y_train=y_train,
            search_algorithm='bayesian'
        )
        
        print(f"✓ Bayesian Search Training Successful!")
        print(f"  Best Model ID: {best_model_id}")
        print(f"  Best Score: {best_score:.4f}")
        print(f"  Best Parameters: {best_params}")
        
    except Exception as e:
        print(f"✗ Bayesian Search Training Failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Test with Grid Search (default)
    print("\n\nTesting with Grid Search (default)...")
    print("-" * 60)
    
    try:
        best_model_id, best_model, best_score, best_params, model_scores = training(
            models=test_models,  # Test with first 2 models
            metric_list=metric_list,
            metric_sort=metric_sort,
            X_train=X_train,
            y_train=y_train
            # search_algorithm not specified, should use grid search
        )
        
        print(f"✓ Grid Search Training Successful!")
        print(f"  Best Model ID: {best_model_id}")
        print(f"  Best Score: {best_score:.4f}")
        print(f"  Best Parameters: {best_params}")
        
    except Exception as e:
        print(f"✗ Grid Search Training Failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("Integration Testing Complete")
    print("=" * 80)


if __name__ == "__main__":
    test_ga_integration()
