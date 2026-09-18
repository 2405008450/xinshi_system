from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from openpyxl import load_workbook

import routers.translation_projects as translation_router
import translation_project_export_service as export_service


def sample_project(*, project_name="示例项目", with_sub_order=True):
    assignment = {
        "translator_id": uuid4(),
        "translator_name": "张三",
        "translation_scope": "正文",
        "translator_return_time": datetime(2026, 9, 5, 18, 30),
        "completion_remarks": "已完成",
        "actual": {"words": 500},
        "settlement_method": "次月结",
        "translator_pricing_method": "按字数",
        "translator_unit_price": Decimal("0.1234"),
        "translator_total_price": Decimal("61.70"),
        "remarks": "术语以附件为准",
    }
    sub_order = SimpleNamespace(
        sub_order_no="TP-260901-001.001",
        sub_project_name="子稿一.docx",
        status="translator_assigned",
        word_count_matrix={
            "company": {"words": 500},
            "customer": {},
            "translator_estimate": {},
        },
        customer_deadline_time=datetime(2026, 9, 6, 17, 0),
        assigned_translators=[assignment],
        translator_delivery_progress="25%",
        remarks="=HYPERLINK(\"https://example.com\")",
        customer_charge_items=[
            SimpleNamespace(
                item_name="翻译费",
                pricing_mode="metric",
                metric_type="words",
                quantity=800,
                unit_size=1000,
                unit_price=120,
                unit_price_excl_tax=120,
                unit_price_incl_tax=127.2,
                total_excl_tax=88,
                total_incl_tax=93.28,
                billing_month="2026-09",
                currency="CNY",
                calculated_amount=96,
                final_amount=88,
                remarks="折扣价",
            )
        ],
    )
    return SimpleNamespace(
        order_no="TP-260901-001",
        project_name=project_name,
        source_file_name="合同原文.docx",
        client_name="母客户全称",
        client_short_name="母客户",
        client_code="CL-001",
        sub_client_name="子客户全称",
        sub_client_short_name="子客户",
        sub_client_code="CL-001.001",
        customer_order_no="PO-20260901",
        project_manager_name="王经理",
        quotation_required=True,
        project_status="confirmed",
        role_assignments=[
            {"role_code": "project_specialist", "assignee_name": "李四"},
            {"role_code": "project_assistant", "assignee_name": None},
        ],
        word_count_matrix={
            "company": {"words": 1000, "characters_no_spaces": 1200},
            "customer": {"pages": 8},
            "translator_estimate": {"foreign_words": 900},
        },
        customer_reception_time=datetime(2026, 9, 1, 9, 0),
        customer_deadline_time=datetime(2026, 9, 8, 18, 0),
        sent_to_client_time=datetime(2026, 9, 8, 17, 30),
        language_pair="中译英",
        assigned_translators=[assignment],
        translator_delivery_progress="50%",
        customer_charge_items=[],
        sub_orders=[sub_order] if with_sub_order else [],
    )


def row_by_headers(sheet, row_number=2):
    headers = [cell.value for cell in sheet[1]]
    values = [cell.value for cell in sheet[row_number]]
    return headers, dict(zip(headers, values))


