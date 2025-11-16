"""
Script to download Health and Lifestyle dataset from Kaggle
Dataset: https://www.kaggle.com/datasets/chik0di/health-and-lifestyle-dataset
"""

import os
import sys

def download_dataset():
    """Download dataset using Kaggle API"""
    try:
        import kaggle
        print("Kaggle API found. Downloading dataset...")
        
        # Download dataset
        kaggle.api.dataset_download_files(
            'chik0di/health-and-lifestyle-dataset',
            path='.',
            unzip=True
        )
        
        print("✅ Dataset downloaded successfully!")
        
        # List downloaded files
        files = [f for f in os.listdir('.') if f.endswith('.csv')]
        if files:
            print(f"\nDownloaded files: {files}")
        
        return True
        
    except ImportError:
        print("❌ Kaggle API not installed.")
        print("\nTo install:")
        print("  pip install kaggle")
        print("\nThen configure your API credentials:")
        print("  1. Go to https://www.kaggle.com/account")
        print("  2. Click 'Create New API Token'")
        print("  3. Place kaggle.json in ~/.kaggle/")
        return False
        
    except Exception as e:
        print(f"❌ Error downloading dataset: {e}")
        print("\nAlternative: Download manually from:")
        print("  https://www.kaggle.com/datasets/chik0di/health-and-lifestyle-dataset")
        return False


if __name__ == "__main__":
    download_dataset()
