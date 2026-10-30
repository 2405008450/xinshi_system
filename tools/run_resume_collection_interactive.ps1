param(
    [Parameter(Mandatory = $true)]
    [string] $ConfigFile
)

$ErrorActionPreference = 'Stop'
$stage = 'load_config'
$statusFile = [IO.Path]::ChangeExtension($ConfigFile, '.status.json')
trap {
    [pscustomobject]@{
        stage = $stage
        error_type = $_.Exception.GetType().Name
        error_line = $_.InvocationInfo.ScriptLineNumber
        error_message = $_.Exception.Message
        result = 'failed'
    } | ConvertTo-Json | Set-Content -LiteralPath $statusFile -Encoding UTF8
    exit 1
}
$project = 'E:\xinshi_system'
$python = Join-Path $project '.conda_env\python.exe'
$script = Join-Path $project 'tools\collect_resume_text.py'
$config = Get-Content -LiteralPath $ConfigFile -Raw -Encoding UTF8 | ConvertFrom-Json

$stage = 'verify_host_and_version'
if ($env:COMPUTERNAME -ne 'WIN-LOLJ8UHT2G5') { throw 'host_mismatch' }
if ((Get-Location).Path -ne $project) { Set-Location -LiteralPath $project }
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'python_missing' }
if (-not (Test-Path -LiteralPath $script -PathType Leaf)) { throw 'script_missing' }
if (-not $config.roots -or -not $config.output -or -not $config.expected_commit -or -not $config.script_sha256) { throw 'config_invalid' }

$commit = (& git.exe rev-parse --short HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $commit -ne [string]$config.expected_commit) { throw 'commit_mismatch' }
$hash = (Get-FileHash -LiteralPath $script -Algorithm SHA256).Hash.ToLowerInvariant()
if ($hash -ne ([string]$config.script_sha256).ToLowerInvariant()) { throw 'script_hash_mismatch' }

$stage = 'verify_interactive_session'
$session = (Get-Process -Id $PID).SessionId
$explorer = @(Get-Process -Name explorer -ErrorAction Stop | Where-Object { $_.SessionId -eq $session })
if ($session -eq 0 -or $explorer.Count -eq 0) { throw 'interactive_session_missing' }
if ([Security.Principal.WindowsIdentity]::GetCurrent().Name -notmatch '\\Administrator$') { throw 'wrong_user' }

$stage = 'verify_share_access'
foreach ($root in @($config.roots)) {
    if (-not ([string]$root).StartsWith('\\')) { throw 'root_not_unc' }
    $item = Get-Item -LiteralPath $root -ErrorAction Stop
    if ($item.PSIsContainer) {
        Get-ChildItem -LiteralPath $root -ErrorAction Stop | Select-Object -First 1 | Out-Null
    } else {
        Get-ChildItem -LiteralPath $item.DirectoryName -ErrorAction Stop | Select-Object -First 1 | Out-Null
    }
}

$stage = 'prepare_output'
$output = [IO.Path]::GetFullPath([string]$config.output)
if (-not $output.StartsWith('E:\resume_text_collection\', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'output_not_allowed'
}
New-Item -ItemType Directory -Path $output -Force | Out-Null
& icacls.exe $output /inheritance:r /grant:r 'Administrator:(OI)(CI)F' 'SYSTEM:(OI)(CI)F' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'output_acl_failed' }

# LibreOffice 的独立用户配置、转换文件和系统临时文件统一写入数据盘。
if (-not (Test-Path -LiteralPath 'D:\' -PathType Container)) { throw 'temp_drive_missing' }
if (([IO.DriveInfo]::new('D:\')).AvailableFreeSpace -lt 50GB) { throw 'temp_drive_low_space' }
New-Item -ItemType Directory -Path 'D:\resume_text_collection_temp' -Force | Out-Null
& icacls.exe 'D:\resume_text_collection_temp' /inheritance:r /grant:r 'Administrator:(OI)(CI)F' 'SYSTEM:(OI)(CI)F' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'temp_acl_failed' }
$env:TEMP = 'D:\resume_text_collection_temp'
$env:TMP = 'D:\resume_text_collection_temp'
$env:RESUME_TEMP_DIR = 'D:\resume_text_collection_temp'

$stage = 'collect'
$workers = 2
if ($null -ne $config.workers) { $workers = [int]$config.workers }
if ($workers -lt 1 -or $workers -gt 4) { throw 'workers_invalid' }
$arguments = @($script)
foreach ($root in @($config.roots)) { $arguments += @('--root', [string]$root) }
foreach ($excluded in @($config.exclude_roots)) { if ($excluded) { $arguments += @('--exclude-root', [string]$excluded) } }
$arguments += @('--output', $output, '--workers', [string]$workers, '--timeout', '120')
& $python @arguments
$collectorCode = $LASTEXITCODE
$organizerCode = 0
if ($config.organize_output) {
    $stage = 'organize'
    $organizer = Join-Path $project 'tools\organize_resume_json.py'
    if (-not (Test-Path -LiteralPath $organizer -PathType Leaf)) { throw 'organizer_missing' }
    if (-not $config.organizer_sha256) { throw 'organizer_hash_missing' }
    $organizerHash = (Get-FileHash -LiteralPath $organizer -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($organizerHash -ne ([string]$config.organizer_sha256).ToLowerInvariant()) { throw 'organizer_hash_mismatch' }
    $organizeOutput = [IO.Path]::GetFullPath([string]$config.organize_output)
    if (-not $organizeOutput.StartsWith('E:\resume_text_collection\', [StringComparison]::OrdinalIgnoreCase) -or $organizeOutput.Equals($output, [StringComparison]::OrdinalIgnoreCase) -or $organizeOutput.StartsWith($output + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'organize_output_not_allowed'
    }
    New-Item -ItemType Directory -Path $organizeOutput -Force | Out-Null
    & icacls.exe $organizeOutput /inheritance:r /grant:r 'Administrator:(OI)(CI)F' 'SYSTEM:(OI)(CI)F' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'organize_output_acl_failed' }
    & $python $organizer --collection $output --output $organizeOutput
    $organizerCode = $LASTEXITCODE
}
$code = if ($organizerCode -ne 0) { 2 } elseif ($collectorCode -ne 0) { 1 } else { 0 }
[pscustomobject]@{ stage = $stage; result = $(if ($code -eq 0) { 'success' } elseif ($organizerCode -ne 0) { 'organizer_failed' } else { 'collector_failed' }); exit_code = $code; collector_exit_code = $collectorCode; organizer_exit_code = $organizerCode } |
    ConvertTo-Json | Set-Content -LiteralPath $statusFile -Encoding UTF8
exit $code
