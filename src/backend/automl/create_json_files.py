import pandas as pd
import yaml
import json
from pathlib import Path
import os
from sklearn.preprocessing import LabelEncoder

current_file_path = Path(__file__).resolve()
project_root = current_file_path.parents[3]
csv_file_path = os.path.join(project_root,'src' ,'backend', 'assets', 'end_users', 'online_shoppers_intention.csv')
yml_file_path = os.path.join(project_root,'src' ,'backend', 'assets', 'end_users', 'config-data-pka.yaml')
json_file_path = os.path.join(project_root,'src' ,'backend', 'assets', 'end_users', 'input_json_file_osi.json')
df = pd.read_csv(csv_file_path)

for column in df.columns:
    if df[column].dtype == 'object':
        le = LabelEncoder()
        df[column] = le.fit_transform(df[column])

with open(yml_file_path, 'r') as yml_file:
    yml_data = yaml.safe_load(yml_file)

csv_data = df.to_dict(orient='records')
json_content = {
    "data": csv_data,
    "config": yml_data
}

with open(json_file_path, 'w') as json_file:
    json.dump(json_content, json_file, indent=4)

print("Dữ liệu đã được lưu vào file JSON.")
