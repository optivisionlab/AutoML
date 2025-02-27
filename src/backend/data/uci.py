from ucimlrepo import fetch_ucirepo 
import pandas as pd
import numpy as np

def get_data_uci_where_id(id):
    data_uci = fetch_ucirepo(id=id) 
    X = data_uci.data.features 
    y = data_uci.data.targets
    df = pd.concat([X, y], axis=1)
    class_names = np.unique(y.values.T[0])
    return df, class_names


def format_data_automl(rows, cols, class_name):
    data_output = []
    for row in rows:
        item = {}
        for key, value in zip(cols, row):
            item[key] = value
        key_last = list(item.keys())[-1]
        item[key_last] = class_name.index(item[key_last])
        data_output.append(item)
    return data_output