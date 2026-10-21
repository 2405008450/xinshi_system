# 项目资料 Word／Excel 在线编辑

## 当前实现与边界

项目资料的 `.docx`、`.xlsx` 双击、回车和“在线编辑”统一打开 ONLYOFFICE 弹窗，系统新建和直接上传的文件使用同一会话流程。Word 使用 `documentType=word`，Excel 使用 `documentType=cell`。`.md`、`.txt` 沿用文本编辑器，其他格式保留下载；旧 `.doc`、`.xls` 提示另存为 `.docx`、`.xlsx`，不开放宏或二进制 Excel 格式。报价单与合同不开放编辑。Word、Excel 上限均为20MiB。

在线编辑标题栏提供“最大化／还原”按钮，Word、Excel、Markdown、文本和只读查看均支持。大屏布局保留16px视口边距，底部操作固定；还原后可继续拖动，每次重新打开默认小窗。该能力由公共 `DraggableFormDialog` 的可选 `maximizable` 属性提供，切换只调整布局，保留正文节点、Office iframe、编辑会话和未保存内容；未接入该属性的其他弹窗保持原行为。

只有点击底部“保存文件／保存为新版本”才提交业务版本。独立页 Ctrl+S／Command+S 与页面保存按钮使用同一业务保存流程；Office 自动保存和关闭回调只产生临时文件；点击关闭／取消并确认只放弃上次业务保存后的修改，已保存版本保留。无修改地打开已有 Word／Excel 再保存，不额外产生空版本。业务保存与项目表单独立，不更新项目修改时间。

Excel 扩展复用既有 Office 会话、保存任务与租约表，不增加迁移或配置项。服务按文件扩展名校验主部件、OOXML 类型及工作表关联，源文件与回调结果必须匹配；拒绝加密、宏、重复 ZIP 部件、超限解压及损坏工作表。Excel 新版仍写入既有云端资料存储，浏览器不会将工作簿转换为 HTML 后保存。公式、图表和复杂 Excel 功能的兼容性以代表样本实测为准。

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
| POST `/office/sessions/{id}/discard` | 关闭当前会话并释放编辑锁，保留已提交版本 |

创建响应包含 SDK 地址和签名后的编辑器配置。保存先持久化任务，再发 forcesave，并用 userdata 关联回调；回调提交版本和任务完成标记在同一事务中。调用方等待 `save_state=complete` 后才显示保存成功。命令超时先查任务；保存回调60秒未完成则允许重试。不同编辑序号的旧回调不能覆盖当前快照；forcesave 返回“没有新修改”时，存在修改的窗口必须取得匹配编辑序号的快照，不能把尚未到达的文件回调误判为保存成功。关闭 SDK 内置 forcesave，通过页面业务保存按钮或独立页快捷键触发强制保存；文档服务也应保持自动强制组装功能关闭。

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

### 云端与局域网真实服务验收（2026-10-21）

用户明确授权后完成云端部署和 Office 专项迁移，两端开关启用。ONLYOFFICE 使用官方 Community 镜像10.0.0.1，固定 digest `sha256:ca17889f10b11141cc6441836aebdd2835cf3e1b49681b2fd6e155c94b7850b3`；云端通过现有 HTTPS 网关 `/office/` 提供服务，未增加公网端口。资料及 Office 会话统一落在云端；JWT 只写入云端受保护 `.env`，局域网不保存此密钥。两个新表时间列核对为 `timestamp with time zone`，常驻服务仍关闭自动迁移。

本机 `.venv` 执行隔离后端回归84项通过、26项因未提供隔离 PostgreSQL 等条件跳过；前端专项17项通过，完整构建及预算通过。模拟浏览器验收37项编辑器、27项资料浏览器通过，无页面脚本错误。模拟结果与下方真实服务结果分别保存。

真实验收使用专用项目“【Office专项验收】云端与局域网共用编辑服务”和两个临时仅有项目权限的账号，未编辑现有业务资料。本机 Edge 浏览器分别访问云端及局域网正式 HTTPS 页面，使用真实 SDK、WebSocket、文件读取、强制保存命令及回调，没有模拟 Office 或业务接口。主要验收结果：

