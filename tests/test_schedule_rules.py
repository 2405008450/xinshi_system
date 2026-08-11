from datetime import date, datetime
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

import pytest
from openpyxl import Workbook
from pydantic import ValidationError

from migrate_legacy_employee_shifts import parse_shift
from leave_service import assignment_disabled_reason, leave_status
from models import Translator
from routers.schedule import (
    _employee_shift_department_options,
    _parse_translator_availability_status,
    _parse_translator_schedule_auto,
)
from schemas import AppUserUpdate, EmployeeShiftLockUpdate, EmployeeShiftOverrideItem, EmployeeShiftTemplateUpdate


class FakeQuery:
    def __init__(self, model, translators):
        self.model = model
        self.translators = translators

    def all(self):
        return self.translators if self.model is Translator else []

    def filter(self, *_args):
        return self

    def first(self):
        return None


class FakeDb:
    def __init__(self, translators):
        self.translators = translators

    def query(self, model):
        return FakeQuery(model, self.translators)


class FakeDepartmentQuery:
    def __init__(self, departments):
        self.departments = departments

    def filter(self, *_args):
        return self

    def distinct(self):
        return self

    def all(self):
        return [(department,) for department in self.departments]


class FakeDepartmentDb:
    def __init__(self, departments):
        self.departments = departments

    def query(self, _model):
        return FakeDepartmentQuery(self.departments)


def workbook_bytes(headers, rows):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def template_days(weekend_code="off"):
    return [
        {"weekday": weekday, "shift_code": weekend_code if weekday >= 6 else "early"}
        for weekday in range(1, 8)
    ]


def test_employee_shift_department_options_are_dynamic_and_sorted():
    options = _employee_shift_department_options(
        FakeDepartmentDb(["翻译部", None, "项目部", "翻译部", ""])
    )

    assert options == [
        {"value": "IT部", "label": "IT部"},
        {"value": "项目部", "label": "项目部"},
        {"value": "__unassigned__", "label": "未分部门"},
    ]


def test_legacy_recruitment_department_is_exposed_as_other():
    options = _employee_shift_department_options(
        FakeDepartmentDb(["招聘项目", "其他"])
    )

    assert options == [{"value": "其他", "label": "其他"}]
    assert AppUserUpdate(department="招聘项目").department == "其他"


def test_legacy_translation_department_is_exposed_as_it():
    options = _employee_shift_department_options(
        FakeDepartmentDb(["翻译部", "IT部"])
    )

    assert options == [{"value": "IT部", "label": "IT部"}]
    assert AppUserUpdate(department="翻译部").department == "IT部"


def test_user_update_accepts_blank_optional_email():
    payload = AppUserUpdate(email="", department="IT部")

    assert payload.email is None
    assert payload.department == "IT部"


def test_week_template_requires_monday_and_all_seven_days():
    payload = EmployeeShiftTemplateUpdate(
        effective_from=date(2026, 8, 3),
        days=template_days(),
    )
    assert len(payload.days) == 7

    with pytest.raises(ValidationError):
        EmployeeShiftTemplateUpdate(
            effective_from=date(2026, 8, 4),
            days=template_days(),
        )

    with pytest.raises(ValidationError):
        EmployeeShiftTemplateUpdate(
            effective_from=date(2026, 8, 3),
            days=template_days()[:-1],
        )


def test_weekend_duty_is_rejected_on_workday():
    days = template_days()
    days[0]["shift_code"] = "weekend_duty"
    with pytest.raises(ValidationError):
        EmployeeShiftTemplateUpdate(effective_from=date(2026, 8, 3), days=days)

    with pytest.raises(ValidationError):
        EmployeeShiftOverrideItem(
            user_id="00000000-0000-0000-0000-000000000001",
            schedule_date=date(2026, 8, 5),
            shift_code="weekend_duty",
        )


