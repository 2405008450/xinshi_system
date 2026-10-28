param(
    [Parameter(Mandatory = $true)]
    [string] $ConfigFile,
    [string] $TaskName = 'XinshiResumeCollection'
)

$ErrorActionPreference = 'Stop'
if ($env:COMPUTERNAME -ne 'WIN-LOLJ8UHT2G5') { throw 'host_mismatch' }
if (-not (Test-Path -LiteralPath $ConfigFile -PathType Leaf)) { throw 'config_missing' }
if (-not (Test-Path -LiteralPath 'E:\xinshi_system\tools\run_resume_collection_interactive.ps1' -PathType Leaf)) { throw 'runner_missing' }
if ($TaskName -notmatch '^[A-Za-z][A-Za-z0-9_-]{3,63}$') { throw 'task_name_invalid' }
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) { throw 'task_already_exists' }

$activeDesktop = @(Get-Process -Name explorer -ErrorAction Stop | Where-Object { $_.SessionId -gt 0 })
if ($activeDesktop.Count -eq 0) { throw 'interactive_desktop_missing' }
quser | Out-Host

$runner = 'E:\xinshi_system\tools\run_resume_collection_interactive.ps1'
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$runner`" -ConfigFile `"$ConfigFile`"" -WorkingDirectory 'E:\xinshi_system'
$principal = New-ScheduledTaskPrincipal -UserId 'Administrator' -LogonType Interactive -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 24) -AllowStartIfOnBatteries
Register-ScheduledTask -TaskName $TaskName -Action $action -Principal $principal -Settings $settings | Out-Null
$registered = Get-ScheduledTask -TaskName $TaskName
if ($registered.Principal.LogonType -ne 'Interactive' -or $registered.Principal.UserId -notmatch 'Administrator$') {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    throw 'task_principal_invalid'
}
Start-ScheduledTask -TaskName $TaskName
Write-Output "started=$TaskName"
