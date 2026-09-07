param(
    [string]$SharePath = ('\\Win-server\' + (-join ([char[]](0x670D, 0x52A1, 0x5668, 0x8D44, 0x6599, 0x37)))),
    [int]$MaxAttempts = 24,
    [int]$RetryDelaySeconds = 5
)

$ErrorActionPreference = 'Stop'
$projectRoot = 'E:\xinshi_system'
$pythonExecutable = Join-Path $projectRoot '.conda_env\python.exe'
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
Write-StartupLog 'UNC validation passed. Starting Uvicorn in the interactive session.'
& $pythonExecutable -m uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info
exit $LASTEXITCODE
