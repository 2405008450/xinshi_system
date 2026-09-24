# 标注开放项目群

## 使用规则

在标注项目的「更多操作 → 沟通」打开项目群。具备 `projects:read` 的有效用户可直接查看历史、发言、邀请其他具备项目查看权限的用户。

参与人表示持续关注者，不是访问白名单。创建人、客户经理、工作台负责人、历史发言人默认关注；首次发言或被邀请会关注。仅打开查看不自动关注。主动取消关注后，重复邀请、再次发言、负责人自动同步均不会覆盖退订。

右上角「项目消息」展示服务端未读。阅读位置仅在前台窗口内消息进入可见区域后推进；在搜索或引用历史定位时不推进。最小化或关闭聊天窗口后仍保留未读。

消息提供引用、复制、私人收藏、收到确认；进度弹窗内支持多选消息转进度。本人24小时内可撤回，`admin`/超级管理员可移除他人的用户消息。撤回删除正文，保留操作人、时间、提示；已有项目进度不追溯改写。

图片支持 JPEG/PNG/GIF/WebP，单张10MB。普通文件支持 PDF/DOC/DOCX/XLS/XLSX/PPT/PPTX/TXT/CSV/ZIP，单文件20MB，每条最多9个附件。上传失败可以重试，消息发送失败保留原客户端UUID，以同一标识重试；「继续编辑」先向后端确认原请求是否已经成功。

## 接口和兼容

复用 `/project-chat/annotation/{project_id}/messages`，新增可选 `client_message_id`、`reply_to_message_id`。扩展返回字段 `sequence_no`、`recalled_at`、`recall_label`、`can_recall`、`reply`。

新增群信息 `GET group`、邀请 `POST invitations`、关注 `PUT following`、阅读位置 `PUT read`、稳定游标列表 `GET timeline`、已加载消息刷新 `POST refresh`、发送结果确认 `GET sent/{client_message_id}`、撤回 `POST messages/{message_id}/recall`、附件 `POST files` / `GET files/{attachment_id}`。未读汇总为 `GET /project-chat/annotation/unread`。

WebSocket 复用 `/notifications/ws`，客户端发送 `annotation_chat_watch` 临时订阅当前查看的项目；服务端用 `annotation_chat_changed` 失效事件通知客户端重新鉴权读取。持久关注与临时查看独立，重连和轮询会刷新全部已加载消息，补齐历史撤回和引用变化。笔译保留原发送、沟通开关和富文本逻辑。

## 迁移与环境

迁移文件：`data/migrations/20260924_annotation_open_group_chat.sql`。增加关注/阅读位置表，消息序号、引用、客户端UUID和撤回列，以及附件项目归属。首次按历史时间生成稳定序号并初始化未读基线；重复执行不重置阅读位置或退订。迁移前备份数据库，旧版本后端兼容新增字段，回退代码时保留新表和新列。

2026-09-24 经用户明确授权使用云端数据库测试。迁移前完整备份位于局域网调试机 `E:\xinshi_system\backups\before_annotation_chat_20260924_150506.dump`。普通数据库测试在外层事务内回滚；浏览器测试仅创建 QA 前缀项目和账号，结束清理。

局域网使用项目 `.conda_env\python.exe` 和交互式任务 `XinshiDebugBackendInteractive`。后端与 explorer 的 SessionId 均须为当前活动控制台会话，启动日志须包含实际 UNC 只读枚举成功记录。

云端图片继续使用现有远程存储。新增普通文件转发到云端标注文件接口，禁止失败后回退本地。云端附件上传和旧URL撤回校验需要本次后端版本；HTTPS网关与前端容器分别使用 `deploy/nginx-cloud-gateway.conf`、`frontend/nginx.conf`，新上传路径上限22MB。更新云端运行服务需用户单独授权。

## 验证入口

- `tools/verify_annotation_open_chat.py --test --allow-cloud-db`：仅在局域网调试机执行；云端数据库参数只能在有明确授权时使用。`--migrate` 在执行前生成完整备份。
- `tests/test_annotation_open_chat.py`：24小时边界、权限、退订保持、引用、幂等、未读、游标以及附件撤回下载拒绝。
- `tools/verify_annotation_chat_ui.py`：三个专用测试账号验证开放聊天、旁观实时消息、引用撤回、关闭窗口未读、小屏和页面脚本错误；截图位于调试机 `.tmp/annotation-chat-ui`。
- 前端回归覆盖 `annotationProjectChat.test.mjs`、`projectChatDock.test.mjs`、`chatImageQueue.test.mjs`；构建输出使用隔离目录，执行 `check-build-budget.mjs --dist-dir <目录>`。

## 本次交付结果（2026-09-24）

顶部布局与关注入口优化：移除独立 @ 按钮，输入符号仍可唤起候选列表。聊天工具栏左侧展示参与人数，右侧展示关注状态与搜索图标，移除标题栏内重复的标注聊天搜索入口。网页右上角新增「收藏夹」，展示已关注的标注项目（含无未读项目）；点击项目名称定位项目并打开进度，点击「沟通」恢复悬浮聊天。复用服务端关注记录，取消关注后同步移除，仍受项目查看权限约束。本次界面与关注列表接口更新仅同步局域网调试机。

输入区后续优化：移除常驻的用户选择框，保留轻量图片/文件与 @ 工具按钮。输入 @ 时在符号上方显示候选用户，支持姓名筛选、方向键/Enter选择、鼠标选择和Esc关闭；选中的姓名插入正文，删除提及后不再发送对应提醒。桌面、小屏及原三账号聊天流程已通过浏览器回归，前端27项测试及构建预算检查通过。

局域网调试界面：`http://192.168.31.144:3000/annotation-details`。新前端已在该调试入口生效，未发布云端前端界面。

- 后端相关测试共50项通过，前端相关回归共27项通过；局域网完整构建及构建体积预算检查通过。
- 三账号浏览器联调通过：无需邀请直接发言、旁观实时接收、引用及撤回脱敏、关闭窗口后未读、中文输入法、发送超时重试去重、断线期间新增与撤回补齐、拖动边界与关闭重开、小屏布局。未发现页面脚本错误。
- 云端文件链路验证通过：经局域网上传20MB文本文件和图片，云端下载校验一致；撤回后新接口和旧附件地址均返回404，引用与收藏同步隐藏。专用测试数据及两份云端测试附件已清理。
- 最终兼容修复已部署：撤回时间统一按香港时区计算，保留既有工作流附件读取权限，并禁止将工作流附件重新绑定到聊天。
- 局域网后端通过 `XinshiDebugBackendInteractive` 重启，已检查交互式会话及实际UNC只读枚举。

用户已明确授权云端后端及附件配置更新。云端后端与两层Nginx附件配置已更新，服务正常；云端前端HTML校验值保持一致，未更新界面资产。

云端发布备份目录：`/home/ubuntu/apps/xinshi_system/backups/annotation-chat-20260924-071752`，保留源文件备份、更新包和前端HTML校验记录。原镜像保留为 `xinshi_prod-backend:before-annotation-chat-20260924-071752`、`xinshi_prod-frontend:before-annotation-chat-20260924-071752`。

回退注意：保留新增数据库表和列，不得用迁移前整库备份覆盖迁移后的业务写入。旧后端不具备撤回附件下载校验，不能直接回退后继续开放附件访问；如需回退，应同时保留该鉴权修复或临时关闭附件访问。数据库备份路径见上文。
