import requests
import json

import requests
import json

def test_正常上传图片():
    url = "http://localhost:5000/pet/1/uploadImage"
    headers = {"Content-Type": "multipart/form-data"}
    payload = {}
    method = "post"
    response = requests.request(method, url, headers=headers, json=payload)
    assert response.status_code == 200
    
    
    
    
    
    
    

import requests
import json

def test_petId_为负数():
    url = "http://localhost:5000/pet/-1/uploadImage"
    headers = {"Content-Type": "multipart/form-data"}
    payload = {}
    method = "post"
    response = requests.request(method, url, headers=headers, json=payload)
    assert response.status_code == 400
    
    
    assert "invalid petId" in response.text
    
    

import requests
import json

def test_petId_缺失_路径参数为空_():
    url = "http://localhost:5000/pet//uploadImage"
    headers = {"Content-Type": "multipart/form-data"}
    payload = {}
    method = "post"
    response = requests.request(method, url, headers=headers, json=payload)
    assert response.status_code == 404
    
    
    assert "not found" in response.text
    
    

import requests
import json

def test_缺少必需的_file_参数():
    url = "http://localhost:5000/pet/123/uploadImage"
    headers = {"Content-Type": "multipart/form-data"}
    payload = {}
    method = "post"
    response = requests.request(method, url, headers=headers, json=payload)
    assert response.status_code == 400
    
    
    assert "file is required" in response.text
    
    

import requests
import json

def test_petId_超出_int64_边界_极大值_():
    url = "http://localhost:5000/pet/9223372036854775808/uploadImage"
    headers = {"Content-Type": "multipart/form-data"}
    payload = {}
    method = "post"
    response = requests.request(method, url, headers=headers, json=payload)
    assert response.status_code == 400
    
    
    assert "invalid" in response.text
    
    