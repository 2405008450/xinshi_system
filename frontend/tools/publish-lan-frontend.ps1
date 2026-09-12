param(
    [string]$ProjectRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)),
    [switch]$SkipInstall
)

$ErrorActionPreference = 'Stop'

$projectPath = [System.IO.Path]::GetFullPath($ProjectRoot)
$frontendPath = Join-Path $projectPath 'frontend'
$liveDistPath = Join-Path $frontendPath 'dist'
$stagingRootPath = Join-Path $frontendPath '.publish-staging'
$publishId = [Guid]::NewGuid().ToString('N')
$stagingPath = Join-Path $stagingRootPath $publishId
$lockPath = Join-Path $frontendPath '.frontend-publish.lock'
$lockStream = $null

if (-not (Test-Path -LiteralPath (Join-Path $frontendPath 'package.json') -PathType Leaf)) {
    throw "Frontend project was not found: $frontendPath"
}

try {
    try {
        $lockStream = [System.IO.File]::Open(
            $lockPath,
            [System.IO.FileMode]::OpenOrCreate,
            [System.IO.FileAccess]::ReadWrite,
            [System.IO.FileShare]::None
        )
    } catch {
        throw 'Another frontend publish is already running. Wait for it to finish before retrying.'
    }

    New-Item -ItemType Directory -Path $stagingPath -Force | Out-Null

    Push-Location $frontendPath
    try {
        if (-not $SkipInstall) {
            & npm.cmd ci
            if ($LASTEXITCODE -ne 0) {
                throw "npm ci failed with exit code $LASTEXITCODE."
            }
        }

        $vitePath = Join-Path $frontendPath 'node_modules\.bin\vite.cmd'
        if (-not (Test-Path -LiteralPath $vitePath -PathType Leaf)) {
            throw "Vite executable was not found: $vitePath"
        }

        & $vitePath build --outDir $stagingPath --emptyOutDir
        if ($LASTEXITCODE -ne 0) {
            throw "Frontend build failed with exit code $LASTEXITCODE."
        }

        & node.exe (Join-Path $frontendPath 'tools\check-build-budget.mjs') --dist-dir $stagingPath
        if ($LASTEXITCODE -ne 0) {
            throw "Build budget validation failed with exit code $LASTEXITCODE."
        }
    } finally {
        Pop-Location
    }

    $stagedIndexPath = Join-Path $stagingPath 'index.html'
    if (-not (Test-Path -LiteralPath $stagedIndexPath -PathType Leaf)) {
        throw 'The staged build does not contain index.html.'
    }

    New-Item -ItemType Directory -Path $liveDistPath -Force | Out-Null

    # 先发布所有带哈希资源，让旧入口和新入口引用的文件在切换期间同时可用。
    Get-ChildItem -LiteralPath $stagingPath -File -Recurse |
        Where-Object { $_.FullName -ne $stagedIndexPath } |
        ForEach-Object {
            $relativePath = $_.FullName.Substring($stagingPath.Length).TrimStart('\', '/')
            $destinationPath = Join-Path $liveDistPath $relativePath
            $destinationDirectory = Split-Path -Parent $destinationPath
            New-Item -ItemType Directory -Path $destinationDirectory -Force | Out-Null
            Copy-Item -LiteralPath $_.FullName -Destination $destinationPath -Force
        }

    $indexHtml = Get-Content -LiteralPath $stagedIndexPath -Raw -Encoding UTF8
    $entryAssetMatches = [regex]::Matches($indexHtml, '(?:src|href)="/?(assets/[^"?]+)')
    foreach ($match in $entryAssetMatches) {
        $entryAssetPath = Join-Path $liveDistPath $match.Groups[1].Value
        if (-not (Test-Path -LiteralPath $entryAssetPath -PathType Leaf)) {
            throw "Published entry asset is missing: $entryAssetPath"
        }
    }

    # Switch index.html last so clients never observe a partially written entry file.
    Copy-Item -LiteralPath $stagedIndexPath -Destination "$liveDistPath\.index.$publishId.pending" -Force

    if (Test-Path -LiteralPath (Join-Path $liveDistPath 'index.html') -PathType Leaf) {
        [System.IO.File]::Replace(
            "$liveDistPath\.index.$publishId.pending",
            (Join-Path $liveDistPath 'index.html'),
            "$liveDistPath\.index.$publishId.previous",
            $true
        )
        Remove-Item -LiteralPath "$liveDistPath\.index.$publishId.previous" -Force
    } else {
        Move-Item -LiteralPath "$liveDistPath\.index.$publishId.pending" -Destination (Join-Path $liveDistPath 'index.html')
    }

    $entryScript = [regex]::Match($indexHtml, 'assets/index-[A-Za-z0-9_-]+\.js').Value
    Write-Output "Frontend publish completed: $entryScript"
    Write-Output 'Old hashed assets were retained so open browser sessions can finish safely.'
} finally {
    if ($lockStream) {
        $lockStream.Dispose()
    }
    if (Test-Path -LiteralPath $lockPath -PathType Leaf) {
        Remove-Item -LiteralPath $lockPath -Force -ErrorAction SilentlyContinue
    }

    $resolvedStagingRootPrefix = [System.IO.Path]::GetFullPath($stagingRootPath).TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
    $resolvedStagingPath = [System.IO.Path]::GetFullPath($stagingPath)
    if ($resolvedStagingPath.StartsWith($resolvedStagingRootPrefix, [System.StringComparison]::OrdinalIgnoreCase) -and
        (Test-Path -LiteralPath $resolvedStagingPath -PathType Container)) {
        Remove-Item -LiteralPath $resolvedStagingPath -Recurse -Force
    }
}
