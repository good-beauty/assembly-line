import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv

load_dotenv()

# 判断是否在 Docker 容器内
IN_DOCKER = os.getenv("IN_DOCKER", "false").lower() == "true"
DB_HOST = "mysql" if IN_DOCKER else "localhost"

# 注意：不再优先读取 DATABASE_URL 环境变量，而是根据 IN_DOCKER 自动生成
DATABASE_URL = f"mysql+pymysql://root:root@{DB_HOST}:3306/test_pipeline?charset=utf8mb4"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()