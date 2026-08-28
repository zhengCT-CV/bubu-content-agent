$ErrorActionPreference = "Continue"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$StateFile = Join-Path $ProjectRoot ".runtime\processes.json"

Set-Location -LiteralPath $ProjectRoot

Write-Host "=== Docker 基础设施 ===" -ForegroundColor Cyan
docker compose ps

Write-Host "`n=== 主机进程 ===" -ForegroundColor Cyan
if (Test-Path -LiteralPath $StateFile) {
    $state = Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json
    foreach ($property in $state.processes.PSObject.Properties) {
        $process = Get-Process -Id $property.Value -ErrorAction SilentlyContinue
        [pscustomobject]@{
            Service = $property.Name
            PID = $property.Value
            Running = [bool]$process
            Process = if ($process) { $process.ProcessName } else { "-" }
        }
    }
}
else {
    Write-Host "没有进程记录。"
}

Write-Host "`n=== HTTP 健康检查 ===" -ForegroundColor Cyan
try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -TimeoutSec 5
    Write-Host "FastAPI: healthy (mode=$($health.mode))" -ForegroundColor Green
}
catch {
    Write-Host "FastAPI: unavailable" -ForegroundColor Red
}
try {
    $frontend = Invoke-WebRequest -Uri "http://127.0.0.1:5173" -UseBasicParsing -TimeoutSec 5
    Write-Host "React: healthy (HTTP $($frontend.StatusCode))" -ForegroundColor Green
}
catch {
    Write-Host "React: unavailable" -ForegroundColor Red
}
$mcp = Get-NetTCPConnection -LocalPort 8100 -State Listen -ErrorAction SilentlyContinue
if ($mcp) {
    Write-Host "MCP: listening (port 8100)" -ForegroundColor Green
}
else {
    Write-Host "MCP: unavailable" -ForegroundColor Red
}
