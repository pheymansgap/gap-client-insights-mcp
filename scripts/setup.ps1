# VS Code MCP Setup Helper

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  Client Intelligence MCP - Setup" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""

# Check uv
Write-Host "Checking for uv..." -ForegroundColor Cyan
$uvInstalled = $false
try {
    $uvVersion = uv --version 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  uv installed: $uvVersion" -ForegroundColor Green
        $uvInstalled = $true
    }
} catch {}

if (-not $uvInstalled) {
    Write-Host "  Installing uv..." -ForegroundColor Cyan
    try {
        irm https://astral.sh/uv/install.ps1 | iex
        Write-Host "  uv installed" -ForegroundColor Green
    } catch {
        Write-Host "  Failed to install uv. Install manually: https://docs.astral.sh/uv/" -ForegroundColor Red
        exit 1
    }
}

# Install dependencies
Write-Host ""
Write-Host "Installing dependencies..." -ForegroundColor Cyan
uv sync
Write-Host "  Dependencies installed" -ForegroundColor Green

# Check .env
Write-Host ""
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        $response = Read-Host "No .env file found. Copy .env.example to .env? (y/n)"
        if ($response -eq 'y' -or $response -eq 'Y') {
            Copy-Item .env.example .env
            Write-Host "  Created .env — edit it to add your API keys" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  No .env or .env.example found" -ForegroundColor Red
    }
} else {
    Write-Host "  .env file found" -ForegroundColor Green
}

# Run verification
Write-Host ""
Write-Host "Running verification..." -ForegroundColor Cyan
uv run python scripts/verify.py

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  Done. See SETUP.md for VS Code config." -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
