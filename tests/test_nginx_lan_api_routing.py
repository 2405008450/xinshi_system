"""静态校验局域网 Nginx 只读查询分流规则；不启动 Nginx、不访问网络或数据库。"""
from pathlib import Path
import re

import pytest

CONFIG = Path(__file__).resolve().parents[1] / "deploy" / "nginx-lan.conf"
TEXT = CONFIG.read_text(encoding="utf-8")


def _map_block(variable):
    match = re.search(r"map\s+(\S+(?:\s+\S+)*?)\s+\$" + variable + r"\s*\{(.*?)\n\s*\}", TEXT, re.S)
    assert match, f"未找到 ${variable} 的 map 定义"
    return match.group(2)


def _rules():
    body = _map_block("xinshi_api_target")
    default = re.search(r"^\s*default\s+(\w+);", body, re.M).group(1)
    rules = [(re.compile(pattern), value)
             for pattern, value in re.findall(r'^\s*"~([^"]+)"\s+(\w+);', body, re.M)]
    assert rules, "分流 map 中没有正则规则"
    return default, rules


def route(method, uri, split="on"):
    """按 nginx map 语义：正则按书写顺序匹配，首个命中生效，否则取 default。"""
    default, rules = _rules()
    key = f"{split} {method} {uri}"
    for pattern, value in rules:
        if pattern.search(key):
            return value
    return default


def test_split_switch_defaults_off_in_repository():
    # Nginx 直接读取仓库文件；默认关闭，前置条件通过后由运维在服务器上开启。
    body = _map_block("xinshi_cloud_read_split")
    assert re.search(r"^\s*default\s+off;", body, re.M)


@pytest.mark.parametrize("uri", [
    "/api/projects/translation/page",
    "/api/talents/page",
    "/api/clients",
    "/api/notifications",
    "/api/manuscript-arrangements/context",
    "/api/manuscript-arrangements/batches/page",
    "/api/manuscript-arrangements/batches",
    "/api/project-files/project/7f0c",
    "/api/project-files/count",
    "/api/translation-statement-workspaces/c1/history",
    "/api/resource-development/issues",
])
def test_plain_queries_go_to_cloud(uri):
    assert route("GET", uri) == "cloud"


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
@pytest.mark.parametrize("uri", [
    "/api/manuscript-arrangements/batches",
    "/api/manuscript-arrangements/batches/d1/send",
    "/api/manuscript-arrangements/batches/d1/arrangements/a1/selected-files",
    "/api/project-files/source-path/inspect",
    "/api/sub-orders/source-files",
    "/api/talents/page",
])
def test_non_get_requests_stay_on_lan(method, uri):
    assert route(method, uri) == "lan"


@pytest.mark.parametrize("uri", [
    # 共享目录与邮件（稿件安排）
    "/api/manuscript-arrangements/projects/p1/dispatch-files",
    "/api/manuscript-arrangements/mail-status",
    "/api/manuscript-arrangements/batches/d1/arrangements/a1/mail-preview",
    "/api/mail-settings/daily-report-policies",
    "/api/project-mails/recipient-groups",
    "/api/mail-inline-images/i1/content",
    # 鉴权、推送、健康检查、截图签名、Office
    "/api/auth/session",
    "/api/auth/captcha/required",
    "/api/auth/mail-account",
    "/api/push/public-key",
    "/api/health/db",
    "/api/editor-screenshots/s1",
    "/api/projects/annotation/office/sessions/o1",
    # 本机磁盘附件、图片、资料
    "/api/talents/p1/attachments/a1",
    "/api/teams/t1/attachments",
    "/api/teams/t1/attachments/a1",
    "/api/annotation-notices/sections/s1/attachments/a1",
    "/api/project-notices/translation/sections/s1/attachments/a1",
    "/api/annotation-ops/custom-field-images/i1",
    "/api/annotation-ops/projects/p1/paired-workspace/contacts/r1/attachments/a1",
    "/api/projects/annotation/p1/task-images",
    "/api/projects/annotation/p1/materials",
    "/api/project-chat/attachments/a1",
    "/api/chat/discussions/d1/files/f1",
    "/api/company-management/sections/s1/images/i1",
    "/api/talents/duplicate-review/operations/o1/original-data/attachments/a1",
    # 导出、模板、Excel/PDF
    "/api/projects/translation/export",
    "/api/projects/translation/reconciliation-export",
    "/api/daily-reports/2026-11-07/export",
    "/api/schedules/translators/import-template",
    "/api/translation-statements/excel",
    "/api/translation-statement-workspaces/c1/pdf",
])
def test_file_mail_and_environment_reads_stay_on_lan(uri):
    assert route("GET", uri) == "lan"


def test_switch_off_routes_everything_to_lan():
    assert route("GET", "/api/talents/page", split="off") == "lan"
    assert route("GET", "/api/projects/translation/page", split="off") == "lan"


def test_cloud_upstream_requires_certificate_verification():
    cloud = re.search(r"location \^~ /__xinshi_cloud/ \{(.*?)\n        \}", TEXT, re.S).group(1)
    assert "internal;" in cloud
    assert "proxy_ssl_verify on;" in cloud
    assert "proxy_ssl_name www.oa.xinshify.com.cn;" in cloud
    assert "proxy_intercept_errors on" not in cloud


def test_websocket_and_internal_targets_stay_local():
    ws = re.search(r"location \^~ /api/notifications/ws \{(.*?)\}", TEXT, re.S).group(1)
    assert "proxy_pass http://127.0.0.1:8000/notifications/ws" in ws
    lan = re.search(r"location \^~ /__xinshi_lan/ \{(.*?)\n        \}", TEXT, re.S).group(1)
    assert "internal;" in lan and "proxy_pass http://127.0.0.1:8000;" in lan
    dispatcher = re.search(r"location /api/ \{(.*?)\}", TEXT, re.S).group(1)
    assert "/__xinshi_$xinshi_api_target/$1 last;" in dispatcher
