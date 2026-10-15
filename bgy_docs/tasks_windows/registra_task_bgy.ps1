<#
.SYNOPSIS
    Registra i task schedulati della BGY Monitoring Suite su Windows.

.DESCRIPTION
    Registra (o ri-registra) in un colpo solo i 5 task necessari:
      BGY_Avvio, BGY_Supervisor, BGY_Backup, BGY_BackupLocal, BGY_BackupEncrypted

    Ogni task viene registrato a partire dal rispettivo XML in
    bgy_docs/tasks_windows/. I task sono configurati con LogonType=S4U.

.VERSION
    v1.1.0 (SEC-04, 13/10/2026):
        - Aggiunto BGY_BackupEncrypted
        - Aggiunta verifica esistenza XML prima della registrazione
        - Gestione errori con try/catch
#>

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$TaskNames = @(
    "BGY_Avvio",
    "BGY_Supervisor",
    "BGY_Backup",
    "BGY_BackupLocal",
    "BGY_BackupEncrypted"
)

# Verifica privilegi admin
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal(
    [Security.Principal.WindowsIdentity]::GetCurrent()
)
$isAdmin = $currentPrincipal.IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)

if (-not $isAdmin) {
    Write-Host "ERRORE: script richiede privilegi di Amministratore." -ForegroundColor Red
    exit 1
}

# Verifica posizione
$tasksDir = Join-Path (Get-Location) "bgy_docs\tasks_windows"
if (-not (Test-Path $tasksDir)) {
    Write-Host "ERRORE: cartella non trovata: $tasksDir" -ForegroundColor Red
    Write-Host "   Esegui lo script dalla root del progetto." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== Registrazione task BGY Monitoring Suite ===" -ForegroundColor Cyan
Write-Host "Cartella XML: $tasksDir" -ForegroundColor Gray
Write-Host "Task da registrare: $($TaskNames.Count)"
Write-Host ""

# Rimozione task esistenti
Write-Host "--- Rimozione task esistenti ---" -ForegroundColor Cyan
foreach ($taskName in $TaskNames) {
    $existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($existing) {
        try {
            Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
            Write-Host "  OK Rimosso: $taskName" -ForegroundColor Green
        } catch {
            Write-Host "  WARN Errore rimozione ${taskName}: $_" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  INFO Non esisteva: $taskName" -ForegroundColor Gray
    }
}

# Registrazione
Write-Host ""
Write-Host "--- Registrazione task ---" -ForegroundColor Cyan
$registered = @()
$failed = @()

foreach ($taskName in $TaskNames) {
    $xmlPath = Join-Path $tasksDir "$taskName.xml"
    if (-not (Test-Path $xmlPath)) {
        Write-Host "  ERR XML non trovato: $xmlPath" -ForegroundColor Red
        $failed += $taskName
        continue
    }
    try {
        $xmlContent = Get-Content $xmlPath -Raw
        Register-ScheduledTask -TaskName $taskName -Xml $xmlContent -Force | Out-Null
        Write-Host "  OK Registrato: $taskName" -ForegroundColor Green
        $registered += $taskName
    } catch {
        Write-Host "  ERR Errore su ${taskName}: $_" -ForegroundColor Red
        $failed += $taskName
    }
}

# Stato finale
Write-Host ""
Write-Host "--- Stato finale ---" -ForegroundColor Cyan
foreach ($taskName in $TaskNames) {
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($task) {
        $info = Get-ScheduledTaskInfo -TaskName $taskName
        Write-Host "  OK $taskName"
        Write-Host "       Stato:      $($task.State)"
        Write-Host "       LogonType:  $($task.Principal.LogonType)"
        Write-Host "       Prossima:   $($info.NextRunTime)"
    } else {
        Write-Host "  ERR $taskName non trovato" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host ("=" * 60) -ForegroundColor Cyan
Write-Host "RIEPILOGO" -ForegroundColor Cyan
Write-Host ("=" * 60) -ForegroundColor Cyan
Write-Host "Registrati: $($registered.Count) ($($registered -join ', '))"
if ($failed.Count -gt 0) {
    Write-Host "Falliti:    $($failed.Count) ($($failed -join ', '))" -ForegroundColor Red
}

exit $failed.Count
