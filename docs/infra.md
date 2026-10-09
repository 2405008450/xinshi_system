# 项目环境与操作边界

## 环境清单

| 环境 | 地址 | SSH 端口 | 登录用户 | 用途 |
| --- | --- | --- | --- | --- |
| 本机开发、部署与验收环境 | 主机名 `PC`；项目 `E:\xinshi_system` | 不需要 SSH | 本机已登录桌面用户 | 源码编辑、项目运行、完整构建、数据库迁移、自动化测试和浏览器验收 |
| 旧局域网服务器 | `192.168.31.144` | `22` | `Administrator` | 不再作为默认部署或验收机器；原有服务仅按明确的维护需求操作 |
| 云端生产环境 | `43.132.156.72` | `22` | 以云端实际账号为准 | 线上正式服务，仅执行经过确认的发布、回滚和运维操作 |

## 默认工作流

1. 在本机 `PC` 的 `E:\xinshi_system` 修改代码，并核对主机名、项目目录和 Git 提交。
2. 直接在本机配置依赖、部署运行、完整构建、自动化测试和浏览器验收，不再要求先同步到旧服务器或通过 SSH 执行。
3. 后端直接使用根目录现有 `.venv\Scripts\python.exe`，前端使用本机 Node.js/npm；缺少依赖时安装到该 `.venv`，不要求创建 Conda 环境，不能回退到旧服务器或其他 Python。数据库迁移前核对目标并备份，自动化回归继续使用隔离测试库。
4. 本机验证通过后形成待发布版本；没有用户明确的发布指令时，不得连接或修改云端生产环境。
5. 发布到 `43.132.156.72` 前必须备份数据库，核对环境变量和迁移清单，并保留可回滚版本。

## Coding Agent 执行约束

- 当前 PC 性能已升级，源码编辑、项目运行、完整构建、完整测试和浏览器联调均默认在本机执行，不再适用“开发机只做源码编辑与轻量检查”的限制。
- 本机采用根目录 Python 虚拟环境 `.venv` 和原生 Node.js/npm，不使用 Docker，不得使用 `docker compose` 启停或验证本机环境。
- 后端运行、迁移及 Python 测试固定使用 `E:\xinshi_system\.venv\Scripts\python.exe`，不得误用系统 Python 或其他虚拟环境。
- 后端依赖交互式 Windows 登录会话中的 SMB 凭据读取 `\\Win-server` 共享目录。本机在已登录桌面会话中可以直接启动，必须验证进程 SessionId 和同一上下文的实际 UNC 目录枚举；非桌面上下文须检查并使用本机 Interactive 计划任务。禁止使用 WMI/CIM、Windows 服务或其他 Session 0 启动方式。
- 本机和远程变更命令都必须先确认主机名、项目目录、Git 提交及目标数据库，避免在错误环境执行。工具脚本的默认允许主机为 `PC`，项目路径、隔离目录、测试库名及专用端口限制继续保留；迁移和结构克隆入口只允许连接 `localhost` 或 `127.0.0.1` 数据库。
- 本机调试入口为 `http://localhost:3000/`，后端为 `http://127.0.0.1:8000/`；同一轮验收保持同一前端来源，避免混用 localhost、IP 与域名。
- 生产构建验收使用本机构建后的静态资源及同源 `/api` 代理；HTTPS、证书、安全响应头、Cookie 和 `wss` 的部署验收仍需本机 HTTPS 入口，Vite 开发页面不能替代这些检查。
- 旧服务器的员工入口、DNS、证书、计划任务和业务数据库不会因默认执行机调整而自动迁移；仅在明确维护旧服务器时使用下方保留的远程步骤。
- 云端 `43.132.156.72` 是生产环境。除非用户明确要求发布或运维，否则只能进行必要的只读核查，不得部署、迁移、重启或修改数据。

## 本机启动与验收

