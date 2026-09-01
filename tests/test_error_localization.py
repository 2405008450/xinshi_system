from error_localization import localize_http_detail, localize_validation_errors, localize_validation_message


def test_missing_validation_error_is_localized_without_changing_structure():
    errors = [{
        "type": "missing",
        "loc": ("body", "project_intake", "locations"),
        "msg": "Field required",
        "input": {},
    }]

    result = localize_validation_errors(errors)

    assert result[0]["loc"] == errors[0]["loc"]
    assert result[0]["type"] == "missing"
    assert result[0]["input"] == {}
    assert result[0]["msg"] == "此字段为必填项"
    assert errors[0]["msg"] == "Field required"


def test_common_pydantic_validation_types_use_specific_chinese_messages():
    assert localize_validation_message({
        "type": "string_too_short", "ctx": {"min_length": 3},
    }) == "内容不能少于 3 个字符"
    assert localize_validation_message({
        "type": "less_than_equal", "ctx": {"le": 100},
    }) == "数值不能大于 100"
    assert localize_validation_message({"type": "uuid_parsing"}) == "标识格式不正确"
    assert localize_validation_message({"type": "datetime_from_date_parsing"}) == "日期时间格式不正确"
    assert localize_validation_message({"type": "unknown_validation_error"}) == "内容格式不正确"


def test_chinese_value_error_keeps_business_reason_and_removes_english_prefix():
    message = localize_validation_message({
        "type": "value_error",
        "msg": "Value error, 结束时间不能早于开始时间",
    })
    assert message == "结束时间不能早于开始时间"


def test_english_value_error_is_replaced_with_safe_chinese_message():
    message = localize_validation_message({
        "type": "value_error",
        "msg": "Value error, invalid internal state",
    })
    assert message == "内容不符合业务规则"


def test_http_exception_detail_uses_safe_chinese_fallbacks():
    assert localize_http_detail("Client not found", 404) == "请求的内容不存在或已被删除"
    assert localize_http_detail("保存失败：SQLAlchemy IntegrityError", 500) == "服务暂时异常，请稍后重试"
    assert localize_http_detail("SMTP 配置无效", 400) == "SMTP 配置无效"


def test_structured_http_error_preserves_business_data_and_localizes_message():
    detail = {"message": "Duplicate talent", "duplicate_ids": ["talent-1"]}

    localized = localize_http_detail(detail, 409)

    assert localized == {
        "message": "数据状态已发生变化，请刷新后重试",
        "duplicate_ids": ["talent-1"],
    }
    assert detail["message"] == "Duplicate talent"
