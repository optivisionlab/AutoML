from pymongo import MongoClient
import yaml


file_path = ".config.yml"
with open(file_path, "r") as f:
    data = yaml.safe_load(f)
connection_string = data['MONGODB_CONNECT']

def get_database(): 
    try:
        client = MongoClient(connection_string)
        return client['AutoML']
    except:
        return -1


# if __name__ == "__main__":
#     dbname = get_database()
#     # Kiểm tra kết nối đã được thiết lập thành công hay không
#     if dbname is not None:
#         print("Kết nối đến cơ sở dữ liệu MongoDB thành công.")
#     else:
#         print("Kết nối đến cơ sở dữ liệu MongoDB không thành công.")