def test_export_workbook_contains_complete_typed_project_and_sub_order_data():
    content = export_service.translation_projects_to_xlsx([[sample_project()]])
    workbook = load_workbook(BytesIO(content), data_only=False)

    assert workbook.sheetnames == ["母订单", "子订单", "子订单客户收费"]
    project_headers, project_row = row_by_headers(workbook["母订单"])
    sub_headers, sub_row = row_by_headers(workbook["子订单"])
    charge_headers, charge_row = row_by_headers(workbook["子订单客户收费"])

    assert sum(header.startswith(("我司-", "客户-", "译员预估-")) for header in project_headers) == 18
    assert project_row["订单号"] == "TP-260901-001"
    assert project_row["文件名称"] == "合同原文.docx"
    assert project_row["母客户全称"] == "母客户全称"
    assert project_row["母客户简称"] == "母客户"
    assert project_row["母客户编号"] == "CL-001"
    assert project_row["子客户全称"] == "子客户全称"
    assert project_row["子客户简称"] == "子客户"
    assert project_row["子客户编号"] == "CL-001.001"
    assert project_row["项目专员"] == "李四"
    assert project_row["项目助理"] == "角色池"
    assert project_row["状态"] == "已确认"
    assert project_row["我司-字数"] == 1000
    assert project_row["客户-页数"] == 8
    assert isinstance(project_row["客户接单时间"], datetime)
    assert project_row["译员交付进度"] == 0.5
    assert project_row["已分配译员"] == "张三（正文）"
    assert "张三：2026-09-05 18:30" in project_row["译员回稿时间"]

    assert sub_headers[:3] == ["母订单号", "母项目名称", "子订单号"]
    assert sub_row["母订单号"] == "TP-260901-001"
    assert sub_row["子订单号"] == "TP-260901-001.001"
    assert sub_row["我司-字数"] == 500
    assert sub_row["译员交付进度"] == 0.25
    assert charge_row["子订单号"] == "TP-260901-001.001"
    assert charge_row["客户字数口径"] == "字数"
    assert charge_row["数量"] == 800
    assert charge_row["计算金额"] == 96
    assert charge_row["最终金额"] == 88

    remarks_cell = workbook["子订单"].cell(row=2, column=sub_headers.index("备注") + 1)
    assert remarks_cell.data_type == "s"
    assert remarks_cell.value.startswith("'=")
    assert workbook["母订单"].freeze_panes == "A2"
    assert workbook["子订单"].auto_filter.ref.endswith("2")
    assert charge_headers[:4] == ["母订单号", "母项目名称", "子订单号", "文件/子项目名称"]


def test_reconciliation_flattens_children_and_parent_only_without_duplicates():
    parent_only = sample_project(project_name="纯母订单", with_sub_order=False)
    parent_only.order_no = "TP-260901-002"
    parent_only.source_file_name = None

    project_with_children = sample_project(project_name="含子订单项目")
    project_with_children.order_no = "TP-260901-003"
    first_sub_order = project_with_children.sub_orders[0]
    first_sub_order.sub_order_no = "TP-260901-003.001"
    first_sub_order.sub_project_name = "第一份文件.docx"
    second_sub_order = SimpleNamespace(
        **{
            **vars(first_sub_order),
            "sub_order_no": "TP-260901-003.002",
            "sub_project_name": "第二份文件.pdf",
            "status": "sent_to_client",
            "word_count_matrix": {"customer": {"pages": 12}},
            "customer_charge_items": [],
        }
    )
    project_with_children.sub_orders = [second_sub_order, first_sub_order]

    content = export_service.translation_reconciliation_to_xlsx(
        [[parent_only, project_with_children]]
    )
    workbook = load_workbook(BytesIO(content), data_only=False)

    assert workbook.sheetnames == ["对账单", "待补数据"]
    formal_rows = list(workbook["对账单"].iter_rows(values_only=True))
    formal_headers = formal_rows[0]
    formal_records = [dict(zip(formal_headers, row)) for row in formal_rows[1:]]
    pending_rows = list(workbook["待补数据"].iter_rows(values_only=True))
    pending_headers = pending_rows[0]
    pending_records = [dict(zip(pending_headers, row)) for row in pending_rows[1:]]

    assert formal_headers[:14] == (
        "订单号", "文件名称", "客户全称", "客户编号", "客户接单时间", "客户交稿时间",
        "翻译方向", "字数", "含税单价", "不含税单价", "含税总价", "不含税总价",
        "账单月份", "备注",
    )
    assert len(formal_records) == 1
    first_child_row = formal_records[0]
    assert first_child_row["订单号"] == "TP-260901-003.001"
    assert first_child_row["文件名称"] == "第一份文件.docx"
    assert first_child_row["客户全称"] == "子客户全称"
    assert first_child_row["客户编号"] == "CL-001.001"
    assert first_child_row["字数"] == 800
    assert first_child_row["含税单价"] == 127.2
    assert first_child_row["不含税总价"] == 88
    assert first_child_row["账单月份"] == "2026-09"

    assert {row["订单号"] for row in pending_records} == {
        "TP-260901-002", "TP-260901-003.002",
    }
    parent_row = next(row for row in pending_records if row["订单号"] == "TP-260901-002")
    assert "缺少文件名称" in parent_row["缺失原因"]
    assert "缺少客户收费项" in parent_row["缺失原因"]
    assert workbook["对账单"].freeze_panes == "A2"
    assert workbook["待补数据"].auto_filter.ref.endswith("3")


