[CmdletBinding()]
param(
    [switch]$OpenBrowser
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Arq = Join-Path $ProjectRoot ".venv\Scripts\arq.exe"
$EnvFile = Join-Path $ProjectRoot ".env"
$RuntimeDir = Join-Path $ProjectRoot ".runtime"
$LogDir = Join-Path $RuntimeDir "logs"
$StateFile = Join-Path $RuntimeDir "processes.json"

function Read-DotEnv {
    param([string]$Path)

    $result = @{}
    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match '^\s*#' -or $line -notmatch '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
            continue
        }
        $key = $matches[1]
        $value = $matches[2].Trim()
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        $result[$key] = $value
    }
    return $result
}

function Test-PortFree {
    param([int]$Port)

    return -not (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Wait-Http {
    param(
        [string]$Uri,
        [int]$TimeoutSeconds = 60
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        try {
            $response = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 3
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) {
                return $response
            }
        }
        catch {
            Start-Sleep -Seconds 2
        }
    } while ((Get-Date) -lt $deadline)
    throw "等待服务超时：$Uri"
}

function Start-ManagedProcess {
    param(
        [string]$Name,
        [string]$FilePath,
        [string[]]$Arguments
    )

    $stdout = Join-Path $LogDir "$Name.out.log"
    $stderr = Join-Path $LogDir "$Name.err.log"
    return Start-Process `
        -FilePath $FilePath `
        -ArgumentList $Arguments `
        -WorkingDirectory $ProjectRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr `
        -PassThru
}

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

if (-not (Test-Path -LiteralPath $Python) -or -not (Test-Path -LiteralPath $Arq)) {
    throw "未找到项目 .venv，请先运行：.\scripts\bootstrap.ps1"
}
if (-not (Test-Path -LiteralPath $EnvFile)) {
    throw "未找到 .env，请先从 .env.example 复制并填写配置。"
}
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "未找到 Docker CLI，请先启动 Docker Desktop。"
}
$pnpmCommand = Get-Command pnpm.cmd -ErrorAction SilentlyContinue
$npmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
if ($pnpmCommand) {
    $frontendCommand = $pnpmCommand.Source
    $frontendArguments = @("--dir", "frontend", "dev", "--host", "127.0.0.1")
}
elseif ($npmCommand) {
    # 普通 PowerShell 可能看不到 Codex 自带的 pnpm；npm 同样可以运行已安装的 Vite。
    $frontendCommand = $npmCommand.Source
    $frontendArguments = @("--prefix", "frontend", "run", "dev", "--", "--host", "127.0.0.1")
    Write-Host "未找到 pnpm，将自动使用 npm 启动前端。" -ForegroundColor Yellow
}
else {
    throw "未找到 Node.js/npm。请安装 Node.js 后重新运行启动脚本。"
}

$config = Read-DotEnv -Path $EnvFile
if ($config.APP_MODE -ne "local") {
    throw ".env 中 APP_MODE 必须为 local，当前为：$($config.APP_MODE)"
}
foreach ($key in "DEEPSEEK_API_KEY", "DASHSCOPE_API_KEY", "WRITEBACK_APPROVAL_SECRET") {
    $value = [string]$config[$key]
    if (-not $value -or $value -match '^(change-me|development-only-change-me|your-|sk-xxx|xxx|\.\.\.)$') {
        throw ".env 中 $key 尚未正确配置。"
    }
}

if (Test-Path -LiteralPath $StateFile) {
    $oldState = Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json
    $alive = @($oldState.processes.PSObject.Properties.Value | Where-Object { Get-Process -Id $_ -ErrorAction SilentlyContinue })
    if ($alive.Count -gt 0) {
        Write-Host "Bubu Local 已在运行。使用 .\scripts\status-local.ps1 查看状态。" -ForegroundColor Yellow
        if ($OpenBrowser) {
            Start-Process "http://127.0.0.1:5173"
        }
        exit 0
    }
    Remove-Item -LiteralPath $StateFile -Force
}

foreach ($port in 5173, 8000, 8100) {
    if (-not (Test-PortFree -Port $port)) {
        throw "端口 $port 已被其他进程占用。请先关闭旧服务，或运行 .\scripts\stop-local.ps1。"
    }
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Engine 尚未运行，请打开 Docker Desktop 并等待 Engine running。"
}