当前 PC 日常服务连接已确认的 `43.132.156.72:15432/xinshi_system`；后端运行在 PC，数据库位于云端。启动不会重建数据库或执行结构迁移；生产部署、数据库迁移及维护性数据修改仍需要单独明确指令。

### 只读检查

在已登录桌面的 PowerShell 中执行统一检查入口：

```powershell
Set-Location -LiteralPath 'E:\xinshi_system'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\deploy\start_local.ps1 -CheckOnly
```

入口核对主机 `PC`、固定项目目录、Git 提交、项目 Python、数据库地址/端口/库名、基础依赖、当前进程与 `explorer.exe` 的非零 SessionId、实际 UNC 目录只读枚举、Node/npm、前端依赖和端口。检查不连接数据库，不启动或停止服务；已有监听会显示 PID。数据库配置中进程环境变量优先于根目录 `.env`，`DATABASE_URL` 优先于 `DB_*`，输出不含用户名或密码。常驻服务必须关闭 `LOCAL_SCHEMA_MIGRATIONS_ENABLED`。

2026-10-09 已核实 Python 3.13.7、Node.js 22.22.0 和 npm 10.9.4。缺少依赖时安装一次，依赖变更后重新安装，不必每次启动都运行：

```powershell
Set-Location -LiteralPath 'E:\xinshi_system'
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
# 需要 Python 测试依赖时：
& '.\.venv\Scripts\python.exe' -m pip install -r requirements-dev.txt
Set-Location -LiteralPath 'E:\xinshi_system\frontend'
npm.cmd ci
```

不得自动创建或改用其他 Python 环境。凭据使用受保护的 `.env`，不纳入 Git，不能直接使用 `.env.example` 的示例凭据。

UNC 检查优先读取有效配置中的 `OPENPATH_ALLOWED_ROOTS`；未配置时检查 `\\Win-server\服务器资料7` 和 `\\Win-server\服务器资料4`。这是权限检查，不自动修改业务白名单。其他业务目录可在分终端启动后端时通过 `-SharePath '\\server\share'` 指定。手工复核命令如下：

```powershell
(Get-Process -Id $PID).SessionId
Get-Process -Name explorer | Select-Object Id, SessionId
Get-Item -LiteralPath '\\Win-server\服务器资料7' -ErrorAction Stop
Get-ChildItem -LiteralPath '\\Win-server\服务器资料7' -ErrorAction Stop | Select-Object -First 1
Get-Item -LiteralPath '\\Win-server\服务器资料4' -ErrorAction Stop
Get-ChildItem -LiteralPath '\\Win-server\服务器资料4' -ErrorAction Stop | Select-Object -First 1
```

### 一键启动

```powershell
Set-Location -LiteralPath 'E:\xinshi_system'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\deploy\start_local.ps1
# 后端需要热重载时，可在上述命令末尾加 -Reload
```

也可双击根目录 `start_local.bat`。入口检查通过后，在同一桌面会话通过 `Start-Process -WindowStyle Hidden` 创建两个子终端。它会等待页面、`/health/db`（只执行 `SELECT 1`）及前端 `/api/health/db` 均通过，再核对监听进程属于本轮启动且 SessionId 相同。访问 `http://localhost:3000/`，后端为 `http://127.0.0.1:8000/`；前后端只绑定回环地址。

每轮日志分别保存到 `logs/backend-*.out.log`、`logs/backend-*.err.log`、`logs/frontend-*.out.log` 和 `logs/frontend-*.err.log`。输出含本轮终端 PID、监听 PID 与停止命令。关闭一键启动窗口不会停止隐藏服务；确认没有进行中的业务操作后，使用本轮输出的 `taskkill.exe /PID <终端PID> /T /F` 分别停止前后端进程树。停止前重新核对 PID，不能复用历史 PID 或按所有 Python/Node 进程批量终止。需要通过 `Ctrl+C` 正常退出时，使用下方分终端调试方式。

