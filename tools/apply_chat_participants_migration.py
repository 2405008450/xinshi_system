"""显式创建共享默认参与人表，并将既有会话参与范围固化为成员记录。"""
import argparse
import json
import socket
import subprocess
import sys
from uuid import uuid4
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def apply_migration(db):
    from sqlalchemy import inspect
    from chat_default_participant_models import AnnotationChatDefaultParticipant
    from models import AppUser, ChatProjectEnabled, ChatProjectMessage, ChatProjectMemberPref, TranslationProject
    from discussion_chat_models import DiscussionMember
    import discussion_chat_service as discussion
    from project_chat_crud import _legacy_chat_participant_user_ids
    existed = inspect(db.connection()).has_table(AnnotationChatDefaultParticipant.__tablename__)
    AnnotationChatDefaultParticipant.__table__.create(db.connection(), checkfirst=True)
    if existed:
        return dict(translation_members_added=0, discussion_members_added=0)
    # 现有标注会话沿用 annotation_chat_member，绝不向既有群套用新默认名单。
    ids = {pid for pid, in db.query(ChatProjectEnabled.project_id).filter(ChatProjectEnabled.enabled.is_(True))}
    ids.update(pid for pid, in db.query(ChatProjectMessage.project_id).filter(ChatProjectMessage.project_id.is_not(None)).distinct())
    translation_added = 0
    for pid in ids:
        if not db.get(TranslationProject, pid):
            continue
        for uid in _legacy_chat_participant_user_ids(db, project_id=pid):
            if not db.get(ChatProjectMemberPref, (pid, uid)):
                db.add(ChatProjectMemberPref(project_id=pid, user_id=uid, last_read_sequence=0, pinned=False, starred=False))
                translation_added += 1
    # 资源讨论原为公共范围：将原本有资源讨论权限的有效账号固化为参与人。
    # 后续新账号不再因为模块权限而自动获得既有会话访问权。
    users = [user for user in db.query(AppUser).filter(AppUser.is_active.is_(True)) if discussion.can_view(db, user)]
    discussion_added = 0
    for room in discussion.room_specs(db):
        from uuid import UUID
        rid = UUID(room['id'])
        for user in users:
            if not db.get(DiscussionMember, (rid, user.id)):
                db.add(DiscussionMember(room_id=rid, user_id=user.id, last_read_id=0, pinned=False, starred=False))
                discussion_added += 1
    db.flush()
    return dict(translation_members_added=translation_added, discussion_members_added=discussion_added)


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-target', required=True)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    roots = {'william': Path(r'D:\xinshi_system'), 'pc': Path(r'E:\xinshi_system')}
    host = socket.gethostname().lower()
    if roots.get(host) != ROOT or Path.cwd().resolve() != ROOT or Path(sys.executable).resolve() != ROOT / '.venv/Scripts/python.exe':
        raise SystemExit('主机、项目目录或项目虚拟环境不匹配')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if args.expected_commit != commit:
        raise SystemExit('Git 提交不匹配')
    from database import engine
    import main  # noqa: F401 注册所有现有 ORM 关联；不运行服务启动钩子。
    target = f'{engine.url.host}:{engine.url.port}/{engine.url.database}'
    if target != args.confirm_target or target != '43.132.156.72:15432/xinshi_system':
        raise SystemExit('数据库目标不匹配')
    from sqlalchemy import inspect, text
    print(json.dumps(dict(host=host, project=str(ROOT), commit=commit, target=target), ensure_ascii=False))
    if args.check_only:
        with engine.connect() as connection:
            print(json.dumps({'default_participant_table_exists': inspect(connection).has_table('annotation_chat_default_participant')}, ensure_ascii=False))
        return
    from sqlalchemy.orm import Session
    from business_time import business_now
    from models import AnnotationChatMember, ChatProjectMemberPref
    from discussion_chat_models import DiscussionMember
    backup_root = ROOT.parent / 'xinshi_runtime' / 'backups'
    backup_root.mkdir(parents=True, exist_ok=True)
    stamp = business_now().strftime('%Y%m%d-%H%M%S+0800')
    with engine.begin() as connection:
        connection.execute(text("SET LOCAL lock_timeout='5s'"))
        connection.execute(text("SET LOCAL statement_timeout='120s'"))
        connection.execute(text('SELECT pg_advisory_xact_lock(646227451908632)'))
        db = Session(bind=connection)
        before = {}
        for model in (AnnotationChatMember, ChatProjectMemberPref, DiscussionMember):
            before[model.__tablename__] = [dict(row._mapping) for row in connection.execute(model.__table__.select())]
        backup = backup_root / f'chat-participants-{stamp}-{uuid4().hex}.json'
        with backup.open('x', encoding='utf-8') as handle:
            handle.write(json.dumps(before, default=str, ensure_ascii=False))
        result = apply_migration(db)
        print(json.dumps(dict(result=result, membership_backup=str(backup)), ensure_ascii=False))


if __name__ == '__main__':
    run()
