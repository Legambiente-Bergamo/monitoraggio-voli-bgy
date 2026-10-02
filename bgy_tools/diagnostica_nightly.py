"""
bgy_tools/diagnostica_nightly.py - Diagnostica duplicati nel report notturno.

Versione 1.0.0

Cerca nel CSV report_nightly_*.csv le righe con chiave duplicata
(data, callsign, orario_schedulato) che violano il vincolo univoco
del DB.

Uso:
    py -3.12 -m bgy_tools.diagnostica_nightly 2026-09-30
"""
import os
import sys
import csv
import argparse
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bgy_core.bgy_paths import OUTPUT_CSV_DIR


def analizza_csv(date_str):
    csv_path = os.path.join(OUTPUT_CSV_DIR, f"report_nightly_{date_str}.csv")
    if not os.path.exists(csv_path):
        print(f"❌ File non trovato: {csv_path}")
        return

    print(f"📄 File: {csv_path}")
    print()

    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Totale righe: {len(rows)}")
    print()

    # Raggruppa per (callsign, orario_schedulato) non-null
    gruppi = defaultdict(list)
    senza_sched = 0
    for i, row in enumerate(rows):
        cs = (row.get("callsign") or "").strip()
        sched = (row.get("orario_schedulato") or "").strip()
        if not sched or not cs:
            senza_sched += 1
            continue
        gruppi[(cs, sched)].append((i, row))

    senza_sched_visibili = sum(1 for r in rows if not (r.get("orario_schedulato") or "").strip())
    print(f"Righe senza orario_schedulato (opt-in, no vincolo): {senza_sched_visibili}")
    print(f"Righe con orario_schedulato: {len(rows) - senza_sched_visibili}")
    print()

    # Trova duplicati
    dup = {k: v for k, v in gruppi.items() if len(v) > 1}
    if not dup:
        print("✅ Nessun duplicato (callsign, orario_schedulato) nel CSV.")
        print("   Il problema potrebbe essere nel DB (dato già presente da import precedenti).")
        return

    print(f"❌ Trovati {len(dup)} duplicati (callsign, orario_schedulato):")
    print()

    # Colonne interessanti
    cols = ["callsign", "tipo_movimento", "direzione_sacbo", "notte_categoria",
            "fase_volo", "orario_schedulato", "timestamp", "is_scheduled"]

    for (cs, sched), entries in sorted(dup.items()):
        print(f"═══ {cs} @ {sched} ({len(entries)} righe) ═══")
        for idx, row in entries:
            print(f"  Riga {idx}:")
            for c in cols:
                val = row.get(c, "")
                print(f"    {c:20s} = {val!r}")
            print()
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Diagnostica duplicati nel report notturno")
    parser.add_argument("date", help="Data YYYY-MM-DD del report notturno")
    args = parser.parse_args()
    analizza_csv(args.date)


if __name__ == "__main__":
    main()