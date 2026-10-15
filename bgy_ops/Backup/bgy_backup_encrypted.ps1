<#
.SYNOPSIS
    Backup cifrato giornaliero dei file sensibili della BGY Monitoring Suite.

.DESCRIPTION
    Crea due archivi .7z e li carica su Google Drive (gdrive:BGY_Backup_Encrypted/):

      1) bgy_config_YYYY-MM-DD.7z  (CIFRATO AES-256, header cifrato)
         Contenuto: bgy_config/*.json + bgy_docs/tasks_windows/*.xml

      2) bgy_suite_YYYY-MM-DD.7z   (NON cifrato)
         Contenuto: codice + script + docs + config pubblica
         Esclude: bgy_config/*.json (credenziali), bgy_data/, bgy_tests/, .git/

    Retention: elimina da Drive i file più vecchi di 7 giorni.

    Eseguito dal task di sistema BGY_BackupEncrypted (LogonType=S4U).

.VERSION
    v1.0.1 (SEC-04, 14/10/2026):
        - FIX CRITICO: variabile $pwd → $secret.
          $pwd è un alias automatico di PowerShell (Get-Location).
          In presenza di Push-Location/Pop-Location, PowerShell sovrascriveva
          silenziosamente $pwd con il path corrente, cifrando gli archivi con
          una stringa pubblica anziché con la password utente.
          Il file .bgy_backup_pwd non è mai stato usato per la cifratura.
        - Con la v1.0.0 gli archivi risultavano cifrati con
          "C:\Users\ncremaschi\Desktop\Monitoraggio BGY 2.5" (path pubblico
          su GitHub). Tutti gli archivi generati vanno considerati compromessi
          e rigenerati.
    v1.0.0 (SEC-04, 13/10/2026) - prima versione (con bug $pwd).

.NOTES
    Password: letta da C:\Users\ncremaschi\.bgy_backup_pwd
    Log:      bgy_data/bgy_logs/backup_encrypted.log
    Riferimenti: Relazione v3.8 §10.3, §13.5; Addendum 4 (ciclo v3.8).
#>

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

# =============================================================================
# CONFIGURAZIONE
# =============================================================================

$ProjectRoot      = "C:\Users\ncremaschi\Desktop\Monitoraggio BGY 2.5"
$SevenZip         = "C:\Program Files\7-Zip\7z.exe"
$Rclone           = "C:\Users\ncremaschi\AppData\Local\Microsoft\WinGet\Links\rclone.exe"
$PwdFile          = "C:\Users\ncremaschi\.bgy_backup_pwd"
$GDriveFolder     = "gdrive:BGY_Backup_Encrypted"
$RetentionDays    = 7

$LogDir           = Join-Path $ProjectRoot "bgy_data\bgy_logs"
$LogFile          = Join-Path $LogDir "backup_encrypted.log"
$TmpDir           = Join-Path $ProjectRoot "bgy_data\bgy_backup_encrypted_tmp"

# =============================================================================
# UTILITY
# =============================================================================

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] [$Level] $Message"
    Write-Host $line
    if (!(Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
}

function Send-BackupAlert {
    param([string]$Reason)
    try {
        $safeReason = $Reason -replace "'", "''"
        $cmd = "from bgy_core.bgy_mailer import send_backup_alert; send_backup_alert('$safeReason')"
        Push-Location $ProjectRoot
        py -3.12 -c $cmd 2>&1 | Out-Null
        Pop-Location
    } catch {
        Write-Log "Impossibile inviare email di allarme: $_" "WARN"
    }
}

# =============================================================================
# START
# =============================================================================

Write-Log "===== AVVIO BACKUP CIFRATO ====="
$exitCode = 0
$dateStr = Get-Date -Format "yyyy-MM-dd"

try {

    # -------------------------------------------------------------------------
    # 1) Verifica prerequisiti
    # -------------------------------------------------------------------------
    Write-Log "Verifica prerequisiti..."

    if (!(Test-Path $SevenZip)) {
        throw "7-Zip non trovato in $SevenZip"
    }
    if (!(Test-Path $Rclone)) {
        throw "rclone non trovato in $Rclone"
    }
    if (!(Test-Path $PwdFile)) {
        throw "File password non trovato: $PwdFile"
    }
    if (!(Test-Path $ProjectRoot)) {
        throw "Project root non trovata: $ProjectRoot"
    }

    # Leggi password (mai loggata)
    # v1.0.1: usa $secret, non $pwd ($pwd è alias automatico di PowerShell).
    $secret = (Get-Content $PwdFile -Raw).Trim()
    if ([string]::IsNullOrWhiteSpace($secret)) {
        throw "File password vuoto: $PwdFile"
    }
    Write-Log "Password letta da $PwdFile (lunghezza: $($secret.Length) caratteri)"

    # Crea cartella temporanea
    if (Test-Path $TmpDir) { Remove-Item $TmpDir -Recurse -Force }
    New-Item -ItemType Directory -Path $TmpDir -Force | Out-Null

    # -------------------------------------------------------------------------
    # 2) Archivio 1 — CIFRATO (credenziali + XML task)
    # -------------------------------------------------------------------------
    $archiveConfig = Join-Path $TmpDir "bgy_config_$dateStr.7z"
    Write-Log "Creazione archivio cifrato: $archiveConfig"

    Push-Location $ProjectRoot
    try {
        & $SevenZip a -t7z -mx=7 `
            "-p$secret" -mhe=on `
            $archiveConfig `
            "bgy_config\*.json" `
            "bgy_docs\tasks_windows\*.xml" `
            | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "7z (config) exit code: $LASTEXITCODE"
        }
    } finally {
        Pop-Location
    }

    if (!(Test-Path $archiveConfig)) {
        throw "Archivio config non creato"
    }
    $sizeConfig = [math]::Round((Get-Item $archiveConfig).Length / 1KB, 1)
    Write-Log "Archivio config creato: $sizeConfig KB"

    # -------------------------------------------------------------------------
    # 3) Archivio 2 — NON cifrato (codice + suite)
    # -------------------------------------------------------------------------
    $archiveSuite = Join-Path $TmpDir "bgy_suite_$dateStr.7z"
    Write-Log "Creazione archivio suite: $archiveSuite"

    Push-Location $ProjectRoot
    try {
        & $SevenZip a -t7z -mx=5 `
            $archiveSuite `
            "bgy_core" "bgy_scanners" "bgy_reports" "bgy_exporters" `
            "bgy_gui" "bgy_utils" "bgy_tools" "bgy_ops" `
            "bgy_docs" `
            "bgy_config\config_data.json" `
            "bgy_scheduler.py" "bgy_watchdog.py" "bgy_gui.py" `
            "bgy_avvia_headless.bat" "Avvia BGY.bat" `
            "bgy_supervisor.ps1" "bgy_backup_db.ps1" "bgy_backup_local.ps1" `
            "requirements.txt" `
            -xr!"__pycache__" -xr!"*.pyc" -xr!".pytest_cache" -xr!".mypy_cache" `
            | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "7z (suite) exit code: $LASTEXITCODE"
        }
    } finally {
        Pop-Location
    }

    if (!(Test-Path $archiveSuite)) {
        throw "Archivio suite non creato"
    }
    $sizeSuite = [math]::Round((Get-Item $archiveSuite).Length / 1KB, 1)
    Write-Log "Archivio suite creato: $sizeSuite KB"

    # -------------------------------------------------------------------------
    # 4) Assicura esistenza cartella remota
    # -------------------------------------------------------------------------
    Write-Log "Verifica cartella remota: $GDriveFolder"
    & $Rclone mkdir $GDriveFolder --log-level ERROR
    if ($LASTEXITCODE -ne 0) {
        throw "rclone mkdir exit code: $LASTEXITCODE"
    }

    # -------------------------------------------------------------------------
    # 5) Upload su Google Drive
    # -------------------------------------------------------------------------
    Write-Log "Upload archivio config su Drive..."
    & $Rclone copy $archiveConfig "$GDriveFolder/" --log-level ERROR
    if ($LASTEXITCODE -ne 0) {
        throw "rclone upload (config) exit code: $LASTEXITCODE"
    }

    Write-Log "Upload archivio suite su Drive..."
    & $Rclone copy $archiveSuite "$GDriveFolder/" --log-level ERROR
    if ($LASTEXITCODE -ne 0) {
        throw "rclone upload (suite) exit code: $LASTEXITCODE"
    }

    Write-Log "Upload completato"

    # -------------------------------------------------------------------------
    # 6) Retention: elimina file >7 giorni
    # -------------------------------------------------------------------------
    Write-Log "Retention: elimino file >$RetentionDays giorni"
    & $Rclone delete $GDriveFolder --min-age "${RetentionDays}d" --log-level ERROR
    if ($LASTEXITCODE -ne 0) {
        Write-Log "rclone delete exit code: $LASTEXITCODE (non bloccante)" "WARN"
    }

    # -------------------------------------------------------------------------
    # 7) Cleanup temporanei
    # -------------------------------------------------------------------------
    Write-Log "Cleanup cartella temporanea"
    Remove-Item $TmpDir -Recurse -Force -ErrorAction SilentlyContinue

    Write-Log "===== BACKUP CIFRATO COMPLETATO ====="

} catch {
    $exitCode = 1
    Write-Log "ERRORE: $_" "ERROR"
    Write-Log $_.ScriptStackTrace "ERROR"
    Send-BackupAlert "Backup cifrato fallito: $_"
    Write-Log "===== BACKUP CIFRATO FALLITO ====="
} finally {
    if (Test-Path $TmpDir) {
        Remove-Item $TmpDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

exit $exitCode