- 通过页面上传现成 Word、保存项目、双击打开编辑器，实际键入正文并保存为新版本；下载新文件包含输入内容，原版本 SHA-256 不变。
- 云端先编辑时局域网只读；反向同样成立。同一用户另一窗口只读；四个跨两端并发会话严格只有一个写权限。只读窗口无保存按钮，直接调用保存接口也被拒绝。
- 云端与局域网分别保存后，另一端已打开的资料窗口自动获取新版本，无需手动刷新。保存释放锁后，另一端重新打开能取得写权限。
- 新建 Word、真实输入、保存文件后，另一端能自动看到并双击重新编辑；仅打开再取消不新增版本。
- 样本含中文、页眉页脚、PAGE 页码、横向分节、图片、合并表格、批注及修订。真实编辑页面正常显示；下载文件检查保留上述 OOXML 结构与实际修改。中文回退字体使用 Noto CJK；未安装的商业字体和其他任意复杂文档仍须单独验收，不承诺与桌面 Word 像素一致。
- 局域网重启后后端与 explorer 同属 Session 1，并在同一交互式任务上下文成功枚举两个实际 UNC 共享根目录；临时检查任务已删除。

真实验收报告及截图位于本机 `.tmp/office-live/`（`live-report.json`、`extra-report.json`、`lan-unc-result.json`），部署前数据库与配置备份位于两端 `backups/releases/office-live-*`。回滚保留资料、版本和 Office 表及持久卷。Community 适用许可继续按官方条款落实，本次未采购商业授权。

### XLSX 扩展真实验收（2026-10-21）

云端和局域网同步发布 XLSX 扩展，复用现有 Office 配置、服务和数据库表，无新增结构迁移；自动迁移保持关闭。隔离后端相关回归87项通过、26项因隔离 PostgreSQL 等条件跳过，前端单元测试17项通过，完整构建和预算通过。模拟编辑器46项、资料浏览器27项通过。

真实浏览器核心验收26项、补充回归9项通过，使用专用验收项目及两个临时账号，无现有业务文件修改：

- 从项目页面上传包含两个中文工作表、公式、跨表引用、合并单元格、冻结窗格、数字格式和图表的真实 `.xlsx`，保存项目后双击进入 Excel 编辑器。
- 云端将数量10改为12，下载文件中单行金额正确重算为150，总额及第二工作表引用重算为182；局域网再将另一项单价8改为10，两端可下载到总额190的新版。保留公式、图表、合并单元格、冻结窗格及数字格式，原上传版本 SHA-256 不变。
- 两端双向编辑互斥；只读窗口无业务保存入口，保存接口拒绝只读提交。同一用户另一窗口只读，四个跨端并发会话严格只有一个写权限。
- 两端保存后另一端自动刷新；历史版本、独立下载、最大化／还原、未保存内容保留、小屏固定操作栏以及重新打开后取消不新增版本均通过。
- 系统新建 Excel、实际输入、保存及从局域网重新打开通过；XLSX 发布后原 Word 真实编辑器仍能正常打开。

真实结果保存在本机 `.tmp/office-xlsx/real-report.json`、`smoke-report.json`、下载文件及截图中。局域网后端与桌面同属 Session 1，在同一交互式任务中验证两个实际 UNC 共享根目录成功。临时验收账号用后停用，专用已结束项目保留表格以便复核。Excel 复杂功能兼容性以实际样本为准，未扩展 `.xls`、`.xlsm`、`.xlsb` 或报价单／合同编辑范围。


### 独立编辑页面

项目资料的 Word／Excel 双击、回车、工具栏和菜单“在线编辑”，以及新建 Word／Excel，统一打开同源的新标签页 `/annotation-office`。页面不加载项目侧栏或资料弹窗，编辑区域占满页面宽度，中间文档区域随视口伸展，底部操作固定可见。原文件菜单保留“小窗编辑”及其最大化／还原能力；文本和 Markdown 沿用原小窗。

新页面只从地址读取项目、文件或新建类型／目录标识，通过已登录会话重新读取资料及申请 Office 会话；地址和跨标签页通知不携带登录令牌、文档签名或正文。打开后切断 opener，来源资料窗口关闭或导航不会关闭编辑器。不同标签页仍分别申请会话，包含同一账号的第二个标签页，均遵循云端独占编辑锁。

