# Assembly Line — 基于大模型的接口自动化测试流水线

> 一条端到端的接口测试流水线：解析 Swagger/OpenAPI 文档 → 大模型自动生成测试用例 → 渲染并执行 Pytest → 生成 Allure 报告 → 钉钉推送结果。
> 被测系统使用与 OpenAPI 同源生成的 Mock 服务，测试用例既覆盖正向场景，也覆盖负向（异常）场景。当前基于 Petstore 规范，**20 个接口每轮生成约 100 条用例，连续多轮通过率 100%**，另有 52 项单元测试保障自身工程质量。
---
## 特性

| 能力 | 说明 |
|:---|:---|
| 规范兼容 | 统一解析 Swagger 2.0 与 OpenAPI 3.0（`spec_normalizer` 规范化层） |
| 用例生成 | 通义千问（DashScope SDK）逐接口生成 3 条正向 + 2 条负向用例，并发生成、单接口失败不阻断 |
| 严格 Mock | Mock 由 OpenAPI 自动生成并手工增强，删除真实生效、不存在返回 404、凭据真实校验 |
| 用例隔离 | 每条用例执行前重置 Mock 预置状态，消除跨用例共享状态导致的顺序依赖 |
| 预期对齐 | 生成层对 LLM 输出的畸形用例/错误预期做确定性归一化，不放宽 Mock 校验 |
| 报告通知 | Allure HTML 报告 + JUnit XML 采集 + 钉钉群 Markdown 通知 |
| CI/CD | Docker Compose（MySQL / Mock / App）+ Jenkins（单测门禁 → 流水线 → 报告归档） |

## 目录结构

```
d:\assembly-line/
├── backend/                    # 后端主服务（FastAPI）
│   ├── run_pipeline.py         # 一键完整流水线（命令行入口）
│   ├── app/
│   │   ├── main.py             # FastAPI 入口：注册路由、启动建表
│   │   ├── database.py         # 数据库引擎 / Session（环境变量读取凭据）
│   │   ├── models.py           # ORM 模型：api_endpoints / test_cases / execution_records
│   │   ├── schemas.py          # Pydantic 入参/响应校验模型
│   │   ├── logging_config.py   # 统一日志模块
│   │   ├── routers/            # API 路由层（parse / generate / execute）
│   │   ├── services/           # 业务逻辑层（解析/规范化/生成/执行/通知）
│   │   └── templates/          # pytest 函数模板
│   ├── tests/                  # 单元测试（52 项）
│   └── requirements.txt        # Python 依赖
├── mock_server/                # 被测 Mock 服务（FastAPI :5000）
├── scripts/generate_mock.py    # 从 OpenAPI 生成 Mock 路由的脚手架
├── specs/petstore.json         # 默认 Swagger 2.0 规范
├── docker-compose.yml          # MySQL / Mock / App 编排
├── Jenkinsfile                 # CI/CD 流水线
└── TECH_DOC.md                 # 详细技术文档（新手友好，逐函数讲解）
```
### 环境要求

- Python 3.11+（建议使用虚拟环境）
- Docker / Docker Compose（用于 MySQL、Mock、App 容器）
- Allure CLI（`ALLURE_CMD`，本地运行报告需要；容器已内置）
- 通义千问 API Key（`LLM_API_KEY`）

### 1. 配置环境变量

