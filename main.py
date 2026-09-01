import datetime as dt
import os
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from database import engine, get_db
from auth_security import cleanup_login_security_data
from auth_security_models import (
    LoginCaptchaChallenge,
    LoginSecurityEvent,
    LoginThrottleState,
    RevokedAccessToken,
)
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
    ProjectRoleAssignment,
    Role,
    RolePermission,
    TranslatorSchedule,
)
from concurrency import StaleUpdateError
from permission_registry import PERMISSION_CODES, SUPER_ROLE_NAMES
from routers import users, roles, translation_projects, interpretation_projects, annotation_projects, annotation_ops, resource_requests, recruitment_projects, project_languages, user_roles, project_files, auth, clients, client_contacts, translators, talents, talent_options, workflow, schedule, leave, consultations, finance, sub_orders, notifications, project_chat, permissions, tasks, manuscript_arrangements, word_counts
from interpretation_models import (
    InterpretationLanguage,
    InterpretationProject,
    InterpretationProjectDirectionExtraLanguage,
    InterpretationProjectInterpreter,
    InterpretationProjectLanguageDirection,
    InterpretationProjectTimeRange,
)
from interpretation_service import ensure_default_interpretation_languages
from annotation_models import (
    AnnotationProject,
    AnnotationProjectAssignee,
    AnnotationProjectLanguageItem,
    AnnotationProjectPriceItem,
)
from annotation_service import (
    ensure_translation_languages_in_catalog,
    migrate_legacy_annotation_projects,
)
from recruitment_models import (
    RecruitmentCandidate,
    RecruitmentCandidateCommunication,
    RecruitmentCandidateInterview,
    RecruitmentProject,
    RecruitmentProjectLanguageDirection,
    RecruitmentProjectProgress,
    RecruitmentResumeSource,
)
from resource_models import (
    AnnotationProfile,
    InterpretationProfile,
    ResourceCapability,
    ResourceCareerProfile,
    ResourcePerson,
    WrittenTranslationProfile,
)
from resource_service import backfill_resource_people
from recruitment_service import ensure_default_resume_sources
from task_models import DailyReport, DailyReportItem, NonProjectTask, NonProjectTaskEvent, NonProjectTaskRecurrence, WorkEntry
from workflow_models import (
    ProjectWorkbenchResponsibility,
    ProjectManagerHandoverItem,
    ProjectManagerHandoverRequest,
    WorkflowHandoverAttachment,
    WorkflowHandoverItem,
    WorkflowHandoverRequest,
)
from word_count_models import WordCountMetric
from business_mail_models import (
    BusinessMail, BusinessMailAttempt, BusinessMailRecipient,
    MailRecipientGroup, MailRecipientGroupMember,
    ProjectMailPolicy, ProjectMailPolicyGroup,
)
from daily_report_mail_models import (
    DailyReportMailAttempt,
    DailyReportMailDelivery,
    DailyReportMailPolicy,
    DailyReportMailPolicyGroup,
    DailyReportMailRecipient,
    UserMailAccount,
)
from annotation_ops_models import (
    AnnotationAccountAssignment,
    AnnotationAccountAssignmentImage,
    AnnotationAccountAssignmentLanguage,
    AnnotationAccountPasswordHistory,
    AnnotationAssigneeRate,
    AnnotationCustomFieldDefinition,
    AnnotationCustomFieldImage,
    AnnotationCredentialAccessLog,
    AnnotationPlatform,
    AnnotationPlatformAccount,
    AnnotationProjectStatusHistory,
    AnnotationTrialRecord,
)
from annotation_custom_field_image_service import cleanup_orphan_custom_field_images
from mail_inline_image_models import MailInlineImage, MailInlineImageBinding
from mail_inline_image_service import cleanup_orphan_inline_images
from resource_request_models import (
    ResourceRequest,
    ResourceRequestItem,
    ResourceRequestItemExtraLanguage,
    ResourceRequestProgressLog,
)
from routers import business_mails, mail_inline_images

app = FastAPI()


def _configured_cors_origins() -> list[str]:
    """只允许显式配置的浏览器来源；生产环境通常通过同源 /api 访问。"""
    return [
        origin.strip()
        for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
        if origin.strip()
    ]


@app.exception_handler(StaleUpdateError)
async def stale_update_handler(_request: Request, exc: StaleUpdateError):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


app.add_middleware(
    CORSMiddleware,
    allow_origins=_configured_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "Idempotency-Key"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    )
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
    )
    return response

