from fastapi import FastAPI
from .database import engine, Base
from . import models 
from .routers import parse, generate 
from .routers import parse, generate, execute



Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI测试流水线")
app.include_router(parse.router)   
app.include_router(generate.router)
app.include_router(execute.router)

@app.get("/health")
def health():
    return {"status": "ok"}

