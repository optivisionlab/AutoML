from fastapi import FastAPI, UploadFile, File, status, HTTPException, Form
import cv2, datetime, os, tempfile, uvicorn, uuid
import numpy as np
from typing import List
from fastapi.responses import JSONResponse
from io import BytesIO
import pandas as pd


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
    message = "This is Users"
    if username == "Admin" and password == "Admin":
        message = "This is Admin"

    return{
        "username": username,
        "password": password,
        "message": message
    }


@app.post("/upload-files")
def api_login(files: List[UploadFile] = File(...), mode: str = Form(...), sep: str = Form(...)):
    
    if mode != "csv":
        return{
            "data": None,
            "messages": "File not CSV",
        }

    data_list = []
    files_list = []
    for file in files:
        files_list.append(file.filename)
        contents = file.file.read()
        data = BytesIO(contents)
        df = pd.read_csv(data, on_bad_lines='skip', sep=sep, engine='python')
        data_list.append(df.values.tolist())
        data.close()
        file.file.close()

    return{
        "data_list": data_list,
        "files_list": files_list
    } 


if __name__ == "__main__":
    uvicorn.run('app:app', host="0.0.0.0", port=9999, reload=True)
    pass