def test_reconciliation_charge_detail_keeps_each_currency_and_numeric_values():
    project = sample_project()
    project.sub_orders[0].customer_charge_items.append(
        SimpleNamespace(
            item_name="排版费",
            pricing_mode="fixed",
            metric_type=None,
            quantity=None,
            unit_size=None,
            unit_price=None,
            unit_price_excl_tax=None,
            unit_price_incl_tax=None,
            total_excl_tax=50,
            total_incl_tax=53,
            billing_month="2026-09",
            currency="USD",
            calculated_amount=None,
            final_amount=50,
            remarks="固定收费",
        )
    )

    content = export_service.translation_reconciliation_to_xlsx([[project]])
    workbook = load_workbook(BytesIO(content), data_only=False)
    rows = list(workbook["对账单"].iter_rows(values_only=True))
    headers = rows[0]
    records = [dict(zip(headers, row)) for row in rows[1:]]

    assert len(records) == 2
    assert [record["币种"] for record in records] == ["CNY", "USD"]
    assert records[0]["字数"] == 800
    assert records[0]["不含税单价"] == 120
    assert records[0]["不含税总价"] == 88
    assert records[1]["不含税总价"] == 50
    assert records[1]["含税总价"] == 53
    assert records[1]["字数"] is None


def test_reconciliation_exports_parent_charge_and_uses_snapshot_file_fallback():
    project = sample_project(with_sub_order=False)
    project.source_file_name = None
    project.reconciliation_file_names = "正文.docx、附件.pdf"
    project.word_count_matrix["customer"]["words"] = 1500
    project.customer_charge_items = [
        SimpleNamespace(
            item_name="翻译费", pricing_mode="metric", metric_type="words",
            quantity=1500, unit_size=1000,
            unit_price_excl_tax=100, unit_price_incl_tax=106,
            total_excl_tax=150, total_incl_tax=159,
            billing_month="2026-09", currency="CNY", remarks="母单收费",
        )
    ]

    content = export_service.translation_reconciliation_to_xlsx([[project]])
    workbook = load_workbook(BytesIO(content), data_only=False)
    _headers, row = row_by_headers(workbook["对账单"])

    assert row["订单号"] == project.order_no
    assert row["文件名称"] == "正文.docx、附件.pdf"
    assert row["客户全称"] == "子客户全称"
    assert row["收费项目"] == "翻译费"
    assert workbook["待补数据"].max_row == 1


def test_effective_file_name_uses_order_level_value_before_same_level_snapshot():
    project = SimpleNamespace(
        source_file_name="母稿.docx",
        reconciliation_file_names="母单快照.docx",
    )
    child = SimpleNamespace(
        sub_order_no="TP-260901-001.001",
        sub_project_name="子稿.docx",
        reconciliation_file_names="子单快照.docx",
    )

    assert export_service._effective_file_name(project, project) == "母稿.docx"
    assert export_service._effective_file_name(project, child) == "子稿.docx"

    project.source_file_name = None
    child.sub_project_name = None
    assert export_service._effective_file_name(project, project) == "母单快照.docx"
    assert export_service._effective_file_name(project, child) == "子单快照.docx"


def test_reconciliation_routes_missing_tax_and_month_to_pending_sheet():
    project = sample_project()
    charge = project.sub_orders[0].customer_charge_items[0]
    charge.billing_month = None
    charge.unit_price_incl_tax = None
    charge.total_incl_tax = None

    content = export_service.translation_reconciliation_to_xlsx([[project]])
    workbook = load_workbook(BytesIO(content), data_only=False)
    assert workbook["对账单"].max_row == 1
    _headers, row = row_by_headers(workbook["待补数据"])
    assert "缺少账单月份" in row["缺失原因"]
    assert "缺少含税单价" in row["缺失原因"]
    assert "缺少含税总价" in row["缺失原因"]


def test_reconciliation_keeps_complete_charge_when_optional_business_details_are_empty():
    project = sample_project()
    project.customer_reception_time = None
    project.customer_deadline_time = None
    project.language_pair = None
    project.sub_orders[0].customer_deadline_time = None
    project.sub_orders[0].language_pair = None

    content = export_service.translation_reconciliation_to_xlsx([[project]])
    workbook = load_workbook(BytesIO(content), data_only=False)

    assert workbook["对账单"].max_row == 2
    assert workbook["待补数据"].max_row == 1