独立页“保存为新版本”完成后只显示成功提示，保留当前文档、编辑器节点、文档 key 和写租约，不跳转结果页或重新加载。服务端将提交的版本设为下次保存的基础版本；再次修改可连续保存新版本。新建文档首次保存后原编辑器转为编辑已有文件，并更新地址中的文件标识，刷新页面不会重新进入新建流程。无新修改时保存按钮禁用，服务端也拒绝重复生成相同修订的版本。失败保留当前编辑现场。取消及应用内导航在有修改时确认放弃，刷新／关闭标签页使用浏览器原生未保存确认。实际离开页面时用携带登录请求头的 keepalive 请求释放会话，断网等情况下仍由120秒租约兜底。保存中离开不主动撤销正在提交的保存任务。

同源页面保存通过 BroadcastChannel 通知来源资料列表刷新；跨云端／局域网域名继续使用既有5秒轮询及焦点刷新。通知只携带项目标识，列表重新读取权限范围内的资料。

本次仅修改前端，不新增数据库迁移、环境变量或文档服务配置。独立页模拟验收命令：

```powershell
& .\.venv\Scripts\python.exe tools/verify_annotation_office_page_ui.py
```

使用隔离前端预览12421端口，模拟 API 与 SDK；报告及截图在 `.tmp/office-page-ui/`。原编辑器小窗回归使用 `tools/verify_annotation_material_editor_ui.py`，通过明确的“小窗编辑”入口测试。


独立页于2026-10-21同步发布到云端和局域网，运行前端代码提交 `f0e4110`，不修改后端、数据库结构、开关或文档服务；两端保留旧哈希资源供已打开的页面继续使用。前端17项单元测试、完整构建及预算检查通过；独立页26项、原编辑器46项、资料浏览器27项模拟检查通过，均无页面脚本错误。

两端真实浏览器验收23项及补充回归4项通过：Word在云端独立页实际输入并保存至V4，Excel在局域网独立页实际修改数量并保存至V4，下载后正文／单元格和跨表公式重算均正确，原版本字节不变。双向跨端以及同账号另一标签页均只有一位编辑者；保存后列表自动刷新，直接关闭干净标签页的keepalive释放锁后另一端可立即编辑。80%／125%界面缩放仍铺满视口，大屏和小屏底部操作始终可见；原Excel小窗拖动、最大化和还原通过，补充浏览未增加版本。

真实报告在本机 `.tmp/office-page/real-report.json`、`smoke-report.json`，截图含 `word-full-page.png` 和 `xlsx-standalone.png`。仅使用既有专项验收项目，未修改其他业务资料；两个临时验收账号已停用，活动专项编辑会话为0，临时凭据已删除。前端回滚备份分别位于云端 `backups/releases/office-page-20261021-161455+0800` 和局域网 `backups/releases/office-page-20261021-161520+0800`；本次不需要数据库回滚。


### 连续保存与编辑锁

独立页每次保存成功后保持 `state=open`，更新基础版本、源文件和最近保存版本，清空旧暂存快照；保存任务仍独立持久化并标记完成。已完成任务的重复／迟到回调不能进入下一轮保存；同修订序号的无变化保存不追加版本，也不能降低已提交的修订计数。相同编辑器内修订序号单调递增，保存失败、版本冲突与租约过期继续按既有规则处理。

保持页面打开并续租时，另一端和同账号其他标签页继续只读；关闭编辑器／标签页或租约过期才释放编辑锁。小窗仍保持原有保存后关闭的交互，并在关闭时释放会话。每轮保存均通知同源资料列表刷新，云端／局域网不同域名通过既有5秒刷新和窗口焦点刷新获取新版本；未保存的项目表单内容保留。

本次使用既有会话与保存任务字段，无新增数据库结构迁移或 Office 配置。部署只需更新云端业务后端和两端前端；局域网 remote 控制接口原样转发到云端，无新增接口，因此代理后端无需重启。


连续保存于2026-10-21同步发布，运行代码提交 `6f90bda`。云端业务后端更新并通过数据库健康检查，文档服务未重启；局域网前端和源码同步，保留既有 remote 代理进程。无数据库迁移，自动迁移仍关闭。发布前数据库、配置和镜像备份位于云端 `backups/releases/office-continuous-20261021-165816+0800`，局域网前端备份位于 `backups/releases/office-continuous-20261021-165851+0800`。

