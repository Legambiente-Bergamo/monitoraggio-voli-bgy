# bgy_supervisor.ps1
$ProjectRoot = "C:\Users\ncremaschi\Desktop\Monitoraggio BGY 2.5"
$LockFile    = Join-Path $ProjectRoot "bgy_data\bgy_logs\scheduler.lock"
$LogFile     = Join-Path $ProjectRoot "bgy_data\bgy_logs\supervisor.log"
$StartScript = Join-Path $ProjectRoot "Avvia BGY.bat"

function Write-Log($msg) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$timestamp - $msg" | Out-File -FilePath $LogFile -Append -Encoding UTF8
}

$schedulerPid = $null
if (Test-Path $LockFile) {
    try { $schedulerPid = [int](Get-Content $LockFile -Raw).Trim() } catch { }
}

$isAlive = $false
if ($schedulerPid) {
    $proc = Get-Process -Id $schedulerPid -ErrorAction SilentlyContinue
    if ($proc) { $isAlive = $true }
}

if ($isAlive) { exit 0 }

Write-Log "Scheduler NON attivo (PID: $schedulerPid). Avvio la suite..."
Start-Process -FilePath $StartScript -WorkingDirectory $ProjectRoot -WindowStyle Hidden
Write-Log "Suite avviata."