# from src.backend.users.connect_db import get_database

# dbname = get_database()
# tbl_user = dbname['Tbl_User'] # collection name


def checkLogin(username, pwd):
    return True

# def check_exits_username(username):
#     result = tbl_user.find_one({'username': username})
#     if result:
#         return True
#     else:
#         return False