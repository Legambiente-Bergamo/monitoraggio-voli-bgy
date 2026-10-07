# bgy_tools/context_bundle.ps1
# Genera un bundle testuale con codice + schema + esempi dati
# per la sessione INFRA-01 (Avionio come fonte cargo).
#
# Uso:
#   cd "C:\Users\ncremaschi\Desktop\Monitoraggio BGY 2.5"
#   .\bgy_tools\context_bundle.ps1 > context_2026-10-07.txt
#
# Non include credenziali.

$ErrorActionPreference = "Continue"
$root = (Get-Location).Path

function Dump-File {
    param([string]$RelPath)
    Write-Output ""
    Write-Output "===== FILE: $RelPath ====="
    $full = Join-Path $root $RelPath
    if (Test-Path $full) {
        Get-Content $full -Raw -Encoding UTF8
    } else {
        Write-Output "(non trovato)"
    }
    Write-Output ""
}

function Dump-Head {
    param([string]$RelPath, [int]$Lines = 5)
    Write-Output ""
    Write-Output "===== HEAD ($Lines): $RelPath ====="
    $full = Join-Path $root $RelPath
    if (Test-Path $full) {
        Get-Content $full -TotalCount $Lines -Encoding UTF8
    } else {
        Write-Output "(non trovato)"
    }
    Write-Output ""
}

function Dump-Dir {
    param([string]$RelPath, [int]$MaxItems = 30)
    Write-Output ""
    Write-Output "===== DIR: $RelPath ====="
    $full = Join-Path $root $RelPath
    if (Test-Path $full) {
        Get-ChildItem $full -File | 
            Select-Object -First $MaxItems Name, Length, LastWriteTime |
            Format-Table -AutoSize | Out-String -Width 200
    } else {
        Write-Output "(cartella non trovata)"
    }
    Write-Output ""
}

# ----------------------------------------------------------------
# HEADER
# ----------------------------------------------------------------
Write-Output "############################################################"
Write-Output "# BGY Monitoring Suite - Context Bundle per INFRA-01"
Write-Output "# Data: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Output "# Root: $root"
Write-Output "############################################################"

# ----------------------------------------------------------------
# 1. CODICE PYTHON
# ----------------------------------------------------------------
Write-Output ""
Write-Output "############################################################"
Write-Output "# SEZIONE 1 - CODICE PYTHON"
Write-Output "############################################################"

$pyFiles = @(
    "bgy_scanners\bgy_scanner_alt.py",
    "bgy_scanners\bgy_scanner_day.py",
    "bgy_scanners\bgy_scanner_radar.py",
    "bgy_reports\bgy_report_night.py",
    "bgy_reports\bgy_report_day.py",
    "bgy_core\bgy_export_web.py",
    "bgy_core\bgy_mailer.py",
    "bgy_core\bgy_db_migrate.py",
    "bgy_core\bgy_update_rules.py",
    "bgy_core\bgy_config_manager.py",
    "bgy_core\bgy_dates.py",
    "bgy_core\bgy_paths.py",
    "bgy_core\__init__.py",
    "bgy_scheduler.py",
    "bgy_watchdog.py"
)

foreach ($f in $pyFiles) { Dump-File $f }

# Cerca il file del check 10 (conferma incrociata Avionio)
Write-Output ""
Write-Output "===== RICERCA: file con confronto o avionio ====="
Get-ChildItem $root -Recurse -Include "*.py" -File -ErrorAction SilentlyContinue |
    Where-Object { 
        $_.Name -match "confronto|avionio" -and 
        $_.FullName -notmatch "\\bgy_data\\|\\__pycache__\\"
    } |
    Select-Object FullName, Length |
    Format-Table -AutoSize | Out-String -Width 250

# ----------------------------------------------------------------
# 2. CONFIGURAZIONE (senza credenziali)
# ----------------------------------------------------------------
Write-Output ""
Write-Output "############################################################"
Write-Output "# SEZIONE 2 - CONFIGURAZIONE"
Write-Output "############################################################"

Dump-File "bgy_config\config_data.json"

# ----------------------------------------------------------------
# 3. SCHEMA DATABASE (comandi, non output)
# ----------------------------------------------------------------
Write-Output ""
Write-Output "############################################################"
Write-Output "# SEZIONE 3 - SCHEMA DATABASE"
Write-Output "############################################################"
Write-Output ""
Write-Output "Esegui questi comandi PSQL e incolla l output nel bundle:"
Write-Output ""
Write-Output "psql -U bgy_user -d bgy_monitoring -c '\d nightly_reports'"
Write-Output "psql -U bgy_user -d bgy_monitoring -c '\d callsign_airline_patterns'"
Write-Output "psql -U bgy_user -d bgy_monitoring -c '\d iata_to_icao'"
Write-Output "psql -U bgy_user -d bgy_monitoring -c '\d airlines'"
Write-Output "psql -U bgy_user -d bgy_monitoring -c '\d radar_detections'"
Write-Output "psql -U bgy_user -d bgy_monitoring -c '\d scans'"
Write-Output "psql -U bgy_user -d bgy_monitoring -c 'SELECT * FROM callsign_airline_patterns;'"
Write-Output ""

