$ErrorActionPreference = 'Stop'

$logDirectory = 'E:\xinshi_system\logs'
$logPath = Join-Path $logDirectory 'autologon-lock.log'
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null

function Write-LockLog {
    param([string]$Message)
    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -LiteralPath $logPath -Encoding UTF8 -Value "[$timestamp] $Message"
}

$currentSessionId = (Get-Process -Id $PID).SessionId
$consoleSessionLine = quser 2>$null | Select-String -Pattern '^\s*administrator\s+console\s+(\d+)\s+'

if (-not $consoleSessionLine) {
    Write-LockLog "Skipped lock because no Administrator console session was found. Current session: $currentSessionId."
    exit 0
}

$consoleSessionId = [int]$consoleSessionLine.Matches[0].Groups[1].Value
if ($currentSessionId -ne $consoleSessionId) {
    Write-LockLog "Skipped lock for non-console session $currentSessionId. Console session: $consoleSessionId."
    exit 0
}

Write-LockLog "Locking Administrator console session $consoleSessionId after automatic logon."
& "$env:SystemRoot\System32\rundll32.exe" user32.dll,LockWorkStation
exit $LASTEXITCODE
