import requests
import os
from dotenv import load_dotenv

load_dotenv()

DINGTALK_WEBHOOK = os.getenv("DINGTALK_WEBHOOK", "")

def send_dingtalk_notification(summary: dict, report_path: str = ""):
    """发送测试结果到钉钉群"""
    if not DINGTALK_WEBHOOK:
        print("未配置 DINGTALK_WEBHOOK，跳过通知")
        return

    # 构造 Markdown 消息
    total = summary.get("total", 0)
    passed = summary.get("passed", 0)
    failed = summary.get("failed", 0)
    error = summary.get("error", 0)
    skipped = summary.get("skipped", 0)
    success_rate = (passed / total * 100) if total > 0 else 0

    markdown_text = f"""### 接口自动化测试流水线执行完成
    - **流水线总用例数**：{total}
    - **通过**：{passed}
    - **失败**：{failed}
    - **错误**：{error}
    - **跳过**：{skipped}
    - **通过率**：{success_rate:.2f}%

    **报告地址**：{report_path}
    """

    payload = {
        "msgtype": "markdown",
        "markdown": {
            "title": "测试流水线通知",
            "text": markdown_text
        }
    }

    try:
        resp = requests.post(DINGTALK_WEBHOOK, json=payload, timeout=10)
        if resp.status_code == 200:
            print("钉钉通知发送成功")
        else:
            print(f"钉钉通知发送失败，状态码：{resp.status_code}，响应：{resp.text}")
    except Exception as e:
        print(f"钉钉通知异常：{e}")