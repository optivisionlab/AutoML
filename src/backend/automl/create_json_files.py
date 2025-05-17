import pandas as pd
import yaml
import json
from pathlib import Path
import os

project_root = "assets/end_users"
csv_file_path = os.path.join(project_root, 'online_shoppers_intention.csv')
yml_file_path = os.path.join(project_root, 'config-data-pka.yaml')

df = pd.read_csv(csv_file_path)
csv_data = df.to_dict(orient='records')

with open(yml_file_path, 'r') as yml_file:
    yml_data = yaml.safe_load(yml_file)

json_content = {
    "data": csv_data,
    "config": yml_data
}


json_file_path = os.path.join(project_root, 'input_json_body.json')
with open(json_file_path, 'w') as json_file:
    json.dump(json_content, json_file, indent=4)

print("Nội dung đã được lưu vào file JSON.")