-- 修复部署库中普通员工缺少 user_role 关联导致登录后 roles 为空的问题。
-- 规则：
-- 1. 只处理当前没有任何角色的用户，避免覆盖或叠加已有人工配置。
-- 2. 优先使用用户名精确补历史上已有的角色，再按部门做兜底推断。
-- 3. 脚本可重复执行，uq_user_role 会配合 ON CONFLICT 保持幂等。

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

WITH explicit_role_map(username, role_name) AS (
    VALUES
        ('shaofei', '项目经理'),
        ('lixian', '项目经理'),
        ('menghua', '项目经理'),
        ('weiqi', '项目专员'),
        ('chuqiao', '客户专员'),
        ('ruizhu', '排版专员'),
        ('cuizhen', '项目助理'),
        ('thomas', '译审')
),
department_role_map(department, role_name) AS (
    VALUES
        ('项目经理', '项目经理'),
        ('项目部', '项目专员'),
        ('客户部', '客户专员'),
        ('排版', '排版专员'),
        ('HR部', '项目助理'),
        ('翻译部', '译审'),
        ('销售', '销售'),
        ('招聘项目', '项目专员')
),
users_without_role AS (
    SELECT u.id, u.username, u.department
    FROM app_user u
    WHERE u.is_active IS TRUE
      AND NOT EXISTS (
          SELECT 1
          FROM user_role ur
          WHERE ur.user_id = u.id
      )
),
inferred_roles AS (
    SELECT uwr.id AS user_id, COALESCE(erm.role_name, drm.role_name) AS role_name
    FROM users_without_role uwr
    LEFT JOIN explicit_role_map erm ON erm.username = uwr.username
    LEFT JOIN department_role_map drm ON drm.department = uwr.department
    WHERE COALESCE(erm.role_name, drm.role_name) IS NOT NULL
)
INSERT INTO user_role (id, user_id, role_id, created_at)
SELECT gen_random_uuid(), ir.user_id, r.id, now()
FROM inferred_roles ir
JOIN role r ON r.role_name = ir.role_name
ON CONFLICT (user_id, role_id) DO NOTHING;

COMMIT;
