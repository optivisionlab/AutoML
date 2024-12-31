import pandas as pd
import yaml
import json
from pathlib import Path
import os

current_file_path = Path(__file__).resolve()
project_root = current_file_path.parents[3]
csv_file_path = os.path.join(project_root,'docs' ,'data', 'glass.csv')
yml_file_path = os.path.join(project_root,'docs' ,'data', 'config.yml')

df = pd.read_csv(csv_file_path)
csv_data = df.to_dict(orient='records')

with open(yml_file_path, 'r') as yml_file:
    yml_data = yaml.safe_load(yml_file)

json_content = {
    "data": csv_data,
    "config": yml_data
}


json_file_path = "D:\Hoc\LAB\AutoML\AutoML\docs\data\output.json"
with open(json_file_path, 'w') as json_file:
    json.dump(json_content, json_file, indent=4)

print("Nội dung đã được lưu vào file JSON.")