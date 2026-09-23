"""
mock_server/main.py
自动生成，请勿手动修改。如需修改请编辑 scripts/generate_mock.py
"""
import re
from fastapi import FastAPI, HTTPException, Query, Request,Form
from typing import Optional, List, Dict, Any

app = FastAPI(title="Mock API (Generated from OpenAPI)")

# ========== 预置资源 ==========
PETS = {
    1: {'id': 1, 'name': 'Dog', 'photoUrls': ['http://example.com/dog.jpg'], 'status': 'available'},
    2: {'id': 2, 'name': 'Cat', 'photoUrls': ['http://example.com/cat.jpg'], 'status': 'pending'},
    3: {'id': 3, 'name': 'Bird', 'photoUrls': ['http://example.com/bird.jpg'], 'status': 'sold'},
}
USERS = {
    'user1': {'id': 1, 'username': 'user1', 'email': 'user1@example.com', 'password': 'pass123'},
    'alice': {'id': 2, 'username': 'alice', 'email': 'alice@example.com', 'password': 'alicepass'},
    'bob': {'id': 3, 'username': 'bob', 'email': 'bob@example.com', 'password': 'bobpass'},
}
# 登录校验用的权威预置凭据（与可变的 USERS 解耦，避免被 createUser/updateUser 改写影响登录）
LOGIN_CREDS = {
    'user1': 'pass123',
    'alice': 'alicepass',
    'bob': 'bobpass',
}
ORDERS = {
    1: {'id': 1, 'petId': 1, 'quantity': 1, 'status': 'placed', 'complete': False},
    2: {'id': 2, 'petId': 2, 'quantity': 2, 'status': 'approved', 'complete': False},
    3: {'id': 3, 'petId': 3, 'quantity': 1, 'status': 'delivered', 'complete': True},
}

def is_valid_email(email: str) -> bool:
    return re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", email) is not None

def unwrap_body(body):
    """兼容模型多包一层 body 的情况"""
    if isinstance(body, dict) and "body" in body:
        return body["body"]
    return body

@app.post("/pet/{petId}/uploadImage")
async def uploadFile(petId: str):
    """uploads an image"""
    # 校验 petId
    try:
        pid = int(petId)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail='Invalid petId supplied')
    if pid <= 0:
        raise HTTPException(status_code=400, detail='Invalid petId supplied')
    return {"code": 200, "message": "success"}

@app.post("/pet")
async def addPet(body: Dict[str, Any]):
    """Add a new pet to the store"""
    body = unwrap_body(body)
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Invalid body")
    # 规范 Pet 必填字段为 name + photoUrls，id 可选自动生成
    if "name" not in body:
        raise HTTPException(status_code=400, detail="Missing required field: name")
    if "photoUrls" not in body or not isinstance(body.get("photoUrls"), list):
        raise HTTPException(status_code=400, detail="Missing required field: photoUrls")
    if "status" in body and body["status"] not in ["available", "pending", "sold"]:
        raise HTTPException(status_code=400, detail='Invalid status value')
    if body.get("id") is None:
        body["id"] = max(PETS.keys()) + 1 if PETS else 1
    PETS[body["id"]] = body
    return body

@app.put("/pet")
async def updatePet(body: Dict[str, Any]):
    """Update an existing pet"""
    body = unwrap_body(body)
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Invalid body")
    if "name" not in body:
        raise HTTPException(status_code=400, detail="Missing required field: name")
    if "photoUrls" not in body or not isinstance(body.get("photoUrls"), list):
        raise HTTPException(status_code=400, detail="Missing required field: photoUrls")
    if "status" in body and body["status"] not in ["available", "pending", "sold"]:
        raise HTTPException(status_code=400, detail='Invalid status value')
    pet_id = body.get("id")
    if pet_id is None:
        pet_id = max(PETS.keys()) + 1 if PETS else 1
        body["id"] = pet_id
    elif not isinstance(pet_id, int) or pet_id <= 0:
        raise HTTPException(status_code=400, detail='Invalid ID supplied')
    PETS[pet_id] = body
    return body

@app.get("/pet/findByStatus")
async def findPetsByStatus(status: Optional[List[str]] = Query(None)):
    """Finds Pets by status"""
    if not status:
        raise HTTPException(status_code=400, detail='Missing status parameter')
    valid = ["available", "pending", "sold"]
    status_values = []
    for s in status:
        status_values.extend([x.strip() for x in s.split(",") if x.strip()])
    if not status_values or any(v not in valid for v in status_values):
        raise HTTPException(status_code=400, detail='Invalid status value')
    # 用 .get() 防止 KeyError
    return [p for p in PETS.values() if p.get("status") in status_values]

@app.get("/pet/findByTags")
async def findPetsByTags(tags: Optional[List[str]] = Query(None)):
    if not tags:
        raise HTTPException(status_code=400, detail='Missing tags parameter')
    tag_values = []
    for t in tags:
        tag_values.extend([x.strip() for x in t.split(",") if x.strip()])
    if not tag_values or all(t.isdigit() for t in tag_values):
        raise HTTPException(status_code=400, detail='Invalid tags value')
    return list(PETS.values())

