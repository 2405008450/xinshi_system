param([Parameter(Mandatory = $true)][string]$url)

$ErrorActionPreference = 'Stop'

function Write-Audit([string]$action, [string]$detail) {
    $auditDirectory = Join-Path $env:LOCALAPPDATA 'XinShi'
    New-Item -ItemType Directory -Path $auditDirectory -Force | Out-Null
    $safeDetail = $detail -replace "[`r`n]", ' '
    Add-Content -LiteralPath (Join-Path $auditDirectory 'openpath-audit.log') `
        -Value "$(Get-Date -Format o)`t$action`t$safeDetail" -Encoding UTF8
}

try {
    if (-not $url.StartsWith('openpath://', [System.StringComparison]::OrdinalIgnoreCase)) {
        throw '无效的 openpath 协议地址'
    }

    $decoded = [System.Uri]::UnescapeDataString($url.Substring('openpath://'.Length))
    if ($decoded.IndexOfAny([char[]]@(0, 10, 13)) -ge 0) {
        throw '路径包含非法控制字符'
    }

    $segments = @($decoded -split '[/\\]' | Where-Object { $_ -ne '' })
    if ($segments.Count -lt 2 -or $segments -contains '.' -or $segments -contains '..') {
        throw '仅允许规范化的 UNC 共享路径'
    }

    $path = '\\' + ($segments -join '\')
    $path = [System.IO.Path]::GetFullPath($path).TrimEnd('\')

    $configuredRoots = @($env:OPENPATH_ALLOWED_ROOTS -split ';' | Where-Object { $_.Trim() })
    if ($configuredRoots.Count -eq 0) {
        throw '未配置企业受控目录 OPENPATH_ALLOWED_ROOTS'
    }

    $allowed = $false
    foreach ($configuredRoot in $configuredRoots) {
        $root = [System.IO.Path]::GetFullPath($configuredRoot.Trim()).TrimEnd('\')
        if (-not $root.StartsWith('\\')) { continue }
        if ($path.Equals($root, [System.StringComparison]::OrdinalIgnoreCase) -or
            $path.StartsWith($root + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
            $allowed = $true
            break
        }
    }
    if (-not $allowed) {
        throw '路径不在企业允许的网络目录中'
    }

    $dangerousExtensions = @('.exe', '.com', '.bat', '.cmd', '.ps1', '.vbs', '.js', '.jse', '.wsf', '.wsh', '.msi', '.msp', '.scr', '.cpl', '.lnk', '.url', '.hta', '.reg', '.dll')
    $extension = [System.IO.Path]::GetExtension($path).ToLowerInvariant()
    if ($dangerousExtensions -contains $extension) {
        Add-Type -AssemblyName System.Windows.Forms
        $choice = [System.Windows.Forms.MessageBox]::Show(
            '该路径指向高风险文件。系统不会执行该文件，只能打开所在文件夹。是否继续？',
            '信实系统安全确认',
            [System.Windows.Forms.MessageBoxButtons]::YesNo,
            [System.Windows.Forms.MessageBoxIcon]::Warning
        )
        if ($choice -ne [System.Windows.Forms.DialogResult]::Yes) {
            Write-Audit 'blocked_by_user' $path
            exit 2
        }
        $folder = [System.IO.Path]::GetDirectoryName($path)
        Write-Audit 'open_parent_only' $path
        Start-Process -FilePath 'explorer.exe' -ArgumentList "`"$folder`""
        exit 0
    }

    Write-Audit 'open_in_explorer' $path
    if ($extension) {
        Start-Process -FilePath 'explorer.exe' -ArgumentList "/select,`"$path`""
    } else {
        Start-Process -FilePath 'explorer.exe' -ArgumentList "`"$path`""
    }
} catch {
    Write-Audit 'blocked' $_.Exception.Message
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show(
        $_.Exception.Message,
        '信实系统已阻止打开路径',
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Error
    ) | Out-Null
    exit 1
}
