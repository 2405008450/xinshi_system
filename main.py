import datetime as dt
import os
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from database import engine, get_db
from manuscript_models import (
    ManuscriptArrangement,
    ManuscriptDeliveryMilestone,
    ManuscriptDispatch,
)
from models import (
    AppNotification,
    ChatProjectAttachment,
    ChatProjectEnabled,
    ChatProjectMention,
    ChatProjectMessage,
    ChatProjectMessageAttachment,
    ClientContact,
    Role,
    RolePermission,
    TranslatorSchedule,
)
from permission_registry import PERMISSION_CODES, SUPER_ROLE_NAMES
from routers import users, roles, translation_projects, user_roles, project_files, auth, clients, client_contacts, translators, workflow, schedule, leave, consultations, finance, sub_orders, notifications, project_chat, permissions, tasks, manuscript_arrangements
from task_models import DailyReport, DailyReportItem, NonProjectTask, NonProjectTaskEvent, NonProjectTaskRecurrence, WorkEntry
from workflow_models import (
    ProjectManagerHandoverItem,
    ProjectManagerHandoverRequest,
    WorkflowHandoverAttachment,
    WorkflowHandoverItem,
    WorkflowHandoverRequest,
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(roles.router)
app.include_router(translation_projects.router)
app.include_router(user_roles.router)
app.include_router(project_files.router)
app.include_router(clients.router)
app.include_router(client_contacts.router)
app.include_router(translators.router)
app.include_router(workflow.router)
app.include_router(schedule.router)
app.include_router(leave.router)
app.include_router(consultations.router)
app.include_router(finance.router)
app.include_router(sub_orders.router)
app.include_router(notifications.router)
app.include_router(project_chat.router)
app.include_router(permissions.router)
app.include_router(tasks.work_items_router)
app.include_router(tasks.tasks_router)
app.include_router(tasks.entries_router)
app.include_router(tasks.reports_router)
app.include_router(manuscript_arrangements.router)


PROJECT_FILE_PATH_COLUMN_STATEMENTS = (
    "ALTER TABLE project_file ADD COLUMN IF NOT EXISTS dispatch_path TEXT",
    "ALTER TABLE project_file ADD COLUMN IF NOT EXISTS translation_path TEXT",
    "ALTER TABLE project_file ADD COLUMN IF NOT EXISTS translator_return_path TEXT",
    "ALTER TABLE project_file ADD COLUMN IF NOT EXISTS client_delivery_path TEXT",
    "ALTER TABLE project_file ADD COLUMN IF NOT EXISTS project_feedback_path TEXT",
    "ALTER TABLE project_file ADD COLUMN IF NOT EXISTS feedback_delivery_path TEXT",
)
PROJECT_FILE_DETAIL_COLUMN_STATEMENTS = (
    "ALTER TABLE project_file ADD COLUMN IF NOT EXISTS translation_domain_level1 VARCHAR(255)",
    "ALTER TABLE project_file ADD COLUMN IF NOT EXISTS translation_domain_level2 VARCHAR(255)",
    "ALTER TABLE project_file ALTER COLUMN file_type TYPE VARCHAR(255)",
    "ALTER TABLE project_file ADD COLUMN IF NOT EXISTS file_type_secondary VARCHAR(255)",
    "ALTER TABLE project_file ADD COLUMN IF NOT EXISTS file_format VARCHAR(100)",
    "ALTER TABLE project_file ADD COLUMN IF NOT EXISTS file_attribute_level1 VARCHAR(255)",
    "ALTER TABLE project_file ADD COLUMN IF NOT EXISTS file_attribute_level2 VARCHAR(255)",
    "ALTER TABLE project_file ADD COLUMN IF NOT EXISTS file_attribute_level3 VARCHAR(255)",
    "ALTER TABLE project_file ADD COLUMN IF NOT EXISTS file_difficulty VARCHAR(100)",
)
CHAT_MESSAGE_COLUMN_STATEMENTS = (
    "ALTER TABLE chat_project_message ADD COLUMN IF NOT EXISTS message_type VARCHAR(30) NOT NULL DEFAULT 'user'",
    "ALTER TABLE chat_project_message ADD COLUMN IF NOT EXISTS content_json JSONB",
    "ALTER TABLE chat_project_message ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb",
)
TRANSLATION_PROJECT_COLUMN_STATEMENTS = (
    "ALTER TABLE translation_project ADD COLUMN IF NOT EXISTS major_project_manager_confirmation VARCHAR(255)",
    "ALTER TABLE translation_project ADD COLUMN IF NOT EXISTS reference_file_path_one VARCHAR(500)",
    "ALTER TABLE translation_project ADD COLUMN IF NOT EXISTS customer_order_no VARCHAR(100)",
    "ALTER TABLE translation_project ADD COLUMN IF NOT EXISTS service_content VARCHAR(255)",
    "ALTER TABLE translation_project ADD COLUMN IF NOT EXISTS project_manager_id UUID",
    "ALTER TABLE translation_project ADD COLUMN IF NOT EXISTS customer_word_count BIGINT",
    "ALTER TABLE translation_project ADD COLUMN IF NOT EXISTS customer_word_count_type VARCHAR(50)",
    "ALTER TABLE translation_project ADD COLUMN IF NOT EXISTS internal_word_count BIGINT",
    "ALTER TABLE translation_project ADD COLUMN IF NOT EXISTS internal_word_count_type VARCHAR(50)",
    "ALTER TABLE translation_project ADD COLUMN IF NOT EXISTS project_contract_type VARCHAR(100)",
    "ALTER TABLE translation_project ADD COLUMN IF NOT EXISTS project_contract_status VARCHAR(100)",
    "ALTER TABLE translation_project ADD COLUMN IF NOT EXISTS quotation_required BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE translation_project ADD COLUMN IF NOT EXISTS quotation_status VARCHAR(100)",
    "ALTER TABLE translation_project ADD COLUMN IF NOT EXISTS quotation_path TEXT",
    "ALTER TABLE translation_project ADD COLUMN IF NOT EXISTS customer_requirement_professional TEXT",
    "ALTER TABLE translation_project ADD COLUMN IF NOT EXISTS customer_requirement_special TEXT",
    "ALTER TABLE translation_project ALTER COLUMN language_pair TYPE VARCHAR(500)",
    "ALTER TABLE translation_project ADD COLUMN IF NOT EXISTS sub_client_id UUID",
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'fk_translation_project_sub_client'
        ) THEN
            ALTER TABLE translation_project
                ADD CONSTRAINT fk_translation_project_sub_client
                FOREIGN KEY (sub_client_id)
                REFERENCES sub_client(id)
                ON DELETE SET NULL;
        END IF;
    END
    $$
    """,
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'fk_translation_project_manager'
        ) THEN
            ALTER TABLE translation_project
                ADD CONSTRAINT fk_translation_project_manager
                FOREIGN KEY (project_manager_id)
                REFERENCES app_user(id)
                ON DELETE SET NULL;
        END IF;
    END
    $$
    """,
    "CREATE INDEX IF NOT EXISTS ix_translation_project_manager_id ON translation_project(project_manager_id)",
)
TRANSLATION_SUB_ORDER_COLUMN_STATEMENTS = (
    "ALTER TABLE translation_sub_order ADD COLUMN IF NOT EXISTS customer_word_count BIGINT",
    "ALTER TABLE translation_sub_order ADD COLUMN IF NOT EXISTS customer_word_count_type VARCHAR(50)",
    "ALTER TABLE translation_sub_order ADD COLUMN IF NOT EXISTS internal_word_count BIGINT",
    "ALTER TABLE translation_sub_order ADD COLUMN IF NOT EXISTS internal_word_count_type VARCHAR(50)",
    "ALTER TABLE translation_sub_order ALTER COLUMN language_pair TYPE VARCHAR(500)",
)
MANUSCRIPT_DISPATCH_COLUMN_STATEMENTS = (
    "ALTER TABLE manuscript_dispatch ADD COLUMN IF NOT EXISTS previous_order_status VARCHAR(50)",
)
MANUSCRIPT_ARRANGEMENT_COLUMN_STATEMENTS = (
    "ALTER TABLE manuscript_arrangement ADD COLUMN IF NOT EXISTS dispatch_id UUID",
    "ALTER TABLE manuscript_arrangement ADD COLUMN IF NOT EXISTS planned_word_count BIGINT",
    "ALTER TABLE manuscript_arrangement ADD COLUMN IF NOT EXISTS actual_word_count BIGINT",
    "ALTER TABLE manuscript_arrangement ADD COLUMN IF NOT EXISTS word_count_type VARCHAR(50)",
    "ALTER TABLE manuscript_arrangement ADD COLUMN IF NOT EXISTS translation_scope TEXT",
    "ALTER TABLE manuscript_arrangement ADD COLUMN IF NOT EXISTS settlement_method VARCHAR(30)",
    "ALTER TABLE manuscript_arrangement ADD COLUMN IF NOT EXISTS custom_settlement_method VARCHAR(100)",
    "ALTER TABLE manuscript_arrangement ADD COLUMN IF NOT EXISTS translator_unit_price NUMERIC(14, 4)",
    "ALTER TABLE manuscript_arrangement ADD COLUMN IF NOT EXISTS translator_total_price NUMERIC(14, 2)",
    "ALTER TABLE manuscript_arrangement ADD COLUMN IF NOT EXISTS send_attempted_at TIMESTAMP",
    "ALTER TABLE manuscript_arrangement ADD COLUMN IF NOT EXISTS delivery_recipient VARCHAR(255)",
    "ALTER TABLE manuscript_arrangement ADD COLUMN IF NOT EXISTS delivery_mode VARCHAR(20)",
    "ALTER TABLE manuscript_arrangement ADD COLUMN IF NOT EXISTS smtp_message_id VARCHAR(255)",
    "ALTER TABLE manuscript_arrangement ADD COLUMN IF NOT EXISTS send_error TEXT",
)


