# 使用官方 Python 3.11 精简版镜像
FROM docker.m.daocloud.io/library/python:3.11-slim

# 安装 Java 和 curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-21-jre-headless \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 Allure
RUN curl -sL https://github.com/allure-framework/allure2/releases/download/2.30.0/allure-2.30.0.tgz | tar -xz -C /opt/ \
    && ln -s /opt/allure-2.30.0/bin/allure /usr/local/bin/allure

# 设置工作目录
WORKDIR /app

# 安装系统依赖（如果需要编译某些包，例如 mysqlclient 等，但这里我们使用 pymysql，不需要额外编译）
# 安装 curl 用于健康检查（可选）
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制 requirements.txt 并安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]