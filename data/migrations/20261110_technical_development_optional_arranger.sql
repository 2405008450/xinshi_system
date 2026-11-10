-- 历史开发任务可能没有安排人；用户明确要求保留空值，禁止归给默认人员。
-- 显式运行导入脚本时，在备份后与本批导入同一事务执行；不接入服务自动迁移。
ALTER TABLE technical_development_task ALTER COLUMN arranger_id DROP NOT NULL;
