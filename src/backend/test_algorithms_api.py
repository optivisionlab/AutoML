"""
Test 3 search algorithms via API with Health and Lifestyle dataset
Dataset: https://www.kaggle.com/datasets/chik0di/health-and-lifestyle-dataset

Tests:
1. Genetic Algorithm
2. Grid Search  
3. Bayesian Search
"""

import requests
import pandas as pd
import numpy as np
import time
import json
from sklearn.preprocessing import LabelEncoder
from typing import Dict, List
import warnings
warnings.filterwarnings('ignore')


# API Configuration
API_BASE_URL = "http://localhost:9999"
USER_ID = "test_user_001"
DATA_ID = "health_lifestyle_test"


def load_and_prepare_dataset(file_path='health_lifestyle_dataset.csv'):
    """Load and prepare dataset for API"""
    print("="*70)
    print("LOADING DATASET")
    print("="*70)
    
    import os
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        print("\nGenerating synthetic data instead...")
        return generate_synthetic_data()
    
    df = pd.read_csv(file_path)
    print(f"Dataset shape: {df.shape}")
    print(f"Columns: {df.columns.tolist()}")
    
    # Drop ID column if exists
    if 'id' in df.columns:
        df = df.drop(columns=['id'])
    
    # Identify target column
    target_col = 'disease_risk' if 'disease_risk' in df.columns else df.columns[-1]
    
    # Encode categorical variables (except target)
    for col in df.select_dtypes(include=['object']).columns:
        if col != target_col:
            le = LabelEncoder()
            df[col] = le.fit_transform(df[col].astype(str))
    
    # Encode target if categorical
    if df[target_col].dtype == 'object':
        le_target = LabelEncoder()
        df[target_col] = le_target.fit_transform(df[target_col])
        print(f"Target classes: {le_target.classes_}")
    
    print(f"Target column: {target_col}")
    print(f"Target distribution: {df[target_col].value_counts().to_dict()}")
    
    # Sample data for faster testing (optional)
    if len(df) > 1000:
        df = df.sample(n=1000, random_state=42)
        print(f"Sampled to {len(df)} rows for faster testing")
    
    return df, target_col


def generate_synthetic_data():
    """Generate synthetic data if real dataset not available"""
    from sklearn.datasets import make_classification
    
    print("Generating synthetic health dataset...")
    X, y = make_classification(
        n_samples=800,
        n_features=15,
        n_informative=10,
        n_redundant=5,
        n_classes=3,
        random_state=42,
        class_sep=0.8
    )
    
    # Create DataFrame
    feature_names = [f'feature_{i}' for i in range(X.shape[1])]
    df = pd.DataFrame(X, columns=feature_names)
    df['health_status'] = y
    
    target_col = 'health_status'
    print(f"Generated dataset shape: {df.shape}")
    print(f"Target distribution: {df[target_col].value_counts().to_dict()}")
    
    return df, target_col


def prepare_api_payload(df: pd.DataFrame, target_col: str, algorithm: str) -> Dict:
    """Prepare payload for API request"""
    
    # Convert DataFrame to list of dicts
    data_records = df.to_dict('records')
    
    # Get feature columns (all except target)
    feature_cols = [col for col in df.columns if col != target_col]
    
    # Define parameter grids for each algorithm
    if algorithm == "genetic_algorithm":
        param_grid = {
            "n_estimators": [50, 100, 150],
            "max_depth": [5, 10, None],
            "min_samples_split": [2, 5, 10]
        }
        search_config = {
            "strategy": "genetic_algorithm",
            "population_size": 10,
            "generation": 8,
            "cv": 3
        }
    elif algorithm == "grid_search":
        param_grid = {
            "n_estimators": [50, 100, 150],
            "max_depth": [5, 10, None],
            "min_samples_split": [2, 5]
        }
        search_config = {
            "strategy": "grid_search",
            "cv": 3
        }
    elif algorithm == "bayesian_search":
        param_grid = {
            "n_estimators": [50, 150],  # Will be converted to Integer(50, 150)
            "max_depth": [5, 10, None],  # Will be converted to Categorical
            "min_samples_split": [2, 10]  # Will be converted to Integer(2, 10)
        }
        search_config = {
            "strategy": "bayesian_search",
            "n_calls": 15,
            "cv": 3
        }
    else:
        raise ValueError(f"Unknown algorithm: {algorithm}")
    
    # Build config matching the API's expected format
    config = {
        "choose": "Classification",  # Required field
        "list_feature": feature_cols,  # Feature columns
        "target": target_col,  # Target column
        "metric_sort": "accuracy"  # Metric to optimize
    }
    
    payload = {
        "data": data_records,
        "config": config
    }
    
    return payload