def test_snapshot_file_fallback_uses_latest_dispatch_and_deduplicates_names():
    project_id = uuid4()
    sub_order_id = uuid4()
    latest_dispatch_id = uuid4()
    old_dispatch_id = uuid4()
    project = SimpleNamespace(
        id=project_id,
        sub_orders=[SimpleNamespace(id=sub_order_id)],
    )

    class FakeQuery:
        def join(self, *_args, **_kwargs):
            return self

        def filter(self, *_args, **_kwargs):
            return self

        def order_by(self, *_args, **_kwargs):
            return self

        def all(self):
            return [
                (latest_dispatch_id, project_id, None, "正文.docx"),
                (latest_dispatch_id, project_id, None, "正文.docx"),
                (latest_dispatch_id, project_id, None, "附件.pdf"),
                (old_dispatch_id, project_id, None, "旧稿.docx"),
                (latest_dispatch_id, project_id, sub_order_id, "子稿.docx"),
            ]

    fake_db = SimpleNamespace(query=lambda *_args: FakeQuery())
    export_service._attach_reconciliation_file_names(fake_db, [project])

    assert project.reconciliation_file_names == "正文.docx、附件.pdf"
    assert project.sub_orders[0].reconciliation_file_names == "子稿.docx"


def test_reconciliation_rejects_business_row_limit():
    project = sample_project()
    project.sub_orders[0].customer_charge_items.append(
        SimpleNamespace(
            item_name="排版费", pricing_mode="fixed", metric_type=None,
            quantity=None, unit_size=None, unit_price=None,
            unit_price_excl_tax=None, unit_price_incl_tax=None,
            total_excl_tax=50, total_incl_tax=53, billing_month="2026-09",
            currency="CNY", remarks=None,
        )
    )
    with pytest.raises(export_service.TranslationExportLimitError, match="对账单"):
        export_service.translation_reconciliation_to_xlsx(
            [[project]], max_rows_per_sheet=1
        )


def test_translator_reconciliation_flattens_parent_children_and_all_translators():
    project = sample_project()
    project.customer_order_no = "PO-20260901"
    project.client_short_name = "母客户"
    project.sub_client_short_name = "子客户"
    parent_assignment = {
        **project.assigned_translators[0],
        "translator_name": "王译员",
        "actual": {"words": 0, "characters_no_spaces": 1200, "pages": 3},
        "remarks": '=HYPERLINK("https://example.com")',
    }
    child_assignment = {
        **project.assigned_translators[0],
        "translator_id": uuid4(),
        "translator_name": "李译员",
        "actual": {
            "words": 800,
            "characters_no_spaces": None,
            "cjk_chars_korean_words": 700,
            "foreign_words": 600,
            "documents": 2,
            "pages": 4,
        },
        "translator_unit_price": Decimal("0.2345"),
        "translator_total_price": Decimal("187.60"),
        "completion_remarks": "按时完成",
    }
    project.assigned_translators = [parent_assignment]
    project.sub_orders[0].assigned_translators = [child_assignment]

    content = export_service.translation_translator_reconciliation_to_xlsx([[project]])
    workbook = load_workbook(BytesIO(content), data_only=False)

    assert workbook.sheetnames == ["译员对账单"]
    rows = list(workbook["译员对账单"].iter_rows(values_only=True))
    headers = rows[0]
    records = [dict(zip(headers, row)) for row in rows[1:]]
    assert headers == tuple(column.label for column in export_service.TRANSLATOR_RECONCILIATION_COLUMNS)
    assert len(records) == 2

    parent_row, child_row = records
    assert parent_row["订单号"] == "TP-260901-001"
    assert parent_row["客户单号"] == "PO-20260901"
    assert parent_row["项目名称"] == "示例项目"
    assert parent_row["文件名称"] == "合同原文.docx"
    assert parent_row["客户简称"] == "子客户"
    assert parent_row["状态"] == "已确认"
    assert parent_row["译员"] == "王译员"
    assert parent_row["实际数量"] == "字数：0；字符数（不计空格）：1200；页数：3"
    assert parent_row["译员单价"] == pytest.approx(0.1234)
    assert parent_row["译员总价"] == pytest.approx(61.70)

    assert child_row["订单号"] == "TP-260901-001.001"
    assert child_row["项目名称"] == "示例项目"
    assert child_row["文件名称"] == "子稿一.docx"
    assert child_row["状态"] == "已排译员"
    assert child_row["译员"] == "李译员"
    assert child_row["实际数量"] == (
        "字数：800；中文字符和朝鲜语单词：700；外文字数：600；份数：2；页数：4"
    )
    assert child_row["派稿补充要求"] == "术语以附件为准"
    assert child_row["任务完成情况"] == "按时完成"
    assert workbook["译员对账单"].freeze_panes == "A2"
    assert workbook["译员对账单"].auto_filter.ref.endswith("3")

    remarks_cell = workbook["译员对账单"].cell(
        row=2,
        column=headers.index("派稿补充要求") + 1,
    )
    assert remarks_cell.data_type == "s"
    assert remarks_cell.value.startswith("'=")