def test_custom_shift_requires_same_day_valid_time_range():
    with pytest.raises(ValidationError):
        EmployeeShiftOverrideItem(
            user_id="00000000-0000-0000-0000-000000000001",
            schedule_date=date(2026, 8, 5),
            shift_code="custom",
            start_time="18:00",
            end_time="09:00",
        )


def test_shift_lock_effective_date_must_be_monday():
    valid = EmployeeShiftLockUpdate(
        effective_from=date(2026, 8, 3),
        is_locked=True,
        reason="长期固定班次",
    )
    assert valid.is_locked is True

    with pytest.raises(ValidationError):
        EmployeeShiftLockUpdate(
            effective_from=date(2026, 8, 4),
            is_locked=False,
            reason="未来解锁",
        )


def test_leave_status_uses_half_open_business_time_window():
    employee = SimpleNamespace(full_name="测试员工", username="tester")
    record = SimpleNamespace(
        employee=employee,
        employee_name="兼容姓名",
        start_date=datetime(2026, 8, 6, 9, 0),
        end_date=datetime(2026, 8, 6, 18, 0),
    )

    assert leave_status(record, datetime(2026, 8, 6, 8, 59, 59)) == "upcoming"
    assert leave_status(record, datetime(2026, 8, 6, 9, 0)) == "active"
    assert leave_status(record, datetime(2026, 8, 6, 17, 59, 59)) == "active"
    assert leave_status(record, datetime(2026, 8, 6, 18, 0)) == "past"
    assert assignment_disabled_reason(record) == "测试员工正在请假，至2026-08-06 18:00结束"


def test_legacy_weekend_0930_shift_maps_to_weekend_duty():
    code, start_value, end_value = parse_shift("周末 9:30~18:00", date(2026, 8, 8))
    assert code == "weekend_duty"
    assert start_value.isoformat(timespec="minutes") == "09:30"
    assert end_value.isoformat(timespec="minutes") == "18:00"

    workday_code, *_ = parse_shift("9:30~18:00", date(2026, 8, 5))
    assert workday_code == "custom"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("可接稿", "available"), ("0", "unavailable"), ("本周期不可接稿", "cycle_blocked")],
)
def test_translator_availability_status_mapping(raw, expected):
    assert _parse_translator_availability_status(raw) == expected


def test_standard_translator_schedule_preview_reports_row_errors():
    translator = SimpleNamespace(id=uuid4(), translator_name="标准模板译员")
    content = workbook_bytes(
        ["译员ID", "译员姓名", "日期", "接稿状态", "可接时段", "剩余容量", "备注"],
        [
            [str(translator.id), translator.translator_name, "2026-08-05", "可接稿", "09:00-18:00", 3000, "可接"],
            [str(translator.id), translator.translator_name, "2026-08-06", "不可接稿", "", "错误容量", "休息"],
        ],
    )

    parsed = _parse_translator_schedule_auto(content, "standard.xlsx", FakeDb([translator]))

    assert parsed["format"] == "standard"
    assert len(parsed["preview_items"]) == 1
    assert parsed["preview_items"][0]["availability_status"] == "available"
    assert parsed["errors"] == [{"row_no": 3, "message": "剩余容量必须是整数"}]


def test_external_g_p_translator_schedule_preview_keeps_unavailable_days():
    translator = SimpleNamespace(id=uuid4(), translator_name="外部收集译员")
    headers = [f"字段{i}" for i in range(16)]
    row = [None] * 16
    row[6] = translator.translator_name
    row[7] = "2026-08-03"
    row[8] = "可接稿"
    row[9] = "10:00-18:00"
    row[10:15] = [1, 0, 1, 0, 1]
    row[15] = "外部收集备注"

    parsed = _parse_translator_schedule_auto(
        workbook_bytes(headers, [row]),
        "external.xlsx",
        FakeDb([translator]),
    )

    assert parsed["format"] == "external_g_p"
    assert [item["availability_status"] for item in parsed["preview_items"]] == [
        "available", "unavailable", "available", "unavailable", "available",
    ]
