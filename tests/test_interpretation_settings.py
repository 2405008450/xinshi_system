from uuid import UUID,uuid4
import pytest
from fastapi import HTTPException
from tests.test_chat_participant_access import environment
from tests.test_project_delivery import delivery
from interpretation_settings import InterpretationProjectSettings,SettingsWrite,catalog,save,mention_ids


def test_settings_defaults_custom_empty_and_revision_conflict(environment):
    db,users=environment
    users[1].username='zixia';users[2].username='kuangjiao';db.commit()
    initial=catalog(db)
    assert set(initial['mention_user_ids'])=={str(users[1].id),str(users[2].id)}
    result=save(db,users[0],SettingsWrite(mention_user_ids=[users[2].id],revision=0))
    assert result['mention_user_ids']==[str(users[2].id)]
    with pytest.raises(HTTPException) as conflict:save(db,users[0],SettingsWrite(mention_user_ids=[],revision=0))
    assert conflict.value.status_code==409
    db.rollback()
    result=save(db,users[0],SettingsWrite(mention_user_ids=[],revision=1))
    assert result['mention_user_ids']==[]
    assert mention_ids(db,users)==set()
    with pytest.raises(HTTPException):save(db,users[0],SettingsWrite(mention_user_ids=[uuid4()],revision=2))


def test_configured_mentions_used_by_new_interpretation_messages(delivery):
    from discussion_chat_models import DiscussionMention
    db,users,projects,service=delivery
    save(db,users[0],SettingsWrite(mention_user_ids=[users[2].id],revision=0))
    service.send(db,users[0],'interpretation',projects['interpretation'].id,uuid4())
    assert {row.user_id for row in db.query(DiscussionMention)}=={users[2].id}


def test_chat_includes_saved_independent_requirements(delivery):
    from discussion_chat_models import DiscussionMessage
    from interpretation_interpreter_requirements import save as save_requirements
    from interpretation_schemas import InterpreterRequirementsInput
    db,users,projects,service=delivery
    save_requirements(db,projects['interpretation'],InterpreterRequirementsInput(passport='半年以上',interview='线上面试'))
    db.commit()
    service.send(db,users[0],'interpretation',projects['interpretation'].id,uuid4())
    content=db.query(DiscussionMessage).one().content
    assert '护照要求：半年以上' in content
    assert '面试要求：线上面试' in content
    assert '13800001234' not in content


def test_mail_and_chat_include_all_interpreter_requirements_once(delivery,monkeypatch):
    from datetime import datetime
    import business_mail_service as mail
    from tests.test_project_delivery import real_mail_preview
    from discussion_chat_models import DiscussionMessage
    from interpretation_models import InterpretationLanguage,InterpretationProjectTimeRange,InterpretationProjectLanguageDirection
    from interpretation_interpreter_requirements import save as save_requirements,REQUIREMENT_LABELS
    from interpretation_schemas import InterpreterRequirementsInput
    db,users,projects,service=delivery
    project=projects['interpretation']
    project.project_types=['business_escort'];project.locations=['深圳市'];project.required_interpreter_count=1
    project.required_interpreter_gender='不限';project.required_interpretation_level='高级'
    project.interpreter_height_requirement='身高测试';project.interpreter_appearance_requirement='相貌测试';project.interpreter_dress_requirement='着装测试'
    languages=[InterpretationLanguage(id=uuid4(),label=name) for name in ['中文','英语']]
    db.add_all(languages)
    project.time_ranges=[InterpretationProjectTimeRange(id=uuid4(),sequence_no=1,scheduled_start=datetime(2026,11,26,9),scheduled_end=datetime(2026,11,26,18))]
    project.language_directions=[InterpretationProjectLanguageDirection(id=uuid4(),sequence_no=1,source_language_id=languages[0].id,target_language_id=languages[1].id,required_count=1)]
    values={key:'测试'+label for key,label in REQUIREMENT_LABELS.items()}
    save_requirements(db,project,InterpreterRequirementsInput(**values));db.commit()
    monkeypatch.setattr(mail,'build_preview',real_mail_preview)
    monkeypatch.setattr(mail,'resolve_project_sender',lambda *_:(None,{}))
    preview=real_mail_preview(db,'interpretation',project_id=project.id,current_user=users[0])
    service.send(db,users[0],'interpretation',project.id,uuid4())
    content=db.query(DiscussionMessage).one().content
    for label,text in [('译员性别','不限'),('口译水平','高级'),('译员身高','身高测试'),('译员相貌','相貌测试'),('着装要求','着装测试'),*[(label,values[key]) for key,label in REQUIREMENT_LABELS.items()]]:
        expected=f'{label}：{text}'
        assert preview['body'].count(expected)==1,expected
        assert content.count(expected)==1,expected
    assert '中文' in preview['body'] and '英语' in preview['body']
    assert '13800001234' not in preview['body'] and '13800001234' not in content