端口被占用时入口报错并显示 PID，不自动终止已有服务。Vite 启用 `strictPort`，不会悄悄切换到其他端口。启动失败只回收本轮创建的子进程树。

### 分终端调试

分别在两个已登录桌面会话的终端执行，日志直接显示在终端，`Ctrl+C` 停止对应服务。

终端 1 启动后端：

```powershell
Set-Location -LiteralPath 'E:\xinshi_system'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\deploy\start_local.ps1 -Service Backend -Reload
```

稳定运行去掉 `-Reload`；桌面上的 `start_backend.bat` 也复用此入口。

终端 2 启动前端：

```powershell
Set-Location -LiteralPath 'E:\xinshi_system'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\deploy\start_local.ps1 -Service Frontend
```

`frontend/start_frontend.bat` 同样复用此入口。开发代理支持 `/api` 与 WebSocket，默认目标为 `http://127.0.0.1:8000`；前端 `.env.local` 如配置 `VITE_API_PROXY_TARGET`，应核对其仍为本机目标。

分终端启动后，在第三个相同桌面会话的终端执行：

```powershell
Invoke-RestMethod 'http://127.0.0.1:8000/health/db'
Invoke-RestMethod 'http://localhost:3000/api/health/db'
(Invoke-WebRequest 'http://localhost:3000/' -UseBasicParsing).StatusCode
Get-NetTCPConnection -State Listen | Where-Object LocalPort -in 3000,8000 |
    Select-Object LocalAddress,LocalPort,OwningProcess
Get-NetTCPConnection -State Listen | Where-Object LocalPort -in 3000,8000 |
    Select-Object -ExpandProperty OwningProcess -Unique |
    ForEach-Object { Get-Process -Id $_ | Select-Object Id,ProcessName,SessionId }
Get-Process explorer | Select-Object Id,SessionId
```

两个健康接口应返回 `status=ok`，页面返回 200。实际页面仍需浏览器验收，健康接口不能替代业务验收。

### 非桌面上下文与构建验收

当前上下文无法继承交互式凭据时，先用 `quser` 确认 `Administrator` 活动会话，再核对本机 `XinshiDebugBackendInteractive` 的主体、`LogonType=Interactive` 和 Actions。任务应调用 `deploy/start_backend_interactive.ps1`，PC 分支复用本机启动检查并记录 `logs/backend-interactive-startup.log`。任务不存在或配置不符时停止并报告，不自动创建 Session 0 服务。2026-10-09 核查时本 PC 未配置该任务，已登录桌面可直接启动。

完整构建使用 `npm.cmd run build`。如果本机 Nginx 正在服务 `frontend/dist`，改用现有两阶段发布脚本 `frontend/tools/publish-lan-frontend.ps1`，不能在服务中的目录直接构建。

启动后确认本机页面和接口可访问、8000 端口进程使用项目 Python，且其 SessionId 与启动所在桌面会话的 explorer.exe 一致。共享目录须在后端相同交互式上下文中只读枚举；其他登录上下文里的 `Test-Path` 不能代替该验证。自动化测试继续使用隔离数据库、专用端口及测试目录。

本机 HTTPS 未配置时先通过 localhost 完成普通功能联调；部署验收需先配置本机静态资源、HTTPS 和同源代理，并核对域名解析指向本机，不得将旧服务器页面记为本机验收结果。

## SSH 建议配置

以下仅供明确维护旧服务器或云端时使用；本机工作流不需要 SSH。在用户级 SSH 配置中维护别名（不要提交包含私钥或密码的文件）：

```sshconfig
Host xinshi-lan
    HostName 192.168.31.144
    User Administrator
    Port 22
    IdentityFile ~/.ssh/xinshi_lan_ed25519

Host xinshi-prod
    HostName 43.132.156.72
    User <云端实际用户>
    Port 22
    IdentityFile ~/.ssh/xinshi_prod_ed25519
```

