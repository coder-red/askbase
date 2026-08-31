# Starts the BaseChatt API + prerequisites on Windows.
# Run:  powershell -ExecutionPolicy Bypass -File scripts\start-env.ps1
$ErrorActionPreference = "Stop"
$root = "C:\Users\hp\basechatt\basechatt"
$py = "$root\.venv\Scripts\python.exe"

Write-Host "==> Checking Postgres (native PG w/ pgvector on :5433)..." -ForegroundColor Cyan
$pg = Get-NetTCPConnection -LocalPort 5433 -State Listen -ErrorAction SilentlyContinue
if (-not $pg) {
    Write-Host "    Postgres not running. Start it from the .pg0 service, or run:" -ForegroundColor Yellow
    Write-Host "    C:\Users\hp\.pg0\installation\18.1.0\bin\pg_ctl -D C:\Users\hp\.pg0\data start"
} else {
    Write-Host "    Postgres OK (pid $($pg.OwningProcess))" -ForegroundColor Green
}

Write-Host "==> Checking Redis (WSL basechatt-dev on :6380)..." -ForegroundColor Cyan
$rd = Get-NetTCPConnection -LocalPort 6380 -State Listen -ErrorAction SilentlyContinue
if (-not $rd) {
    Write-Host "    Redis not up. Start WSL distro and redis-server inside it:" -ForegroundColor Yellow
    Write-Host "    wsl -d basechatt-dev -u root -- redis-server --port 6380 --daemonize yes"
} else {
    Write-Host "    Redis OK (pid $($rd.OwningProcess))" -ForegroundColor Green
}

Write-Host "==> Ensuring httpx/json logging fixed (console utf-8)..." -ForegroundColor Cyan
$env:PYTHONIOENCODING = "utf-8"

$portInUse = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($portInUse) {
    Write-Host "    Port 8000 in use (pid $($portInUse.OwningProcess)); killing stale server..." -ForegroundColor Yellow
    Stop-Process -Id $portInUse.OwningProcess -Force -ErrorAction SilentlyContinue
    Start-Sleep 2
}

Write-Host "==> Starting API at http://127.0.0.1:8000 (logs in temp\opencode\uvicorn.*.log)..." -ForegroundColor Cyan
$out = "$env:TEMP\opencode\uvicorn.out.log"; $err = "$env:TEMP\opencode\uvicorn.err.log"
Remove-Item $out,$err -ErrorAction SilentlyContinue
Start-Process -FilePath $py -ArgumentList "-m","uvicorn","apps.api.main:app","--host","127.0.0.1","--port","8000" `
    -WorkingDirectory $root -RedirectStandardOutput $out -RedirectStandardError $err -WindowStyle Hidden
Start-Sleep 5
try {
    $h = Invoke-RestMethod "http://127.0.0.1:8000/api/v1/health" -TimeoutSec 5
    Write-Host "    API online: $($h.status) | db=$($h.database) | provider=$($h.provider)" -ForegroundColor Green
    Write-Host "Open the chat UI:  http://127.0.0.1:8000/" -ForegroundColor Green
} catch {
    Write-Host "    API failed to start. Check $err" -ForegroundColor Red
}