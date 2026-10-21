# 项目资料 Word 在线编辑

## 当前实现与边界

项目资料的 `.docx` 双击、回车和“在线编辑”统一打开 ONLYOFFICE 弹窗，系统新建和直接上传的 Word 使用同一会话流程。`.md`、`.txt` 沿用文本编辑器，其他格式保留下载；`.doc` 提示另存为 `.docx`。报价单与合同不开放编辑。Word 上限20MiB。

只有点击底部“保存文件／保存为新版本”才提交业务版本。Office 的内部保存、Ctrl+S、自动保存和关闭回调只产生临时文件；点击取消并确认后原资料不变。无修改地打开已有 Word 再保存，不额外产生空版本。业务保存与项目表单独立，不更新项目修改时间。

同一逻辑文件只有一个写会话，第二人及同一用户的第二个窗口只读查看最新已保存版本。只读内容不跟随另一人的未保存修改实时变化。上传新版、移除文件及项目删除也检查编辑锁。浏览器每30秒续租，120秒失联后会话失效；旧签名和迟到回调不能提交新版本。重新取得编辑权限需关闭后重新打开。

## 独立文档服务准备

ONLYOFFICE Docs 统一部署在云端 Linux，使用官方镜像并固定 digest；PC 和局域网 Windows 不安装文档服务，继续沿用现有 Python／Node 启动方式。云端部署叠加 `deploy/docker-compose.office.yml`，只重建所需服务，不重启 PostgreSQL 或其他业务容器。安装方式参考[官方安装指南](https://helpcenter.onlyoffice.com/docs/installation/docs-community-install-docker.aspx)；适用许可单独落实，不自动采购。

为文档服务准备独立 HTTPS 域名、受信任证书、持久化缓存、磁盘监控以及与实际 Word 文件匹配的中文字体。反向代理示例见 `deploy/onlyoffice-nginx.conf.example`，需要 WebSocket 和长连接。禁止开启公开测试示例或关闭 JWT 验证。

存储端配置（仅为变量说明，无真实密钥）：

```dotenv
ANNOTATION_OFFICE_ENABLED=false
ANNOTATION_OFFICE_SERVER_ORIGIN=https://docs.example.invalid
ANNOTATION_OFFICE_PUBLIC_ORIGIN=https://oa.example.invalid
ANNOTATION_OFFICE_JWT_SECRET=
```

- `SERVER_ORIGIN` 为浏览器和存储端均可访问的文档服务 HTTPS 地址，支持官方虚拟目录部署，如 `https://www.oa.xinshify.com.cn/office`。只允许普通目录名，禁止查询串、凭据和路径穿越。命令和回传文件从该地址获取；回传路径限制在对应目录下的 `/cache/files/`，不跟随重定向。
- `PUBLIC_ORIGIN` 为**资料存储端应用**的 HTTPS 来源，不含 `/api`。文档服务器须能够读取签名源文件并向此地址回调，不能填 PC 的 localhost 地址。
- JWT 密钥至少32字符，通过受保护环境提供，并与文档服务器 browser、inbox、outbox 签名配置保持一致。回调使用标准 Authorization Bearer 或回调体 token；不转发应用用户的登录令牌给文档服务。
- PC 的资料存储若为 remote，浏览器的 Office 控制请求使用原有登录凭据转发到存储端。PC 不保存 Office 文件，不需要配置文档服务密钥；PC 与存储端均需运行同一版本并同步启用 `ANNOTATION_OFFICE_ENABLED`，保证各端上传新版和删除都会检查共享数据库中的锁。上线窗口内暂停旧版本后端的资料写入，不能让未接入锁的旧服务继续修改同一资料库。

启用前显式执行 `data/migrations/20261021_annotation_office_sessions.sql`，可重复执行；启动不会自动建表。按项目约定先核对主机、目录、Git 提交和目标库，生产操作须有明确发布授权；本次实现未执行业务库迁移或生产部署。

## 应用代理、CSP 与日志

现有应用 Nginx 的 CSP 默认禁止加载外部编辑器。准备启用时，对**实际使用的应用站点配置**（根目录或 `frontend/nginx.conf`，PC HTTPS 为 `deploy/nginx-lan.conf`）增加精确来源：`script-src 'self' https://docs.example.invalid` 和 `frame-src 'self' https://docs.example.invalid`，替换成实际文档域名并保留其余安全指令；不要放开所有脚本来源。应用的 `frame-ancestors 'none'` 可以保留，文档站点则必须允许应用来源嵌入。

资料存储端的 `/api/projects/annotation/office/sessions/<id>/source` 和 `/callback` 使用带作用域及24小时有效期的签名 URL。Nginx 为这两个路径配置独立 location，沿用现有 `/api` 的 rewrite 与 proxy_pass，但设置 `access_log off`，不要在代理、错误采集或请求调试工具记录查询串、回调体或 JWT。应用已对 Uvicorn 的 Office URL 查询令牌脱敏。正常浏览器控制接口继续使用登录鉴权并保留审计能力。

回调校验文档服务 JWT、签名 URL、会话及文档 key；下载结果限制20MiB，并验证 OOXML 结构、解压大小和禁止宏。新会话与任务时间使用 timestamptz，响应为 `+08:00`；既有资料表继续使用其历史 UTC 存储语义，展示固定为 UTC+8。

## 接口与故障处理

浏览器接口均位于 `/projects/annotation`，由现有 `/api` 代理：

| 方法与路径 | 输入／用途 |
| --- | --- |
| POST `/{project_id}/office/sessions` | 已有文件 `{file_id}`；新建 `{name, folder_id?}` |
| GET `/office/sessions/{id}` | 状态、占用者、租约、保存任务状态和版本ID |
| POST `/office/sessions/{id}/heartbeat` | 续租，过期不能复活 |
| POST `/office/sessions/{id}/save` | `{save_id, revision}`，客户端UUID和本窗口的编辑序号 |
| POST `/office/sessions/{id}/discard` | 放弃未提交会话，已保存会话不受影响 |

创建响应包含 SDK 地址和签名后的编辑器配置。保存先持久化任务，再发 forcesave，并用 userdata 关联回调；回调提交版本和任务完成标记在同一事务中。调用方等待 `save_state=complete` 后才显示保存成功。命令超时先查任务；保存回调60秒未完成则允许重试。不同编辑序号的旧回调不能覆盖当前快照；forcesave 返回“没有新修改”时，存在修改的窗口必须取得匹配编辑序号的快照，不能把尚未到达的文件回调误判为保存成功。关闭 SDK 内置 forcesave，仅通过底部业务保存触发强制保存；文档服务也应保持自动强制组装功能关闭。

服务中断、保存冲突、回调失败时保留编辑器；未同步到 Office 服务时禁用提交，提交期间阻止继续编辑。浏览器关闭仍可能丢失未同步内容，发生提示时保持窗口打开并重试。临时文件复用资料暂存的24小时过期和删除重试队列；历史版本不会被清理。关闭功能开关保留已有数据，故障时可下载已保存文件，不自动使用 HTML 转换的 Word 编辑器。

## 验证与启用清单

本机隔离验证使用项目 `.venv`，不连接业务数据库：

```powershell
& .\.venv\Scripts\python.exe -m pytest tests/test_annotation_office.py tests/test_annotation_materials.py -q
Set-Location frontend
node --test tests/materialDocument.test.mjs tests/annotationMaterialFolders.test.mjs
node node_modules/vite/bin/vite.js build --outDir ../.tmp/office-build
node tools/check-build-budget.mjs --dist-dir ../.tmp/office-build
Set-Location ..
& .\.venv\Scripts\python.exe tools/verify_annotation_material_editor_ui.py
```

独立构建目录避免覆盖在用 dist。浏览器脚本使用该构建结果、专用12420端口及模拟 API／SDK，不启动业务后端；报告保存于 `.tmp/material-editor-ui/report.json`。PostgreSQL 专项须提供本机隔离测试实例，不能使用业务连接。

真实服务就绪后还须执行：

1. 浏览器加载 SDK 和 iframe；验证 HTTPS、CSP、WebSocket；从文档服务器读取签名源文件并回调存储端，从存储端访问文档服务 healthcheck、命令和回传地址。无效签名、过期URL及跨项目访问必须失败。
2. 在隔离库／存储中上传现成 Word，保存项目，双击编辑、保存新版、下载并重新打开；再验证新建 Word 的完整流程和另一账号只读。
3. 使用含中文字体、页眉页脚、页码、分节、横向页面、图片、合并表格、批注和修订的代表文件，检查打开、编辑和下载结果。仅打开或取消时原文件 SHA-256 不变。记录实际不兼容项，不能以模拟 SDK 测试宣称排版通过。
4. 验证故障重试、回调重复和迟到、锁过期、浏览器重开、弹窗拖拽边界／复位、小屏 Office 界面及固定底部操作。
5. 确认许可证、备份、迁移、网络、字体与所有验收通过后，按单独发布流程启用开关；未满足条件保持关闭。

最初接入时未配置真实文档服务，下方本机记录为模拟验收；云端部署后的真实验收单独记录，不能混用。

### 云端共用服务运维

两端文件、业务版本和会话锁均以云端为准。局域网使用 remote 资料存储，只启用开关，不配置 Office JWT 密钥。当前入口为 `https://www.oa.xinshify.com.cn/office/`，复用现有可信证书；网关根据官方虚拟目录代理示例透传 `X-Forwarded-Host` 和 WebSocket，不需要额外公网端口或 DNS 记录。

云端启动文档服务：

```bash
sudo docker-compose --env-file .env -f deploy/docker-compose.cloud.yml -f deploy/docker-compose.cloud.local.yml -f deploy/docker-compose.office.yml up -d --no-deps onlyoffice
```

`ANNOTATION_OFFICE_IMAGE` 应固定验收通过的版本和 digest。JWT 在受保护的云端 `.env` 中生成，保持与文档服务一致，不在终端或日志输出。文档缓存、日志、配置、内部数据库及附加字体使用持久卷；仅 Office 内部自动保存不会生成业务版本。Noto CJK 字体用于中文回退；未安装的商业字体不能视为已匹配。

项目资料组件在当前项目处于打开且页面可见时每5秒拉取最新资料，切回窗口立即刷新；后台页面暂停请求，组件关闭后注销监听并取消未完成请求。静默刷新不覆盖待保存上传、移除标记或新目录；资料版本变化时关闭旧历史列表，重新打开获取新版本。两端编辑锁始终由云端 PostgreSQL 事务和唯一索引控制，不依赖刷新周期。

启用前先备份数据库、两端 `.env` 和实际 Nginx 配置，再显式执行 Office 两表迁移；`LOCAL_SCHEMA_MIGRATIONS_ENABLED` 始终为 false。回滚先关闭所有端的 Office 开关，再恢复备份的应用镜像／静态资源及代理配置；保留 Office 表、资料和历史版本，不执行 DROP TABLE，不移除持久卷。

### 本机验收记录（2026-10-21）

- 后端 Office、资料、标注项目及子订单相关回归83项通过，26项因缺少隔离 PostgreSQL 等前置条件跳过；包含新增的跨连接租约专项，未将 SQLite 测试视作 PostgreSQL 行锁验收。
- 前端文档、目录和业务时区专项17项通过，独立完整构建及体积预算通过。
- 编辑器34项、资料浏览器27项模拟浏览器验收通过，页面脚本错误均为0。覆盖真实页面中的上传文件、保存项目、双击编辑、保存新版、只读、取消、重试、下载、拖拽、位置复位及小屏固定底部；ONLYOFFICE SDK 与接口使用模拟实现。
- 未修改业务数据库、真实资料或生产服务，临时预览进程已停止。尚未验证真实 Office 引擎的排版、网络和字体兼容性。
