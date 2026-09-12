param(
    [string]$NginxRoot = 'E:\xinshi_runtime\nginx-1.30.4',
    [string]$ConfigPath = 'E:\xinshi_system\deploy\nginx-lan.conf'
)

$ErrorActionPreference = 'Stop'

$nginxExecutable = Join-Path $NginxRoot 'nginx.exe'
if (-not (Test-Path -LiteralPath $nginxExecutable -PathType Leaf)) {
    throw "Nginx executable was not found: $nginxExecutable"
}

if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) {
    throw "LAN Nginx configuration was not found: $ConfigPath"
}

if (-not (Test-Path -LiteralPath 'E:\xinshi_system\frontend\dist\index.html' -PathType Leaf)) {
    throw 'The frontend production build is missing. Run frontend\tools\publish-lan-frontend.ps1 first.'
}

& $nginxExecutable -t -p "$NginxRoot\" -c $ConfigPath
if ($LASTEXITCODE -ne 0) {
    throw "Nginx configuration validation failed with exit code $LASTEXITCODE."
}

& $nginxExecutable -p "$NginxRoot\" -c $ConfigPath
exit $LASTEXITCODE
