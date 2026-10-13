-- 团队对接人显式增量迁移；禁止接入启动自动迁移。
ALTER TABLE resource_team ADD COLUMN IF NOT EXISTS contacts jsonb NOT NULL DEFAULT '[]'::jsonb;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'resource_team'::regclass AND conname = 'ck_resource_team_contacts') THEN
        ALTER TABLE resource_team ADD CONSTRAINT ck_resource_team_contacts
            CHECK (jsonb_typeof(contacts) = 'array' AND jsonb_array_length(contacts) <= 3);
    END IF;
END $$;
