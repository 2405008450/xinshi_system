"""仅由隔离验收调用的固定身份与聊天数据。"""
from uuid import UUID, uuid4
from models import AppUser, Role, RolePermission, UserRole, TranslationProject, ChatProjectEnabled, ChatDirectConversation, ChatDirectMember, ChatProjectMessage
from annotation_models import AnnotationProject
from resource_issue_models import business_now

IDS = {name: UUID(int=number) for number, name in enumerate(('collector', 'proposer', 'executor', 'outsider', 'manager', 'admin', 'inactive'), 501)}
NAMES = {'collector': '验收收录人', 'proposer': '验收提出人', 'executor': '验收执行人', 'outsider': '无关联资源用户', 'manager': '验收统筹人', 'admin': '验收管理员', 'inactive': '停用人员'}
PERMISSIONS = {'collector': ['talents:read','talents:write','projects:read'], 'proposer':['projects:read'],
               'executor':[], 'outsider':['talents:read'], 'manager':['resource_development:delegate','projects:read'], 'admin':[],'inactive':[]}


def seed(db):
    users = {key: AppUser(id=value, username='issue_qa_'+key, full_name=NAMES[key], password_hash='isolated-no-login', is_active=key!='inactive') for key,value in IDS.items()}
    db.add_all(users.values()); db.flush()
    for key, user in users.items():
        role = Role(role_name='admin' if key=='admin' else 'issue_qa_'+key)
        db.add(role); db.flush(); db.add(UserRole(user_id=user.id, role_id=role.id))
        db.add_all(RolePermission(role_id=role.id,permission_code=code) for code in PERMISSIONS[key])
    translation = TranslationProject(id=uuid4(), order_no='ISSUE-QA-TRANSLATION', project_name='开拓来源笔译项目')
    annotation = AnnotationProject(id=uuid4(), order_no='ISSUE-QA-ANNOTATION', project_name='开拓来源标注项目', project_types=[])
    low,high=sorted((users['collector'].id,users['proposer'].id))
    direct = ChatDirectConversation(id=uuid4(),user_low_id=low,user_high_id=high)
    db.add_all([translation,annotation,direct]); db.flush()
    db.add(ChatProjectEnabled(project_id=translation.id,enabled=True))
    db.add_all(ChatDirectMember(conversation_id=direct.id,user_id=u.id) for u in (users['collector'],users['proposer']))
    messages={}
    for key,fields in [('translation',dict(project_id=translation.id)),('annotation',dict(annotation_project_id=annotation.id)),('direct',dict(direct_conversation_id=direct.id))]:
        message=ChatProjectMessage(id=uuid4(),sender_user_id=users['proposer'].id,sender_name=users['proposer'].full_name,
                                  content=f'{key}：请整理开拓资源，并记录遇到的问题。',message_type='user',**fields)
        db.add(message);messages[key]=message
    db.flush()
    return dict(users=users,messages=messages,translation=translation,annotation=annotation,direct=direct)