def ensure_project_file_path_columns():
    inspector = inspect(engine)
    if "project_file" not in inspector.get_table_names():
        return

    with engine.begin() as conn:
        for statement in PROJECT_FILE_PATH_COLUMN_STATEMENTS:
            conn.execute(text(statement))


def ensure_project_file_detail_columns():
    """兼容尚未单独执行文件详情 SQL 迁移的已有部署。"""
    inspector = inspect(engine)
    if "project_file" not in inspector.get_table_names():
        return

    with engine.begin() as conn:
        for statement in PROJECT_FILE_DETAIL_COLUMN_STATEMENTS:
            conn.execute(text(statement))


def ensure_chat_message_columns():
    inspector = inspect(engine)
    if "chat_project_message" not in inspector.get_table_names():
        return
    with engine.begin() as conn:
        for statement in CHAT_MESSAGE_COLUMN_STATEMENTS:
            conn.execute(text(statement))


def ensure_translation_project_columns():
    """兼容尚未单独执行 SQL 迁移的已有部署。"""
    inspector = inspect(engine)
    if "translation_project" not in inspector.get_table_names():
        return
    with engine.begin() as conn:
        for statement in TRANSLATION_PROJECT_COLUMN_STATEMENTS:
            conn.execute(text(statement))
        if "translation_sub_order" in inspector.get_table_names():
            for statement in TRANSLATION_SUB_ORDER_COLUMN_STATEMENTS:
                conn.execute(text(statement))


