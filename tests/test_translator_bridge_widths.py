from unittest.mock import MagicMock
from uuid import uuid4
import main  # 仅注册模型，不执行启动钩子或连接业务数据库。

from models import Translator
from resource_models import ResourcePerson, WrittenTranslationProfile, InterpretationProfile
from resource_service import _sync_legacy_translator


def test_all_legacy_text_fields_accept_authoritative_talent_widths():
    aliases={'translator_name':'full_name','email1':'primary_email','email2':'secondary_email','phone':'primary_phone','phone2':'secondary_phone'}
    for target in Translator.__table__.columns:
        source_name=aliases.get(target.name,target.name)
        for model in (ResourcePerson,WrittenTranslationProfile,InterpretationProfile):
            source=model.__table__.columns.get(source_name)
            if source is None or not hasattr(source.type,'length'):
                continue
            if hasattr(target.type,'length') and target.type.length is not None:
                assert source.type.length is not None and target.type.length>=source.type.length, target.name


def test_long_translation_direction_is_preserved_in_compatibility_record():
    direction='中英双向翻译，兼顾技术资料、合同与市场宣传文案'
    assert len(direction)>20
    person=ResourcePerson(id=uuid4(),resource_code='RC-QA',full_name='隔离测试人才')
    person.written_profile=WrittenTranslationProfile(direction=direction,languages='中文、英语')
    # 只替换关系的读取，不向任何业务数据库提交。
    from resource_models import ResourceCapability
    person.capabilities=[ResourceCapability(capability_type='written_translation',status='active')]
    db=MagicMock()
    db.query.return_value.filter.return_value.first.return_value=None
    _sync_legacy_translator(db,person)
    legacy=db.add.call_args.args[0]
    assert legacy.direction==direction