def test_translator_reconciliation_filters_translator_rows_and_rejects_empty_or_limit():
    project = sample_project(with_sub_order=False)
    project.sub_client_short_name = None
    project.assigned_translators = [
        {**project.assigned_translators[0], "translator_name": "张三"},
        {
            **project.assigned_translators[0],
            "translator_id": uuid4(),
            "translator_name": "李四",
        },
    ]

    content = export_service.translation_translator_reconciliation_to_xlsx(
        [[project]], translator_name="李"
    )
    workbook = load_workbook(BytesIO(content), data_only=False)
    _headers, row = row_by_headers(workbook["译员对账单"])
    assert row["译员"] == "李四"
    assert row["客户简称"] == "母客户"
    assert workbook["译员对账单"].max_row == 2

    with pytest.raises(export_service.TranslationExportEmptyError, match="有效译员安排"):
        export_service.translation_translator_reconciliation_to_xlsx(
            [[project]], translator_name="不存在"
        )
    with pytest.raises(export_service.TranslationExportLimitError, match="译员对账单"):
        export_service.translation_translator_reconciliation_to_xlsx(
            [[project]], max_rows_per_sheet=1
        )


def test_export_rejects_empty_data_and_sheet_row_limit():
    with pytest.raises(export_service.TranslationExportEmptyError, match="没有可导出"):
        export_service.translation_projects_to_xlsx([])

    with pytest.raises(export_service.TranslationExportLimitError, match="母订单"):
        export_service.translation_projects_to_xlsx(
            [[sample_project(with_sub_order=False), sample_project(with_sub_order=False)]],
            max_rows_per_sheet=1,
        )


def test_export_filters_override_same_time_field_and_preserve_other_filters():
    raw = (
        '{"project_status":{"op":"in","value":["confirmed"]},'
        '"customer_reception_time":{"op":"between","from":"2026-08-01","to":"2026-08-31"},'
        '"customer_deadline_time":{"op":"between","from":"2026-09-15","to":"2026-09-30"}}'
    )
    filters = translation_router._export_field_filters(
        raw,
        time_field="customer_reception_time",
        date_start=date(2026, 9, 1),
        date_end=date(2026, 9, 10),
    )

    assert filters["project_status"]["value"] == ["confirmed"]
    assert filters["customer_reception_time"] == {
        "op": "between", "from": "2026-09-01", "to": "2026-09-10",
    }
    assert filters["customer_deadline_time"]["from"] == "2026-09-15"


def test_export_filters_reject_reverse_date_range():
    with pytest.raises(HTTPException) as exc_info:
        translation_router._export_field_filters(
            None,
            time_field="created_at",
            date_start=date(2026, 9, 2),
            date_end=date(2026, 9, 1),
        )
    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "开始日期不能晚于结束日期"


def test_export_query_is_paged_and_reuses_all_filters(monkeypatch):
    calls = []
    projects = [sample_project(with_sub_order=False), sample_project(with_sub_order=False)]

    def fake_get_projects(_db, **kwargs):
        calls.append(kwargs)
        return projects[kwargs["skip"]:kwargs["skip"] + kwargs["limit"]]

    monkeypatch.setattr(export_service, "EXPORT_BATCH_SIZE", 1)
    monkeypatch.setattr(export_service, "get_translation_projects", fake_get_projects)
    content = export_service.create_translation_project_export(
        object(),
        keyword="客户A",
        field_filters={"created_at": {"op": "between", "from": "2026-09-01", "to": "2026-09-02"}},
        sort="order_no_desc",
    )

    assert content.startswith(b"PK")
    assert [call["skip"] for call in calls] == [0, 1, 2]
    assert all(call["keyword"] == "客户A" for call in calls)
    assert all(call["sort"] == "order_no_desc" for call in calls)


