from fastapi import FastAPI, Request, HTTPException
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

app = FastAPI(title="Mock Petstore API")

# 模拟数据存储
pets = {
    1: {"id": 1, "name": "Dog", "photoUrls": ["http://example.com/dog.jpg"], "status": "available"},
    2: {"id": 2, "name": "Cat", "photoUrls": ["http://example.com/cat.jpg"], "status": "pending"},
}
orders = {
    1: {"id": 1, "petId": 1, "quantity": 1, "status": "placed", "complete": False}
}
users = {
    "user1": {"id": 1, "username": "user1", "email": "user1@example.com", "password": "pass123"}
}

# ---------- Pet 相关 ----------
@app.get("/pet/{pet_id}")
async def get_pet(pet_id: str):
    try:
        pid = int(pet_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID supplied")
    if pid <= 0:
        raise HTTPException(status_code=400, detail="Invalid ID supplied")
    if pid not in pets:
        raise HTTPException(status_code=404, detail="Pet not found")
    return pets[pid]

@app.post("/pet")
async def create_pet(pet: Dict[str, Any]):
    if "name" not in pet or "photoUrls" not in pet:
        raise HTTPException(status_code=400, detail="Invalid input")
    new_id = max(pets.keys()) + 1 if pets else 1
    pets[new_id] = pet
    return {**pet, "id": new_id}

@app.put("/pet/{pet_id}")
async def update_pet(pet_id: str, pet: Dict[str, Any]):
    try:
        pid = int(pet_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID supplied")
    if pid <= 0:
        raise HTTPException(status_code=400, detail="Invalid ID supplied")
    if pid not in pets:
        raise HTTPException(status_code=404, detail="Pet not found")
    if "name" not in pet or "photoUrls" not in pet:
        raise HTTPException(status_code=400, detail="Invalid input")
    pets[pid] = pet
    return pet

@app.post("/pet/{pet_id}/uploadImage")
async def upload_image(pet_id: str, file: Optional[bytes] = None):
    try:
        pid = int(pet_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID supplied")
    if pid <= 0:
        raise HTTPException(status_code=400, detail="Invalid ID supplied")
    if file is None:
        raise HTTPException(status_code=400, detail="File is required")
    return {"code": 200, "message": "success"}

@app.get("/pet/findByStatus")
async def find_pets_by_status(status: Optional[str] = None):
    if status not in ["available", "pending", "sold"]:
        raise HTTPException(status_code=400, detail="Invalid status value")
    return [p for p in pets.values() if p["status"] == status]

@app.get("/pet/findByTags")
async def find_pets_by_tags(tags: Optional[str] = None):
    if not tags:
        raise HTTPException(status_code=400, detail="Invalid tags value")
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    if not tag_list:
        raise HTTPException(status_code=400, detail="Invalid tags value")
    # 简化：返回所有宠物
    return list(pets.values())

# ---------- Store 相关 ----------
@app.get("/store/inventory")
async def get_inventory():
    return {"available": sum(1 for p in pets.values() if p["status"] == "available")}

@app.post("/store/order")
async def place_order(order: Dict[str, Any]):
    if "petId" not in order or "quantity" not in order:
        raise HTTPException(status_code=400, detail="Invalid order")
    try:
        pet_id = int(order["petId"])
        quantity = int(order["quantity"])
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid order")
    if pet_id <= 0 or quantity < 0:
        raise HTTPException(status_code=400, detail="Invalid order")
    order_id = max(orders.keys()) + 1 if orders else 1
    orders[order_id] = order
    return {**order, "id": order_id}

@app.get("/store/order/{order_id}")
async def get_order(order_id: str):
    try:
        oid = int(order_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID supplied")
    if oid <= 0 or oid > 10:
        raise HTTPException(status_code=400, detail="Invalid ID supplied")
    if oid not in orders:
        raise HTTPException(status_code=404, detail="Order not found")
    return orders[oid]

@app.delete("/store/order/{order_id}")
async def delete_order(order_id: str):
    try:
        oid = int(order_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID supplied")
    if oid <= 0:
        raise HTTPException(status_code=400, detail="Invalid ID supplied")
    if oid not in orders:
        raise HTTPException(status_code=404, detail="Order not found")
    del orders[oid]
    return {"message": "Order deleted"}

# ---------- User 相关 ----------
@app.get("/user/{username}")
async def get_user(username: str):
    if not username or username.strip() == "":
        raise HTTPException(status_code=400, detail="Invalid username")
    if username not in users:
        raise HTTPException(status_code=404, detail="User not found")
    return users[username]

@app.post("/user")
async def create_user(user: Dict[str, Any]):
    if "username" not in user or "email" not in user:
        raise HTTPException(status_code=400, detail="Missing required fields")
    # 简单 email 格式检查
    email = user["email"]
    if "@" not in email or "." not in email:
        raise HTTPException(status_code=422, detail="Invalid email format")
    if user["username"] in users:
        raise HTTPException(status_code=400, detail="User already exists")
    users[user["username"]] = user
    return user

@app.put("/user/{username}")
async def update_user(username: str, user: Dict[str, Any]):
    if not username or username.strip() == "":
        raise HTTPException(status_code=400, detail="Invalid username")
    if username not in users:
        raise HTTPException(status_code=404, detail="User not found")
    if "email" not in user:
        raise HTTPException(status_code=400, detail="Missing required fields")
    users[username] = user
    return user

@app.delete("/user/{username}")
async def delete_user(username: str):
    if not username or username.strip() == "":
        raise HTTPException(status_code=400, detail="Invalid username")
    if username not in users:
        raise HTTPException(status_code=404, detail="User not found")
    del users[username]
    return {"message": "User deleted"}

@app.get("/user/login")
async def login_user(username: Optional[str] = None, password: Optional[str] = None):
    if not username or not password:
        raise HTTPException(status_code=400, detail="Missing username or password")
    if username not in users or users[username]["password"] != password:
        raise HTTPException(status_code=400, detail="Invalid username/password")
    return {"code": 200, "message": "ok"}

@app.get("/user/logout")
async def logout_user():
    return {"code": 200, "message": "ok"}

# 通用回退：其他未实现路径返回 200（可根据需要调整）
@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def catch_all(full_path: str, request: Request):
    return {"message": "Mock success", "path": full_path}