Write-Host "[1/5] 启动 PostgreSQL/pgvector 与 Redis..." -ForegroundColor Cyan
docker compose up -d --wait --wait-timeout 120
if ($LASTEXITCODE -ne 0) {
    throw "Docker 基础设施启动失败。"
}

New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

# MCP 原生读取 .env；这里额外导出配置，让所有子进程的环境来源保持一致。
$oldPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = "$ProjectRoot\backend;$ProjectRoot"
foreach ($item in $config.GetEnumerator()) {
    Set-Item -Path "Env:$($item.Key)" -Value $item.Value
}
$startedProcesses = @()

try {
    Write-Host "[2/5] 启动微信公众号数据 MCP..." -ForegroundColor Cyan
    $mcp = Start-ManagedProcess -Name "mcp" -FilePath $Python -Arguments @("-m", "mcp_server.app.server")
    $startedProcesses += $mcp

    $mcpDeadline = (Get-Date).AddSeconds(45)
    while ((Test-PortFree -Port 8100) -and (Get-Date) -lt $mcpDeadline) {
        if ($mcp.HasExited) {
            throw "MCP 启动失败，请查看 $LogDir\mcp.err.log"
        }
        Start-Sleep -Seconds 1
    }
    if (Test-PortFree -Port 8100) {
        throw "MCP 启动超时，请查看 $LogDir\mcp.err.log"
    }

    Write-Host "[3/5] 启动 FastAPI 与 LangGraph..." -ForegroundColor Cyan
    $api = Start-ManagedProcess -Name "api" -FilePath $Python -Arguments @("-m", "app.serve_api")
    $startedProcesses += $api

    Write-Host "[4/5] 启动 ARQ 异步 Worker..." -ForegroundColor Cyan
    $worker = Start-ManagedProcess -Name "worker" -FilePath $Arq -Arguments @("app.workers.settings.WorkerSettings")
    $startedProcesses += $worker

    Write-Host "[5/5] 启动 React 工作台..." -ForegroundColor Cyan
    $frontend = Start-ManagedProcess `
        -Name "frontend" `
        -FilePath $frontendCommand `
        -Arguments $frontendArguments
    $startedProcesses += $frontend

    $state = [ordered]@{
        started_at = (Get-Date).ToString("o")
        processes = [ordered]@{
            mcp = $mcp.Id
            api = $api.Id
            worker = $worker.Id
            frontend = $frontend.Id
        }
    }
    $state | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $StateFile -Encoding UTF8

    $healthResponse = Wait-Http -Uri "http://127.0.0.1:8000/api/health" -TimeoutSeconds 90
    $health = $healthResponse.Content | ConvertFrom-Json
    if ($health.mode -ne "local") {
        throw "API 已启动，但运行模式不是 local。"
    }
    Wait-Http -Uri "http://127.0.0.1:5173" -TimeoutSeconds 60 | Out-Null
    if ($worker.HasExited) {
        throw "ARQ Worker 启动后退出，请查看 $LogDir\worker.err.log"
    }

    Write-Host ""
    Write-Host "Bubu ContentOps Agent 已启动。" -ForegroundColor Green
    Write-Host "工作台：http://127.0.0.1:5173"
    Write-Host "API 文档：http://127.0.0.1:8000/docs"
    Write-Host "日志目录：$LogDir"
    Write-Host "停止应用：.\scripts\stop-local.ps1"

    if ($OpenBrowser) {
        Start-Process "http://127.0.0.1:5173"
    }
}
catch {
    Write-Host "启动未完成，正在清理本次启动的进程..." -ForegroundColor Yellow
    for ($index = $startedProcesses.Count - 1; $index -ge 0; $index--) {
        Stop-ProcessTree -ProcessId ([int]$startedProcesses[$index].Id)
    }
    if (Test-Path -LiteralPath $StateFile) {
        Remove-Item -LiteralPath $StateFile -Force
    }
    Write-Error $_
    throw
}
finally {
    $env:PYTHONPATH = $oldPythonPath
}
