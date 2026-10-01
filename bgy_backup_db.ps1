# bgy_backup_db.ps1
# Esegue il dump di PostgreSQL, verifica l'integrita, applica la retention
# locale e remota, carica su Google Drive tramite rclone.
# In caso di errore, invia una notifica email immediata.

$ProjectRoot  = "C:\Users\ncremaschi\Desktop\Monitoraggio BGY 2.5"
$BackupDir    = Join-Path $ProjectRoot "bgy_data\bgy_db_backup"
$LogFile      = Join-Path $ProjectRoot "bgy_data\bgy_logs\backup.log"
$PgDump       = "C:\Program Files\PostgreSQL\17\bin\pg_dump.exe"
$PgRestore    = "C:\Program Files\PostgreSQL\17\bin\pg_restore.exe"
$RcloneRemote = "gdrive:BGY_Backup"

$DbUser = "bgy_user"
$DbName = "bgy_monitoring"
$DbHost = "localhost"

$RetentionDays = 30

function Write-Log($msg) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$timestamp - $msg" | Out-File -FilePath $LogFile -Append -Encoding UTF8
}

function Send-FailureAlert($reason) {
    # Chiama il mailer Python per inviare l'email di allarme
    try {
        $py = "py"
        $pyArgs = @(
            "-3.12", "-c",
            "from bgy_core.bgy_mailer import send_backup_alert; send_backup_alert('$reason')"
        )
        Set-Location $ProjectRoot
        & $py $pyArgs 2>&1 | Out-Null
        Write-Log "Email di allarme inviata."
    } catch {
        Write-Log "Impossibile inviare email di allarme: $_"
    }
}

# Crea cartella backup se non esiste
if (-not (Test-Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
}

$dateStr = Get-Date -Format "yyyy-MM-dd_HHmm"
$dumpFile = Join-Path $BackupDir "bgy_monitoring_$dateStr.dump"

# 1. pg_dump
Write-Log "Avvio backup DB: $dumpFile"
try {
    & $PgDump -U $DbUser -h $DbHost -d $DbName -F c -f $dumpFile 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "pg_dump ha restituito codice $LASTEXITCODE"
    }
    Write-Log "pg_dump completato."
} catch {
    $reason = "pg_dump fallito: $_"
    Write-Log "ERRORE: $reason"
    Send-FailureAlert $reason
    exit 1
}

# 2. Verifica integrità
try {
    $verify = & $PgRestore -l $dumpFile 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "pg_restore -l ha restituito codice $LASTEXITCODE"
    }
    Write-Log "Verifica integrità OK."
} catch {
    $reason = "Verifica integrità fallita: $_"
    Write-Log "ERRORE: $reason"
    Send-FailureAlert $reason
    exit 1
}

# 3. Retention locale
$cutoff = (Get-Date).AddDays(-$RetentionDays)
$oldFiles = Get-ChildItem -Path $BackupDir -Filter "bgy_monitoring_*.dump" |
    Where-Object { $_.LastWriteTime -lt $cutoff }
foreach ($f in $oldFiles) {
    Remove-Item $f.FullName -Force
    Write-Log "Rimosso dump locale vecchio: $($f.Name)"
}

# 4. Upload su Google Drive
Write-Log "Upload su Google Drive: $RcloneRemote"
try {
    & rclone copy $dumpFile $RcloneRemote --log-file $LogFile --log-level INFO 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "rclone copy ha restituito codice $LASTEXITCODE"
    }
    Write-Log "Upload completato."
} catch {
    $reason = "Upload rclone fallito: $_"
    Write-Log "ERRORE: $reason"
    Send-FailureAlert $reason
    exit 1
}

# 5. Retention remota
Write-Log "Retention remota su Google Drive..."
try {
    & rclone delete $RcloneRemote --min-age "${RetentionDays}d" --log-file $LogFile --log-level INFO 2>&1 | Out-Null
    Write-Log "Retention remota completata."
} catch {
    Write-Log "ATTENZIONE: retention remota fallita: $_"
    # Non blocca: il backup locale è OK, il file remoto è stato caricato.
}

Write-Log "Backup completato con successo."
exit 0