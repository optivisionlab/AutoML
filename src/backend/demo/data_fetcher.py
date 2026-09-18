# Standard Libraries
import pandas as pd

# Third-party Libraries
from ucimlrepo import fetch_ucirepo


def fetch_uci_dataset(dataset_choice: str):
    """
    Pulling data from UCI
    """
    try:
        if not dataset_choice:
            return "### Please select dataset", "", pd.DataFrame(), None
        
        # Extract ID number
        dataset_id = int(dataset_choice.split("ID: ")[1].replace(")", ""))
        
        # Call the UCI library
        dataset = fetch_ucirepo(id=dataset_id)
        
        df_full = pd.concat([dataset.data.features, dataset.data.targets], axis=1)
        
        # Prepare metadata
        title = f"### Dataset: {dataset.metadata.name}"
        desc = dataset.metadata.abstract or "No detailed description"
        
        df_preview = df_full.head(15)
        
        return title, desc, df_preview, df_full
        
    except Exception as e:
        return f"### System error", f"Details: {str(e)}", pd.DataFrame(), None
