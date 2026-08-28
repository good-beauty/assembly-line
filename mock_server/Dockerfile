FROM docker.m.daocloud.io/library/python:3.11-slim

WORKDIR /app

# 复制依赖（mock 服务只需要 fastapi 和 uvicorn）
RUN pip install --no-cache-dir fastapi uvicorn

# 复制代码
COPY main.py .

EXPOSE 5000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]