def test_export_route_returns_xlsx_headers(monkeypatch):
    monkeypatch.setattr(
        translation_router,
        "create_translation_project_export",
        lambda *_args, **_kwargs: b"xlsx-content",
    )
    response = translation_router.export_projects(
        time_field="created_at",
        date_start=date(2026, 9, 1),
        date_end=date(2026, 9, 30),
        keyword=None,
        sort=None,
        field_filters=None,
        db=object(),
    )

    assert response.media_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    disposition = response.headers["content-disposition"]
    assert "translation-projects-2026-09-01-2026-09-30.xlsx" in disposition
    assert "filename*=UTF-8''" in disposition


def test_reconciliation_route_returns_xlsx_headers(monkeypatch):
    monkeypatch.setattr(
        translation_router,
        "create_translation_reconciliation_export",
        lambda *_args, **_kwargs: b"xlsx-content",
    )
    response = translation_router.export_reconciliation(
        time_field="customer_reception_time",
        date_start=date(2026, 9, 1),
        date_end=date(2026, 9, 30),
        keyword="客户A",
        sort="order_no_desc",
        field_filters=None,
        db=object(),
    )

    assert response.media_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    disposition = response.headers["content-disposition"]
    assert "translation-reconciliation-2026-09-01-2026-09-30.xlsx" in disposition
    assert "filename*=UTF-8''" in disposition


def test_reconciliation_route_supports_exact_client_export(monkeypatch):
    client_id = uuid4()
    captured = {}
    monkeypatch.setattr(
        translation_router,
        "get_client",
        lambda *_args, **_kwargs: SimpleNamespace(
            client_short_name="测试/客户",
            client_name="测试客户有限公司",
            client_code="C001",
        ),
    )

    def fake_export(_db, **kwargs):
        captured.update(kwargs)
        return b"xlsx-content"

    monkeypatch.setattr(
        translation_router,
        "create_translation_reconciliation_export",
        fake_export,
    )
    response = translation_router.export_reconciliation(
        client_id=client_id,
        keyword=None,
        sort=None,
        field_filters=None,
        db=object(),
    )

    assert captured["field_filters"] == {
        "client_id": {"op": "eq", "value": str(client_id)},
    }
    disposition = response.headers["content-disposition"]
    assert f"translation-reconciliation-client-{client_id}.xlsx" in disposition
    assert "%E6%B5%8B%E8%AF%95_%E5%AE%A2%E6%88%B7" in disposition


def test_reconciliation_route_requires_time_range_without_client():
    with pytest.raises(HTTPException) as exc_info:
        translation_router.export_reconciliation(
            keyword=None,
            sort=None,
            field_filters=None,
            db=object(),
        )
    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "请选择完整的时间口径和时间范围"


def test_translator_reconciliation_route_returns_xlsx_headers(monkeypatch):
    monkeypatch.setattr(
        translation_router,
        "create_translation_translator_reconciliation_export",
        lambda *_args, **_kwargs: b"xlsx-content",
    )
    response = translation_router.export_translator_reconciliation(
        time_field="customer_deadline_time",
        date_start=date(2026, 9, 1),
        date_end=date(2026, 9, 30),
        keyword="李译员",
        sort="order_no_desc",
        field_filters='{"translator_name":{"op":"contains","value":"李"}}',
        db=object(),
    )

    assert response.media_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    disposition = response.headers["content-disposition"]
    assert "translation-translator-reconciliation-2026-09-01-2026-09-30.xlsx" in disposition
    assert "filename*=UTF-8''" in disposition


@pytest.mark.parametrize(
    ("exception", "status_code"),
    [
        (export_service.TranslationExportEmptyError("无数据"), 404),
        (export_service.TranslationExportLimitError("超限"), 422),
    ],
)
def test_export_route_maps_business_errors(monkeypatch, exception, status_code):
    def raise_error(*_args, **_kwargs):
        raise exception

    monkeypatch.setattr(translation_router, "create_translation_project_export", raise_error)
    with pytest.raises(HTTPException) as exc_info:
        translation_router.export_projects(
            time_field="created_at",
            date_start=date(2026, 9, 1),
            date_end=date(2026, 9, 30),
            keyword=None,
            sort=None,
            field_filters=None,
            db=object(),
        )
    assert exc_info.value.status_code == status_code
