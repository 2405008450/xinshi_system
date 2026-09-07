-- 标注项目进度节点由日期升级为日期时间；历史日期统一补为当天 00:00:00。

ALTER TABLE annotation_project
    ALTER COLUMN status_effective_on DROP DEFAULT,
    ALTER COLUMN status_effective_on TYPE TIMESTAMP WITHOUT TIME ZONE
        USING status_effective_on::timestamp,
    ALTER COLUMN status_effective_on SET DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE annotation_project_status_history
    ALTER COLUMN effective_on TYPE TIMESTAMP WITHOUT TIME ZONE
        USING effective_on::timestamp;
