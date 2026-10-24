-- 双人采标增量结构。不得在服务启动时自动执行；历史业务记录不改写。

BEGIN;

ALTER TABLE resource_language_skill ADD COLUMN IF NOT EXISTS accent VARCHAR(255);

ALTER TABLE annotation_platform ADD COLUMN IF NOT EXISTS platform_url2 TEXT;

CREATE TABLE IF NOT EXISTS annotation_paired_workspace (
	project_id UUID NOT NULL, 
	allow_multiple_groups BOOLEAN NOT NULL, 
	archived BOOLEAN NOT NULL, 
	notes JSONB NOT NULL, 
	revision INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (project_id), 
	FOREIGN KEY(project_id) REFERENCES annotation_project (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS annotation_paired_contact (
	id UUID NOT NULL, 
	project_id UUID NOT NULL, 
	person_id UUID NOT NULL, 
	willingness VARCHAR(40) NOT NULL, 
	data JSONB NOT NULL, 
	revision INTEGER NOT NULL, 
	created_by UUID, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_paired_contact_person UNIQUE (project_id, person_id), 
	FOREIGN KEY(project_id) REFERENCES annotation_paired_workspace (project_id) ON DELETE CASCADE, 
	FOREIGN KEY(person_id) REFERENCES resource_person (id) ON DELETE RESTRICT, 
	FOREIGN KEY(created_by) REFERENCES app_user (id)
);

CREATE INDEX IF NOT EXISTS ix_annotation_paired_contact_project_id ON annotation_paired_contact (project_id);

CREATE TABLE IF NOT EXISTS annotation_paired_group (
	id UUID NOT NULL, 
	project_id UUID NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	request_key UUID NOT NULL, 
	request_hash VARCHAR(64) NOT NULL, 
	archived BOOLEAN NOT NULL, 
	revision INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_paired_group_request UNIQUE (project_id, request_key), 
	FOREIGN KEY(project_id) REFERENCES annotation_paired_workspace (project_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_annotation_paired_group_project_id ON annotation_paired_group (project_id);

CREATE TABLE IF NOT EXISTS annotation_paired_members (
	id UUID NOT NULL, 
	group_id UUID, 
	version INTEGER NOT NULL, 
	person1_id UUID NOT NULL, 
	person2_id UUID NOT NULL, 
	reason TEXT NOT NULL, 
	created_by UUID, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_paired_members_version UNIQUE (group_id, version), 
	CONSTRAINT ck_paired_members_distinct CHECK (person1_id <> person2_id), 
	FOREIGN KEY(group_id) REFERENCES annotation_paired_group (id) ON DELETE CASCADE, 
	FOREIGN KEY(person1_id) REFERENCES resource_person (id) ON DELETE RESTRICT, 
	FOREIGN KEY(person2_id) REFERENCES resource_person (id) ON DELETE RESTRICT, 
	FOREIGN KEY(created_by) REFERENCES app_user (id)
);

CREATE INDEX IF NOT EXISTS ix_annotation_paired_members_group_id ON annotation_paired_members (group_id);

CREATE TABLE IF NOT EXISTS annotation_paired_task (
	id UUID NOT NULL, 
	project_id UUID NOT NULL, 
	group_id UUID NOT NULL, 
	members_id UUID NOT NULL, 
	source_task_id UUID, 
	request_key UUID NOT NULL, 
	request_hash VARCHAR(64) NOT NULL, 
	stage VARCHAR(20) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	person_ids JSONB NOT NULL, 
	data JSONB NOT NULL, 
	revision INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_paired_task_request UNIQUE (project_id, request_key), 
	CONSTRAINT uq_paired_task_source UNIQUE (source_task_id), 
	CONSTRAINT ck_paired_task_stage CHECK (stage IN ('collection','annotation')), 
	CONSTRAINT ck_paired_task_revision CHECK (revision > 0), 
	FOREIGN KEY(project_id) REFERENCES annotation_paired_workspace (project_id) ON DELETE CASCADE, 
	FOREIGN KEY(group_id) REFERENCES annotation_paired_group (id) ON DELETE RESTRICT, 
	FOREIGN KEY(members_id) REFERENCES annotation_paired_members (id) ON DELETE RESTRICT, 
	FOREIGN KEY(source_task_id) REFERENCES annotation_paired_task (id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS ix_annotation_paired_task_project_id ON annotation_paired_task (project_id);

CREATE TABLE IF NOT EXISTS annotation_paired_participant (
	task_id UUID NOT NULL, 
	person_id UUID NOT NULL, 
	active BOOLEAN NOT NULL, 
	PRIMARY KEY (task_id, person_id), 
	FOREIGN KEY(task_id) REFERENCES annotation_paired_task (id) ON DELETE CASCADE, 
	FOREIGN KEY(person_id) REFERENCES resource_person (id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS annotation_paired_record (
	id UUID NOT NULL, 
	task_id UUID NOT NULL, 
	kind VARCHAR(30) NOT NULL, 
	position INTEGER NOT NULL, 
	request_key UUID NOT NULL, 
	request_hash VARCHAR(64) NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	data JSONB NOT NULL, 
	person_ids JSONB NOT NULL, 
	revision INTEGER NOT NULL, 
	created_by UUID, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_paired_record_request UNIQUE (task_id, request_key), 
	CONSTRAINT ck_paired_record_position CHECK (position > 0), 
	FOREIGN KEY(task_id) REFERENCES annotation_paired_task (id) ON DELETE RESTRICT, 
	FOREIGN KEY(created_by) REFERENCES app_user (id)
);

CREATE INDEX IF NOT EXISTS ix_annotation_paired_record_task_id ON annotation_paired_record (task_id);

CREATE TABLE IF NOT EXISTS annotation_paired_audit (
	id UUID NOT NULL, 
	project_id UUID NOT NULL, 
	entity_id UUID NOT NULL, 
	action VARCHAR(40) NOT NULL, 
	before JSONB NOT NULL, 
	after JSONB NOT NULL, 
	actor_id UUID, 
	actor_name VARCHAR(255) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES annotation_paired_workspace (project_id) ON DELETE CASCADE, 
	FOREIGN KEY(actor_id) REFERENCES app_user (id)
);

CREATE INDEX IF NOT EXISTS ix_annotation_paired_audit_project_id ON annotation_paired_audit (project_id);

CREATE INDEX IF NOT EXISTS ix_annotation_paired_audit_entity_id ON annotation_paired_audit (entity_id);

CREATE TABLE IF NOT EXISTS annotation_paired_attachment (
	id UUID NOT NULL, 
	contact_id UUID NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	content BYTEA NOT NULL, 
	created_by UUID, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(contact_id) REFERENCES annotation_paired_contact (id) ON DELETE CASCADE, 
	FOREIGN KEY(created_by) REFERENCES app_user (id)
);

CREATE INDEX IF NOT EXISTS ix_annotation_paired_attachment_contact_id ON annotation_paired_attachment (contact_id);

ALTER TABLE annotation_project DROP CONSTRAINT IF EXISTS ck_annotation_project_status;

ALTER TABLE annotation_project ADD CONSTRAINT ck_annotation_project_status CHECK (project_status IN ('assessment_preparation','assessment_in_progress','assessment_completed','initial_consultation','consultation_no_result','resource_sourcing','resource_sourcing_cancelled','trial_preparation','trial_in_progress','trial_submitted','trial_passed','trial_failed','trial_partially_passed','project_in_progress','sent_to_client','client_feedback','cancelled','partially_cancelled','paused','actively_abandoned','ended'));

ALTER TABLE annotation_project_status_history DROP CONSTRAINT IF EXISTS ck_annotation_status_history_from;

ALTER TABLE annotation_project_status_history ADD CONSTRAINT ck_annotation_status_history_from CHECK (from_status IS NULL OR from_status IN ('assessment_preparation','assessment_in_progress','assessment_completed','initial_consultation','consultation_no_result','resource_sourcing','resource_sourcing_cancelled','trial_preparation','trial_in_progress','trial_submitted','trial_passed','trial_failed','trial_partially_passed','project_in_progress','sent_to_client','client_feedback','cancelled','partially_cancelled','paused','actively_abandoned','ended'));

ALTER TABLE annotation_project_status_history DROP CONSTRAINT IF EXISTS ck_annotation_status_history_to;

ALTER TABLE annotation_project_status_history ADD CONSTRAINT ck_annotation_status_history_to CHECK (to_status IN ('assessment_preparation','assessment_in_progress','assessment_completed','initial_consultation','consultation_no_result','resource_sourcing','resource_sourcing_cancelled','trial_preparation','trial_in_progress','trial_submitted','trial_passed','trial_failed','trial_partially_passed','project_in_progress','sent_to_client','client_feedback','cancelled','partially_cancelled','paused','actively_abandoned','ended'));

COMMIT;
