from sqlalchemy import Column, Integer, String, Text, JSON, DateTime,ForeignKey
from .database import Base
from datetime import datetime
from sqlalchemy.orm import relationship

class APIEndpoint(Base):
    __tablename__ = "api_endpoints"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255))
    method = Column(String(10))
    path = Column(String(500))
    summary = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    parameters = Column(JSON, nullable=True)
    request_body = Column(JSON, nullable=True)
    responses = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    test_cases = relationship("TestCase", back_populates="api_endpoint")

class TestCase(Base):
    __tablename__ = "test_cases"

    id = Column(Integer, primary_key=True, index=True)
    api_id = Column(Integer, ForeignKey("api_endpoints.id"))
    name = Column(String(255))
    method = Column(String(10))
    url = Column(String(500))
    headers = Column(JSON, nullable=True)
    payload = Column(JSON, nullable=True)
    expected_status = Column(Integer)
    assertions = Column(JSON, nullable=True)
    model_used = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)

    api_endpoint = relationship("APIEndpoint", back_populates="test_cases")

class ExecutionRecord(Base):
    __tablename__ = "execution_records"

    id = Column(Integer, primary_key=True, index=True)
    test_case_id = Column(Integer, ForeignKey("test_cases.id"))
    status = Column(String(20))  # passed / failed / error
    duration = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
    executed_at = Column(DateTime, default=datetime.utcnow)