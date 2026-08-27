BEGIN;

ALTER TABLE annotation_custom_field_definition VALIDATE CONSTRAINT ck_annotation_custom_field_scope;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='annotation_project_platform')
       AND NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='annotation_project_platform_legacy') THEN
        ALTER TABLE annotation_project_platform RENAME TO annotation_project_platform_legacy;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='annotation_platform_member')
       AND NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='annotation_platform_member_legacy') THEN
        ALTER TABLE annotation_platform_member RENAME TO annotation_platform_member_legacy;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='annotation_platform_member_language')
       AND NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='annotation_platform_member_language_legacy') THEN
        ALTER TABLE annotation_platform_member_language RENAME TO annotation_platform_member_language_legacy;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='annotation_platform_credential')
       AND NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='annotation_platform_credential_legacy') THEN
        ALTER TABLE annotation_platform_credential RENAME TO annotation_platform_credential_legacy;
    END IF;
END $$;

ALTER TABLE annotation_trial_record DROP COLUMN IF EXISTS legacy_platform_member_id;

COMMIT;
