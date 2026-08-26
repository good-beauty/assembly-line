from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import APIEndpoint, TestCase
from ..services.ai_generator import generate_cases_for_endpoint

router = APIRouter(prefix="/generate_cases", tags=["generate"])

@router.post("/{endpoint_id}")
async def generate_for_endpoint(endpoint_id: int, db: Session = Depends(get_db)):
    endpoint = db.query(APIEndpoint).filter(APIEndpoint.id == endpoint_id).first()
    if not endpoint:
        raise HTTPException(status_code=404, detail="接口不存在")

    try:
        cases = generate_cases_for_endpoint(endpoint)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")

    # 存入数据库
    for case_data in cases:
        case = TestCase(api_id=endpoint.id, **case_data)
        db.add(case)
    db.commit()

    return {"message": "生成成功", "generated_count": len(cases)}