def test_algorithm_via_api(algorithm: str, df: pd.DataFrame, target_col: str) -> Dict:
    """Test a single algorithm via API"""
    print(f"\n{'='*70}")
    print(f"TESTING: {algorithm.upper().replace('_', ' ')}")
    print(f"{'='*70}")
    
    # Prepare payload
    payload = prepare_api_payload(df, target_col, algorithm)
    
    # API endpoint
    url = f"{API_BASE_URL}/train-from-requestbody-json/"
    params = {
        "userId": USER_ID,
        "id_data": f"{DATA_ID}_{algorithm}"
    }
    
    print(f"Sending request to: {url}")
    print(f"Algorithm: {algorithm}")
    print(f"Dataset size: {len(df)} rows, {len(df.columns)} columns")
    
    # Send request
    start_time = time.time()
    try:
        response = requests.post(
            url,
            params=params,
            json=payload,
            timeout=300  # 5 minutes timeout
        )
        elapsed_time = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            
            print(f"\n✅ Success!")
            print(f"   Time: {elapsed_time:.2f}s")
            
            # Extract results
            if isinstance(result, dict):
                best_params = result.get('best_params', {})
                best_score = result.get('best_score', 0)
                all_scores = result.get('best_all_scores', {})
                
                print(f"   Best Score: {best_score:.4f}")
                print(f"   Best Params: {best_params}")
                print(f"   All Scores: {all_scores}")
                
                return {
                    'algorithm': algorithm.replace('_', ' ').title(),
                    'success': True,
                    'best_score': best_score,
                    'best_params': best_params,
                    'all_scores': all_scores,
                    'time': elapsed_time,
                    'response': result
                }
            else:
                print(f"   Response: {result}")
                return {
                    'algorithm': algorithm.replace('_', ' ').title(),
                    'success': True,
                    'time': elapsed_time,
                    'response': result
                }
        else:
            print(f"\n❌ Error: HTTP {response.status_code}")
            print(f"   Response: {response.text}")
            return {
                'algorithm': algorithm.replace('_', ' ').title(),
                'success': False,
                'error': response.text,
                'time': elapsed_time
            }
            
    except requests.exceptions.Timeout:
        elapsed_time = time.time() - start_time
        print(f"\n❌ Timeout after {elapsed_time:.2f}s")
        return {
            'algorithm': algorithm.replace('_', ' ').title(),
            'success': False,
            'error': 'Request timeout',
            'time': elapsed_time
        }
    except Exception as e:
        elapsed_time = time.time() - start_time
        print(f"\n❌ Exception: {e}")
        return {
            'algorithm': algorithm.replace('_', ' ').title(),
            'success': False,
            'error': str(e),
            'time': elapsed_time
        }


def compare_results(results: List[Dict]):
    """Compare and display results"""
    print(f"\n{'='*70}")
    print("COMPARISON RESULTS")
    print(f"{'='*70}")
    
    successful_results = [r for r in results if r.get('success', False)]
    
    if not successful_results:
        print("\n❌ No successful results to compare")
        return None
    
    # Create comparison DataFrame
    comparison_data = []
    for r in successful_results:
        all_scores = r.get('all_scores', {})
        comparison_data.append({
            'Algorithm': r['algorithm'],
            'Best Score': r.get('best_score', 0),
            'Accuracy': all_scores.get('accuracy', 0),
            'Precision': all_scores.get('precision', 0),
            'Recall': all_scores.get('recall', 0),
            'F1': all_scores.get('f1', 0),
            'Time (s)': r['time']
        })
    
    df_comparison = pd.DataFrame(comparison_data)
    print("\n", df_comparison.to_string(index=False))
    
    # Find winner
    if len(df_comparison) > 0 and 'Best Score' in df_comparison.columns:
        best_idx = df_comparison['Best Score'].idxmax()
        print(f"\n🏆 Winner: {df_comparison.loc[best_idx, 'Algorithm']}")
        print(f"   Score: {df_comparison.loc[best_idx, 'Best Score']:.4f}")
        print(f"   Time: {df_comparison.loc[best_idx, 'Time (s)']:.2f}s")
    
    return df_comparison


def check_api_health():
    """Check if API is running"""
    print("Checking API health...")
    try:
        response = requests.get(f"{API_BASE_URL}/docs", timeout=5)
        if response.status_code == 200:
            print("✅ API is running")
            return True
        else:
            print(f"⚠️  API returned status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to API: {e}")
        print(f"   Make sure the API is running at {API_BASE_URL}")
        return False


def main():
    """Main function"""
    print("="*70)
    print("ALGORITHM COMPARISON VIA API")
    print("Health and Lifestyle Dataset")
    print("="*70)
    
    # Check API
    if not check_api_health():
        print("\n❌ Please start the API first:")
        print("   docker run --name hautoml_toolkit_v1 --network host --env-file temp.env hautoml-toolkit python app.py")
        return
    
    # Load dataset
    df, target_col = load_and_prepare_dataset()
    
    # Test algorithms
    algorithms = ["genetic_algorithm", "grid_search", "bayesian_search"]
    results = []
    
    for algo in algorithms:
        result = test_algorithm_via_api(algo, df, target_col)
        results.append(result)
        time.sleep(1)  # Small delay between requests
    
    # Compare results
    df_comparison = compare_results(results)
    
    # Save results
    if df_comparison is not None and len(df_comparison) > 0:
        output_file = 'api_test_results.csv'
        df_comparison.to_csv(output_file, index=False)
        print(f"\n💾 Results saved to '{output_file}'")
    
    # Save detailed results
    with open('api_test_detailed_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"💾 Detailed results saved to 'api_test_detailed_results.json'")


if __name__ == "__main__":
    main()
