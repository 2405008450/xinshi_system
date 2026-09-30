"""备注回填真实接口及页面验收。只使用 GET，短期凭证只在内存中。"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import timedelta
import json
from pathlib import Path
import re
import socket
import sys
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.normalize_talent_remarks import outside, read, atomic_json
from tools.talent_remark_rules import CONTACT_FIELDS, CONTACT_MAP, vacant


def main():
    if socket.gethostname().upper() != "WIN-LOLJ8UHT2G5" or ROOT != Path(r"E:\xinshi_system"):
        raise RuntimeError("页面运行验收仅允许在局域网调试机")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    directory = outside(args.directory)
    plan, ledger = read(directory / "plan.json"), read(directory / "ledger.json")
    records = [r for r in plan["records"] if ledger["records"].get(r["id"], {}).get("status") == "committed"]
    if not records: raise ValueError("没有已提交记录可验收")
    # 每个实际变更类别至少取一人，再覆盖文本/JSON来源及教育现有数据。
    samples, covered = [], set()
    for r in records:
        categories = set(r["changes"]) | {a["table"] for a in r["adds"]} | {a["table"] + "." + key for a in r["updates"] for key in a["changes"]}
        note = r["before"]["person"].get("remarks") or ""
        categories.add("json_source" if '"batch"' in note else "text_source")
        if categories - covered:
            samples.append(r); covered |= categories
    if "resource_education_experience" not in covered:
        education_sample = next((r for r in records if r["before"]["relations"]["resource_education_experience"]), None)
        if education_sample and education_sample not in samples: samples.append(education_sample)
    import main as _registered_models  # noqa: F401
    from database import SessionLocal, engine
    from models import AppUser
    from permission_service import get_user_permission_codes
    from routers.auth import create_access_token
    from talent_privacy import can_view_talent_contacts
    from crud import get_user_roles_with_role_names
    if engine.url.host != plan["database"]["host"] or engine.url.database != plan["database"]["name"]:
        raise RuntimeError("实际接口环境与计划目标不一致")
    credentials = {}
    with SessionLocal() as db:
        for user in db.query(AppUser).filter(AppUser.is_active.is_(True)).all():
            permissions = get_user_permission_codes(db, user.id)
            if not ({"*", "talents:read", "talents:write"} & set(permissions)): continue
            kind = "visible" if can_view_talent_contacts(db, user) else "restricted"
            if kind not in credentials:
                credentials[kind] = {"token": create_access_token({"sub": user.username, "user_id": str(user.id)}, timedelta(minutes=45)), "roles": get_user_roles_with_role_names(db, user.id), "permissions": permissions, "user_id": str(user.id), "username": user.username, "full_name": user.full_name or user.username}
    if set(credentials) != {"visible", "restricted"}: raise RuntimeError("缺少现有的两种权限账号，禁止创建或提权")
    def api(path, kind="visible"):
        request = Request("http://127.0.0.1:8000" + path, headers={"Authorization": "Bearer " + credentials[kind]["token"]})
        with urlopen(request, timeout=60) as response: return json.load(response)
    for kind in credentials: api("/auth/session", kind)
    details = {}
    assertions = Counter()
    for r in samples:
        detail = api("/talents/" + r["id"])
        hidden = api("/talents/" + r["id"], "restricted")
        details[r["id"]] = detail
        assert detail["contact_restricted"] is False and hidden["contact_restricted"] is True
        for key, value in r["changes"].items(): assert detail[key] == value, "详情字段回显不符"
        relationship_keys = {"resource_language_skill": "language_skills", "resource_certificate": "certificates", "resource_education_experience": "education_experiences"}
        for update in r["updates"]:
            observed = next(x for x in detail[relationship_keys[update["table"]]] if x["id"] == update["id"])
            assert all(observed.get(k) == v for k, v in update["changes"].items()), "关联字段回显不符"
        for added in r["adds"]:
            observed = next(x for x in detail[relationship_keys[added["table"]]] if x["id"] == added["values"]["id"])
            assert all(observed.get(k) == v for k, v in added["values"].items() if k != "person_id"), "新增关联回显不符"
        for key in CONTACT_FIELDS:
            assert hidden[key] == ("******" if not vacant(detail.get(key)) else None), "受限接口未脱敏"
        for d in r["decisions"]:
            if d.get("key") in CONTACT_MAP and d["status"] in {"filled", "satisfied"} and d.get("normalized"):
                assert d["normalized"] not in hidden["remarks"], "转存账号仍暴露于备注"
        params = {"field_filters": json.dumps({"resource_code": {"op": "contains", "value": r["resource_code"]}}), "limit": 100}
        page_data = api("/talents/page?" + urlencode(params))
        count = api("/talents/count?" + urlencode({"field_filters": params["field_filters"]}))
        assert page_data["total"] == count["total"] == 1
        assert page_data["items"][0]["id"] == r["id"]
        # 再按回填的可筛选字段过滤，确保列表与总数复用同一条件。
        filter_keys = {"registration_source", "nationality", "employment_status", "highest_education", "wechat_account"}
        for key in filter_keys & r["changes"].keys():
            descriptor = {"op": "in", "value": [r["changes"][key]]} if key in {"employment_status", "highest_education"} else {"op": "contains", "value": r["changes"][key]}
            filters = {"resource_code": {"op": "contains", "value": r["resource_code"]}, key: descriptor}
            q = urlencode({"field_filters": json.dumps(filters)})
            assert api("/talents/page?" + q)["total"] == api("/talents/count?" + q)["total"] == 1
            assertions["changed_field_filter"] += 1
        assertions["api_detail_list_count_and_privacy"] += 1
    print(json.dumps({"api_samples_passed": len(samples), "categories": sorted(covered)}, ensure_ascii=True), flush=True)
    from playwright.sync_api import sync_playwright, expect
    errors, mutations = [], []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True, args=["--no-proxy-server", "--host-resolver-rules=MAP oa.xinshify.com.cn 127.0.0.1"])
        for kind in ("visible", "restricted"):
            context = browser.new_context(viewport={"width": 1440, "height": 1000})
            auth = credentials[kind]
            stored = {"token": auth["token"], "user_roles": json.dumps(auth["roles"], ensure_ascii=False), "user_permissions": json.dumps(auth["permissions"]), "user_id": auth["user_id"], "user_name": auth["username"], "user_full_name": auth["full_name"]}
            context.add_init_script("for (const [k,v] of Object.entries(" + json.dumps(stored) + ")) localStorage.setItem(k,v);")
            def guard(route):
                request = route.request
                if request.method not in {"GET", "HEAD", "OPTIONS"}:
                    mutations.append({"path": urlparse(request.url).path, "method": request.method})
                    route.abort()
                else: route.continue_()
            context.route("**/api/**", guard)
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(type(error).__name__))
            page.goto("https://oa.xinshify.com.cn/resource-management/talents", wait_until="domcontentloaded")
            keyword = page.get_by_placeholder("姓名、编号、电话或邮箱" if kind == "visible" else "姓名或编号", exact=True)
            expect(keyword).to_be_visible(timeout=30000)
            for index, r in enumerate(samples):
                detail = details[r["id"]]
                with page.expect_response(lambda response: "/talents/page" in response.url and response.status == 200 and parse_qs(urlparse(response.url).query).get("keyword") == [r["resource_code"]], timeout=30000):
                    keyword.fill(r["resource_code"])
                    page.get_by_role("button", name="查询", exact=True).click()
                table_row = page.locator(".el-table__body-wrapper tbody tr").filter(has=page.get_by_role("button", name="查看详情", exact=True))
                expect(table_row).to_have_count(1, timeout=30000)
                display_name = next(v for v in [detail.get("chinese_name"), detail.get("english_name"), detail.get("nickname"), *(detail.get("other_names") or []), detail["full_name"]] if v)
                expect(table_row.locator(".talent-name-link")).to_have_text(display_name, timeout=30000)
                table_row.get_by_role("button", name="查看详情", exact=True).click()
                popover = page.locator(".talent-detail-popper:visible").filter(has=page.locator(".talent-detail-content"))
                expect(popover).to_be_visible(timeout=30000)
                expect(popover.locator(".talent-detail-content")).to_be_visible()
                assert popover.evaluate("el => el.classList.contains('el-popover')")
                assert popover.get_attribute("data-popper-placement").startswith("left")
                assert popover.locator(".talent-detail-content").evaluate("el => getComputedStyle(el).overflowY") == "auto"
                for key, value in r["changes"].items():
                    if key not in {"remarks", *CONTACT_FIELDS} and value is not None and isinstance(value, str):
                        expect(popover).to_contain_text(value, timeout=30000)
                if kind == "restricted":
                    for key in CONTACT_FIELDS:
                        value = detail.get(key)
                        if value: assert value not in popover.inner_text(), "受限详情展示了联系方式"
                assertions["popover_and_privacy"] += 1
                page.locator(".page-title").click()
                if kind == "visible":
                    table_row.get_by_role("button", name="编辑", exact=True).click()
                    dialog = page.locator(".talent-editor-dialog:visible")
                    expect(dialog).to_be_visible()
                    expect(dialog.get_by_role("button", name="保存", exact=True)).to_be_visible()
                    label_map = {"reported_age": "年龄", "registration_source": "来源", "wechat_account": "所在微信", "employment_detail": "具体说明", "primary_email": "邮箱", "other_contact": "其他", "remarks": "备注"}
                    for key, label in label_map.items():
                        if key not in r["changes"]: continue
                        item = dialog.locator(".el-form-item").filter(has=page.locator(".el-form-item__label", has_text=re.compile("^"+re.escape(label)+"$")))
                        item.scroll_into_view_if_needed()
                        if key == "wechat_account":
                            custom = item.locator('input[maxlength="100"]')
                            if custom.count(): value = custom.input_value()
                            else: value = item.locator(".el-select__selected-item:not(.el-select__placeholder)").inner_text()
                        else: value = item.locator("input,textarea").first.input_value()
                        wanted = detail["current_age"] if key == "reported_age" and (detail.get("birth_date") or detail.get("birth_year_month")) else r["changes"][key]
                        assert value == str(wanted).replace("\r\n", "\n"), f"编辑字段回显不符: {key}（读取长度{len(value)}，预期长度{len(str(wanted))}）"
                    proficiency_labels = {"very_familiar": "非常熟悉", "familiar": "熟悉", "basic": "基础交流", "listening_mainly": "听懂为主", "listening_only": "仅能听懂"}
                    for update in r["updates"]:
                        if update["table"] != "resource_language_skill" or "proficiency" not in update["changes"]: continue
                        skill = next(x for x in detail["language_skills"] if x["id"] == update["id"])
                        subrow = dialog.locator(".sub-record").filter(has_text=skill["language_label"])
                        proficiency_item = subrow.locator(".el-form-item").filter(has=page.locator(".el-form-item__label", has_text=re.compile("^熟悉程度$")))
                        proficiency_item.scroll_into_view_if_needed()
                        expect(proficiency_item).to_contain_text(proficiency_labels[update["changes"]["proficiency"]])
                    dialog.get_by_role("button", name="取消", exact=True).click()
                    expect(dialog).not_to_be_visible()
                    assertions["edit_read_only_check"] += 1
            context.close()
        browser.close()
    report = {"passed": not errors and not mutations, "samples": len(samples), "covered_categories": sorted(covered), "assertions": dict(assertions), "page_error_count": len(errors), "blocked_mutation_requests": mutations, "tokens_saved": False}
    atomic_json(directory / "live-verification.json", report)
    print(json.dumps(report, ensure_ascii=True))
    if not report["passed"]: raise SystemExit(2)


if __name__ == "__main__":
    main()
