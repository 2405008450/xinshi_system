# 标注项目云端资料管理

标注项目资料、报价单和合同各自支持多个文件，单文件上限为100 MiB（界面显示100MB）。上传新版明确指定文件ID，同名上传不覆盖。新版保留全部历史，取消编辑不改变正式文件。历史共享路径保留只读，笔译文件管理不变。

## 数据与接口

独立使用 `annotation_material_upload/file/version/deletion` 四张表。上传记录在关联前为暂存，24小时过期；关联后作为不可变版本内容记录。删除队列与项目变更同事务提交，只有云端清理进程删除物理文件并重试失败项。

接口前缀为 `/api/projects/annotation`：

- `POST /material-uploads`：单文件multipart上传，返回暂存ID、原名称、大小、SHA-256、上传人及UTC时间。
- `DELETE /material-uploads/{id}`：取消自己的暂存，已关联文件不受影响。
- `GET /{project_id}/materials`：三类资料的最新版本。
- `GET /{project_id}/materials/{file_id}/versions`：历史版本。
- `GET /{project_id}/materials/{file_id}/versions/{version_id}/download`：鉴权下载，强制附件响应。
- 项目新增/编辑增加 `material_changes`，包含 `additions: [{upload_id, category, file_id?}]` 和 `removed_file_ids`。category为project、quotation、contract。编辑必须携带 `expected_updated_at`。省略变更参数不修改资料。

移除文件会移除全部版本，不提供回收站。附件不会自动加入业务邮件。文件不执行、不解压，不提供预览或匿名公开链接。

## 发布配置（本次不执行生产发布）

1. 备份数据库，执行 `data/migrations/20261013_annotation_materials.sql`；已有显式全量迁移入口也会创建新表。服务启动不自动迁移。
2. 云端配置 `ANNOTATION_MATERIAL_STORAGE_MODE=local`，使用独立持久化卷 `annotation_materials`，路径 `/app/data/annotation_materials`。默认disabled，完成迁移前不启用。
3. 局域网配置 `ANNOTATION_MATERIAL_STORAGE_MODE=remote`、`ANNOTATION_MATERIAL_REMOTE_ORIGIN=https://oa.xinshify.com.cn`。两端必须使用同一业务数据库、用户身份及兼容的签名配置；只在受保护运维渠道配置密钥，不把凭据放入仓库。
4. 发布两层Nginx配置：资料接口请求体110MiB、读写超时300秒，关闭代理请求/响应缓冲。局域网额外反向代理如存在，也需要相同限制。后端仍按实际文件字节限制100MiB。
5. 云端每分钟清理过期暂存及删除队列；失败保留attempts和last_error，日志输出失败重试。存储不可用时请求明确失败，remote模式绝不降级为本地长期存储。
6. 正式切换前核对云端/局域网相同项目、互认令牌、上传下载校验摘要以及文件只落云端。上游401转换为502提示配置问题，避免退出局域网用户登录。

按项目环境规范重启局域网后端：先确认Administrator活动交互会话、任务主体及Interactive登录类型，仅使用XinshiDebugBackendInteractive；重启后核对进程SessionId和任务上下文的UNC枚举。不能用SSH直接启动正式后端。

## 备份与回滚

数据库备份必须包含四张资料表，文件备份必须包含独立资料卷。备份窗口暂停资料写入与清理，取得配套的数据库和卷快照，并记录时间及文件SHA-256；恢复到隔离环境抽检最新版和历史版下载。仅数据库备份不能恢复文件。

回滚时先暂停资料写入，恢复应用版本并保留新表与资料卷；不能删除卷或把新上传资料视作共享路径文件。正式数据校验完成前不执行破坏性回滚。

## 验证

自动化用隔离数据库和临时存储验证版本、回滚、同名、跨项目访问、上传边界、暂存过期、清理失败重试及远程失败关闭。完整构建及浏览器验证在192.168.31.144进行，不修改真实项目资料。生产跨端联调不在本次授权范围。

本次在调试机隔离快照 `E:\xinshi_validation\annotation-materials-20260929` 完成：

- 后端资料、标注项目、聊天附件相关回归76项通过。
- 独立PostgreSQL 18实例专项16项通过，直接执行迁移SQL两次，并验证真实行锁、并发消费、事务回滚、进程中断孤立文件及删除重试。
- 前端相关检查15项通过，完整构建及体积预算通过。
- 真实标注页面配合模拟API完成9组浏览器场景：取消、失败重试、新版保存、历史下载、拖拽边界、位置复位、小屏固定操作栏、只读浮层和新增上传；页面脚本错误为0。验收脚本为 `tools/verify_annotation_materials_ui.py`，结果保存在快照 `.tmp/material-ui`。
- 临时PostgreSQL及前端预览进程已停止。未修改生产数据库、存储配置或正式服务；真实公网与局域网的认证、代理限制和持久化卷仍需在获准发布时验收。
