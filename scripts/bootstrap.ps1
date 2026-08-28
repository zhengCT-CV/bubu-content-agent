$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = "D:\anaconda3\envs\agent\python.exe"
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $VenvPython)) {
    & $Python -m venv (Join-Path $ProjectRoot ".venv")
}

& $VenvPython -m pip install -U pip
& $VenvPython -m pip install -e (Join-Path $ProjectRoot "backend[dev]")
pnpm --dir (Join-Path $ProjectRoot "frontend") install

$EnvFile = Join-Path $ProjectRoot ".env"
if (-not (Test-Path -LiteralPath $EnvFile)) {
    Copy-Item -LiteralPath (Join-Path $ProjectRoot ".env.example") -Destination $EnvFile
}

Write-Host "Bootstrap complete. See README.md for demo/local startup commands."

