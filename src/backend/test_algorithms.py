"""
Test script to check search strategy algorithms with online shoppers data.
"""
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, classification_report
import warnings

# Import the search strategies
from automl.search.strategy.grid_search import GridSearchStrategy
from automl.search.strategy.bayesian_search import BayesianSearchStrategy
from automl.search.strategy.genetic_algorithm import GeneticAlgorithm

# Suppress convergence warnings
warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', message='lbfgs failed to converge')


def load_and_prepare_data(csv_path, label_encoders=None, scaler=None):
    """Load and prepare the online shoppers data."""
    print(f"Loading data from {csv_path}...")
    df = pd.read_csv(csv_path)
    
    print(f"Dataset shape: {df.shape}")
    print(f"Columns: {df.columns.tolist()}")
    
    # Encode categorical variables
    if label_encoders is None:
        label_encoders = {}
        categorical_cols = ['Month', 'VisitorType', 'Weekend', 'Revenue']
        
        for col in categorical_cols:
            if col in df.columns:
                le = LabelEncoder()
                df[col] = le.fit_transform(df[col].astype(str))
                label_encoders[col] = le
    else:
        # Use existing encoders for test data
        categorical_cols = ['Month', 'VisitorType', 'Weekend', 'Revenue']
        for col in categorical_cols:
            if col in df.columns and col in label_encoders:
                df[col] = label_encoders[col].transform(df[col].astype(str))
    
    # Separate features and target
    X = df.drop('Revenue', axis=1)
    y = df['Revenue']
    
    # Scale features for better convergence
    if scaler is None:
        scaler = StandardScaler()
        X_scaled = pd.DataFrame(
            scaler.fit_transform(X),
            columns=X.columns,
            index=X.index
        )
    else:
        X_scaled = pd.DataFrame(
            scaler.transform(X),
            columns=X.columns,
            index=X.index
        )
    
    print(f"Features shape: {X_scaled.shape}")
    print(f"Target distribution: {y.value_counts().to_dict()}")
    
    return X_scaled, y, label_encoders, scaler


def test_grid_search(X, y, model, param_grid):
    """Test Grid Search strategy."""
    print("\n" + "="*60)
    print("Testing Grid Search Strategy")
    print("="*60)
    
    # Use a small subset for faster testing
    X_sample, _, y_sample, _ = train_test_split(X, y, train_size=0.1, random_state=42, stratify=y)
    
    strategy = GridSearchStrategy(
        cv=3,
        scoring='accuracy',
        n_jobs=-1,
        verbose=1
    )
    
    best_params, best_score, best_all_scores, cv_results = strategy.search(
        model, param_grid, X_sample.values, y_sample.values
    )
    
    print(f"\nBest Parameters: {best_params}")
    print(f"Best Score: {best_score:.4f}")
    print(f"All Scores: {best_all_scores}")
    print(f"Total combinations tested: {len(cv_results['params'])}")
    
    # Train final model with best params
    final_model = model.__class__(**{**model.get_params(), **best_params})
    final_model.fit(X_sample.values, y_sample.values)
    
    return best_params, best_score, final_model


def test_bayesian_search(X, y, model, param_grid):
    """Test Bayesian Search strategy."""
    print("\n" + "="*60)
    print("Testing Bayesian Search Strategy")
    print("="*60)
    
    # Use a small subset for faster testing
    X_sample, _, y_sample, _ = train_test_split(X, y, train_size=0.1, random_state=42, stratify=y)
    
    strategy = BayesianSearchStrategy(
        n_calls=10,
        cv=3,
        scoring='accuracy',
        n_jobs=-1,
        verbose=1,
        random_state=42  # Cố định seed để kết quả nhất quán
    )
    
    best_params, best_score, best_all_scores, cv_results = strategy.search(
        model, param_grid, X_sample.values, y_sample.values
    )
    
    print(f"\nBest Parameters: {best_params}")
    print(f"Best Score: {best_score:.4f}")
    print(f"All Scores: {best_all_scores}")
    print(f"Total iterations: {len(cv_results['params'])}")
    
    # Train final model with best params
    final_model = model.__class__(**{**model.get_params(), **best_params})
    final_model.fit(X_sample.values, y_sample.values)
    
    return best_params, best_score, final_model


def test_genetic_algorithm(X, y, model, param_grid):
    """Test Genetic Algorithm strategy."""
    print("\n" + "="*60)
    print("Testing Genetic Algorithm Strategy")
    print("="*60)
    
    # Use a small subset for faster testing
    X_sample, _, y_sample, _ = train_test_split(X, y, train_size=0.1, random_state=42, stratify=y)
    
    strategy = GeneticAlgorithm(
        population_size=8,
        generation=5,
        cv=3,
        scoring='accuracy',
        n_jobs=-1,
        verbose=1,
        random_state=42  # Cố định seed để kết quả nhất quán
    )
    
    best_params, best_score, best_all_scores, cv_results = strategy.search(
        model, param_grid, X_sample.values, y_sample.values
    )
    
    print(f"\nBest Parameters: {best_params}")
    print(f"Best Score: {best_score:.4f}")
    print(f"All Scores: {best_all_scores}")
    print(f"Total evaluations: {cv_results.get('total_evaluations', 'N/A')}")
    
    # Train final model with best params
    final_model = model.__class__(**{**model.get_params(), **best_params})
    final_model.fit(X_sample.values, y_sample.values)
    
    return best_params, best_score, final_model


