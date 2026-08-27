BEGIN;

CREATE TABLE IF NOT EXISTS annotation_platform (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID REFERENCES client(id) ON DELETE RESTRICT,
    sub_client_id UUID REFERENCES sub_client(id) ON DELETE SET NULL,
    origin_project_id UUID REFERENCES annotation_project(id) ON DELETE SET NULL,
    platform_name VARCHAR(150),
    platform_url TEXT NOT NULL,
    platform_url_normalized TEXT NOT NULL,
    login_notes TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    sequence_no INTEGER NOT NULL CHECK (sequence_no > 0),
    created_by UUID REFERENCES app_user(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_annotation_platform_client_sequence UNIQUE (client_id, sequence_no)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_annotation_platform_client_url
    ON annotation_platform(client_id, platform_url_normalized) NULLS NOT DISTINCT;
CREATE INDEX IF NOT EXISTS ix_annotation_platform_client_sequence ON annotation_platform(client_id, sequence_no);
CREATE INDEX IF NOT EXISTS ix_annotation_platform_normalized_url ON annotation_platform(platform_url_normalized);

CREATE TABLE IF NOT EXISTS annotation_platform_account (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id UUID NOT NULL REFERENCES annotation_platform(id) ON DELETE CASCADE,
    parent_account_id UUID REFERENCES annotation_platform_account(id) ON DELETE SET NULL,
    nickname VARCHAR(255),
    login_account TEXT,
    login_account_normalized TEXT,
    password TEXT,
    account_status VARCHAR(20) NOT NULL DEFAULT 'available',
    registration_status VARCHAR(30) NOT NULL DEFAULT 'unregistered',
    account_source VARCHAR(30) NOT NULL DEFAULT 'client_provided',
    expires_on DATE,
    remarks TEXT,
    custom_values JSONB NOT NULL DEFAULT '{}'::jsonb,
    sequence_no INTEGER NOT NULL CHECK (sequence_no > 0),
    password_updated_at TIMESTAMP,
    created_by UUID REFERENCES app_user(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_annotation_account_login_normalized UNIQUE (platform_id, login_account_normalized),
    CONSTRAINT uq_annotation_account_sequence UNIQUE (platform_id, sequence_no),
    CONSTRAINT ck_annotation_account_parent CHECK (parent_account_id IS NULL OR parent_account_id <> id),
    CONSTRAINT ck_annotation_account_status CHECK (account_status IN ('available','assigned','suspended','banned','retired')),
    CONSTRAINT ck_annotation_account_registration_status CHECK (registration_status IN ('unregistered','registering','registered','registration_failed','disabled','not_required')),
    CONSTRAINT ck_annotation_account_source CHECK (account_source IN ('client_provided','self_registered','annotator_owned')),
    CONSTRAINT ck_annotation_account_registered_credential CHECK (
        registration_status <> 'registered'
        OR (login_account IS NOT NULL AND password IS NOT NULL)
    )
);
CREATE INDEX IF NOT EXISTS ix_annotation_account_platform_status ON annotation_platform_account(platform_id, account_status);
CREATE INDEX IF NOT EXISTS ix_annotation_account_registration_status ON annotation_platform_account(registration_status);
CREATE INDEX IF NOT EXISTS ix_annotation_account_expires_on ON annotation_platform_account(expires_on) WHERE expires_on IS NOT NULL;

CREATE TABLE IF NOT EXISTS annotation_account_assignment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES annotation_platform_account(id) ON DELETE CASCADE,
    person_id UUID REFERENCES resource_person(id) ON DELETE RESTRICT,
    project_id UUID REFERENCES annotation_project(id) ON DELETE SET NULL,
    assigned_on DATE NOT NULL DEFAULT CURRENT_DATE,
    released_on DATE,
    release_reason VARCHAR(30),
    assignment_note TEXT,
    assigned_by UUID REFERENCES app_user(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_annotation_assignment_dates CHECK (released_on IS NULL OR released_on >= assigned_on),
    CONSTRAINT ck_annotation_assignment_release_reason CHECK (
        release_reason IS NULL OR release_reason IN ('project_completed','person_left','account_banned','reassigned','other')
    )
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_annotation_assignment_active ON annotation_account_assignment(account_id) WHERE released_on IS NULL;
CREATE INDEX IF NOT EXISTS ix_annotation_assignment_person_active ON annotation_account_assignment(person_id, released_on);
CREATE INDEX IF NOT EXISTS ix_annotation_assignment_project ON annotation_account_assignment(project_id);
CREATE INDEX IF NOT EXISTS ix_annotation_assignment_timeline ON annotation_account_assignment(account_id, assigned_on DESC);

CREATE TABLE IF NOT EXISTS annotation_account_assignment_language (
    assignment_id UUID NOT NULL REFERENCES annotation_account_assignment(id) ON DELETE CASCADE,
    language_item_id UUID NOT NULL REFERENCES annotation_project_language_item(id) ON DELETE RESTRICT,
    PRIMARY KEY (assignment_id, language_item_id)
);

CREATE TABLE IF NOT EXISTS annotation_account_password_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES annotation_platform_account(id) ON DELETE CASCADE,
    password TEXT NOT NULL,
    effective_from TIMESTAMP NOT NULL,
    replaced_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    changed_by UUID REFERENCES app_user(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_annotation_password_history_timeline ON annotation_account_password_history(account_id, replaced_at DESC);

CREATE TABLE IF NOT EXISTS annotation_credential_access_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES annotation_platform_account(id) ON DELETE CASCADE,
    user_id UUID REFERENCES app_user(id) ON DELETE SET NULL,
    accessed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    access_reason TEXT,
    client_ip VARCHAR(64)
);
CREATE INDEX IF NOT EXISTS ix_annotation_access_log_account_timeline ON annotation_credential_access_log(account_id, accessed_at DESC);
CREATE INDEX IF NOT EXISTS ix_annotation_access_log_user_timeline ON annotation_credential_access_log(user_id, accessed_at DESC);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='annotation_trial_record' AND column_name='platform_member_id'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='annotation_trial_record' AND column_name='legacy_platform_member_id'
    ) THEN
        ALTER TABLE annotation_trial_record DROP CONSTRAINT IF EXISTS fk_annotation_trial_member;
        ALTER TABLE annotation_trial_record RENAME COLUMN platform_member_id TO legacy_platform_member_id;
    END IF;
END $$;
ALTER TABLE annotation_trial_record ADD COLUMN IF NOT EXISTS platform_account_id UUID;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_annotation_trial_account') THEN
        ALTER TABLE annotation_trial_record
            ADD CONSTRAINT fk_annotation_trial_account FOREIGN KEY(platform_account_id)
            REFERENCES annotation_platform_account(id) ON DELETE SET NULL;
    END IF;
END $$;

ALTER TABLE annotation_custom_field_definition DROP CONSTRAINT IF EXISTS ck_annotation_custom_field_scope;
ALTER TABLE annotation_custom_field_definition
    ADD CONSTRAINT ck_annotation_custom_field_scope CHECK (
        (table_code IN ('project','account') AND project_id IS NULL) OR
        (table_code IN ('trial','assignment') AND project_id IS NOT NULL)
    ) NOT VALID;

INSERT INTO role_permission(role_id, permission_code)
SELECT DISTINCT role_id, 'annotation_accounts:read'
FROM role_permission
WHERE permission_code IN ('projects:read', 'projects:write')
ON CONFLICT (role_id, permission_code) DO NOTHING;

INSERT INTO role_permission(role_id, permission_code)
SELECT DISTINCT role_id, 'annotation_accounts:write'
FROM role_permission
WHERE permission_code = 'projects:write'
ON CONFLICT (role_id, permission_code) DO NOTHING;

COMMIT;

-- annotation_accounts:reveal 不自动授予。上线前由管理员在角色管理中人工指定。