def ensure_manuscript_arrangement_columns():
    """补齐已有稿件安排表的状态快照及邮件投递审计字段。"""
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    with engine.begin() as conn:
        if "manuscript_dispatch" in table_names:
            for statement in MANUSCRIPT_DISPATCH_COLUMN_STATEMENTS:
                conn.execute(text(statement))
        if "manuscript_arrangement" in table_names:
            for statement in MANUSCRIPT_ARRANGEMENT_COLUMN_STATEMENTS:
                conn.execute(text(statement))


def backfill_manuscript_dispatches():
    """把旧的一译员一记录数据无损转换为单译员批次。"""
    inspector = inspect(engine)
    required_tables = {
        "manuscript_dispatch",
        "manuscript_arrangement",
        "manuscript_delivery_milestone",
    }
    if not required_tables.issubset(set(inspector.get_table_names())):
        return
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO manuscript_dispatch (
                id,
                entity_type,
                translation_project_id,
                sub_order_id,
                order_no_snapshot,
                project_name_snapshot,
                status,
                remarks,
                created_by,
                created_by_name,
                created_at,
                updated_at,
                confirmed_at,
                cancelled_at
            )
            SELECT
                ma.id,
                ma.entity_type,
                ma.translation_project_id,
                ma.sub_order_id,
                ma.order_no_snapshot,
                ma.project_name_snapshot,
                CASE
                    WHEN ma.status = 'sent' THEN 'sent'
                    WHEN ma.status = 'cancelled' THEN 'cancelled'
                    WHEN ma.status = 'draft' THEN 'draft'
                    ELSE 'ready'
                END,
                NULL,
                ma.created_by,
                ma.created_by_name,
                ma.created_at,
                ma.updated_at,
                CASE
                    WHEN ma.status = 'draft' THEN NULL
                    ELSE COALESCE(ma.updated_at, ma.created_at)
                END,
                CASE
                    WHEN ma.status = 'cancelled' THEN COALESCE(ma.updated_at, ma.created_at)
                    ELSE NULL
                END
            FROM manuscript_arrangement ma
            WHERE ma.dispatch_id IS NULL
            ON CONFLICT (id) DO NOTHING
        """))
        conn.execute(text("""
            UPDATE manuscript_arrangement
            SET dispatch_id = id
            WHERE dispatch_id IS NULL
        """))
        conn.execute(text("""
            INSERT INTO manuscript_delivery_milestone (
                arrangement_id,
                milestone_type,
                name,
                sequence_no,
                planned_at
            )
            SELECT
                ma.id,
                'final',
                '全稿',
                1,
                ma.planned_delivery_at
            FROM manuscript_arrangement ma
            WHERE ma.planned_delivery_at IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM manuscript_delivery_milestone mdm
                  WHERE mdm.arrangement_id = ma.id
                    AND mdm.milestone_type = 'final'
              )
        """))


def ensure_manuscript_constraints():
    """为通过启动兼容逻辑升级的旧表补齐关键约束。"""
    inspector = inspect(engine)
    if "manuscript_arrangement" not in inspector.get_table_names():
        return
    with engine.begin() as conn:
        conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'fk_manuscript_arrangement_dispatch'
                ) THEN
                    ALTER TABLE manuscript_arrangement
                        ADD CONSTRAINT fk_manuscript_arrangement_dispatch
                        FOREIGN KEY (dispatch_id)
                        REFERENCES manuscript_dispatch(id) ON DELETE CASCADE;
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'uq_manuscript_arrangement_dispatch_translator'
                ) THEN
                    ALTER TABLE manuscript_arrangement
                        ADD CONSTRAINT uq_manuscript_arrangement_dispatch_translator
                        UNIQUE (dispatch_id, translator_id);
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'ck_manuscript_arrangement_planned_words'
                ) THEN
                    ALTER TABLE manuscript_arrangement
                        ADD CONSTRAINT ck_manuscript_arrangement_planned_words
                        CHECK (planned_word_count IS NULL OR planned_word_count >= 0);
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'ck_manuscript_arrangement_actual_words'
                ) THEN
                    ALTER TABLE manuscript_arrangement
                        ADD CONSTRAINT ck_manuscript_arrangement_actual_words
                        CHECK (actual_word_count IS NULL OR actual_word_count >= 0);
                END IF;
            END $$;
        """))
        conn.execute(text("""
            ALTER TABLE manuscript_arrangement
            ALTER COLUMN dispatch_id SET NOT NULL
        """))


