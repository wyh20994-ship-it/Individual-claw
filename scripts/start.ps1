# HangClaw 一键启动脚本 (Windows PowerShell)

$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

Write-Host "=== HangClaw Starting ===" -ForegroundColor Cyan

# 启动 Python Runner
Write-Host "[1/2] Starting Python Runner..." -ForegroundColor Yellow
$runner = Start-Process -FilePath "python" -ArgumentList "main.py" -WorkingDirectory "$RootDir\runner" -PassThru -NoNewWindow
Write-Host "  Runner PID: $($runner.Id)"

Start-Sleep -Seconds 2

# 启动 Node.js Gateway
Write-Host "[2/2] Starting Node.js Gateway..." -ForegroundColor Yellow
$gateway = Start-Process -FilePath "npm" -ArgumentList "run dev" -WorkingDirectory "$RootDir\gateway" -PassThru -NoNewWindow
Write-Host "  Gateway PID: $($gateway.Id)"

Write-Host ""
Write-Host "=== HangClaw Running ===" -ForegroundColor Green
Write-Host "  Gateway: http://localhost:3000"
Write-Host "  Press Ctrl+C to stop"

try {
    Wait-Process -Id $runner.Id, $gateway.Id
} finally {
    Stop-Process -Id $runner.Id -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $gateway.Id -Force -ErrorAction SilentlyContinue
    Write-Host "Stopped." -ForegroundColor Red
}