隔离后端回归91项通过、26项因隔离PostgreSQL等条件跳过；前端17项单元测试、完整构建及预算通过，独立页27项与原编辑器46项模拟检查通过。真实验收涵盖Word同一编辑器连续保存两轮至V6，Excel同一编辑器连续保存两轮至V7并保留选中单元格，新建Excel首次保存更新地址后继续原地保存至V2；每轮两端列表自动刷新，保持写租约期间跨端只读，关闭才释放锁。下载内容和重算值正确，初始版本字节不变；无修改保存不追加版本，保存后继续修改再放弃保留最后已保存版本。

真实报告和截图位于本机 `.tmp/office-continuous/`（`real-report.json`、`word-after-two-saves.png`、`excel-after-two-saves.png`）。仅操作既有已结束专项验收项目；两个临时账号已停用，活动专项会话为0，临时凭据已删除。


### 独立页快捷保存与顶部操作

独立页右上角以24px高的“保存”小按钮代替底部保存栏，按钮的辅助名称仍为“保存为新版本／保存文件”，标题提示Ctrl+S；关闭和当前保存状态也移至固定顶部。底部不再保留占位，小窗继续沿用原有底部操作。Ctrl+S和Command+S与顶部按钮共用业务保存入口，成功后继续原文档、保留写租约，并通知两端资料列表更新。无修改、只读、过期、未就绪和保存中均不会重复提交；同步中触发快捷键会等待同步，超时明确提示重试。

跨域编辑器的按键不会冒泡到业务页面。云端网关只在Word／Excel主入口HTML注入自有静态脚本 `/office-save-bridge.v1.js`；不修改ONLYOFFICE安装目录、不启用SDK内置forcesave，也不添加新的回调提交途径。脚本与父页面通过精确origin、当前iframe窗口和每轮随机nonce握手，仅传递保存意图。桥不会读取或传输正文、登录凭证或Office签名。原生编辑器仍处理按键，以提交正在输入的单元格；业务页面随后等待SDK同步完成，再调用原有强制保存接口。

更新云端实际挂载的 `deploy/nginx-gateway.cloud.local.conf` 时须合并 `deploy/nginx-cloud-gateway.conf` 中两项map和Office代理的三项转发／替换设置；保留原配置差异，先 `nginx -t` 后reload。HTML上游禁用压缩以支持注入，其他资源保持原压缩协商。脚本文件名包含版本号，后续修改桥脚本应更换文件名并同步引用，以兼容静态资源长期缓存。局域网仍访问云端同一编辑器，无需修改局域网代理、重启后端或迁移数据库。仅新增快捷键监听到外层页面不足以完成此功能，必须同步云端网关注入配置。

官方原生快捷键见[ONLYOFFICE键盘快捷键](https://helpcenter.onlyoffice.com/docs/userguides/document_editor/keyboardshortcuts.aspx)，强制保存的协议继续沿用[官方保存机制](https://api.onlyoffice.com/docs/docs-api/get-started/how-it-works/saving-file/)。浏览器专项模拟命令为 `.\.venv\Scripts\python.exe tools/verify_annotation_office_shortcut_ui.py`，使用独立12422端口和真实跨域iframe但模拟SDK／业务接口；报告在 `.tmp/office-shortcut-ui/`，不得等同真实编辑引擎验收。


快捷键和顶部操作于2026-10-21同步发布，运行前端代码 `65ea8b8`；云端实际网关配置已合并并通过 `nginx -t` 后热加载。仅更新两端静态前端及云端网关配置，未重启业务后端或ONLYOFFICE，不执行数据库迁移。备份分别位于云端 `backups/releases/office-shortcut-20261021-171721+0800` 和局域网 `backups/releases/office-shortcut-20261021-171756+0800`；网关reload完成后检查两个真实编辑器入口均只注入一次桥脚本。

21项前端单元测试、完整构建与预算通过；独立页27项、原编辑器46项、跨域快捷键18项模拟检查通过。真实验收验证正文内Ctrl+S、单元格尚未按回车时Ctrl+S、重复快捷键仅保存一次、顶部小按钮连续保存、编辑现场与写租约保留、两端列表同步、只读禁止提交和大小屏操作可见。文档复制自既有专项样本，均生成两个新业务版本，下载文件包含实际输入和正确重算结果。

本轮发现既有样本正由其他用户编辑，保持其写锁并改用两份唯一命名的“快捷键隔离验收”副本，未改变其他用户的会话或文件。真实报告、截图及副本名称在本机 `.tmp/office-shortcut/`；临时验收账号已停用，活动专项会话为0，临时凭据已删除。正在打开的旧页面需重新打开编辑页后使用新快捷键。
