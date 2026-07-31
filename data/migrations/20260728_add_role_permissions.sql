BEGIN;

CREATE TABLE IF NOT EXISTS role_permission (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_id UUID NOT NULL,
    permission_code VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_role_permission_role
        FOREIGN KEY (role_id) REFERENCES role(id) ON DELETE CASCADE,
    CONSTRAINT uq_role_permission UNIQUE (role_id, permission_code)
);

CREATE INDEX IF NOT EXISTS ix_role_permission_role_id
    ON role_permission(role_id);

-- 首次升级时保持普通角色原有的业务访问能力，管理员可在角色页面进一步收紧。
INSERT INTO role_permission (role_id, permission_code)
SELECT r.id, p.permission_code
FROM role AS r
CROSS JOIN (
    VALUES
        ('projects:read'),
        ('projects:write'),
        ('workflow:operate'),
        ('project_files:read'),
        ('project_files:write'),
        ('clients:read'),
        ('clients:write'),
        ('consultations:read'),
        ('consultations:write'),
        ('translators:read'),
        ('translators:write'),
        ('schedule:read'),
        ('schedule:write'),
        ('finance:read'),
        ('finance:write')
) AS p(permission_code)
WHERE r.role_name NOT IN ('admin', '超级管理员')
ON CONFLICT (role_id, permission_code) DO NOTHING;

COMMIT;