首次配置局域网机器时，可用管理员密码完成公钥安装；后续统一使用：

```powershell
ssh xinshi-lan
```

## 凭据安全

- 局域网登录密码属于敏感凭据，不写入 `infra.md`、脚本、`.env`、Git 提交或终端历史。
- 用户本次提供的密码仅作为首次建立密钥认证的引导凭据；完成后应更换密码，并关闭不必要的密码登录能力。
- 局域网与云端必须使用不同密钥和不同凭据，禁止复用生产密钥。
- 应限制 `192.168.31.144` 的 SSH、数据库和调试端口只允许受信任局域网访问。

## 企业共享路径白名单

- `OPENPATH_ALLOWED_ROOTS` 是后端允许保存的企业 UNC 根目录白名单，只进行路径规范化、根目录边界和危险扩展名校验；不会探测目录是否存在，也不要求云服务器能够连接 SMB。
- `VITE_OPENPATH_ALLOWED_ROOTS` 是前端构建期的“打开路径”白名单。两项配置应保持一致，当前统一值为 `\\Win-server\服务器资料7;\\Win-server\服务器资料4`。
- 云端配置上述目录只代表允许保存这些逻辑路径，不挂载共享盘、不配置 SMB 凭据，也不改变云服务器的网络边界。实际打开或读取仍由具备局域网权限的 Windows 客户端或局域网交互式后端完成。
- 修改 `OPENPATH_ALLOWED_ROOTS` 后需要重新创建后端进程或容器；修改 `VITE_OPENPATH_ALLOWED_ROOTS` 后必须重新构建并发布前端静态资源。
- 白名单必须配置到共享根目录层级，不得为了兼容保存而允许任意 UNC 主机；路径穿越和可执行文件、脚本、快捷方式仍应被拒绝。

## 旧服务器远程验证基线

仅在明确维护旧局域网服务器时，先执行以下只读检查：

```powershell
ssh xinshi-lan 'powershell -NoProfile -Command "$env:COMPUTERNAME; Set-Location -LiteralPath ''E:\xinshi_system''; (Get-Location).Path; git rev-parse --short HEAD; & ''.\.conda_env\python.exe'' -c ''import sys; print(sys.executable)''"'
```

确认输出来自 `192.168.31.144`、项目目录为 `E:\xinshi_system` 且提交版本正确后，再执行构建或部署命令。生产环境不得复用调试机命令或调试用环境变量。

## 局域网启动方式

以下为旧服务器 `192.168.31.144` 的保留操作记录，不用于本机默认部署与验收。本机需通过交互式任务启动时，须先确认本机存在该任务，并执行相同的活动会话、任务主体、Interactive 登录类型、SessionId 与 UNC 验证规则。

后端使用项目已配置好的 Conda 环境。服务器本机人工启动时，可以在已登录的 `Administrator` 桌面会话中执行：

```powershell
Set-Location -LiteralPath 'E:\xinshi_system'
& '.\.conda_env\python.exe' -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

旧服务器使用上方显式 Conda 命令；仓库中的批处理入口现在仅用于 PC。

Coding Agent 通过 SSH 远程重启时，不得直接执行上述 Uvicorn 命令，也不得使用 WMI、CIM 或 `Start-Process` 创建后台进程。必须先确认交互式会话与计划任务：

```powershell
quser
Get-ScheduledTask -TaskName 'XinshiDebugBackendInteractive' |
    Select-Object TaskName, State, @{Name='UserId'; Expression={$_.Principal.UserId}}, @{Name='LogonType'; Expression={$_.Principal.LogonType}}
