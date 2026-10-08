# bgy_backup_local.ps1
# Backup locale completo su HD esterno E:\BGY_Backup
# Include codice, config, credenziali, dump DB, output, logs.
# Retention: 30 giorni.
#
# Eseguito da Task Scheduler ogni giorno alle 08:00.
# Log: bgy_data\bgy_logs\backup_local.log
#
# Versione 1.0.0 — 07/10/2026

$ProjectRoot = "C:\Users\ncremaschi\Desktop\Monitoraggio BGY 2.5"
$BackupRoot  = "E:\BGY_Backup"
$LogFile     = "$ProjectRoot\bgy_data\bgy_logs\backup_local.log"
$StateFile   = "$ProjectRoot\bgy_data\bgy_logs\backup_local_state.json"
$PgDump      = "C:\Program Files\PostgreSQL\17\bin\pg_dump.exe"
$PgRestore   = "C:\Program Files\PostgreSQL\17\bin\pg_restore.exe"

$DbUser = "bgy_user"
$DbName = "bgy_monitoring"
$DbHost = "localhost"

$RetentionDays = 30

function Write-Log($msg) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$timestamp - $msg" | Out-File -FilePath $LogFile -Append -Encoding UTF8
}

function Send-FailureAlert($reason) {
    try {
        Set-Location $ProjectRoot
        py -3.12 -c "from bgy_core.bgy_mailer import send_backup_alert; send_backup_alert('Backup locale: $reason')" 2>&1 | Out-Null
        Write-Log "Email di allarme inviata."
    } catch {
        Write-Log "Impossibile inviare email di allarme: $_"
    }
}

# --- Verifica HD collegato ---
if (-not (Test-Path "E:\")) {
    Write-Log "HD esterno E: non collegato. Backup saltato."
    exit 2
}

# --- Prepara cartella backup di oggi ---
$today = Get-Date -Format "yyyy-MM-dd"
$backupDir = Join-Path $BackupRoot $today

Write-Log "=========================================="
Write-Log "Avvio backup locale: $backupDir"

if (-not (Test-Path $BackupRoot)) {
    New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null
    Write-Log "Creata cartella base: $BackupRoot"
}

if (Test-Path $backupDir) {
    Write-Log "Cartella di oggi gia' esistente, la rimuovo"
    Remove-Item $backupDir -Recurse -Force
}

New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

# --- 1. Robocopy del progetto ---
Write-Log "Avvio robocopy del progetto..."
$robolog = Join-Path $backupDir "robocopy.log"

& robocopy `
    $ProjectRoot `
    $backupDir `
    /E `
    /R:0 `
    /W:0 `
    /XD "__pycache__" ".pytest_cache" ".mypy_cache" `
    /XF "*.tmp" "_tmp_run.py" "*.pyc" `
    /NP /NFL /NDL `
    /LOG:$robolog | Out-Null

$rc = $LASTEXITCODE

# Robocopy exit code: 0-7 = OK, 8+ = errore
if ($rc -ge 8) {
    $reason = "robocopy fallito (code $rc)"
    Write-Log "ERRORE: $reason"
    Send-FailureAlert $reason
    exit 1
}
Write-Log "Robocopy completato (code $rc)"

# --- 2. pg_dump del DB ---
Write-Log "Avvio pg_dump..."
$dumpFile = Join-Path $backupDir "bgy_monitoring.dump"

try {
    & $PgDump -U $DbUser -h $DbHost -d $DbName -F c -f $dumpFile 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "pg_dump ha restituito codice $LASTEXITCODE"
    }
    Write-Log "pg_dump completato"
} catch {
    $reason = "pg_dump fallito: $_"
    Write-Log "ERRORE: $reason"
    Send-FailureAlert $reason
    exit 1
}

# --- 3. Verifica integrita' dump ---
try {
    & $PgRestore -l $dumpFile 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "pg_restore -l ha restituito codice $LASTEXITCODE"
    }
    Write-Log "Verifica integrita' dump OK"
} catch {
    $reason = "Verifica integrita' dump fallita: $_"
    Write-Log "ERRORE: $reason"
    Send-FailureAlert $reason
    exit 1
}

# --- 4. Manifest ---
$manifest = Join-Path $backupDir "MANIFEST.txt"
$totalSize = (Get-ChildItem $backupDir -Recurse -File -ErrorAction SilentlyContinue |
              Measure-Object -Property Length -Sum).Sum
$sizeMB = [math]::Round($totalSize / 1MB, 1)
$now = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

@"
Backup locale BGY Monitoring Suite
Data: $today
Ora:  $now
Dimensione: $sizeMB MB
Sorgente: $ProjectRoot
Dump DB: bgy_monitoring.dump
"@ | Out-File -FilePath $manifest -Encoding UTF8

Write-Log "Manifest scritto: $sizeMB MB totali"

# --- 5. State file per verify_sync ---
$stateJson = @{
    last_success = (Get-Date -Format "o")
    folder = $backupDir
    size_mb = $sizeMB
} | ConvertTo-Json -Compress

try {
    $stateJson | Out-File -FilePath $StateFile -Encoding UTF8 -Force
    Write-Log "State file scritto: $StateFile"
} catch {
    Write-Log "ATTENZIONE: impossibile scrivere state file: $_"
}

# --- 6. Retention ---
Write-Log "Retention: rimuovo backup piu' vecchi di $RetentionDays giorni..."
$cutoffDate = (Get-Date).AddDays(-$RetentionDays).Date
$removed = 0

Get-ChildItem -Path $BackupRoot -Directory -ErrorAction SilentlyContinue | ForEach-Object {
    if ($_.Name -match '^(\d{4}-\d{2}-\d{2})$') {
        try {
            $folderDate = [datetime]::ParseExact($matches[1], 'yyyy-MM-dd', $null)
            if ($folderDate -lt $cutoffDate) {
                Remove-Item $_.FullName -Recurse -Force
                Write-Log "Rimosso backup vecchio: $($_.Name)"
                $removed++
            }
        } catch { }
    }
}

Write-Log "Retention completata ($removed cartelle rimosse)"
Write-Log "Backup locale completato con successo."
exit 0