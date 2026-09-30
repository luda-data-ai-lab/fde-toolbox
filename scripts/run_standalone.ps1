# Runs FDE Toolbox without Docker on Windows: uvicorn serving the API and the built frontend.
# Prerequisites: Python 3.12 (py launcher) and a built frontend (frontend\dist).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$HostAddr = if ($env:HOST) { $env:HOST } else { "127.0.0.1" }
$Port = if ($env:PORT) { $env:PORT } else { "8000" }
Set-Location (Join-Path $Root "backend")

if (-not (Test-Path (Join-Path $Root "frontend\dist\index.html"))) {
    Write-Error "frontend\dist not found. Build it first: cd frontend; npm ci; npm run build"
}
$Py = Join-Path (Get-Location) ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) {
    py -3.12 -m venv .venv
    & $Py -m pip install --upgrade pip | Out-Null
    & $Py -m pip install -e .
}
if (-not (Test-Path ".env")) {
    $secret = & $Py -c "import secrets; print(secrets.token_urlsafe(48))"
    $fernet = & $Py -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    (Get-Content ".env.example") `
        -replace '^SECRET_KEY=.*', "SECRET_KEY=$secret" `
        -replace '^ENCRYPTION_KEY=.*', "ENCRYPTION_KEY=$fernet" | Set-Content ".env" -Encoding UTF8
    Write-Host "created backend\.env with generated keys"
}
New-Item -ItemType Directory -Force -Path "data" | Out-Null
$env:STATIC_DIR = Join-Path $Root "frontend\dist"
& $Py -m app.cli migrate
& $Py -m app.cli seed-assets
if ($LASTEXITCODE -ne 0) { Write-Host "seed-assets skipped: run 'python -m app.cli init-admin' first" }
Write-Host "FDE Toolbox on http://${HostAddr}:${Port}"
& $Py -m uvicorn app.main:app --host $HostAddr --port $Port