```

只有在 `Administrator` 控制台会话处于活动状态，且任务的 `LogonType` 为 `Interactive` 时，才允许停止经过命令行校验的旧 Uvicorn 进程并执行：

```powershell
Start-ScheduledTask -TaskName 'XinshiDebugBackendInteractive'
```

重启验收必须同时满足：

1. 8000 端口返回 HTTP 200；
2. 监听进程使用 `E:\xinshi_system\.conda_env\python.exe`；
3. 监听进程的 `SessionId` 与 `explorer.exe` 的 `SessionId` 一致，当前应为交互式控制台会话而不是 Session 0；
4. 使用 `LogonType=Interactive` 的临时只读计划任务，在同一会话中对实际 `\\Win-server` 业务目录执行 `Get-Item` 和一次 `Get-ChildItem`，验证完成后删除临时任务和结果文件。

SSH 自身属于另一个登录会话。在 SSH 终端中直接执行 `Test-Path \\Win-server\...` 得到成功或失败，都不能证明后端进程拥有相同的共享目录权限。如果交互式会话不存在、任务配置不符或共享目录验收失败，应保持服务停止或恢复原交互式任务状态并向用户报告，不得回退到 Session 0 启动。

前端开发入口使用：

```powershell
Set-Location -LiteralPath 'E:\xinshi_system\frontend'
npm run dev -- --host 0.0.0.0 --port 3000
```

调试访问地址为 `http://192.168.31.144:3000/`，后端为 `http://192.168.31.144:8000/`。

局域网日常使用入口为 `https://oa.xinshify.com.cn/`。内网 DNS 将该域名解析到
`192.168.31.144`，Windows Nginx 在 443 端口提供 HTTPS；80 和 3100 端口只负责跳转到
正式 HTTPS 地址。证书与私钥保存在仓库外的 `E:\xinshi_runtime\certs`，不得提交到 Git。
Nginx 提供 `frontend/dist` 生产构建，并通过 `/api` 反向代理到本机 8000 端口；计划任务
`XinshiLanProductionFrontend` 使用 `SYSTEM` 账号在开机时启动，不依赖交互式桌面会话。
更新代码后的前端发布使用两阶段脚本，不得直接在 Nginx 正在服务的 `frontend/dist` 中运行
`npm run build`。脚本会先在隔离目录完成依赖安装、构建和预算校验，再先复制哈希资源、最后
原子替换 `index.html`；旧哈希资源会保留，避免刷新页面时混用新旧版本：

```powershell
Set-Location -LiteralPath 'E:\xinshi_system'
& '.\frontend\tools\publish-lan-frontend.ps1'
```

只更新前端静态产物不需要重启 Nginx。修改 Nginx 配置时，才执行配置校验并通过计划任务重启：

```powershell
Set-Location -LiteralPath 'E:\xinshi_system'

& 'E:\xinshi_runtime\nginx-1.30.4\nginx.exe' `
    -t `
    -p 'E:\xinshi_runtime\nginx-1.30.4\' `
    -c 'E:\xinshi_system\deploy\nginx-lan.conf'
Stop-ScheduledTask -TaskName 'XinshiLanProductionFrontend'
Get-Process -Name nginx -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -eq 'E:\xinshi_runtime\nginx-1.30.4\nginx.exe' } |
    Stop-Process -Force
Start-ScheduledTask -TaskName 'XinshiLanProductionFrontend'
```

Nginx 由 `SYSTEM` 计划任务启动。SSH 管理员会话直接执行 `nginx -s reload` 会因为无权访问
该进程的全局 reload 事件而失败，因此远程更新统一通过上述计划任务重启，不直接热重载。

## 公网生产 HTTPS 入口

公网生产环境的正式入口为 `https://www.oa.xinshify.com.cn/`，阿里云公网 DNS 使用 A 记录
`www.oa.xinshify.com.cn -> 43.132.156.72`。局域网入口继续使用
`https://oa.xinshify.com.cn/ -> 192.168.31.144`，不要覆盖现有 `oa` 记录，以免公网与内网环境
互相影响。

