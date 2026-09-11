$ErrorActionPreference = 'Stop'
try {
  $resp = Invoke-WebRequest -Uri 'https://127.0.0.1/' -Headers @{ Host = 'oa.xinshify.com.cn' } -UseBasicParsing
  Write-Output ("STATUS=" + [int]$resp.StatusCode)
} catch {
  Write-Output ("HTTP_ERR=" + $_.Exception.Message)
}
$hit = Get-ChildItem -LiteralPath 'E:\xinshi_system\frontend\dist\assets' -Filter '*.css' |
  Select-String -Pattern 'project-name-ellipsis' -SimpleMatch -List |
  Select-Object -First 3
foreach ($item in $hit) {
  Write-Output ("CSS_HIT=" + $item.Path)
}
$task = Get-ScheduledTask -TaskName 'XinshiLanProductionFrontend'
Write-Output ("TASK=" + $task.State)