在项目根目录创建 `.env`（参考 [附录 env 模板](TECH_DOC.md#env文件模板)）：

```env
LLM_API_KEY=sk-xxxxxxxx            # 必填，未配置流水线启动即报错
LLM_MODEL=qwen-plus                # 可选，默认 qwen-plus
DINGTALK_WEBHOOK=                  # 可选，钉钉机器人 Webhook
SWAGGER_URL=https://petstore.swagger.io/v2/swagger.json
# 数据库（本地默认 localhost/root/空密码/test_pipeline，可只留本行）：
DATABASE_URL=mysql+pymysql://root:root@localhost:3306/test_pipeline?charset=utf8mb4
ALLURE_CMD=allure                  # 本地 Allure 命令
```
### 2. 启动基础设施

```bash
# 启动 MySQL + Mock 服务（Mock 修改后需 --build 重建）
docker compose up -d --build mysql mock
```

### 3. 安装依赖并运行流水线（本地）

```bash
pip install -r backend/requirements.txt
```

```bash
cd backend
python run_pipeline.py
```

> 注意：流水线内部以 `pytest` 子进程执行用例，请确保虚拟环境（venv）在 PATH 中，否则会解析到全局 Python 导致 `--alluredir` 不被识别。Windows 下可先执行 `.venv\Scripts\Activate.ps1`。

### 4. 查看结果

- Allure 报告：打开 `backend/allure-report/index.html`
- 钉钉群：配置了 `DINGTALK_WEBHOOK` 后自动推送统计

### 全部容器化运行（含后端 App）

```bash
docker compose up -d --build
docker exec -w /app test-pipeline-app python run_pipeline.py
```

## 配置项一览

| 变量 | 默认 | 用途 | 必填 |
|:---|:---|:---|:---:|
| `LLM_API_KEY` | 无 | DashScope API Key，缺失则抛 `RuntimeError` | ✅ |
| `LLM_MODEL` | `qwen-plus` | 用例生成模型 | |
| `SPEC_PATH` | `specs/petstore.json` | 用例生成的规范来源 | |
| `SWAGGER_URL` | Petstore 官方 URL | 流水线解析的规范地址 | |
| `DATABASE_URL` | 空 | 完整连接串，优先于分字段 | |
| `DB_HOST` | `mysql`(容器)/`localhost` | 数据库地址（受 `IN_DOCKER` 影响） | |
| `DB_PORT` / `DB_USER` / `DB_PASSWORD` / `DB_NAME` | `3306`/`root`/空/`test_pipeline` | 分字段连接 | |
| `IN_DOCKER` | `false` | 容器内标识：决定 DB 与 Mock 地址 | |
| `BASE_URL` | `http://localhost:5000` | 被测 Mock 地址（容器内 `http://mock:5000`） | |
| `ALLURE_CMD` | `allure` | Allure 命令行（不使用 shell） | |
| `DINGTALK_WEBHOOK` | 空 | 钉钉机器人 Webhook，为空则跳过通知 | |


### REST API（FastAPI 默认 :8000）

| 方法 | 路径 | 说明 |
|:---|:---|:---|
| POST | `/parse` | 上传 Swagger 文件（multipart `file`）或 `url` 表单，解析并入库 |
| POST | `/generate_cases/{endpoint_id}` | 为指定接口生成用例并入库 |
| POST | `/run_tests` | 执行测试（body 可选 `{"test_case_ids": [...]}`，缺省执行全部） |
| GET | `/health` | 健康检查 |

API 交互文档：启动后端后访问 `http://localhost:8000/docs`。

## 质量保障

- **通过率**：Petstore 20 接口 → 100 条用例，连续两轮 **98 通过 / 0 失败**
- **单元测试**：`backend/tests/` 52 项，覆盖规范层/解析器/生成器/执行器/模式校验，作为 CI 门禁
- **三道保障**：同源严格 Mock + 用例级隔离（`POST /__reset__`）+ 生成层确定性归一化，详见 [TECH_DOC.md §2](TECH_DOC.md#2-三大核心设计机制)

## CI/CD（Jenkins）

| Stage | 内容 |
|:---|:---|
| Build & Deploy | `docker compose up -d --build` |
| Unit Tests | 容器内 `pytest tests/ -q`（失败即中断） |
| Run Pipeline | 容器内执行 `run_pipeline.py` |
| Archive Report | 归档 `backend/allure-results` 供 Jenkins Allure 插件出报告 |
| Notify | 完成/失败通知 |


## License / 说明

本项目为技术示例工程，被测试规范为 Swagger 官方 Petstore 示例。