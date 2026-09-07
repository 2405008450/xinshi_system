param(
    [string]$SharePath = ('\\Win-server\' + (-join ([char[]](0x670D, 0x52A1, 0x5668, 0x8D44, 0x6599, 0x37)))),
    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

$ErrorActionPreference = 'Stop'
$result = [ordered]@{
    checked_at = (Get-Date).ToString('o')
    computer = $env:COMPUTERNAME
    user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    session_id = (Get-Process -Id $PID).SessionId
    share_path = $SharePath
    item_readable = $false
    enumeration_readable = $false
    success = $false
    error = $null
}

try {
    $null = Get-Item -LiteralPath $SharePath -ErrorAction Stop
    $result.item_readable = $true
    $null = Get-ChildItem -LiteralPath $SharePath -Force -ErrorAction Stop | Select-Object -First 1
    $result.enumeration_readable = $true
    $result.success = $true
}
catch {
    $result.error = $_.Exception.Message
}

$outputDirectory = Split-Path -Parent $OutputPath
if ($outputDirectory) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}
$result | ConvertTo-Json | Set-Content -LiteralPath $OutputPath -Encoding UTF8

if (-not $result.success) {
    exit 1
}
