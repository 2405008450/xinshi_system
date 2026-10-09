param(
    [ValidateSet('All', 'Backend', 'Frontend')]
    [string]$Service = 'All',
    [switch]$CheckOnly,
    [switch]$Reload,
    [string[]]$SharePath,
    [ValidateRange(1, 24)]
    [int]$MaxAttempts = 1,
    [ValidateRange(1, 5)]
    [int]$RetryDelaySeconds = 5
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8 = '1'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExecutable = Join-Path $projectRoot '.venv\Scripts\python.exe'
$frontendRoot = Join-Path $projectRoot 'frontend'
$needsBackend = $Service -in @('All', 'Backend')
$needsFrontend = $Service -in @('All', 'Frontend')

function Get-PortListener {
    param([int]$Port)
    # 枚举后筛选，避免把“没有监听”与查询失败混为一谈。
    @(Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object LocalPort -eq $Port)
}

function Assert-DesktopSession {
    $currentSession = (Get-Process -Id $PID).SessionId
    $desktop = @(Get-Process -Name explorer -ErrorAction SilentlyContinue |
        Where-Object SessionId -eq $currentSession)
    if ($currentSession -eq 0 -or $desktop.Count -eq 0) {
        throw '后端必须在已登录桌面会话启动；请按 docs/infra.md 检查 Interactive 计划任务，不得使用 Session 0。'
    }
    Write-Host "桌面会话：SessionId=$currentSession；explorer PID=$($desktop.Id -join ',')"
    return $currentSession
}

function Assert-PortAvailable {
    param([int]$Port)
    $listeners = @(Get-PortListener $Port)
    if ($listeners.Count -gt 0) {
        throw "端口 $Port 已被占用，PID=$($listeners.OwningProcess -join ',')。请核对现有进程后手动处理；脚本不会终止已有服务。"
    }
}

if ($env:COMPUTERNAME -ne 'PC' -or $projectRoot -ne 'E:\xinshi_system') {
    throw "本机入口只允许在 PC 的 E:\xinshi_system 执行；当前主机=$env:COMPUTERNAME，目录=$projectRoot"
}
Set-Location -LiteralPath $projectRoot
$commit = & git rev-parse --short HEAD
if ($LASTEXITCODE -ne 0) { throw '无法确认 Git 提交。' }
Write-Host "主机：$env:COMPUTERNAME；项目：$projectRoot；Git：$commit"

if ($needsBackend) {
    if (-not (Test-Path -LiteralPath $pythonExecutable -PathType Leaf)) {
        throw "缺少项目 Python：$pythonExecutable；不得回退到系统 Python。"
    }
    $sessionId = Assert-DesktopSession
    $configJson = & $pythonExecutable (Join-Path $projectRoot 'tools\local_startup_config.py')
    if ($LASTEXITCODE -ne 0) { throw '后端配置检查失败。' }
    $config = $configJson | ConvertFrom-Json
    Write-Host "Python：$($config.python)"
    Write-Host "数据库：$($config.database_driver) $($config.database_host):$($config.database_port)/$($config.database_name)；APP_ENV=$($config.app_env)；结构迁移关闭"
    & $pythonExecutable -c 'import uvicorn, fastapi, sqlalchemy, psycopg2'
    if ($LASTEXITCODE -ne 0) { throw '后端依赖缺失，请使用项目 Python -m pip 安装 requirements.txt。' }
    Write-Host '后端基础依赖检查通过。'
    $paths = if ($SharePath) { $SharePath } else { @($config.share_paths) }
    foreach ($path in $paths) {
        if (-not $path.StartsWith('\\')) { throw "共享检查必须使用实际 UNC 路径：$path" }
        $ready = $false
        for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
            try {
                $null = Get-Item -LiteralPath $path -ErrorAction Stop
                $null = Get-ChildItem -LiteralPath $path -Force -ErrorAction Stop | Select-Object -First 1
                $ready = $true
                break
            } catch {
                if ($attempt -lt $MaxAttempts) { Start-Sleep -Seconds $RetryDelaySeconds }
            }
        }
        if (-not $ready) { throw "UNC 只读枚举失败：$path；请在当前桌面会话确认共享权限。" }
        Write-Host "UNC 只读枚举成功：$path"
    }
}

if ($needsFrontend) {
    $null = Get-Command node -ErrorAction Stop
    $null = Get-Command npm.cmd -ErrorAction Stop
    & node --version
    & npm.cmd --version
    if ($LASTEXITCODE -ne 0) { throw 'Node.js/npm 检查失败。' }
    if (-not (Test-Path -LiteralPath (Join-Path $frontendRoot 'node_modules\vite\bin\vite.js'))) {
        throw '缺少前端依赖，请在 frontend 目录执行 npm.cmd ci。'
    }
}

$ports = @()
if ($needsBackend) { $ports += 8000 }
if ($needsFrontend) { $ports += 3000 }
foreach ($port in $ports) {
    $listeners = @(Get-PortListener $port)
    Write-Host "端口 $port：$(if ($listeners.Count) { '已监听，PID=' + ($listeners.OwningProcess -join ',') } else { '空闲' })"
    if (-not $CheckOnly) { Assert-PortAvailable $port }
}
if ($CheckOnly) {
    Write-Host '只读检查完成；未启动服务、连接数据库或执行迁移。'
    return
}
if ($Service -eq 'All' -and $SharePath) {
    throw '自定义 SharePath 请分别使用 -Service Backend 与 -Service Frontend 启动。'
}

