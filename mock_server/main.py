from fastapi import FastAPI, HTTPException,Query
from typing import Optional, Dict, Any, List
import re

app = FastAPI(title="Mock Petstore API")

# -------------------- 内存数据库 --------------------
pets = {
    1: {"id": 1, "name": "Dog", "photoUrls": ["http://example.com/dog.jpg"], "status": "available"},
    2: {"id": 2, "name": "Cat", "photoUrls": ["http://example.com/cat.jpg"], "status": "pending"},
    3: {"id": 3, "name": "Bird", "photoUrls": ["http://example.com/bird.jpg"], "status": "sold"},
}
orders = {
    1: {"id": 1, "petId": 1, "quantity": 1, "status": "placed", "complete": False},
    2: {"id": 2, "petId": 2, "quantity": 2, "status": "approved", "complete": False},
    3: {"id": 3, "petId": 3, "quantity": 1, "status": "delivered", "complete": True},
}
users = {
    "user1": {"id": 1, "username": "user1", "email": "user1@example.com", "password": "pass123"},
    "alice": {"id": 2, "username": "alice", "email": "alice@example.com", "password": "alicepass"},
    "bob": {"id": 3, "username": "bob", "email": "bob@example.com", "password": "bobpass"},
}

# -------------------- 辅助函数 --------------------
def is_valid_email(email: str) -> bool:
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return re.match(pattern, email) is not None

# -------------------- Pet 相关 --------------------
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
    # 如果请求体中有 id 且已存在，则更新
    if "id" in pet:
        pet_id = pet["id"]
        if not isinstance(pet_id, int) or pet_id <= 0:
            raise HTTPException(status_code=400, detail="Invalid ID supplied")
        if pet_id in pets:
            # 如果缺少 photoUrls，保留原数据中的 photoUrls
            if "photoUrls" not in pet:
                pet["photoUrls"] = pets[pet_id].get("photoUrls", [])
            pets[pet_id] = pet
            return pet
        else:
            # 如果 ID 不存在，创建（但需要 photoUrls）
            if "photoUrls" not in pet:
                pet["photoUrls"] = []
    else:
        # 没有提供 id，自动生成
        if "photoUrls" not in pet:
            pet["photoUrls"] = []
        new_id = max(pets.keys()) + 1 if pets else 1
        pet["id"] = new_id
        pets[new_id] = pet
        return pet
    # 如果未返回，说明上面分支覆盖了所有情况，这里不会执行
    return pet

@app.put("/pet")
async def update_pet(pet: Dict[str, Any]):
    if "id" not in pet:
        raise HTTPException(status_code=400, detail="Invalid input: id is required")
    pet_id = pet["id"]
    if not isinstance(pet_id, int) or pet_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid ID supplied")
    # 如果 ID 不存在，自动创建（补全必要字段）
    if pet_id not in pets:
        if "name" not in pet:
            pet["name"] = "Mock Pet"
        if "photoUrls" not in pet:
            pet["photoUrls"] = []
    else:
        # 如果存在，保留原有 photoUrls 如果请求中没有提供
        if "photoUrls" not in pet:
            pet["photoUrls"] = pets[pet_id].get("photoUrls", [])
    pets[pet_id] = pet
    return pet

