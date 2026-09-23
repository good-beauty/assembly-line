from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from ..database import get_db
from ..services.test_executor import execute_tests
from ..schemas import RunTestsRequest

router = APIRouter(prefix="/run_tests", tags=["execute"])

@router.post("")
async def run_tests(
    body: Optional[RunTestsRequest] = None,
    db: Session = Depends(get_db)
):
    try:
        test_case_ids = body.test_case_ids if body else None
        summary = execute_tests(db, test_case_ids)
        return {"message": "执行完成", **summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"执行失败: {str(e)}")