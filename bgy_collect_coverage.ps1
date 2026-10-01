# bgy_collect_coverage.ps1
#
# SCOPO: raccogliere un campione di copertura delle fonti ADS-B per
# decidere se serve un'antenna locale.
#
# Lancia il parallel-test dello scanner radar e appende una riga al file
# di log coverage_log.txt con timestamp e percorso del JSON prodotto.
#
# VA RIMOSSO alla fine della raccolta dati (previsto: 5-7 giorni).
# Per rimuoverlo: eseguire in PowerShell amministratore
#     Unregister-ScheduledTask -TaskName "BGY_Coverage" -Confirm:$false
# e cancellare questo script, il log e i file radar_test_*.json.

$ProjectRoot = "C:\Users\ncremaschi\Desktop\Monitoraggio BGY 2.5"
$PythonExe   = "py"
$PythonArgs  = "-3.12"
$LogFile     = Join-Path $ProjectRoot "bgy_data\bgy_logs\coverage_log.txt"

Set-Location $ProjectRoot

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

try {
    $output = & $PythonExe $PythonArgs -m bgy_scanners.bgy_scanner_radar --parallel-test 2>&1
    $exitCode = $LASTEXITCODE

    # Trova la riga con il percorso del riepilogo JSON
    $jsonPath = ($output | Select-String "Riepilogo test salvato:" |
                 Select-Object -Last 1) -replace '.*Riepilogo test salvato:\s*', ''

    # Estrai i conteggi per fonte
    $counts = @{}
    foreach ($line in $output) {
        if ($line -match "adsb\.lol\s+:\s+(\d+)\s+aerei")    { $counts["adsb_lol"] = [int]$Matches[1] }
        if ($line -match "adsb\.fi\s+:\s+(\d+)\s+aerei")     { $counts["adsb_fi"] = [int]$Matches[1] }
        if ($line -match "airplanes\.live\s+:\s+(\d+)\s+aerei") { $counts["airplanes_live"] = [int]$Matches[1] }
        if ($line -match "opensky\s+:\s+(\d+)\s+aerei")      { $counts["opensky"] = [int]$Matches[1] }
    }

    $summary = "adsb.lol={0} adsb.fi={1} airplanes.live={2} opensky={3}" -f `
        $counts["adsb_lol"], $counts["adsb_fi"], $counts["airplanes_live"], $counts["opensky"]

    $line = "$timestamp | exit=$exitCode | $summary | json=$jsonPath"
    $line | Out-File -FilePath $LogFile -Append -Encoding UTF8
}
catch {
    "$timestamp | ERRORE: $_" | Out-File -FilePath $LogFile -Append -Encoding UTF8
}