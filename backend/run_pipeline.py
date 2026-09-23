import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.logging_config import get_logger
from app.services.notifier import send_dingtalk_notification
from app.database import SessionLocal
from app.services.swagger_parser import load_swagger_from_url, extract_endpoints
from app.models import APIEndpoint, TestCase, ExecutionRecord
from app.services.ai_generator import generate_cases_for_endpoints_batch
from app.services.test_executor import execute_tests

logger = get_logger("run_pipeline")

def run_full_pipeline(swagger_url: str):
    """一键执行完整流水线：解析 -> 生成 -> 执行"""
    db = SessionLocal()
    try:
        logger.info("[1/4] 解析 Swagger 文档...")
        swagger_data = load_swagger_from_url(swagger_url)
        endpoints = extract_endpoints(swagger_data)
        logger.info("解析到 %d 个接口", len(endpoints))

        # 可选：清空旧数据，避免重复累积
        db.query(ExecutionRecord).delete()
        db.query(TestCase).delete()
        db.query(APIEndpoint).delete()
        db.commit()

        # 存入接口元数据
        for ep in endpoints:
            db.add(APIEndpoint(**ep))
        db.commit()
        logger.info("接口元数据已入库")

        logger.info("[2/4] 生成测试用例...")
        all_endpoints = db.query(APIEndpoint).all()
        total_cases = 0
        # 并发生成。ORM 对象的标量列(已加载)可被线程安全读取，DB 写入只在本线程进行
        results = generate_cases_for_endpoints_batch(all_endpoints, max_workers=4)
        for ep in all_endpoints:
            cases = results.get(ep.id, [])
            for case_data in cases:
                db.add(TestCase(api_id=ep.id, **case_data))
            total_cases += len(cases)
            logger.info("接口 '%s' 生成 %d 条用例", ep.name, len(cases))
        db.commit()
        logger.info("共生成 %d 条测试用例", total_cases)

        logger.info("[3/4] 执行测试并生成报告...")
        summary = execute_tests(db)  # 执行所有用例并生成 Allure 报告
        logger.info("执行完成: 总数=%s, 通过=%s, 失败=%s", summary['total'], summary['passed'], summary['failed'])
        logger.info("报告已生成，请打开 allure-report/index.html 查看")

        logger.info("[4/4] 发送钉钉通知...")
        send_dingtalk_notification(summary, report_path="allure-report/index.html")

        return summary
    finally:
        db.close()

if __name__ == "__main__":
    swagger_url = os.getenv("SWAGGER_URL", "https://petstore.swagger.io/v2/swagger.json")
    run_full_pipeline(swagger_url)