def evaluate_on_test_set(model, X_test, y_test, model_name):
    """Evaluate a trained model on the test set."""
    print(f"\n{model_name} - Test Set Evaluation:")
    print("-" * 40)
    
    y_pred = model.predict(X_test)
    
    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, average='macro', zero_division=0)
    recall = recall_score(y_test, y_pred, average='macro', zero_division=0)
    f1 = f1_score(y_test, y_pred, average='macro', zero_division=0)
    
    print(f"Accuracy:  {accuracy:.4f}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall:    {recall:.4f}")
    print(f"F1-Score:  {f1:.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, zero_division=0))
    
    return accuracy, precision, recall, f1


def get_all_model_configs():
    """
    Get all model configurations to test.
    Returns a list of (model_name, model, grid_params, bayes_params, ga_params).
    """
    from skopt.space import Integer
    from sklearn.linear_model import LogisticRegression
    from sklearn.svm import SVC
    from sklearn.neighbors import KNeighborsClassifier
    
    configs = []
    
    # DecisionTreeClassifier
    configs.append((
        'DecisionTree',
        DecisionTreeClassifier(random_state=42),
        {
            'max_depth': [3, 5, 7],
            'min_samples_split': [2, 5]
        },
        {
            'max_depth': Integer(3, 10, name='max_depth'),
            'min_samples_split': Integer(2, 10, name='min_samples_split')
        },
        {
            'max_depth': [3, 5, 7, 10],
            'min_samples_split': (2, 10)
        }
    ))
    
    # RandomForestClassifier
    configs.append((
        'RandomForest',
        RandomForestClassifier(random_state=42),
        {
            'n_estimators': [50, 100],
            'max_depth': [5, 10],
            'min_samples_split': [2, 5]
        },
        {
            'n_estimators': Integer(50, 200, name='n_estimators'),
            'max_depth': Integer(5, 20, name='max_depth'),
            'min_samples_split': Integer(2, 10, name='min_samples_split')
        },
        {
            'n_estimators': [50, 100, 150],
            'max_depth': [5, 10, 15],
            'min_samples_split': (2, 10)
        }
    ))
    
    # LogisticRegression
    configs.append((
        'LogisticRegression',
        LogisticRegression(random_state=42, max_iter=5000, solver='lbfgs'),
        {
            'C': [0.1, 1.0, 10.0],
            'penalty': ['l2']
        },
        {
            'C': Integer(1, 100, name='C', prior='log-uniform')
        },
        {
            'C': [0.1, 1.0, 10.0, 100.0]
        }
    ))
    
    # KNeighborsClassifier
    configs.append((
        'KNeighbors',
        KNeighborsClassifier(),
        {
            'n_neighbors': [3, 5, 7],
            'weights': ['uniform', 'distance']
        },
        {
            'n_neighbors': Integer(3, 15, name='n_neighbors')
        },
        {
            'n_neighbors': [3, 5, 7, 9, 11],
            'weights': ['uniform', 'distance']
        }
    ))
    
    return configs


def main():
    """Main test function."""
    train_csv = '/home/vananh/Homeworks/python/HAutoML/AutoML/src/backend/assets/online_shoppers/online_shoppers_intention_train.csv'
    test_csv = '/home/vananh/Homeworks/python/HAutoML/AutoML/src/backend/assets/online_shoppers/online_shoppers_intention_test.csv'
    
    # Load training data
    X_train, y_train, label_encoders, scaler = load_and_prepare_data(train_csv)
    
    # Load testing data using the same encoders and scaler
    print("\n" + "="*60)
    X_test, y_test, _, _ = load_and_prepare_data(test_csv, label_encoders, scaler)
    
    # Get all model configurations
    model_configs = get_all_model_configs()
    
    # Store all results
    all_results = []
    
    # Loop through each model
    for model_name, model, grid_params, bayes_params, ga_params in model_configs:
        print("\n" + "#"*60)
        print(f"# TESTING MODEL: {model_name}")
        print("#"*60)
        
        model_result = {
            'model_name': model_name,
            'grid': {'model': None, 'score': None, 'params': None, 'test_metrics': None},
            'bayes': {'model': None, 'score': None, 'params': None, 'test_metrics': None},
            'ga': {'model': None, 'score': None, 'params': None, 'test_metrics': None}
        }
        
        # Test Grid Search
        try:
            params, score, trained_model = test_grid_search(X_train, y_train, model, grid_params)
            model_result['grid'] = {'model': trained_model, 'score': score, 'params': params}
        except Exception as e:
            print(f"Grid Search failed for {model_name}: {e}")
        
        # Test Bayesian Search
        try:
            params, score, trained_model = test_bayesian_search(X_train, y_train, model, bayes_params)
            model_result['bayes'] = {'model': trained_model, 'score': score, 'params': params}
        except Exception as e:
            print(f"Bayesian Search failed for {model_name}: {e}")
        
        # Test Genetic Algorithm
        try:
            params, score, trained_model = test_genetic_algorithm(X_train, y_train, model, ga_params)
            model_result['ga'] = {'model': trained_model, 'score': score, 'params': params}
        except Exception as e:
            print(f"Genetic Algorithm failed for {model_name}: {e}")
        
        # Evaluate on test set
        for strategy_name in ['grid', 'bayes', 'ga']:
            if model_result[strategy_name]['model'] is not None:
                strategy_label = {'grid': 'Grid Search', 'bayes': 'Bayesian Search', 'ga': 'Genetic Algorithm'}[strategy_name]
                acc, prec, rec, f1 = evaluate_on_test_set(
                    model_result[strategy_name]['model'], 
                    X_test.values, 
                    y_test.values, 
                    f"{model_name} - {strategy_label}"
                )
                model_result[strategy_name]['test_metrics'] = {
                    'accuracy': acc, 'precision': prec, 'recall': rec, 'f1': f1
                }
        
        all_results.append(model_result)
    
    # Final summary - find best model
    print("\n" + "="*80)
    print("FINAL SUMMARY - ALL MODELS AND STRATEGIES")
    print("="*80)
    
    best_overall = None
    best_f1 = -1
    
    for result in all_results:
        model_name = result['model_name']
        print(f"\n{model_name}:")
        
        for strategy_name in ['grid', 'bayes', 'ga']:
            strategy_label = {'grid': 'Grid Search', 'bayes': 'Bayesian', 'ga': 'Genetic Algo'}[strategy_name]
            strategy_data = result[strategy_name]
            
            if strategy_data['test_metrics']:
                metrics = strategy_data['test_metrics']
                cv_score = strategy_data['score']
                print(f"  {strategy_label:15s} - CV: {cv_score:.4f}, Test Acc: {metrics['accuracy']:.4f}, F1: {metrics['f1']:.4f}")
                
                # Track best model
                if metrics['f1'] > best_f1:
                    best_f1 = metrics['f1']
                    best_overall = {
                        'model_name': model_name,
                        'strategy': strategy_label,
                        'metrics': metrics,
                        'cv_score': cv_score,
                        'params': strategy_data['params']
                    }
    
    # Best model per algorithm
    print("\n" + "="*80)
    print("BEST MODEL FOR EACH ALGORITHM")
    print("="*80)
    
    best_per_algorithm = {
        'grid': {'f1': -1, 'data': None},
        'bayes': {'f1': -1, 'data': None},
        'ga': {'f1': -1, 'data': None}
    }
    
    # Find best model for each algorithm
    for result in all_results:
        model_name = result['model_name']
        for strategy_name in ['grid', 'bayes', 'ga']:
            strategy_data = result[strategy_name]
            if strategy_data['test_metrics']:
                f1 = strategy_data['test_metrics']['f1']
                if f1 > best_per_algorithm[strategy_name]['f1']:
                    best_per_algorithm[strategy_name]['f1'] = f1
                    best_per_algorithm[strategy_name]['data'] = {
                        'model_name': model_name,
                        'metrics': strategy_data['test_metrics'],
                        'cv_score': strategy_data['score'],
                        'params': strategy_data['params']
                    }
    
    # Print best for each algorithm
    strategy_labels = {
        'grid': 'Grid Search',
        'bayes': 'Bayesian Search',
        'ga': 'Genetic Algorithm'
    }
    
    for strategy_name, strategy_label in strategy_labels.items():
        best_data = best_per_algorithm[strategy_name]['data']
        if best_data:
            print(f"\n{strategy_label}:")
            print(f"  Best Model:  {best_data['model_name']}")
            print(f"  CV Score:    {best_data['cv_score']:.4f}")
            print(f"  Test Acc:    {best_data['metrics']['accuracy']:.4f}")
            print(f"  Test F1:     {best_data['metrics']['f1']:.4f}")
            print(f"  Params:      {best_data['params']}")
    
    # Print overall best model
    print("\n" + "="*80)
    print("OVERALL BEST MODEL")
    print("="*80)
    if best_overall:
        print(f"Model:     {best_overall['model_name']}")
        print(f"Strategy:  {best_overall['strategy']}")
        print(f"CV Score:  {best_overall['cv_score']:.4f}")
        print(f"Test Acc:  {best_overall['metrics']['accuracy']:.4f}")
        print(f"Test F1:   {best_overall['metrics']['f1']:.4f}")
        print(f"Params:    {best_overall['params']}")
    
    print("\nAll tests completed!")


if __name__ == "__main__":
    main()
