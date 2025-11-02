from pymongo import MongoClient
import yaml
import os


# Get the directory of the current file and construct the config path
current_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(os.path.dirname(current_dir), ".config.yml")

with open(config_path, "r") as f:
    data = yaml.safe_load(f)
connection_string = data['MONGODB_CONNECT']

def get_database(): 
    try:
        client = MongoClient(connection_string)
        return client['AutoML']
    except:
        return -1


if __name__ == "__main__":
    dbname = get_database()
    # Kiểm tra kết nối đã được thiết lập thành công hay không
    if dbname is not None:
        print("Kết nối đến cơ sở dữ liệu MongoDB thành công.")
    else:
        print("Kết nối đến cơ sở dữ liệu MongoDB không thành công.")
