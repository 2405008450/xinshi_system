-- 允许在项目操作审计中永久留存标注项目具体进度的删除记录。
ALTER TABLE project_operation_audit
    DROP CONSTRAINT IF EXISTS ck_project_operation_audit_operation;

ALTER TABLE project_operation_audit
    ADD CONSTRAINT ck_project_operation_audit_operation
    CHECK (operation_type IN ('create','delete','order_no_change','progress_delete'));

COMMENT ON TABLE project_operation_audit
    IS '四类项目新增、删除、订单号修改及标注具体进度删除的永久审计记录';
