param([string]$url)

# Properly decode UTF-8 percent-encoding (handles Chinese characters, etc.)
$path = [System.Uri]::UnescapeDataString($url)

# Remove the custom protocol prefix
$path = $path -replace '^openpath://', ''

# Convert forward slashes back to backslashes
$path = $path -replace '/', '\'

# Re-add the \\ prefix that was stripped during URL encoding
if (-not $path.StartsWith('\\')) {
    $path = '\\' + $path
}

Start-Process 'explorer.exe' -ArgumentList "`"$path`""