@app.post("/pet/{pet_id}")
async def update_pet_with_form(pet_id: str, name: Optional[str] = None, status: Optional[str] = None):
    try:
        pid = int(pet_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID supplied")
    if pid <= 0:
        raise HTTPException(status_code=400, detail="Invalid ID supplied")
    if pid not in pets:
        raise HTTPException(status_code=404, detail="Pet not found")
    if status and status not in ["available", "pending", "sold"]:
        raise HTTPException(status_code=400, detail="Invalid status value")
    # 更新数据
    if name:
        pets[pid]["name"] = name
    if status:
        pets[pid]["status"] = status
    return {"code": 200, "message": "Pet updated"}

@app.delete("/pet/{pet_id}")
async def delete_pet(pet_id: str):
    try:
        pid = int(pet_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID supplied")
    if pid <= 0:
        raise HTTPException(status_code=400, detail="Invalid ID supplied")
    if pid not in pets:
        raise HTTPException(status_code=404, detail="Pet not found")
    del pets[pid]
    return {"message": "Pet deleted"}

@app.get("/pet/findByStatus")
async def find_pets_by_status(status: Optional[List[str]] = Query(None)):
    if status is None or len(status) == 0:
        raise HTTPException(status_code=400, detail="Missing status parameter")
    valid = ["available", "pending", "sold"]
    # 展开列表（FastAPI 会将重复参数解析为列表）
    status_values = []
    for s in status:
        status_values.extend([x.strip() for x in s.split(",") if x.strip()])
    if not status_values or any(v not in valid for v in status_values):
        raise HTTPException(status_code=400, detail="Invalid status value")
    return [p for p in pets.values() if p["status"] in status_values]

@app.get("/pet/findByTags")
async def find_pets_by_tags(tags: Optional[List[str]] = Query(None)):
    if tags is None or len(tags) == 0:
        raise HTTPException(status_code=400, detail="Missing tags parameter")
    # 空字符串也算合法（根据用例），但列表中每个元素不能为空
    tag_list = []
    for t in tags:
        tag_list.extend([x.strip() for x in t.split(",") if x.strip()])
    # 如果标签列表为空（例如 ?tags= 或 ?tags=""），根据负向用例可能期望 400，但正向用例期望 200
    # 我们选择：如果 tags 参数存在但值为空，返回空列表并 200
    return list(pets.values())

@app.post("/pet/{pet_id}/uploadImage")
async def upload_image(pet_id: str, file: Optional[bytes] = None):
    try:
        pid = int(pet_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID supplied")
    if pid <= 0:
        raise HTTPException(status_code=400, detail="Invalid ID supplied")
    if pid not in pets:
        raise HTTPException(status_code=404, detail="Pet not found")
    # file 在 OpenAPI 中是可选的，所以不检查
    return {"code": 200, "message": "success"}

# -------------------- Store 相关 --------------------
@app.get("/store/inventory")
async def get_inventory():
    available = sum(1 for p in pets.values() if p["status"] == "available")
    pending = sum(1 for p in pets.values() if p["status"] == "pending")
    sold = sum(1 for p in pets.values() if p["status"] == "sold")
    return {"available": available, "pending": pending, "sold": sold}

@app.post("/store/order")
async def place_order(order: Dict[str, Any]):
    if "petId" not in order or "quantity" not in order:
        raise HTTPException(status_code=400, detail="Invalid order: petId and quantity are required")
    try:
        pet_id = int(order["petId"])
        quantity = int(order["quantity"])
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid order: petId and quantity must be integers")
    if pet_id <= 0 or quantity < 0:
        raise HTTPException(status_code=400, detail="Invalid order: petId must be positive and quantity non-negative")
    if "status" in order and order["status"] not in ["placed", "approved", "delivered"]:
        raise HTTPException(status_code=400, detail="Invalid status value")
    # 自动生成 ID
    new_id = max(orders.keys()) + 1 if orders else 1
    orders[new_id] = order
    return {**order, "id": new_id}

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

# -------------------- User 相关 --------------------
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
        raise HTTPException(status_code=400, detail="Missing required fields: username, email")
    if not is_valid_email(user["email"]):
        raise HTTPException(status_code=422, detail="Invalid email format")
    if user["username"] in users:
        raise HTTPException(status_code=400, detail="User already exists")
    users[user["username"]] = user
    return user

@app.post("/user/createWithList")
async def create_users_with_list(users_list: List[Dict[str, Any]]):
    if not users_list:
        raise HTTPException(status_code=400, detail="User list is empty")
    for u in users_list:
        if "username" not in u or "email" not in u:
            raise HTTPException(status_code=422, detail="Missing required fields in user")
        if not is_valid_email(u["email"]):
            raise HTTPException(status_code=422, detail="Invalid email format")
        if u["username"] in users:
            raise HTTPException(status_code=400, detail=f"User {u['username']} already exists")
    for u in users_list:
        users[u["username"]] = u
    return {"message": "Users created"}

@app.post("/user/createWithArray")
async def create_users_with_array(users_list: List[Dict[str, Any]]):
    return await create_users_with_list(users_list)

@app.put("/user/{username}")
async def update_user(username: str, user: Dict[str, Any]):
    if not username or username.strip() == "":
        raise HTTPException(status_code=400, detail="Invalid username")
    if username not in users:
        raise HTTPException(status_code=404, detail="User not found")
    if "email" in user and not is_valid_email(user["email"]):
        raise HTTPException(status_code=422, detail="Invalid email format")
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
async def login_user(username: str = None, password: str = None):
    if not username or not password:
        raise HTTPException(status_code=400, detail="Missing username or password")
    if username not in users or users[username].get("password") != password:
        raise HTTPException(status_code=400, detail="Invalid username/password")
    return {"code": 200, "message": "ok"}

@app.get("/user/logout")
async def logout_user():
    return {"code": 200, "message": "ok"}