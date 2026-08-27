BEGIN;

-- 账号可先确定项目和适用语言，人员稍后再分配。
-- 此时沿用 active assignment 记录项目上下文，但 person_id 保持为空，
-- 账号状态仍为 available。
ALTER TABLE annotation_account_assignment
    ALTER COLUMN person_id DROP NOT NULL;

COMMIT;
