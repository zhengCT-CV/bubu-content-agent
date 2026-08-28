[CmdletBinding()]
param(
    [switch]$StopInfrastructure
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$RuntimeDir = Join-Path $ProjectRoot ".runtime"
$StateFile = Join-Path $RuntimeDir "processes.json"

function Stop-ProcessTree {
    param([int]$ProcessId)

    $children = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.ParentProcessId -eq $ProcessId }
    foreach ($child in $children) {
        Stop-ProcessTree -ProcessId $child.ProcessId
    }
    if (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue) {
        Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
    }
}

Set-Location -LiteralPath $ProjectRoot

if (Test-Path -LiteralPath $StateFile) {
    $state = Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json
    foreach ($property in $state.processes.PSObject.Properties) {
        Write-Host "停止 $($property.Name)..."
        Stop-ProcessTree -ProcessId ([int]$property.Value)
    }
    Remove-Item -LiteralPath $StateFile -Force
    Write-Host "FastAPI、MCP、Worker 和前端已停止。" -ForegroundColor Green
}
else {
    Write-Host "没有找到由 start-local.ps1 启动的进程记录。" -ForegroundColor Yellow
}

if ($StopInfrastructure) {
    docker compose stop
    if ($LASTEXITCODE -ne 0) {
        throw "Docker 容器停止失败。"
    }
    Write-Host "PostgreSQL 与 Redis 已暂停；Volume 数据仍然保留。" -ForegroundColor Green
}
else {
    Write-Host "PostgreSQL 与 Redis 继续在 Docker 中运行。"
}
