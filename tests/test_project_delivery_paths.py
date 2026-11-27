"""口译、标注、招聘的路径进入邮件及会话；只用隔离数据库，不发送邮件。"""
from uuid import uuid4
from types import SimpleNamespace
import pytest
import business_mail_service as mail
from tests.test_project_delivery import delivery
from tests.test_chat_participant_access import environment


@pytest.mark.parametrize('module',['interpretation','annotation','recruitment'])
@pytest.mark.parametrize('path',[r'\\server\项目资料\项目 A&B',r'D:\项目资料\项目 A&B',''])
def test_saved_path_shared_by_mail_preview_and_chat(delivery,monkeypatch,module,path):
    from discussion_chat_models import DiscussionMessage
    db,users,projects,service=delivery
    project=projects[module]
    setattr(project,'file_path' if module=='interpretation' else 'project_path',path)
    db.commit()
    core={
        'interpretation':dict(project_types=['onsite'],time_ranges=['2026-11-27'],locations=['深圳'],language_directions=['中英'],required_interpreter_count=1),
        'annotation':dict(project_types=['text_annotation'],task_description='任务',language_items=['中文']),
        'recruitment':dict(position_title='译员',headcount_min=1,employment_start='2026-12-01',employment_end='2026-12-02',work_location='深圳'),
    }
    # delivery fixture 模拟发送；此处恢复真实内容生成，仍模拟邮件发送方和通知推送。
    from tests.test_project_delivery import real_mail_preview
    monkeypatch.setattr(mail,'resolve_project_sender',lambda *_:(None,{}))
    monkeypatch.setattr(mail,'build_preview',lambda db,kind,**kwargs:real_mail_preview(db,kind,**{**kwargs,'source':{**kwargs.get('source',{}),**core[kind]}}))
    preview=mail.build_preview(db,module,project_id=project.id,current_user=users[0])
    assert not preview['missing_fields']
    assert preview['body'].count('【登记时自动发送】')==1
    if path:
        assert preview['body'].count('项目路径：'+path)==1
        assert '项目 A&amp;B' in preview['body_html']
    else:assert '项目路径：' not in preview['body']
    service.send(db,users[0],module,project.id,uuid4())
    content=db.query(DiscussionMessage).one().content
    assert content.count('【登记时自动发送】')==1
    if path:assert content.count('项目路径：'+path)==1
    else:assert '项目路径：' not in content


@pytest.mark.parametrize('module,key',[('interpretation','file_path'),('annotation','project_path'),('recruitment','project_path')])
def test_unsaved_preview_source_path(monkeypatch,module,key):
    monkeypatch.setattr(mail,'policy_recipients',lambda *_:([],[]))
    monkeypatch.setattr(mail,'resolve_project_sender',lambda *_:(None,{}))
    value=r'\\server\项目资料\待保存项目'
    result=mail.build_preview(SimpleNamespace(info={}),module,source={key:value})
    assert result['body'].count('项目路径：'+value)==1
