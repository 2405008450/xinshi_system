-- 为 2026-08-27 Foxmail 地址簿导入的公司用户补齐角色。
-- 只处理当前完全没有角色的账号，保留所有既有人工配置。
-- IT部在系统中没有同名或正式映射角色，因此不自动授权。
-- 经确认，“其他”部门统一分配为“项目经理”。

BEGIN;

WITH imported_email(email) AS (
    VALUES
        ('media_m-spec@xinshifanyi.com.cn'),
        ('service3@xinshifanyi.com.cn'),
        ('trans4@xinshifanyi.com.cn'),
        ('trans15@xinshifanyi.com.cn'),
        ('trans9@xinshifanyi.com.cn'),
        ('trans8@xinshifanyi.com.cn'),
        ('carol@xinshifanyi.com.cn'),
        ('trans10@xinshifanyi.com.cn'),
        ('pb01@xinshifanyi.com.cn'),
        ('pb02@xinshifanyi.com.cn'),
        ('hr2@xinshifanyi.com.cn'),
        ('service9@xinshifanyi.com.cn'),
        ('service7@xinshifanyi.com.cn'),
        ('sales3@xinshifanyi.com.cn'),
        ('service16@xinshifanyi.com.cn'),
        ('service11@xinshifanyi.com.cn'),
        ('service14@xinshifanyi.com.cn'),
        ('service15@xinshifanyi.com.cn'),
        ('service6@xinshifanyi.com.cn'),
        ('service5@xinshifanyi.com.cn'),
        ('sales@xinshifanyi.com.cn'),
        ('service13@xinshifanyi.com.cn'),
        ('service8@xinshifanyi.com.cn'),
        ('tech002@xinshifanyi.com.cn'),
        ('tech@xinshifanyi.com.cn'),
        ('luke@xinshifanyi.com.cn'),
        ('trans3@xinshifanyi.com.cn'),
        ('trans7@xinshifanyi.com.cn'),
        ('lulu@xinshify.com.cn'),
        ('thomas@xinshifanyi.com.cn'),
        ('shen@xinshifanyi.com.cn'),
        ('service12@xinshifanyi.com.cn'),
        ('service10@xinshifanyi.com.cn'),
        ('hr8@xinshifanyi.com.cn'),
        ('hr7@xinshifanyi.com.cn'),
        ('hr5@xinshifanyi.com.cn'),
        ('hr10@xinshifanyi.com.cn'),
        ('hr9@xinshifanyi.com.cn'),
        ('hr4@xinshifanyi.com.cn'),
        ('hr@xinshifanyi.com.cn'),
        ('hr3@xinshifanyi.com.cn'),
        ('ethan@xinshifanyi.com.cn'),
        ('erichuang@xinshifanyi.com.cn'),
        ('williamzhao@xinshifanyi.com.cn'),
        ('service18@xinshifanyi.com.cn'),
        ('service17@xinshifanyi.com.cn'),
        ('trans12@xinshifanyi.com.cn'),
        ('jz@xinshifanyi.com.cn'),
        ('trans6@xinshifanyi.com.cn')
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
        ('招聘项目', '项目专员'),
        ('其他', '项目经理')
),
users_without_role AS (
    SELECT u.id, u.department
    FROM app_user u
    JOIN imported_email ie ON ie.email = lower(u.email)
    WHERE u.is_active IS TRUE
      AND NOT EXISTS (
          SELECT 1
          FROM user_role ur
          WHERE ur.user_id = u.id
      )
),
inferred_roles AS (
    SELECT uwr.id AS user_id, drm.role_name
    FROM users_without_role uwr
    JOIN department_role_map drm ON drm.department = uwr.department
)
INSERT INTO user_role (user_id, role_id)
SELECT ir.user_id, r.id
FROM inferred_roles ir
JOIN role r ON r.role_name = ir.role_name
ON CONFLICT (user_id, role_id) DO NOTHING;

COMMIT;
