# 项目环境与操作边界

## 环境清单

| 环境 | 地址 | SSH 端口 | 登录用户 | 用途 |
| --- | --- | --- | --- | --- |
| 当前开发机 | 当前工作区所在机器 | - | - | 仅运行 Coding Agent、编辑代码、搜索文件和执行轻量静态检查 |
| 局域网部署调试机 | `192.168.31.144` | `22` | `Administrator` | 项目目录为 `E:\xinshi_system`；使用项目内 `.conda_env` 环境进行部署调试、接口联调和自动化测试 |
| 云端生产环境 | `43.132.156.72` | `22` | 以云端实际账号为准 | 线上正式服务，仅执行经过确认的发布、回滚和运维操作 |

## 默认工作流

1. 在当前开发机使用 Coding Agent 修改代码；不要在本机启动完整前后端或数据库。
2. 将待验证代码同步到局域网部署调试机的 `E:\xinshi_system`。
3. 在 `192.168.31.144` 的 `E:\xinshi_system` 中使用已有 Conda 环境 `.conda_env` 完成后端启动、数据库迁移、自动化测试和页面联调；前端使用服务器已有的 Node.js/npm 启动。
4. 调试机验证通过后形成待发布版本；没有用户明确的发布指令时，不得连接或修改云端生产环境。
5. 发布到 `43.132.156.72` 前必须备份数据库，核对环境变量和迁移清单，并保留可回滚版本。

## Coding Agent 执行约束

- 源码编辑、差异检查和轻量静态分析在当前开发机执行。
- 所有会启动项目运行时或消耗较多 CPU、内存、磁盘的命令，默认通过远程连接在 `192.168.31.144` 执行，包括 Conda 后端、前端服务、完整构建、完整测试和浏览器联调。
- 局域网项目不是 Docker 部署，不得使用 `docker compose` 启停或验证该环境。
- 后端固定使用 `E:\xinshi_system\.conda_env\python.exe`，不得误用 Conda `base`、`fastapi-llm-py311` 或系统 Python。
- 后端依赖交互式 Windows 登录会话中的 SMB 凭据读取 `\\Win-server` 共享目录。Coding Agent 远程重启时只能启动计划任务 `XinshiDebugBackendInteractive`；禁止使用 WMI/CIM `Win32_Process.Create`、SSH 会话中的 `Start-Process`、Windows 服务或其他会把 Uvicorn 放入 Session 0 的方式。
- 远程命令必须先确认当前主机名、工作目录为 `E:\xinshi_system`，并核对 Git 提交，避免在错误目录或生产机执行。
- 局域网调试入口以 `http://192.168.31.144:3000/` 为准；后端端口仅供受控联调，不作为员工正式入口。
- 云端 `43.132.156.72` 是生产环境。除非用户明确要求发布或运维，否则只能进行必要的只读核查，不得部署、迁移、重启或修改数据。

## SSH 建议配置

在开发机用户级 SSH 配置中维护别名（不要提交包含私钥或密码的文件）：

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

## 远程验证基线

每次部署调试前先执行以下只读检查：

```powershell
ssh xinshi-lan 'powershell -NoProfile -Command "$env:COMPUTERNAME; Set-Location -LiteralPath ''E:\xinshi_system''; (Get-Location).Path; git rev-parse --short HEAD; & ''.\.conda_env\python.exe'' -c ''import sys; print(sys.executable)''"'
```

确认输出来自 `192.168.31.144`、项目目录为 `E:\xinshi_system` 且提交版本正确后，再执行构建或部署命令。生产环境不得复用调试机命令或调试用环境变量。

## 局域网启动方式

后端使用项目已配置好的 Conda 环境。服务器本机人工启动时，可以在已登录的 `Administrator` 桌面会话中执行：

```powershell
Set-Location -LiteralPath 'E:\xinshi_system'
& '.\.conda_env\python.exe' -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

也可以在服务器桌面上运行 `E:\xinshi_system\start_backend.bat`。

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
更新代码后的部署步骤为：

```powershell
Set-Location -LiteralPath 'E:\xinshi_system\frontend'
npm ci
npm run build

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

`XinshiDebugBackendInteractive` 调用 `deploy/start_backend_interactive.ps1`。脚本会在启动
Uvicorn 前最多重试 120 秒，对 `\\Win-server\服务器资料7` 执行 `Get-Item` 和一次只读枚举；
只有验证成功才会启动后端。服务器重启后仍必须先建立 `Administrator` 交互式控制台会话，
当前机器未配置自动登录；无人登录时交互式后端任务不会启动，也不得改用 Session 0 绕过此限制。