if ($Service -eq 'Backend') {
    Write-Host '后端：http://127.0.0.1:8000/；当前终端 Ctrl+C 停止。'
    $uvicornArgs = @('-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', '8000', '--log-level', 'info')
    if ($Reload) { $uvicornArgs += '--reload' }
    & $pythonExecutable @uvicornArgs
    if ($LASTEXITCODE -ne 0) { throw "后端退出，错误码 $LASTEXITCODE" }
    return
}
if ($Service -eq 'Frontend') {
    Set-Location -LiteralPath $frontendRoot
    Write-Host '前端：http://localhost:3000/；当前终端 Ctrl+C 停止。'
    & npm.cmd run dev -- --host 127.0.0.1 --port 3000 --strictPort
    if ($LASTEXITCODE -ne 0) { throw "前端退出，错误码 $LASTEXITCODE" }
    return
}

# 一键启动使用同一桌面会话的隐藏子终端；日志分开保存，不杀已有进程。
$logRoot = Join-Path $projectRoot 'logs'
$null = New-Item -ItemType Directory -Path $logRoot -Force
$runId = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$shellExecutable = (Get-Process -Id $PID).Path
$children = @()
try {
    foreach ($component in @('Backend', 'Frontend')) {
        $outLog = Join-Path $logRoot "$($component.ToLower())-$runId.out.log"
        $errLog = Join-Path $logRoot "$($component.ToLower())-$runId.err.log"
        $arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Service $component -MaxAttempts $MaxAttempts -RetryDelaySeconds $RetryDelaySeconds"
        if ($Reload -and $component -eq 'Backend') { $arguments += ' -Reload' }
        $child = Start-Process -FilePath $shellExecutable -ArgumentList $arguments -WorkingDirectory $projectRoot `
            -WindowStyle Hidden -RedirectStandardOutput $outLog -RedirectStandardError $errLog -PassThru
        $children += $child
        Write-Host "$component 启动终端 PID=$($child.Id)；日志：$outLog；$errLog"
    }
    $deadline = (Get-Date).AddSeconds(60)
    $verified = $false
    while ((Get-Date) -lt $deadline) {
        foreach ($child in $children) {
            $child.Refresh()
            if ($child.HasExited) { throw '启动子终端提前退出，请检查本轮启动日志。' }
        }
        try {
            $backend = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health/db' -TimeoutSec 3
            $frontend = Invoke-WebRequest -Uri 'http://localhost:3000/' -UseBasicParsing -TimeoutSec 3
            $proxy = Invoke-RestMethod -Uri 'http://localhost:3000/api/health/db' -TimeoutSec 3
            if ($backend.status -eq 'ok' -and $proxy.status -eq 'ok' -and $frontend.StatusCode -eq 200) {
                $verified = $true
                break
            }
        } catch { }
        Start-Sleep -Seconds 1
    }
    if (-not $verified) { throw '60 秒内未通过页面、数据库健康检查和 /api 代理检查，请检查启动日志。' }
    foreach ($port in @(8000, 3000)) {
        $listenerIds = @(Get-PortListener $port | Select-Object -ExpandProperty OwningProcess -Unique)
        if (-not $listenerIds.Count) { throw "端口 $port 没有监听进程。" }
        foreach ($listenerId in $listenerIds) {
            $process = Get-Process -Id $listenerId
            if ($process.SessionId -ne $sessionId) { throw "端口 $port 的进程不属于启动桌面会话。" }
            if ($port -eq 8000 -and $process.Path -ne $pythonExecutable) {
                throw '8000 端口未使用项目 .venv Python。'
            }
            # 沿父进程链确认监听者确实由本轮启动，不接受抢占端口的其他程序。
            $ancestorId = $listenerId
            $owned = $false
            for ($depth = 0; $depth -lt 12 -and $ancestorId -gt 0; $depth++) {
                if ($ancestorId -in $children.Id) { $owned = $true; break }
                $info = Get-CimInstance Win32_Process -Filter "ProcessId=$ancestorId"
                if (-not $info) { break }
                $ancestorId = $info.ParentProcessId
            }
            if (-not $owned) { throw "端口 $port 的监听者不属于本轮启动。" }
            Write-Host "运行验证：端口=$port；PID=$listenerId；SessionId=$($process.SessionId)"
        }
    }
    Write-Host '启动成功：http://localhost:3000/；后端 http://127.0.0.1:8000/；数据库及同源代理健康检查通过。'
    Write-Host "停止本轮服务：taskkill.exe /PID $($children[0].Id) /T /F；taskkill.exe /PID $($children[1].Id) /T /F（确认无进行中的操作，仅使用本轮打印的终端 PID）"
} catch {
    # 仅回收本轮创建的进程树，失败时不留下半套运行服务。
    foreach ($child in $children) {
        $child.Refresh()
        if (-not $child.HasExited) { & taskkill.exe /PID $child.Id /T /F | Out-Null }
    }
    throw
}
