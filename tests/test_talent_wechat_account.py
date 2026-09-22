"""所在微信与人才本人微信独立，允许预设账号和自定义名称。"""

import pytest
from pydantic import ValidationError

from resource_schemas import ResourcePersonCreate, ResourcePersonUpdate


@pytest.mark.parametrize("schema", [ResourcePersonCreate, ResourcePersonUpdate])
@pytest.mark.parametrize("value", [*[f"HR{i}" for i in range(1, 7)], *[f"HR{i}企微" for i in range(1, 7)], "其他招聘微信"])
def test_wechat_account_accepts_presets_and_custom_names(schema, value):
    payload = schema(full_name="测试人才", wechat="personal_wechat", wechat_account=f" {value} ")
    saved_values = payload.model_dump()
    assert saved_values["wechat_account"] == value
    assert saved_values["wechat"] == "personal_wechat"


@pytest.mark.parametrize("value", [None, "", "   "])
def test_wechat_account_can_be_empty_or_cleared(value):
    payload = ResourcePersonUpdate(full_name="测试人才", wechat_account=value)
    assert payload.model_dump(exclude_unset=True)["wechat_account"] is None


def test_wechat_account_rejects_overlong_names():
    with pytest.raises(ValidationError):
        ResourcePersonCreate(full_name="测试人才", wechat_account="微" * 101)