# 注册路由
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(roles.router)
app.include_router(translation_projects.router)
app.include_router(interpretation_projects.router)
app.include_router(annotation_projects.router)
app.include_router(annotation_ops.router)
app.include_router(resource_requests.router)
app.include_router(recruitment_projects.router)
app.include_router(project_languages.router)
app.include_router(user_roles.router)
app.include_router(project_files.router)
app.include_router(clients.router)
app.include_router(client_contacts.router)
app.include_router(translators.router)
app.include_router(talents.router)
app.include_router(talents.recruitment_router)
app.include_router(talent_options.router)
app.include_router(workflow.router)
app.include_router(schedule.workbench_router)
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
app.include_router(word_counts.router)
app.include_router(business_mails.settings_router)
app.include_router(business_mails.mail_router)
app.include_router(mail_inline_images.router)


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
    "ALTER TABLE translation_project ADD COLUMN IF NOT EXISTS email_subject_preview TEXT",
    "ALTER TABLE translation_project ADD COLUMN IF NOT EXISTS service_content VARCHAR(255)",
    "ALTER TABLE translation_project ADD COLUMN IF NOT EXISTS project_manager_id UUID",
    "ALTER TABLE translation_project ADD COLUMN IF NOT EXISTS project_contract_type VARCHAR(100)",
    "ALTER TABLE translation_project ADD COLUMN IF NOT EXISTS project_contract_status VARCHAR(100)",
    "ALTER TABLE translation_project ADD COLUMN IF NOT EXISTS quotation_required BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE translation_project ADD COLUMN IF NOT EXISTS quotation_status VARCHAR(100)",
    "ALTER TABLE translation_project ADD COLUMN IF NOT EXISTS quotation_path TEXT",
    "ALTER TABLE translation_project ADD COLUMN IF NOT EXISTS customer_requirement_professional TEXT",
    "ALTER TABLE translation_project ADD COLUMN IF NOT EXISTS customer_requirement_special TEXT",
    "ALTER TABLE translation_project ALTER COLUMN language_pair TYPE VARCHAR(500)",
    "ALTER TABLE translation_project ADD COLUMN IF NOT EXISTS sub_client_id UUID",
    "ALTER TABLE translation_project ADD COLUMN IF NOT EXISTS annotation_project_id UUID",
    "ALTER TABLE translation_project ADD COLUMN IF NOT EXISTS annotation_migrated_at TIMESTAMP",
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
    "ALTER TABLE translation_sub_order ALTER COLUMN language_pair TYPE VARCHAR(500)",
)
INTERPRETATION_REQUIREMENT_COLUMN_STATEMENTS = (
    "ALTER TABLE translator ADD COLUMN IF NOT EXISTS interpretation_level VARCHAR(20)",
    "ALTER TABLE interpretation_project ADD COLUMN IF NOT EXISTS required_interpreter_count INTEGER",
    "ALTER TABLE interpretation_project ADD COLUMN IF NOT EXISTS required_interpreter_gender VARCHAR(20)",
    "ALTER TABLE interpretation_project ADD COLUMN IF NOT EXISTS required_interpretation_level VARCHAR(20)",
    "ALTER TABLE interpretation_project ADD COLUMN IF NOT EXISTS interpreter_special_requirements TEXT",
    "ALTER TABLE interpretation_project ADD COLUMN IF NOT EXISTS interpreter_height_requirement VARCHAR(100)",
    "ALTER TABLE interpretation_project ADD COLUMN IF NOT EXISTS interpreter_appearance_requirement VARCHAR(255)",
    "ALTER TABLE interpretation_project ADD COLUMN IF NOT EXISTS interpreter_dress_requirement VARCHAR(255)",
)
ANNOTATION_PROJECT_COLUMN_STATEMENTS = (
    "ALTER TABLE annotation_project ADD COLUMN IF NOT EXISTS email_subject_preview VARCHAR(1000)",
    "ALTER TABLE annotation_project ADD COLUMN IF NOT EXISTS language_region VARCHAR(255)",
    "ALTER TABLE annotation_project ADD COLUMN IF NOT EXISTS status_effective_on DATE NOT NULL DEFAULT CURRENT_DATE",
    "ALTER TABLE annotation_project ADD COLUMN IF NOT EXISTS custom_values JSONB NOT NULL DEFAULT '{}'::jsonb",
    "UPDATE annotation_project SET project_status=CASE project_status WHEN 'pending_confirmation' THEN 'initial_consultation' WHEN 'trial' THEN 'trial_in_progress' WHEN 'in_progress' THEN 'project_in_progress' ELSE project_status END WHERE project_status IN ('pending_confirmation','trial','in_progress')",
    "ALTER TABLE annotation_project ALTER COLUMN project_status SET DEFAULT 'initial_consultation'",
    """
    DO $$ BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_annotation_project_status') THEN
        ALTER TABLE annotation_project ADD CONSTRAINT ck_annotation_project_status CHECK(project_status IN ('initial_consultation','consultation_no_result','resource_sourcing','resource_sourcing_cancelled','trial_preparation','trial_in_progress','trial_passed','trial_failed','trial_partially_passed','project_in_progress','sent_to_client','client_feedback','cancelled','partially_cancelled'));
      END IF;
    END $$
    """,
)
ANNOTATION_ASSIGNEE_COLUMN_STATEMENTS = (
    "ALTER TABLE annotation_project_assignee ADD COLUMN IF NOT EXISTS assignment_role VARCHAR(30) NOT NULL DEFAULT 'annotator'",
    "ALTER TABLE annotation_project_assignee ADD COLUMN IF NOT EXISTS language_item_id UUID",
    "ALTER TABLE annotation_project_assignee ADD COLUMN IF NOT EXISTS audio_duration_value NUMERIC(18,3)",
    "ALTER TABLE annotation_project_assignee ADD COLUMN IF NOT EXISTS audio_duration_unit VARCHAR(20)",
    "ALTER TABLE annotation_project_assignee ADD COLUMN IF NOT EXISTS custom_values JSONB NOT NULL DEFAULT '{}'::jsonb",
    "ALTER TABLE annotation_project_assignee ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
    "ALTER TABLE annotation_project_assignee ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
    "ALTER TABLE annotation_project_assignee DROP CONSTRAINT IF EXISTS uq_annotation_project_assignee",
    """
    DO $$ BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_annotation_assignee_language_item') THEN
        ALTER TABLE annotation_project_assignee ADD CONSTRAINT fk_annotation_assignee_language_item FOREIGN KEY(language_item_id) REFERENCES annotation_project_language_item(id) ON DELETE RESTRICT;
      END IF;
      IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_annotation_assignee_role') THEN
        ALTER TABLE annotation_project_assignee ADD CONSTRAINT ck_annotation_assignee_role CHECK(assignment_role IN ('annotator','quality_inspector'));
      END IF;
      IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_annotation_assignee_audio_duration_value') THEN
        ALTER TABLE annotation_project_assignee ADD CONSTRAINT ck_annotation_assignee_audio_duration_value CHECK(audio_duration_value IS NULL OR audio_duration_value >= 0);
      END IF;
      IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_annotation_assignee_audio_duration_unit') THEN
        ALTER TABLE annotation_project_assignee ADD CONSTRAINT ck_annotation_assignee_audio_duration_unit CHECK(audio_duration_unit IS NULL OR audio_duration_unit IN ('second','minute','hour'));
      END IF;
    END $$
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_annotation_project_assignee_scope ON annotation_project_assignee(project_id, person_id, language_item_id, assignment_role) NULLS NOT DISTINCT",
)
RESOURCE_COMPAT_COLUMN_STATEMENTS = (
    "ALTER TABLE translator ADD COLUMN IF NOT EXISTS resource_person_id UUID",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_translator_resource_person ON translator(resource_person_id) WHERE resource_person_id IS NOT NULL",
    "ALTER TABLE recruitment_candidate ADD COLUMN IF NOT EXISTS person_id UUID",
    "CREATE INDEX IF NOT EXISTS ix_recruitment_candidate_person ON recruitment_candidate(person_id)",
    """
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_translator_resource_person') THEN
            ALTER TABLE translator ADD CONSTRAINT fk_translator_resource_person
                FOREIGN KEY (resource_person_id) REFERENCES resource_person(id) ON DELETE SET NULL;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_recruitment_candidate_person') THEN
            ALTER TABLE recruitment_candidate ADD CONSTRAINT fk_recruitment_candidate_person
                FOREIGN KEY (person_id) REFERENCES resource_person(id) ON DELETE RESTRICT;
        END IF;
    END
    $$
    """,
)
RESOURCE_REQUEST_LIFECYCLE_STATEMENTS = (
    "ALTER TABLE resource_request ADD COLUMN IF NOT EXISTS demand_status VARCHAR(30) NOT NULL DEFAULT 'confirmed'",
    "UPDATE resource_request SET demand_status=CASE WHEN request_status='cancelled' THEN 'cancelled' ELSE 'confirmed' END WHERE demand_status IS NULL OR demand_status NOT IN ('draft','confirmed','cancelled')",
    """
    DO $$ BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_resource_request_demand_status') THEN
        ALTER TABLE resource_request ADD CONSTRAINT ck_resource_request_demand_status CHECK(demand_status IN ('draft','confirmed','cancelled'));
      END IF;
    END $$
    """,
    "CREATE INDEX IF NOT EXISTS ix_resource_request_demand_status ON resource_request(demand_status, updated_at DESC)",
)
INTERPRETATION_LANGUAGE_COLUMN_STATEMENTS = (
    "ALTER TABLE interpretation_language ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE",
    "ALTER TABLE interpretation_language ADD COLUMN IF NOT EXISTS updated_by UUID",
    "ALTER TABLE interpretation_language ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'fk_interpretation_language_updater'
        ) THEN
            ALTER TABLE interpretation_language
                ADD CONSTRAINT fk_interpretation_language_updater
                FOREIGN KEY (updated_by)
                REFERENCES app_user(id)
                ON DELETE SET NULL;
        END IF;
    END
    $$
    """,
    "CREATE INDEX IF NOT EXISTS ix_interpretation_language_active ON interpretation_language(is_active)",
)
RECRUITMENT_PROJECT_COLUMN_STATEMENTS = (
    "ALTER TABLE recruitment_project ADD COLUMN IF NOT EXISTS position_title VARCHAR(255)",
    "ALTER TABLE recruitment_project ADD COLUMN IF NOT EXISTS headcount_min INTEGER",
    "ALTER TABLE recruitment_project ADD COLUMN IF NOT EXISTS headcount_max INTEGER",
    "ALTER TABLE recruitment_project ADD COLUMN IF NOT EXISTS client_manager_id UUID REFERENCES app_user(id) ON DELETE SET NULL",
    "ALTER TABLE recruitment_project ADD COLUMN IF NOT EXISTS client_manager_name_snapshot VARCHAR(255)",
    "ALTER TABLE recruitment_project ADD COLUMN IF NOT EXISTS target_onboard_type VARCHAR(20) NOT NULL DEFAULT 'date'",
    "ALTER TABLE recruitment_project ADD COLUMN IF NOT EXISTS target_onboard_date DATE",
    "ALTER TABLE recruitment_project ADD COLUMN IF NOT EXISTS employment_start DATE",
    "ALTER TABLE recruitment_project ADD COLUMN IF NOT EXISTS employment_end DATE",
    "ALTER TABLE recruitment_project ADD COLUMN IF NOT EXISTS service_fee_type VARCHAR(30)",
    "ALTER TABLE recruitment_project ADD COLUMN IF NOT EXISTS service_fee_currency VARCHAR(10) DEFAULT 'CNY'",
    "ALTER TABLE recruitment_project ADD COLUMN IF NOT EXISTS service_fee_amount NUMERIC(14, 2)",
    "ALTER TABLE recruitment_project ADD COLUMN IF NOT EXISTS service_fee_rate NUMERIC(7, 4)",
    "ALTER TABLE recruitment_project ADD COLUMN IF NOT EXISTS service_fee_note TEXT",
    "ALTER TABLE recruitment_project ADD COLUMN IF NOT EXISTS project_path TEXT",
)
RECRUITMENT_CANDIDATE_COLUMN_STATEMENTS = (
    "ALTER TABLE recruitment_candidate ADD COLUMN IF NOT EXISTS contact_info VARCHAR(500)",
    "ALTER TABLE recruitment_candidate ADD COLUMN IF NOT EXISTS stage VARCHAR(50) NOT NULL DEFAULT 'screening'",
    "ALTER TABLE recruitment_candidate ADD COLUMN IF NOT EXISTS recommended_at TIMESTAMP",
    "ALTER TABLE recruitment_candidate ADD COLUMN IF NOT EXISTS interview_at TIMESTAMP",
    "ALTER TABLE recruitment_candidate ADD COLUMN IF NOT EXISTS offer_at TIMESTAMP",
    "ALTER TABLE recruitment_candidate ADD COLUMN IF NOT EXISTS planned_onboard_date DATE",
    "ALTER TABLE recruitment_candidate ADD COLUMN IF NOT EXISTS actual_onboard_date DATE",
    "ALTER TABLE recruitment_candidate ADD COLUMN IF NOT EXISTS owner_id UUID REFERENCES app_user(id) ON DELETE SET NULL",
    "ALTER TABLE recruitment_candidate ADD COLUMN IF NOT EXISTS next_follow_up_at TIMESTAMP",
    "ALTER TABLE recruitment_candidate ADD COLUMN IF NOT EXISTS remarks TEXT",
    "ALTER TABLE recruitment_candidate ADD COLUMN IF NOT EXISTS resume_source_id UUID REFERENCES recruitment_resume_source(id) ON DELETE SET NULL",
    "ALTER TABLE recruitment_candidate ADD COLUMN IF NOT EXISTS first_interview_date DATE",
    "ALTER TABLE recruitment_candidate ADD COLUMN IF NOT EXISTS first_interview_details TEXT",
    "ALTER TABLE recruitment_candidate ADD COLUMN IF NOT EXISTS second_interview_date DATE",
    "ALTER TABLE recruitment_candidate ADD COLUMN IF NOT EXISTS second_interview_details TEXT",
)
RECRUITMENT_COMMUNICATION_COLUMN_STATEMENTS = (
    "ALTER TABLE recruitment_candidate_communication ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
    "ALTER TABLE recruitment_candidate_communication ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
    "CREATE INDEX IF NOT EXISTS ix_recruitment_candidate_communication_candidate ON recruitment_candidate_communication(candidate_id)",
)
MANUSCRIPT_DISPATCH_COLUMN_STATEMENTS = (
    "ALTER TABLE manuscript_dispatch ADD COLUMN IF NOT EXISTS previous_order_status VARCHAR(50)",
)
MANUSCRIPT_ARRANGEMENT_COLUMN_STATEMENTS = (
    "ALTER TABLE manuscript_arrangement ADD COLUMN IF NOT EXISTS dispatch_id UUID",
    "ALTER TABLE manuscript_arrangement ADD COLUMN IF NOT EXISTS translation_scope TEXT",
    "ALTER TABLE manuscript_arrangement ADD COLUMN IF NOT EXISTS settlement_method VARCHAR(100)",
    "ALTER TABLE manuscript_arrangement ALTER COLUMN settlement_method TYPE VARCHAR(100)",
    "ALTER TABLE manuscript_arrangement ADD COLUMN IF NOT EXISTS custom_settlement_method VARCHAR(100)",
    "ALTER TABLE manuscript_arrangement ADD COLUMN IF NOT EXISTS translator_pricing_method VARCHAR(100)",
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


def ensure_interpretation_requirement_columns():
    """补齐译员口译水平和口译项目译员要求字段。"""
    table_names = set(inspect(engine).get_table_names())
    if not {"translator", "interpretation_project"}.issubset(table_names):
        return
    with engine.begin() as conn:
        for statement in INTERPRETATION_REQUIREMENT_COLUMN_STATEMENTS:
            conn.execute(text(statement))


def ensure_interpretation_language_columns():
    """补齐自定义口译语种的启停与修改审计字段。"""
    if "interpretation_language" not in inspect(engine).get_table_names():
        return
    with engine.begin() as conn:
        for statement in INTERPRETATION_LANGUAGE_COLUMN_STATEMENTS:
            conn.execute(text(statement))


def ensure_annotation_project_columns():
    """兼容尚未单独执行标注项目邮件主题迁移的已有部署。"""
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "annotation_project" not in table_names:
        return
    with engine.begin() as conn:
        for statement in ANNOTATION_PROJECT_COLUMN_STATEMENTS:
            conn.execute(text(statement))
        if "annotation_project_price_item" in table_names:
            conn.execute(text("ALTER TABLE annotation_project_price_item ALTER COLUMN currency DROP NOT NULL"))
            conn.execute(text("ALTER TABLE annotation_project_price_item ALTER COLUMN currency DROP DEFAULT"))
            conn.execute(text("UPDATE annotation_project_price_item SET currency = NULL WHERE currency = 'CNY'"))


def ensure_annotation_assignee_columns():
    """补齐正式标注安排第三阶段字段，并替换旧唯一约束。"""
    if "annotation_project_assignee" not in inspect(engine).get_table_names():
        return
    with engine.begin() as conn:
        for statement in ANNOTATION_ASSIGNEE_COLUMN_STATEMENTS:
            conn.execute(text(statement))


def ensure_annotation_status_history_seed():
    """为升级前已有项目补齐首条状态履历。"""
    required = {"annotation_project", "annotation_project_status_history"}
    if not required.issubset(set(inspect(engine).get_table_names())):
        return
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO annotation_project_status_history
                (project_id, from_status, to_status, effective_on, changed_by, changed_at)
            SELECT p.id, NULL, p.project_status,
                   COALESCE(p.status_effective_on, p.created_at::date),
                   p.created_by, p.created_at
            FROM annotation_project p
            WHERE NOT EXISTS (
                SELECT 1 FROM annotation_project_status_history h
                WHERE h.project_id = p.id
            )
        """))


def ensure_annotation_custom_field_scope_constraint():
    """确保动态字段作用域规则在数据库层同样生效。"""
    if "annotation_custom_field_definition" not in inspect(engine).get_table_names():
        return
    with engine.begin() as conn:
        conn.execute(text("""
            DO $$ BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname='ck_annotation_custom_field_scope'
              ) THEN
                ALTER TABLE annotation_custom_field_definition
                  ADD CONSTRAINT ck_annotation_custom_field_scope CHECK(
                    (table_code IN ('project','account') AND project_id IS NULL) OR
                    (table_code IN ('trial','assignment','account_assignment') AND project_id IS NOT NULL)
                  );
              END IF;
            END $$
        """))


def ensure_annotation_custom_field_type_constraint():
    """为已有数据库开放仅限项目账号表使用的图片字段类型。"""
    if "annotation_custom_field_definition" not in inspect(engine).get_table_names():
        return
    with engine.begin() as conn:
        conn.execute(text("""
            ALTER TABLE annotation_custom_field_definition
              DROP CONSTRAINT IF EXISTS ck_annotation_custom_field_type;
            ALTER TABLE annotation_custom_field_definition
              ADD CONSTRAINT ck_annotation_custom_field_type CHECK (
                data_type IN ('text','number','date','datetime','boolean','single_select','multi_select','url')
                OR (data_type = 'image' AND table_code = 'account_assignment')
              )
        """))


def ensure_resource_request_view():
    """创建资源需求统一展示视图。"""
    required = {"resource_request", "annotation_project", "recruitment_project", "interpretation_project", "translation_project"}
    if not required.issubset(set(inspect(engine).get_table_names())):
        return
    with engine.begin() as conn:
        # 视图中的 r.* 会在创建时展开；主表增加列后 CREATE OR REPLACE 无法在
        # 中间插入新列，因此先删除再创建，确保展示视图与主表字段同步。
        conn.execute(text("DROP VIEW IF EXISTS v_resource_request_display"))
        conn.execute(text("""
            CREATE VIEW v_resource_request_display AS
            SELECT r.*,
              COALESCE(ap.project_status, rp.project_status, ip.project_status, tp.project_status) AS current_project_status,
              COALESCE(ap.order_no, rp.order_no, ip.order_no, tp.order_no) AS current_order_no,
              COALESCE(ap.project_name, rp.project_name, ip.project_name, tp.project_name, r.other_source_name) AS current_project_name
            FROM resource_request r
            LEFT JOIN annotation_project ap ON ap.id=r.annotation_project_id
            LEFT JOIN recruitment_project rp ON rp.id=r.recruitment_project_id
            LEFT JOIN interpretation_project ip ON ip.id=r.interpretation_project_id
            LEFT JOIN translation_project tp ON tp.id=r.translation_project_id
        """))


def ensure_recruitment_project_columns():
    """补齐早期招聘模拟表与正式招聘项目域之间的字段差异。"""
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    with engine.begin() as conn:
        if "recruitment_project" in table_names:
            for statement in RECRUITMENT_PROJECT_COLUMN_STATEMENTS:
                conn.execute(text(statement))
            columns = {item["name"] for item in inspect(conn).get_columns("recruitment_project")}
            if "position_name_type" in columns:
                conn.execute(text("UPDATE recruitment_project SET position_title = COALESCE(position_title, position_name_type)"))
            if "recruitment_headcount" in columns:
                conn.execute(text("UPDATE recruitment_project SET headcount_min = COALESCE(headcount_min, recruitment_headcount), headcount_max = COALESCE(headcount_max, recruitment_headcount)"))
                conn.execute(text("ALTER TABLE recruitment_project ALTER COLUMN recruitment_headcount SET DEFAULT 0"))
            if "proposed_start_date" in columns:
                conn.execute(text("UPDATE recruitment_project SET target_onboard_date = COALESCE(target_onboard_date, proposed_start_date)"))
            if "service_fee" in columns:
                conn.execute(text("UPDATE recruitment_project SET service_fee_note = COALESCE(service_fee_note, service_fee)"))
        if "recruitment_candidate" in table_names:
            for statement in RECRUITMENT_CANDIDATE_COLUMN_STATEMENTS:
                conn.execute(text(statement))
            columns = {item["name"] for item in inspect(conn).get_columns("recruitment_candidate")}
            if "sequence_no" in columns:
                conn.execute(text("ALTER TABLE recruitment_candidate ALTER COLUMN sequence_no DROP NOT NULL"))
            conn.execute(text("UPDATE recruitment_candidate SET first_interview_date = interview_at::date WHERE first_interview_date IS NULL AND interview_at IS NOT NULL"))
            if "entry_date" in columns:
                conn.execute(text("UPDATE recruitment_candidate SET actual_onboard_date = COALESCE(actual_onboard_date, entry_date)"))
            if "resume_source" in columns:
                conn.execute(text("""
                    INSERT INTO recruitment_resume_source (label, is_custom)
                    SELECT DISTINCT trim(candidate.resume_source), TRUE
                    FROM recruitment_candidate candidate
                    WHERE candidate.resume_source IS NOT NULL AND trim(candidate.resume_source) <> ''
                    ON CONFLICT DO NOTHING
                """))
                conn.execute(text("""
                    UPDATE recruitment_candidate candidate
                    SET resume_source_id = source.id
                    FROM recruitment_resume_source source
                    WHERE candidate.resume_source_id IS NULL
                      AND lower(trim(candidate.resume_source)) = lower(trim(source.label))
                """))


def ensure_recruitment_communication_columns():
    """兼容早期招聘候选人沟通表。"""
    if "recruitment_candidate_communication" not in inspect(engine).get_table_names():
        return
    with engine.begin() as conn:
        for statement in RECRUITMENT_COMMUNICATION_COLUMN_STATEMENTS:
            conn.execute(text(statement))


def ensure_resource_compat_columns():
    """为旧译员、招聘候选记录补齐统一人才主档关联。"""
    tables = set(inspect(engine).get_table_names())
    if not {"translator", "recruitment_candidate", "resource_person"}.issubset(tables):
        return
    with engine.begin() as conn:
        for statement in RESOURCE_COMPAT_COLUMN_STATEMENTS:
            conn.execute(text(statement))


def ensure_resource_request_lifecycle_columns():
    """补齐资源需求草稿、发送与取消的独立生命周期字段。"""
    if "resource_request" not in inspect(engine).get_table_names():
        return
    with engine.begin() as conn:
        for statement in RESOURCE_REQUEST_LIFECYCLE_STATEMENTS:
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
        code for code in PERMISSION_CODES
        if not code.startswith(("system:", "talents:", "recruitment_talents:"))
    )
    with Session(engine) as db:
        roles = db.query(Role).filter(~Role.role_name.in_(SUPER_ROLE_NAMES)).all()
        for role in roles:
            db.add_all(
                RolePermission(role_id=role.id, permission_code=code)
                for code in legacy_permissions
            )
        db.commit()


def ensure_consultation_project_intake_columns():
    """兼容直接启动升级，正式部署仍应执行对应 SQL 迁移。"""
    statements = (
        "ALTER TABLE consultation ADD COLUMN IF NOT EXISTS sub_client_id UUID",
        "ALTER TABLE consultation ADD COLUMN IF NOT EXISTS contact_name VARCHAR(255)",
        "ALTER TABLE consultation ADD COLUMN IF NOT EXISTS customer_order_no VARCHAR(150)",
        "ALTER TABLE consultation ADD COLUMN IF NOT EXISTS project_name VARCHAR(500)",
        "ALTER TABLE consultation ADD COLUMN IF NOT EXISTS project_intake JSONB NOT NULL DEFAULT '{}'::jsonb",
        "ALTER TABLE consultation ADD COLUMN IF NOT EXISTS project_intake_version INTEGER NOT NULL DEFAULT 1",
        "ALTER TABLE consultation ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(128)",
        "ALTER TABLE consultation ADD COLUMN IF NOT EXISTS consultation_method_detail VARCHAR(255)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_consultation_idempotency_key ON consultation(idempotency_key) WHERE idempotency_key IS NOT NULL",
    )
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


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


def ensure_talent_permission_compatibility():
    """把原译员资源权限平滑映射到统一人才资源库。"""
    mapping = {
        "translators:read": "talents:read",
        "translators:write": "talents:write",
        "projects:read": "recruitment_talents:read",
        "projects:write": "recruitment_talents:write",
    }
    with Session(engine) as db:
        existing = {
            (row.role_id, row.permission_code)
            for row in db.query(RolePermission).filter(
                RolePermission.permission_code.in_(tuple(mapping) + tuple(mapping.values()))
            ).all()
        }
        for role_id, old_code in list(existing):
            new_code = mapping.get(old_code)
            if new_code and (role_id, new_code) not in existing:
                db.add(RolePermission(role_id=role_id, permission_code=new_code))
        db.commit()


def ensure_multitype_workbench_schema():
    """兼容未单独执行 20260825 工作台迁移的部署。"""
    tables = set(inspect(engine).get_table_names())
    required_projects = {"interpretation_project", "annotation_project", "recruitment_project"}
    if not required_projects.issubset(tables):
        return
    ProjectWorkbenchResponsibility.__table__.create(bind=engine, checkfirst=True)
    with engine.begin() as conn:
        if "workflow_handover_item" in tables:
            conn.execute(text("ALTER TABLE workflow_handover_item ADD COLUMN IF NOT EXISTS project_responsibility_id UUID"))
            conn.execute(text("ALTER TABLE workflow_handover_item ALTER COLUMN workflow_instance_id DROP NOT NULL"))
            conn.execute(text("""
                DO $$ BEGIN
                    IF EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'ck_wf_handover_item_exactly_one_source'
                          AND position('project_responsibility_id' in pg_get_constraintdef(oid)) = 0
                    ) THEN
                        ALTER TABLE workflow_handover_item DROP CONSTRAINT ck_wf_handover_item_exactly_one_source;
                    END IF;
                    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_wf_handover_item_exactly_one_source') THEN
                        ALTER TABLE workflow_handover_item ADD CONSTRAINT ck_wf_handover_item_exactly_one_source CHECK (
                            (workflow_instance_id IS NOT NULL AND project_responsibility_id IS NULL) OR
                            (workflow_instance_id IS NULL AND project_responsibility_id IS NOT NULL)
                        );
                    END IF;
                    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_wf_handover_item_responsibility') THEN
                        ALTER TABLE workflow_handover_item ADD CONSTRAINT fk_wf_handover_item_responsibility
                            FOREIGN KEY (project_responsibility_id) REFERENCES project_workbench_responsibility(id) ON DELETE CASCADE;
                    END IF;
                    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_wf_handover_item_responsibility') THEN
                        ALTER TABLE workflow_handover_item ADD CONSTRAINT uq_wf_handover_item_responsibility
                            UNIQUE (request_id, project_responsibility_id);
                    END IF;
                END $$;
            """))
        if "project_manager_handover_item" in tables:
            conn.execute(text("ALTER TABLE project_manager_handover_item ADD COLUMN IF NOT EXISTS project_responsibility_id UUID"))
            conn.execute(text("ALTER TABLE project_manager_handover_item ALTER COLUMN translation_project_id DROP NOT NULL"))
            conn.execute(text("""
                DO $$ BEGIN
                    IF EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'ck_pm_handover_item_exactly_one_source'
                          AND position('project_responsibility_id' in pg_get_constraintdef(oid)) = 0
                    ) THEN
                        ALTER TABLE project_manager_handover_item DROP CONSTRAINT ck_pm_handover_item_exactly_one_source;
                    END IF;
                    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_pm_handover_item_exactly_one_source') THEN
                        ALTER TABLE project_manager_handover_item ADD CONSTRAINT ck_pm_handover_item_exactly_one_source CHECK (
                            (translation_project_id IS NOT NULL AND project_responsibility_id IS NULL) OR
                            (translation_project_id IS NULL AND project_responsibility_id IS NOT NULL)
                        );
                    END IF;
                    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_pm_handover_item_responsibility') THEN
                        ALTER TABLE project_manager_handover_item ADD CONSTRAINT fk_pm_handover_item_responsibility
                            FOREIGN KEY (project_responsibility_id) REFERENCES project_workbench_responsibility(id) ON DELETE CASCADE;
                    END IF;
                    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_pm_handover_item_responsibility') THEN
                        ALTER TABLE project_manager_handover_item ADD CONSTRAINT uq_pm_handover_item_responsibility
                            UNIQUE (request_id, project_responsibility_id);
                    END IF;
                END $$;
            """))
        if "work_entry" in tables:
            conn.execute(text("ALTER TABLE work_entry ADD COLUMN IF NOT EXISTS project_responsibility_id UUID"))
            conn.execute(text("""
                DO $$ BEGIN
                    IF EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'ck_work_entry_exactly_one_source'
                          AND position('project_responsibility_id' in pg_get_constraintdef(oid)) = 0
                    ) THEN
                        ALTER TABLE work_entry DROP CONSTRAINT ck_work_entry_exactly_one_source;
                    END IF;
                    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_work_entry_exactly_one_source') THEN
                        ALTER TABLE work_entry ADD CONSTRAINT ck_work_entry_exactly_one_source CHECK (
                            (CASE WHEN workflow_instance_id IS NOT NULL THEN 1 ELSE 0 END +
                             CASE WHEN project_responsibility_id IS NOT NULL THEN 1 ELSE 0 END +
                             CASE WHEN non_project_task_id IS NOT NULL THEN 1 ELSE 0 END) = 1
                        );
                    END IF;
                    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_work_entry_project_responsibility') THEN
                        ALTER TABLE work_entry ADD CONSTRAINT fk_work_entry_project_responsibility
                            FOREIGN KEY (project_responsibility_id) REFERENCES project_workbench_responsibility(id) ON DELETE CASCADE;
                    END IF;
                END $$;
            """))
        if "app_notification" in tables:
            conn.execute(text("ALTER TABLE app_notification ADD COLUMN IF NOT EXISTS related_project_type VARCHAR(30)"))
            conn.execute(text("ALTER TABLE app_notification ADD COLUMN IF NOT EXISTS related_entity_id UUID"))
            conn.execute(text("""
                UPDATE app_notification
                SET related_project_type = 'translation', related_entity_id = related_project_id
                WHERE related_project_id IS NOT NULL AND related_entity_id IS NULL
            """))
        conn.execute(text("""
            INSERT INTO project_workbench_responsibility (interpretation_project_id, role_code)
            SELECT p.id, r.role_code FROM interpretation_project p
            CROSS JOIN (VALUES ('project_manager'), ('project_specialist'), ('project_assistant')) r(role_code)
            WHERE p.project_status IN ('initial_follow_up', 'in_progress') ON CONFLICT DO NOTHING
        """))
        conn.execute(text("""
            INSERT INTO project_workbench_responsibility (annotation_project_id, role_code)
            SELECT p.id, r.role_code FROM annotation_project p
            CROSS JOIN (VALUES ('project_manager'), ('project_specialist'), ('project_assistant')) r(role_code)
            WHERE p.project_status IN ('initial_consultation', 'resource_sourcing', 'trial_preparation', 'trial_in_progress', 'trial_passed', 'trial_partially_passed', 'project_in_progress', 'sent_to_client', 'client_feedback') ON CONFLICT DO NOTHING
        """))
        conn.execute(text("""
            INSERT INTO project_workbench_responsibility (recruitment_project_id, role_code)
            SELECT p.id, r.role_code FROM recruitment_project p
            CROSS JOIN (VALUES ('project_manager'), ('project_specialist'), ('project_assistant')) r(role_code)
            WHERE p.project_status <> 'closed' ON CONFLICT DO NOTHING
        """))


def ensure_project_idempotency_columns() -> None:
    """在显式迁移窗口补齐核心创建接口的幂等键及唯一约束。"""
    tables = (
        ("translation_project", "uq_translation_project_idempotency_key"),
        ("interpretation_project", "uq_interpretation_project_idempotency_key"),
        ("annotation_project", "uq_annotation_project_idempotency_key"),
        ("recruitment_project", "uq_recruitment_project_idempotency_key"),
        ("resource_request", "uq_resource_request_idempotency_key"),
        ("client", "uq_client_idempotency_key"),
        ("sub_client", "uq_sub_client_idempotency_key"),
        ("client_contact", "uq_client_contact_idempotency_key"),
        ("resource_person", "uq_resource_person_idempotency_key"),
        ("translation_sub_order", "uq_translation_sub_order_idempotency_key"),
    )
    with engine.begin() as conn:
        for table_name, constraint_name in tables:
            conn.execute(text(
                f"ALTER TABLE {table_name} "
                "ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(128)"
            ))
            conn.execute(text(f"""
                DO $$ BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint WHERE conname = '{constraint_name}'
                    ) THEN
                        ALTER TABLE {table_name}
                        ADD CONSTRAINT {constraint_name} UNIQUE (idempotency_key);
                    END IF;
                END $$;
            """))


def run_runtime_migrations():
    """执行历史运行时迁移。

    该函数不得注册为 FastAPI 启动钩子，只允许本地迁移工具显式调用。
    """
    LoginThrottleState.__table__.create(bind=engine, checkfirst=True)
    LoginSecurityEvent.__table__.create(bind=engine, checkfirst=True)
    RevokedAccessToken.__table__.create(bind=engine, checkfirst=True)
    LoginCaptchaChallenge.__table__.create(bind=engine, checkfirst=True)
    with Session(engine) as db:
        cleanup_login_security_data(db)
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_app_user_email_normalized
            ON app_user (lower(btrim(email)))
            WHERE email IS NOT NULL AND btrim(email) <> ''
        """))
    ensure_consultation_project_intake_columns()
    ClientContact.__table__.create(bind=engine, checkfirst=True)
    AppNotification.__table__.create(bind=engine, checkfirst=True)
    ChatProjectEnabled.__table__.create(bind=engine, checkfirst=True)
    ChatProjectMessage.__table__.create(bind=engine, checkfirst=True)
    ChatProjectMention.__table__.create(bind=engine, checkfirst=True)
    ensure_chat_message_columns()
    ChatProjectAttachment.__table__.create(bind=engine, checkfirst=True)
    ChatProjectMessageAttachment.__table__.create(bind=engine, checkfirst=True)
    WorkflowHandoverRequest.__table__.create(bind=engine, checkfirst=True)
    WorkflowHandoverAttachment.__table__.create(bind=engine, checkfirst=True)
    NonProjectTaskRecurrence.__table__.create(bind=engine, checkfirst=True)
    NonProjectTask.__table__.create(bind=engine, checkfirst=True)
    NonProjectTaskEvent.__table__.create(bind=engine, checkfirst=True)
    DailyReport.__table__.create(bind=engine, checkfirst=True)
    DailyReportItem.__table__.create(bind=engine, checkfirst=True)
    ManuscriptDispatch.__table__.create(bind=engine, checkfirst=True)
    ManuscriptArrangement.__table__.create(bind=engine, checkfirst=True)
    ensure_manuscript_arrangement_columns()
    ManuscriptDeliveryMilestone.__table__.create(bind=engine, checkfirst=True)
    WordCountMetric.__table__.create(bind=engine, checkfirst=True)
    backfill_manuscript_dispatches()
    ensure_manuscript_constraints()
    cleanup_orphan_chat_attachments()
    TranslatorSchedule.__table__.create(bind=engine, checkfirst=True)
    ensure_role_permission_table()
    ensure_personal_task_permissions()
    ensure_talent_permission_compatibility()
    ResourcePerson.__table__.create(bind=engine, checkfirst=True)
    ResourceCapability.__table__.create(bind=engine, checkfirst=True)
    WrittenTranslationProfile.__table__.create(bind=engine, checkfirst=True)
    InterpretationProfile.__table__.create(bind=engine, checkfirst=True)
    AnnotationProfile.__table__.create(bind=engine, checkfirst=True)
    ResourceCareerProfile.__table__.create(bind=engine, checkfirst=True)
    ensure_project_file_path_columns()
    ensure_project_file_detail_columns()
    ensure_translation_project_columns()
    ProjectRoleAssignment.__table__.create(bind=engine, checkfirst=True)
    ProjectManagerHandoverRequest.__table__.create(bind=engine, checkfirst=True)
    InterpretationLanguage.__table__.create(bind=engine, checkfirst=True)
    ensure_interpretation_language_columns()
    InterpretationProject.__table__.create(bind=engine, checkfirst=True)
    InterpretationProjectTimeRange.__table__.create(bind=engine, checkfirst=True)
    InterpretationProjectLanguageDirection.__table__.create(bind=engine, checkfirst=True)
    InterpretationProjectDirectionExtraLanguage.__table__.create(bind=engine, checkfirst=True)
    InterpretationProjectInterpreter.__table__.create(bind=engine, checkfirst=True)
    ensure_interpretation_requirement_columns()
    AnnotationProject.__table__.create(bind=engine, checkfirst=True)
    ensure_annotation_project_columns()
    AnnotationProjectLanguageItem.__table__.create(bind=engine, checkfirst=True)
    AnnotationProjectPriceItem.__table__.create(bind=engine, checkfirst=True)
    AnnotationProjectAssignee.__table__.create(bind=engine, checkfirst=True)
    ensure_annotation_assignee_columns()
    AnnotationProjectStatusHistory.__table__.create(bind=engine, checkfirst=True)
    ensure_annotation_status_history_seed()
    AnnotationPlatform.__table__.create(bind=engine, checkfirst=True)
    AnnotationPlatformAccount.__table__.create(bind=engine, checkfirst=True)
    AnnotationAccountAssignment.__table__.create(bind=engine, checkfirst=True)
    AnnotationAccountAssignmentLanguage.__table__.create(bind=engine, checkfirst=True)
    AnnotationAccountPasswordHistory.__table__.create(bind=engine, checkfirst=True)
    AnnotationCredentialAccessLog.__table__.create(bind=engine, checkfirst=True)
    AnnotationTrialRecord.__table__.create(bind=engine, checkfirst=True)
    AnnotationAssigneeRate.__table__.create(bind=engine, checkfirst=True)
    AnnotationCustomFieldDefinition.__table__.create(bind=engine, checkfirst=True)
    ensure_annotation_custom_field_scope_constraint()
    ensure_annotation_custom_field_type_constraint()
    AnnotationCustomFieldImage.__table__.create(bind=engine, checkfirst=True)
    AnnotationAccountAssignmentImage.__table__.create(bind=engine, checkfirst=True)
    cleanup_orphan_custom_field_images()
    RecruitmentResumeSource.__table__.create(bind=engine, checkfirst=True)
    RecruitmentProject.__table__.create(bind=engine, checkfirst=True)
    ensure_recruitment_project_columns()
    ensure_multitype_workbench_schema()
    WorkflowHandoverItem.__table__.create(bind=engine, checkfirst=True)
    ProjectManagerHandoverItem.__table__.create(bind=engine, checkfirst=True)
    WorkEntry.__table__.create(bind=engine, checkfirst=True)
    MailRecipientGroup.__table__.create(bind=engine, checkfirst=True)
    MailRecipientGroupMember.__table__.create(bind=engine, checkfirst=True)
    ProjectMailPolicy.__table__.create(bind=engine, checkfirst=True)
    ProjectMailPolicyGroup.__table__.create(bind=engine, checkfirst=True)
    BusinessMail.__table__.create(bind=engine, checkfirst=True)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE business_mail ADD COLUMN IF NOT EXISTS body_html TEXT"))
    BusinessMailRecipient.__table__.create(bind=engine, checkfirst=True)
    BusinessMailAttempt.__table__.create(bind=engine, checkfirst=True)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE business_mail_attempt ADD COLUMN IF NOT EXISTS sender_user_id UUID"))
        conn.execute(text("ALTER TABLE business_mail_attempt ADD COLUMN IF NOT EXISTS sender_name_snapshot VARCHAR(255)"))
        conn.execute(text("ALTER TABLE business_mail_attempt ADD COLUMN IF NOT EXISTS sender_email_snapshot VARCHAR(255)"))
        conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'fk_business_mail_attempt_sender'
                ) THEN
                    ALTER TABLE business_mail_attempt
                    ADD CONSTRAINT fk_business_mail_attempt_sender
                    FOREIGN KEY (sender_user_id) REFERENCES app_user(id) ON DELETE SET NULL;
                END IF;
            END $$
        """))
    UserMailAccount.__table__.create(bind=engine, checkfirst=True)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE user_mail_account ADD COLUMN IF NOT EXISTS email_snapshot VARCHAR(255)"))
        conn.execute(text("UPDATE user_mail_account SET email_snapshot = app_user.email FROM app_user WHERE user_mail_account.user_id = app_user.id AND user_mail_account.email_snapshot IS NULL"))
        conn.execute(text("ALTER TABLE user_mail_account ALTER COLUMN email_snapshot SET NOT NULL"))
    DailyReportMailPolicy.__table__.create(bind=engine, checkfirst=True)
    DailyReportMailPolicyGroup.__table__.create(bind=engine, checkfirst=True)
    DailyReportMailDelivery.__table__.create(bind=engine, checkfirst=True)
    DailyReportMailRecipient.__table__.create(bind=engine, checkfirst=True)
    DailyReportMailAttempt.__table__.create(bind=engine, checkfirst=True)
    MailInlineImage.__table__.create(bind=engine, checkfirst=True)
    MailInlineImageBinding.__table__.create(bind=engine, checkfirst=True)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE manuscript_arrangement ADD COLUMN IF NOT EXISTS email_body_html TEXT"))
    with Session(engine) as db:
        cleanup_orphan_inline_images(db, prune_missing_scopes=True)
    RecruitmentProjectLanguageDirection.__table__.create(bind=engine, checkfirst=True)
    RecruitmentProjectProgress.__table__.create(bind=engine, checkfirst=True)
    RecruitmentCandidate.__table__.create(bind=engine, checkfirst=True)
    ensure_resource_compat_columns()
    RecruitmentCandidateCommunication.__table__.create(bind=engine, checkfirst=True)
    ensure_recruitment_communication_columns()
    RecruitmentCandidateInterview.__table__.create(bind=engine, checkfirst=True)
    ResourceRequest.__table__.create(bind=engine, checkfirst=True)
    ResourceRequestItem.__table__.create(bind=engine, checkfirst=True)
    ResourceRequestItemExtraLanguage.__table__.create(bind=engine, checkfirst=True)
    ResourceRequestProgressLog.__table__.create(bind=engine, checkfirst=True)
    ensure_resource_request_lifecycle_columns()
    ensure_project_idempotency_columns()
    ensure_resource_request_view()
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO recruitment_candidate_interview
                (candidate_id, round_no, interview_date, details)
            SELECT id, 1, first_interview_date, first_interview_details
            FROM recruitment_candidate
            WHERE (first_interview_date IS NOT NULL OR first_interview_details IS NOT NULL)
            ON CONFLICT (candidate_id, round_no) DO NOTHING
        """))
        conn.execute(text("""
            INSERT INTO recruitment_candidate_interview
                (candidate_id, round_no, interview_date, details)
            SELECT id, 1, NULL, NULL
            FROM recruitment_candidate
            WHERE (second_interview_date IS NOT NULL OR second_interview_details IS NOT NULL)
            ON CONFLICT (candidate_id, round_no) DO NOTHING
        """))
        conn.execute(text("""
            INSERT INTO recruitment_candidate_interview
                (candidate_id, round_no, interview_date, details)
            SELECT id, 2, second_interview_date, second_interview_details
            FROM recruitment_candidate
            WHERE (second_interview_date IS NOT NULL OR second_interview_details IS NOT NULL)
            ON CONFLICT (candidate_id, round_no) DO NOTHING
        """))
    with Session(engine) as db:
        ensure_default_interpretation_languages(db)
        ensure_translation_languages_in_catalog(db)
        migrate_legacy_annotation_projects(db)
        ensure_default_resume_sources(db)
        backfill_resource_people(db)


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
