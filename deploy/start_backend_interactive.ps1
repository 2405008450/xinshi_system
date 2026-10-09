param(
    [string]$SharePath,
    [ValidateRange(1, 24)]
    [int]$MaxAttempts = 24,
    [ValidateRange(1, 5)]
    [int]$RetryDelaySeconds = 5,
    [string]$PythonPath = '.venv\Scripts\python.exe'
)

$ErrorActionPreference = 'Stop'

# PC 与人工启动复用同一入口；计划任务不会绕过会话、数据库及 UNC 检查。
if ($env:COMPUTERNAME -eq 'PC') {
    if ($PythonPath -ne '.venv\Scripts\python.exe') {
        throw 'PC 后端必须使用项目 .venv\Scripts\python.exe。'
    }
    $localArguments = @{ Service = 'Backend'; MaxAttempts = $MaxAttempts; RetryDelaySeconds = $RetryDelaySeconds }
    if ($SharePath) { $localArguments.SharePath = @($SharePath) }
    $pcLogDirectory = Join-Path (Split-Path -Parent $PSScriptRoot) 'logs'
    $null = New-Item -ItemType Directory -Path $pcLogDirectory -Force
    $pcStartupLog = Join-Path $pcLogDirectory 'backend-interactive-startup.log'
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] PC interactive backend startup" |
        Out-File -LiteralPath $pcStartupLog -Encoding UTF8 -Append
    Start-Transcript -Path $pcStartupLog -Append | Out-Null
    try {
        & (Join-Path $PSScriptRoot 'start_local.ps1') @localArguments
    } finally {
        Stop-Transcript | Out-Null
    }
    exit 0
}

# 以下仅保留明确维护旧服务器时的兼容入口。
if (-not $SharePath) {
    $SharePath = '\\Win-server\服务器资料7'
}
$sessionId = (Get-Process -Id $PID).SessionId
if ($sessionId -eq 0 -or -not (Get-Process explorer -ErrorAction SilentlyContinue | Where-Object SessionId -eq $sessionId)) {
    throw '交互式后端任务必须与 explorer.exe 属于同一非零桌面会话。'
}
$projectRoot = 'E:\xinshi_system'
$pythonExecutable = Join-Path $projectRoot $PythonPath
$logDirectory = Join-Path $projectRoot 'logs'
$startupLog = Join-Path $logDirectory 'backend-interactive-startup.log'

New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null

function Write-StartupLog {
    param([string]$Message)
    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -LiteralPath $startupLog -Encoding UTF8 -Value "[$timestamp] $Message"
}

if (-not (Test-Path -LiteralPath $pythonExecutable -PathType Leaf)) {
    Write-StartupLog "Backend startup failed because Python was not found: $pythonExecutable"
    exit 2
}

$shareReady = $false
for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
    try {
        $null = Get-Item -LiteralPath $SharePath -ErrorAction Stop
        $null = Get-ChildItem -LiteralPath $SharePath -Force -ErrorAction Stop | Select-Object -First 1
        $shareReady = $true
        Write-StartupLog "UNC read validation succeeded for $SharePath on attempt $attempt."
        break
    }
    catch {
        Write-StartupLog "UNC read validation failed for $SharePath on attempt $attempt/$MaxAttempts."
        if ($attempt -lt $MaxAttempts) {
            Start-Sleep -Seconds $RetryDelaySeconds
        }
    }
}

if (-not $shareReady) {
    Write-StartupLog "Backend was not started because UNC validation failed after $MaxAttempts attempts."
    exit 3
}

Set-Location -LiteralPath $projectRoot
Write-StartupLog "Host=$env:COMPUTERNAME; project=$projectRoot; session=$sessionId; Git=$(& git rev-parse --short HEAD)"
$configJson = & $pythonExecutable (Join-Path $projectRoot 'tools\local_startup_config.py')
if ($LASTEXITCODE -ne 0) { throw '数据库目标检查失败。' }
$config = $configJson | ConvertFrom-Json
Write-StartupLog "Database=$($config.database_host):$($config.database_port)/$($config.database_name); schema migrations disabled."
if (Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object LocalPort -eq 8000) {
    throw '8000 端口已占用；必须核对原有进程后手动停止。'
}
Write-StartupLog 'UNC validation passed. Starting Uvicorn in the interactive session.'
& $pythonExecutable -m uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info
exit $LASTEXITCODE
