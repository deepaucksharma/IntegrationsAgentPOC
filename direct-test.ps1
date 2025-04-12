# DEPRECATED: This script has been moved
# Please use examples/direct-test.ps1 instead

Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Yellow
Write-Host "║                                                              ║" -ForegroundColor Yellow
Write-Host "║   DEPRECATED: This script has been moved                     ║" -ForegroundColor Yellow
Write-Host "║                                                              ║" -ForegroundColor Yellow
Write-Host "║   Please use examples/direct-test.ps1 instead                ║" -ForegroundColor Yellow
Write-Host "║                                                              ║" -ForegroundColor Yellow
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Yellow
Write-Host ""

# Forward to the new script location
$newPath = Join-Path $PSScriptRoot "examples\direct-test.ps1"
if (Test-Path $newPath) {
    Write-Host "Forwarding to: $newPath"
    & $newPath
} else {
    Write-Host "Error: New script not found at $newPath" -ForegroundColor Red
    exit 1
}
