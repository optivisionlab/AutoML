# Standard Libraries
import ssl
import logging

# Fix SSL context for UCI repository downloads over network
ssl._create_default_https_context = ssl._create_unverified_context

# Third-party Libraries
import pandas as pd
from ucimlrepo import fetch_ucirepo

# Logging
logger = logging.getLogger("demo_data_fetcher")


def fetch_uci_dataset(dataset_choice: str) -> tuple[str, str, pd.DataFrame, pd.DataFrame | None]:
    """
    Fetch dataset directly from UCI Machine Learning Repository via ucimlrepo into memory.
    No disk caching is performed.
    """
    if not dataset_choice:
        return "### Please select dataset", "", pd.DataFrame(), None

    try:
        # Extract ID number from selection string
        if "ID: " not in dataset_choice:
            raise ValueError(f"Could not parse dataset ID from '{dataset_choice}'")

        dataset_id = int(dataset_choice.split("ID: ")[1].replace(")", "").strip())
        logger.info(f"Downloading dataset ID {dataset_id} from UCI repository over network...")

        dataset = fetch_ucirepo(id=dataset_id)
        if dataset is None or dataset.data is None:
            raise ValueError(f"No data returned for UCI dataset ID {dataset_id}")

        features = dataset.data.features
        targets = dataset.data.targets

        # If targets is a DataFrame with multiple columns, select the primary target column
        if isinstance(targets, pd.DataFrame):
            if targets.shape[1] > 1:
                targets = targets.iloc[:, [0]]
        elif isinstance(targets, pd.Series):
            targets = targets.to_frame()

        df_full = pd.concat([features, targets], axis=1)

        # Clean rows with NaN values
        df_full = df_full.dropna(how="all")
        if df_full.isnull().values.any():
            df_full = df_full.dropna()

        title = f"### Dataset: {dataset.metadata.name}"
        desc = dataset.metadata.abstract or "Benchmark dataset from UCI Machine Learning Repository."

        return title, desc, df_full.head(15), df_full

    except Exception as e:
        logger.error(f"Failed to fetch dataset '{dataset_choice}' from UCI repository: {e}", exc_info=True)
        return "", "", pd.DataFrame(), None