def cleanup_orphan_chat_attachments():
    cutoff = dt.datetime.utcnow() - dt.timedelta(hours=24)
    upload_dir = Path(os.getenv('CHAT_UPLOAD_DIR', 'data/chat_uploads')).resolve()
    with Session(engine) as db:
        orphans = (
            db.query(ChatProjectAttachment)
            .outerjoin(
                ChatProjectMessageAttachment,
                ChatProjectMessageAttachment.attachment_id == ChatProjectAttachment.id,
            )
            .outerjoin(
                WorkflowHandoverAttachment,
                WorkflowHandoverAttachment.attachment_id == ChatProjectAttachment.id,
            )
            .filter(
                ChatProjectMessageAttachment.id == None,
                WorkflowHandoverAttachment.id == None,
                ChatProjectAttachment.created_at < cutoff,
            )
            .all()
        )
        for attachment in orphans:
            (upload_dir / attachment.storage_name).unlink(missing_ok=True)
            db.delete(attachment)
        if orphans:
            db.commit()


def ensure_role_permission_table():
    """首次引入 RBAC 时保留普通角色原有业务访问能力，之后由管理员收紧。"""
    inspector = inspect(engine)
    table_existed = "role_permission" in inspector.get_table_names()
    RolePermission.__table__.create(bind=engine, checkfirst=True)
    if table_existed:
        return

    legacy_permissions = sorted(
        code for code in PERMISSION_CODES if not code.startswith("system:")
    )
    with Session(engine) as db:
        roles = db.query(Role).filter(~Role.role_name.in_(SUPER_ROLE_NAMES)).all()
        for role in roles:
            db.add_all(
                RolePermission(role_id=role.id, permission_code=code)
                for code in legacy_permissions
            )
        db.commit()