# ----------------------------------------------------------------
# 4. INVENTARIO DATI
# ----------------------------------------------------------------
Write-Output ""
Write-Output "############################################################"
Write-Output "# SEZIONE 4 - INVENTARIO DATI"
Write-Output "############################################################"

Dump-Dir "bgy_data\bgy_avionio" 50
Dump-Dir "bgy_data\bgy_raw" 40
Dump-Dir "bgy_data\bgy_output\bgy_csv" 20
Dump-Dir "bgy_data\bgy_output\bgy_web" 10
Dump-Dir "bgy_data\bgy_logs" 15

# ----------------------------------------------------------------
# 5. ESEMPI DATI
# ----------------------------------------------------------------
Write-Output ""
Write-Output "############################################################"
Write-Output "# SEZIONE 5 - ESEMPI DATI"
Write-Output "############################################################"

# Esempio radar notturno
Dump-Head "bgy_data\bgy_raw\radar_2026-10-06.csv" 5

# Esempio report notturno - ultimo disponibile
$lastReport = Get-ChildItem "bgy_data\bgy_output\bgy_csv\report_nightly_*.csv" -File -ErrorAction SilentlyContinue |
    Sort-Object Name -Descending | Select-Object -First 1
if ($lastReport) {
    Dump-Head "bgy_data\bgy_output\bgy_csv\$($lastReport.Name)" 10
}

# Esempio scan SACBO notturno
$lastScan = Get-ChildItem "bgy_data\bgy_raw\scan_2026-10-06_23-00.csv" -File -ErrorAction SilentlyContinue
if ($lastScan) {
    Dump-Head "bgy_data\bgy_raw\scan_2026-10-06_23-00.csv" 5
} else {
    Write-Output "===== SCAN SACBO 06/10 23:00: non trovato ====="
    Write-Output "Cerco l ultimo scan disponibile..."
    $anyScan = Get-ChildItem "bgy_data\bgy_raw\scan_*.csv" -File -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending | Select-Object -First 1
    if ($anyScan) { Dump-Head "bgy_data\bgy_raw\$($anyScan.Name)" 5 }
}

# ----------------------------------------------------------------
# 6. CONTEGGIO AVIONIO
# ----------------------------------------------------------------
Write-Output ""
Write-Output "############################################################"
Write-Output "# SEZIONE 6 - CONTEGGIO AVIONIO"
Write-Output "############################################################"
Write-Output ""

$avDir = Join-Path $root "bgy_data\bgy_avionio"
if (Test-Path $avDir) {
    $arrFiles = Get-ChildItem $avDir -Filter "avionio_arrivals_*.csv" -File
    $depFiles = Get-ChildItem $avDir -Filter "avionio_departures_*.csv" -File
    Write-Output "Arrivals totali:   $($arrFiles.Count)"
    Write-Output "Departures totali: $($depFiles.Count)"
    Write-Output ""
    Write-Output "Prime 5 date coperte (arrivals):"
    $arrFiles | Sort-Object Name | Select-Object -First 5 Name | Format-Table -AutoSize
    Write-Output "Ultime 5 date coperte (arrivals):"
    $arrFiles | Sort-Object Name | Select-Object -Last 5 Name | Format-Table -AutoSize
} else {
    Write-Output "(cartella bgy_data\bgy_avionio non trovata)"
}

# ----------------------------------------------------------------
# 7. STATO GIT
# ----------------------------------------------------------------
Write-Output ""
Write-Output "############################################################"
Write-Output "# SEZIONE 7 - STATO GIT"
Write-Output "############################################################"
Write-Output ""

Write-Output "--- File tracciati con avionio nel path ---"
git ls-files | Select-String "avionio"
Write-Output ""
Write-Output "--- File tracciati con scan_ nel path ---"
git ls-files | Select-String "scan_"
Write-Output ""
Write-Output "--- File tracciati con output nel path ---"
git ls-files | Select-String "output"
Write-Output ""
Write-Output "--- Ultimo commit ---"
git log -1 --oneline
Write-Output ""

Write-Output ""
Write-Output "############################################################"
Write-Output "# FINE BUNDLE"
Write-Output "############################################################"