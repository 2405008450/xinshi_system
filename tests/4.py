import sys
import os
# 确保能找到项目根目录
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 👇 核心：直接导入 main（或者你的 FastAPI app 实例）
# 这会让 SQLAlchemy 扫描并加载项目里所有的模型关系
import main

import os
from pywebpush import webpush, WebPushException
from database import SessionLocal
from models import PushSubscription

# 👇 设置你电脑的代理
# os.environ['https_proxy'] = 'http://127.0.0.1:7890'
# os.environ['http_proxy'] = 'http://127.0.0.1:7890'

def send():
    db = SessionLocal()
    try:
        subs = db.query(PushSubscription).all()
        if not subs:
            print("数据库中没有找到订阅记录。")
            return

        for sub in subs:
            print(f"正在向端点 {sub.endpoint[:40]}... 发送通知")
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": {"p256dh": sub.p256dh, "auth": sub.auth}
                    },
                    data='{"title": "测试通知", "body": "来自后端的系统级推送！"}',
                    vapid_private_key=os.getenv("VAPID_PRIVATE_KEY"), # 确保你的环境变量里有这个私钥
                    vapid_claims={"sub": "mailto:admin@example.com"}, # 换成你的邮箱
                    content_encoding="aes128gcm",
                    ttl=600
                )
                print("✅ 发送成功")
            except WebPushException as ex:
                print(f"❌ 发送失败: {ex}")
                if ex.response is not None and ex.response.status_code in [404, 410]:
                    print("端点失效，已删除")
                    db.delete(sub)
                    db.commit()
    finally:
        db.close()

if __name__ == "__main__":
    send()