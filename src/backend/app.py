from fastapi import FastAPI, UploadFile, File, status, HTTPException, Form
import cv2, datetime, os, tempfile, uvicorn, uuid
import numpy as np
from typing import List
from fastapi.responses import JSONResponse
from io import BytesIO
import pandas as pd
from users.engine import checkLogin
import pathlib
from automl.engine import get_config, train_process, get_data_and_config_from_MongoDB

# default sync
app = FastAPI()

@app.get("/")
def ping():
    return{
        "AutoML": "version 1.0",
        "message": "Hi there :P"
    }


@app.post("/login")
def api_login(username: str = Form(...), password: str = Form(...)):

    if checkLogin(username=username, pwd=password):
        message = "Login OKE >>> "

    message += "This is Users"
    if username == "Admin" and password == "Admin":
        message += "This is Admin"

    return{
        "username": username,
        "password": password,
        "message": message
    }


@app.post("/upload-files")
def api_login(files: List[UploadFile] = File(...), sep: str = Form(...)):
    
    """
        file: test.csv
        stem => test
        suffix => .csv
    """

    data_list = []
    files_list = []
    for file in files:
        if pathlib.Path(os.path.basename(file.filename)).suffix != ".csv":
            data_list.append(None)
            files_list.append(file.filename)
            continue

        files_list.append(file.filename)
        contents = file.file.read()
        data = BytesIO(contents)
        df = pd.read_csv(data, on_bad_lines='skip', sep=sep, engine='python')
        data_list.append(df.values.tolist())
        data.close()
        file.file.close()

    return {
        "data_list": data_list,
        "files_list": files_list
    } 


@app.post("/training_file_local")
def api_train1(file_data: UploadFile, file_config : UploadFile):

    
    contents = file_data.file.read()
    data_file = BytesIO(contents)
    data = pd.read_csv(data_file)

    contents = file_config.file.read()
    data_file = BytesIO(contents)
    choose, list_model_search, list_feature, target, matrix,models = get_config(data_file)


    best_model_id, best_model ,best_score, best_params = train_process(data, choose, list_model_search, list_feature, target,matrix,models)
    
    return {
        "Best Model ID: ": best_model_id,
        "Best Model: ": str(best_model),
        "Best Params: ": best_params,
        "Best Score: ": best_score
    } 


@app.post("/training_file_MongoDB")
def api_train2():
    data, choose, list_model_search, list_feature, target,matrix,models = get_data_and_config_from_MongoDB()
    best_model_name, best_model ,best_score, best_params = train_process(data, choose, list_model_search, list_feature, target,matrix,models)
    
    return {
        "Best Model Name: ": best_model_name,
        "Best Model: ": str(best_model),
        "Best Params: ": best_params,
        "Best Score: ": best_score
    } 


if __name__ == "__main__":
    uvicorn.run('app:app', host="0.0.0.0", port=9999, reload=True)
    pass