@app.get("/pet/{petId}")
async def getPetById(petId: str):
    """Find pet by ID"""
    # 校验 petId
    try:
        pid = int(petId)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail='Invalid petId supplied')
    if int(petId) <= 0:
        raise HTTPException(status_code=400, detail='Invalid petId supplied')
    if pid not in PETS:
        raise HTTPException(status_code=404, detail='Pet not found')
    return PETS[pid]

@app.post("/pet/{petId}")
async def updatePetWithForm(
    petId: str,
    request: Request,
    name: str = Form(None),
    status: str = Form(None)
):
    """Updates a pet in the store with form data"""
    # 兼容 JSON body 形式（仅当 form 字段均缺失时尝试解析）
    if name is None and status is None:
        try:
            body = await request.json()
        except Exception:
            body = {}
        if isinstance(body, dict):
            if "body" in body:
                body = body["body"]
            if isinstance(body, dict):
                name = body.get("name", name)
                status = body.get("status", status)
    # 校验 petId
    try:
        pid = int(petId)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail='Invalid petId supplied')
    if int(petId) <= 0:
        raise HTTPException(status_code=400, detail='Invalid petId supplied')
    if pid not in PETS:
        raise HTTPException(status_code=404, detail='Pet not found')
    if status is not None and status not in ["available", "pending", "sold"]:
        raise HTTPException(status_code=400, detail='Invalid status value')
    if name is not None:
        PETS[pid]["name"] = name
    if status is not None:
        PETS[pid]["status"] = status
    return {"code": 200, "message": "Pet updated"}

@app.delete("/pet/{petId}")
async def deletePet(petId: str):
    """Deletes a pet"""
    # 校验 petId
    try:
        pid = int(petId)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail='Invalid petId supplied')
    if int(petId) <= 0:
        raise HTTPException(status_code=400, detail='Invalid petId supplied')
    if pid not in PETS:
        raise HTTPException(status_code=404, detail='Pet not found')
    del PETS[pid]
    return {"message": "Pet deleted"}

@app.get("/store/inventory")
async def getInventory(request:Request):
    """Returns pet inventories by status"""
    # inventory 无查询参数，拒绝多余的未知参数（与 logout 的校验保持一致）
    if request.query_params:
        raise HTTPException(status_code=400, detail='Unexpected query parameters')
    result = {}
    for p in PETS.values():
        s = p.get("status", "unknown")
        result[s] = result.get(s, 0) + 1
    return result

@app.post("/store/order")
async def placeOrder(body: Dict[str, Any]):
    """Place an order for a pet"""
    if "petId" not in body or "quantity" not in body:
        raise HTTPException(status_code=400, detail='Invalid order: petId and quantity are required')
    try:
        pet_id = int(body["petId"])
        quantity = int(body["quantity"])
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail='Invalid order: petId and quantity must be integers')
    if pet_id <= 0 or quantity < 0:
        raise HTTPException(status_code=400, detail='Invalid order values')
    if "status" in body and body["status"] not in ["placed", "approved", "delivered"]:
        raise HTTPException(status_code=400, detail='Invalid status value')
    new_id = max(ORDERS.keys()) + 1 if ORDERS else 1
    body["id"] = new_id
    ORDERS[new_id] = body
    return body

@app.get("/store/order/{orderId}")
async def getOrderById(orderId: str):
    """Find purchase order by ID"""
    # 校验 orderId
    try:
        oid = int(orderId)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail='Invalid orderId supplied')
    if oid <= 0 or oid > 10:
        raise HTTPException(status_code=400, detail='Invalid orderId supplied')
    if oid not in ORDERS:
        raise HTTPException(status_code=404, detail='Order not found')
    return ORDERS[oid]

@app.delete("/store/order/{orderId}")
async def deleteOrder(orderId: str):
    """Delete purchase order by ID"""
    # 校验 orderId
    try:
        oid = int(orderId)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail='Invalid orderId supplied')
    if int(orderId) <= 0:
        raise HTTPException(status_code=400, detail='Invalid orderId supplied')
    if oid not in ORDERS:
        raise HTTPException(status_code=404, detail='Order not found')
    del ORDERS[oid]
    return {"message": "Order deleted"}


@app.get("/user/login")
async def loginUser(username: str = None, password: str = None):
    """Logs user into the system"""
    if not username or not password:
        raise HTTPException(status_code=400, detail='Missing username or password')
    # 校验凭据是否匹配权威预置账号（不受 createUser/updateUser 改写影响）
    if LOGIN_CREDS.get(username) != password:
        raise HTTPException(status_code=400, detail='Invalid username/password supplied')
    return {"code": 200, "message": "ok", "type": "string"}

@app.get("/user/logout")
async def logoutUser(request:Request):
    """Logs out current logged in user session"""
    if request.query_params:
        raise HTTPException(status_code=400, detail='Unexpected query parameters')
    return {"code": 200, "message": "ok"}

