"""微信群不覆盖个人微信或联系账号，允许清空和保留多行群名。"""
import pytest
from pydantic import ValidationError
from resource_schemas import ResourcePersonCreate, ResourcePersonUpdate

@pytest.mark.parametrize('schema', [ResourcePersonCreate, ResourcePersonUpdate])
def test_groups_preserve_multiline_and_independent_contacts(schema):
    value = schema(full_name='测试人才', wechat='personal', wechat_account='HR1',
                   wechat_groups='  温州话沟通群\n（已退群）历史沟通群  ')
    assert value.wechat_groups == '温州话沟通群\n（已退群）历史沟通群'
    assert value.wechat == 'personal' and value.wechat_account == 'HR1'

@pytest.mark.parametrize('value', [None, '', '   '])
def test_groups_can_be_cleared(value):
    payload = ResourcePersonUpdate(full_name='测试人才', wechat_groups=value)
    assert payload.model_dump(exclude_unset=True)['wechat_groups'] is None

def test_groups_have_length_limit():
    with pytest.raises(ValidationError):
        ResourcePersonCreate(full_name='测试人才', wechat_groups='群' * 4001)
