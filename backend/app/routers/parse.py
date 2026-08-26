from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
import requests  
from ..database import get_db
from ..models import APIEndpoint
from ..services.swagger_parser import load_swagger_content, load_swagger_from_url, extract_endpoints

router = APIRouter(prefix="/parse", tags=["parse"])

@router.post("")
async def parse_swagger(
    file: UploadFile = File(None),
    url: str = Form(None),
    db: Session = Depends(get_db)
):
    try:
        if file:
            content = await file.read()
            swagger_data = load_swagger_content(content, file.filename)
        elif url:
            swagger_data = load_swagger_from_url(url)
        else:
            raise HTTPException(status_code=400, detail="请提供Swagger文件或URL")

        endpoints = extract_endpoints(swagger_data)
    except requests.RequestException:
        raise HTTPException(status_code=400, detail="无法访问提供的URL，请检查地址是否正确")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"解析失败: {str(e)}")

    # 存入数据库
    for ep in endpoints:
        db_ep = APIEndpoint(**ep)
        db.add(db_ep)
    db.commit()

    return {"message": "解析成功", "parsed_count": len(endpoints)}