def ensure_personal_task_permissions():
    """为普通角色开放个人任务/日报，项目经理额外获得分配权限。"""
    default_codes = ("tasks:read", "tasks:self_write", "reports:read", "reports:export")
    with Session(engine) as db:
        roles = db.query(Role).filter(~Role.role_name.in_(SUPER_ROLE_NAMES)).all()
        existing = {
            (row.role_id, row.permission_code)
            for row in db.query(RolePermission).filter(
                RolePermission.permission_code.in_((*default_codes, "tasks:assign"))
            )
        }
        for role in roles:
            for code in default_codes:
                if (role.id, code) not in existing:
                    db.add(RolePermission(role_id=role.id, permission_code=code))
            if role.role_name == "项目经理" and (role.id, "tasks:assign") not in existing:
                db.add(RolePermission(role_id=role.id, permission_code="tasks:assign"))
        db.commit()


@app.on_event("startup")
def ensure_runtime_tables():
    ClientContact.__table__.create(bind=engine, checkfirst=True)
    AppNotification.__table__.create(bind=engine, checkfirst=True)
    ChatProjectEnabled.__table__.create(bind=engine, checkfirst=True)
    ChatProjectMessage.__table__.create(bind=engine, checkfirst=True)
    ChatProjectMention.__table__.create(bind=engine, checkfirst=True)
    ensure_chat_message_columns()
    ChatProjectAttachment.__table__.create(bind=engine, checkfirst=True)
    ChatProjectMessageAttachment.__table__.create(bind=engine, checkfirst=True)
    WorkflowHandoverRequest.__table__.create(bind=engine, checkfirst=True)
    WorkflowHandoverItem.__table__.create(bind=engine, checkfirst=True)
    WorkflowHandoverAttachment.__table__.create(bind=engine, checkfirst=True)
    NonProjectTaskRecurrence.__table__.create(bind=engine, checkfirst=True)
    NonProjectTask.__table__.create(bind=engine, checkfirst=True)
    NonProjectTaskEvent.__table__.create(bind=engine, checkfirst=True)
    WorkEntry.__table__.create(bind=engine, checkfirst=True)
    DailyReport.__table__.create(bind=engine, checkfirst=True)
    DailyReportItem.__table__.create(bind=engine, checkfirst=True)
    ManuscriptDispatch.__table__.create(bind=engine, checkfirst=True)
    ManuscriptArrangement.__table__.create(bind=engine, checkfirst=True)
    ensure_manuscript_arrangement_columns()
    ManuscriptDeliveryMilestone.__table__.create(bind=engine, checkfirst=True)
    backfill_manuscript_dispatches()
    ensure_manuscript_constraints()
    cleanup_orphan_chat_attachments()
    TranslatorSchedule.__table__.create(bind=engine, checkfirst=True)
    ensure_role_permission_table()
    ensure_personal_task_permissions()
    ensure_project_file_path_columns()
    ensure_project_file_detail_columns()
    ensure_translation_project_columns()
    ProjectManagerHandoverRequest.__table__.create(bind=engine, checkfirst=True)
    ProjectManagerHandoverItem.__table__.create(bind=engine, checkfirst=True)


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}


@app.get("/health/db")
def db_healthcheck(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}