公网 HTTPS 由 Compose 服务 `https_gateway` 提供。该服务监听宿主机 443 端口，再反向代理到
Compose 网络中的 `frontend:80`；原有 `http://43.132.156.72:3000/` 暂时保留为故障排查入口。
配置文件为 `deploy/nginx-cloud-gateway.conf`，服务定义位于
`deploy/docker-compose.cloud.yml`。证书与私钥保存在云服务器仓库外：

```text
/etc/xinshi/certs/oa.xinshify.com.cn.pem
/etc/xinshi/certs/oa.xinshify.com.cn.key
```

私钥权限必须保持为仅 root 可读，不得把证书私钥提交到 Git。更新网关配置后，先在云服务器
`/home/ubuntu/apps/xinshi_system/deploy` 中校验 Compose 配置，再只更新网关服务：

```bash
sudo docker-compose --env-file ../.env \
  -f docker-compose.cloud.yml \
  -f docker-compose.cloud.local.yml config --quiet

sudo docker-compose --env-file ../.env \
  -f docker-compose.cloud.yml \
  -f docker-compose.cloud.local.yml up -d --no-deps https_gateway
```

部署后至少验证 HTTPS 页面、`/api/auth/session` 以及 WebSocket 握手路径。证书续期时只替换
仓库外的 `.pem` 和 `.key` 文件，并重新创建 `https_gateway` 使新证书生效。

`XinshiDebugBackendInteractive` 调用 `deploy/start_backend_interactive.ps1`。脚本默认使用本机 `.venv\Scripts\python.exe`；明确维护仍使用 Conda 的旧服务器时，任务参数须指定 `-PythonPath '.conda_env\python.exe'`。脚本会在启动
Uvicorn 前最多尝试 24 次、间隔 5 秒，只读检查实际 UNC 目录（文件系统调用耗时另计）；
只有验证成功才会启动后端。服务器重启后仍必须先建立 `Administrator` 交互式控制台会话，
旧服务器未配置自动登录；无人登录时交互式后端任务不会启动，也不得改用 Session 0 绕过此限制。

## 沟通图片云端统一存储

- `CHAT_STORAGE_MODE=local`（默认）：使用 `CHAT_UPLOAD_DIR`；云端保持该模式及现有 Docker 持久化卷。
- `CHAT_STORAGE_MODE=remote`：局域网经 HTTPS 转发上传和读取，必须配置 `CHAT_REMOTE_ORIGIN=https://www.oa.xinshify.com.cn`。源站只能为 HTTPS origin，不含路径、查询参数或凭据。
- 转发携带用户原登录凭证，不跟随重定向、不使用系统代理、不退回本地存储。切换前必须验证局域网签发的令牌能通过云端 `/api/auth/session`；签名配置统一后，原局域网登录可能需要重新登录。密钥由有权限的运维人员通过受保护渠道配置，禁止写入文档和提交。
- `CHAT_UPLOADS_PAUSED=true` 可临时禁止本机附件上传（环境变量修改后需按对应环境规范重启）。日常必须为 `false`；维护不影响已有图片读取。
- 两层云端 Nginx 的附件上传路径均设 `client_max_body_size 12m`，后端仍执行单张 10MB 限制。前端上传/读取超时 60 秒，远程连接超时 5 秒、读写超时 45 秒。
- `tools/chat_image_inventory.py` 只读输出附件记录及文件大小/SHA-256。合并文件时保留 `storage_name` 和附件 ID；同名不同哈希禁止覆盖，复制后再次盘点。局域网原图作为迁移备份保留。
- 云端前端可采用 `deploy/Dockerfile.frontend-prebuilt` 封装已在本机构建和预算校验通过的 `dist/` 与 `nginx.conf`；构建上下文必须保留旧哈希资源，切换前为旧镜像加备份标签，切换后重新加载 HTTPS 网关以更新上游地址。
- 回滚前端可使用旧镜像或旧入口文件；远程图片服务故障时禁止以自动恢复本地写入作为回滚方案，以免产生新的分散文件。