@app.get("/user/{username}")
async def getUserByName(username: str):
    """Get user by user name"""
    # 校验 username
    if not username or not username.strip():
        raise HTTPException(status_code=400, detail='Invalid username')
    if not re.match(r"^[a-zA-Z0-9_.-]+$", username):
        raise HTTPException(status_code=400, detail='Invalid username format')
    if username not in USERS:
        raise HTTPException(status_code=404, detail='User not found')
    return USERS[username]

@app.put("/user/{username}")
async def updateUser(username: str, body: Dict[str, Any]):
    """Updated user"""
    body = unwrap_body(body)
    # 校验 username
    if not username or not username.strip():
        raise HTTPException(status_code=400, detail='Invalid username supplied')
    if not re.match(r"^[a-zA-Z0-9_.-]+$", username):
        raise HTTPException(status_code=400, detail='Invalid username format')
    if not isinstance(body, dict) or "username" not in body:
        raise HTTPException(status_code=400, detail='Missing required field: username')
    if body["username"] != username:
        raise HTTPException(status_code=400, detail='Username mismatch')
    if "email" in body and not is_valid_email(body["email"]):
        raise HTTPException(status_code=422, detail='Invalid email format')
    USERS[username] = body
    return body

@app.delete("/user/{username}")
async def deleteUser(username: str):
    """Delete user"""
    # 校验 username
    if not username or not username.strip():
        raise HTTPException(status_code=400, detail='Invalid username supplied')
    if not re.match(r"^[a-zA-Z0-9_.-]+$", username):
        raise HTTPException(status_code=400, detail='Invalid username supplied')
    if username not in USERS:
        raise HTTPException(status_code=404, detail='User not found')
    USERS.pop(username, None)
    return {"message": "User deleted"}


@app.post("/user")
async def createUser(body: Dict[str, Any]):
    """Create user"""
    body = unwrap_body(body)
    if not isinstance(body, dict) or "username" not in body:
        raise HTTPException(status_code=400, detail="Missing required field: username")
    username = str(body["username"])
    if not username or not username.strip():
        raise HTTPException(status_code=400, detail="Invalid username: must be non-empty")
    if not re.match(r"^[a-zA-Z0-9_.-]+$", username):
        raise HTTPException(status_code=400, detail="Invalid username format")
    if "password" not in body:
        raise HTTPException(status_code=400, detail="Missing required field: password")
    if "email" in body and not is_valid_email(body["email"]):
        raise HTTPException(status_code=422, detail="Invalid email format")
    USERS[username] = body
    return body

@app.post("/user/createWithList")
async def createUsersWithListInput(request:Request):
    """Creates list of users with given input array"""
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail='Invalid JSON')
    if isinstance(data, dict) and "body" in data:
        data = data["body"]
    if not isinstance(data, list) or len(data) == 0:
        raise HTTPException(status_code=400, detail='User list is empty')
    for u in data:
        if not isinstance(u, dict) or "username" not in u or "email" not in u:
            raise HTTPException(status_code=400, detail='Missing required fields: username, email')
        uname = str(u["username"])
        if not uname or not uname.strip():
            raise HTTPException(status_code=400, detail='Invalid username: must be non-empty')
        if not re.match(r"^[a-zA-Z0-9_.-]+$", uname):
            raise HTTPException(status_code=400, detail='Invalid username format')
        if not is_valid_email(u["email"]):
            raise HTTPException(status_code=422, detail='Invalid email format')
    for u in data:
        USERS[u["username"]] = u
    return {"message": "Users created"}

@app.post("/user/createWithArray")
async def createUsersWithArrayInput(request: Request):
    """Creates list of users with given input array"""
    return await createUsersWithListInput(request)


# ========== 测试隔离辅助端点（仅测试套件内部调用）==========
def reset_state():
    """将预置资源恢复到初始状态，用于用例间隔离。"""
    return {
        'pets': {
            1: {'id': 1, 'name': 'Dog', 'photoUrls': ['http://example.com/dog.jpg'], 'status': 'available'},
            2: {'id': 2, 'name': 'Cat', 'photoUrls': ['http://example.com/cat.jpg'], 'status': 'pending'},
            3: {'id': 3, 'name': 'Bird', 'photoUrls': ['http://example.com/bird.jpg'], 'status': 'sold'},
        },
        'users': {
            'user1': {'id': 1, 'username': 'user1', 'email': 'user1@example.com', 'password': 'pass123'},
            'alice': {'id': 2, 'username': 'alice', 'email': 'alice@example.com', 'password': 'alicepass'},
            'bob': {'id': 3, 'username': 'bob', 'email': 'bob@example.com', 'password': 'bobpass'},
        },
        'orders': {
            1: {'id': 1, 'petId': 1, 'quantity': 1, 'status': 'placed', 'complete': False},
            2: {'id': 2, 'petId': 2, 'quantity': 2, 'status': 'approved', 'complete': False},
            3: {'id': 3, 'petId': 3, 'quantity': 1, 'status': 'delivered', 'complete': True},
        },
    }

@app.post("/__reset__")
async def reset_mock():
    """重置预置资源，供测试套件开始前调用以保证用例隔离。"""
    global PETS, USERS, ORDERS
    state = reset_state()
    PETS = state['pets']
    USERS = state['users']
    ORDERS = state['orders']
    return {"message": "mock state reset"}
