import sys
import os
from app.services.notifier import send_dingtalk_notification
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.services.swagger_parser import load_swagger_from_url, extract_endpoints
from app.models import APIEndpoint, TestCase, ExecutionRecord
from app.services.ai_generator import generate_cases_for_endpoint
from app.services.test_executor import execute_tests

def run_full_pipeline(swagger_url: str):
    """一键执行完整流水线：解析 -> 生成 -> 执行"""
    db = SessionLocal()
    try:
        print("[1/4] 解析 Swagger 文档...")
        swagger_data = load_swagger_from_url(swagger_url)
        endpoints = extract_endpoints(swagger_data)
        print(f"  解析到 {len(endpoints)} 个接口")

        # 可选：清空旧数据，避免重复累积
        db.query(ExecutionRecord).delete()
        db.query(TestCase).delete()
        db.query(APIEndpoint).delete()
        db.commit()

        # 存入接口元数据
        for ep in endpoints:
            db.add(APIEndpoint(**ep))
        db.commit()
        print("  接口元数据已入库")

        print("[2/4] 生成测试用例...")
        all_endpoints = db.query(APIEndpoint).all()
        total_cases = 0
        for ep in all_endpoints:
            try:
                cases = generate_cases_for_endpoint(ep)
                for case_data in cases:
                    db.add(TestCase(api_id=ep.id, **case_data))
                total_cases += len(cases)
                print(f"  接口 '{ep.name}' 生成 {len(cases)} 条用例")
            except Exception as e:
                print(f"  接口 '{ep.name}' 生成失败: {e}")
        db.commit()
        print(f"  共生成 {total_cases} 条测试用例")

        print("[3/4] 执行测试...")
        summary = execute_tests(db)  # 执行所有用例
        print(f"  执行完成: 总数={summary['total']}, 通过={summary['passed']}, 失败={summary['failed']}")

        print("[4/4] 生成 Allure 报告...")
        # 报告已在 execute_tests 内部生成到 backend/allure-report
        print("  报告已生成，请打开 backend/allure-report/index.html 查看")
        # ... 在生成报告后
        print("[5/5] 发送钉钉通知...")
        send_dingtalk_notification(summary, report_path="backend/allure-report/index.html")

        return summary
    finally:
        db.close()

if __name__ == "__main__":
    # 使用 Petstore Swagger 作为示例，也可以改为本地文件路径
    swagger_url = "https://petstore.swagger.io/v2/swagger.json"
    run_full_pipeline(swagger_url)