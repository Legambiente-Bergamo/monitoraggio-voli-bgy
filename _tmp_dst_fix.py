"""
_tmp_dst_fix.py - Corregge il check DST-03 in bgy_report_night.py.
Sostituisce la vecchia logica (00:00 -> +1 giorno) con quella corretta
(23:00 -> +7 ore). Include un test sintetico per date 21-26/10/2026.
Script self-deleting (Regola n.4). Rollback automatico via .bak.
"""
import ast
import shutil
import sys
from pathlib import Path

ROOT = Path.cwd()
PATH = ROOT / "bgy_reports" / "bgy_report_night.py"

OLD_BLOCK = (
    "    # DST-03 (22/10/2026): warning se la sessione attraversa cambio ora legale/solare.\n"
    "    # La fascia 02:00-02:59 puo' essere ambigua nei timestamp naive.\n"
    "    # Vedi bgy_docs/DST_2026.md e backlog DST-05.\n"
    "    try:\n"
    "        from zoneinfo import ZoneInfo\n"
    "        _dst_d1 = datetime.strptime(date_norm, \"%Y-%m-%d\").replace(tzinfo=ZoneInfo(\"Europe/Rome\"))\n"
    "        _dst_d2 = _dst_d1 + timedelta(days=1)\n"
    "        if _dst_d1.utcoffset() != _dst_d2.utcoffset():\n"
    "            logger.warning(\n"
    "                f\"DST: sessione {date_norm} attraversa cambio ora legale/solare. \"\n"
    "                f\"Timestamp 02:00-02:59 possono essere ambigui. Verificare manualmente il report.\"\n"
    "            )\n"
    "    except Exception:\n"
    "        pass\n"
)

NEW_BLOCK = (
    "    # DST-03 (22/10/2026, fix 22/10/2026): warning se la sessione attraversa cambio DST.\n"
    "    # La sessione notturna va da date_norm 23:00 a (date_norm+1) 06:00.\n"
    "    # Se gli offset UTC degli estremi differiscono, la sessione attraversa il cambio.\n"
    "    # La fascia 02:00-02:59 puo' essere ambigua nei timestamp naive.\n"
    "    # Vedi bgy_docs/DST_2026.md e backlog DST-05.\n"
    "    try:\n"
    "        from zoneinfo import ZoneInfo\n"
    "        _tz_rome = ZoneInfo(\"Europe/Rome\")\n"
    "        _dst_d1 = datetime.strptime(date_norm, \"%Y-%m-%d\").replace(hour=23, minute=0, tzinfo=_tz_rome)\n"
    "        _dst_d2 = _dst_d1 + timedelta(hours=7)\n"
    "        if _dst_d1.utcoffset() != _dst_d2.utcoffset():\n"
    "            logger.warning(\n"
    "                f\"DST: sessione {date_norm} (23:00 -> {_dst_d2.strftime('%Y-%m-%d %H:%M')}) \"\n"
    "                f\"attraversa cambio ora legale/solare. \"\n"
    "                f\"Timestamp 02:00-02:59 possono essere ambigui. Verificare manualmente il report.\"\n"
    "            )\n"
    "    except Exception:\n"
    "        pass\n"
)


def apply_fix():
    if not PATH.exists():
        return "ERRORE", f"file non trovato: {PATH}"
    src = PATH.read_text(encoding="utf-8-sig")
    if NEW_BLOCK in src:
        return "SKIP", "check DST gia' corretto (new block trovato)"
    if OLD_BLOCK not in src:
        return "ERRORE", "vecchio blocco DST-03 non trovato (file modificato manualmente?)"
    new_src = src.replace(OLD_BLOCK, NEW_BLOCK, 1)
    try:
        ast.parse(new_src)
    except SyntaxError as e:
        return "ERRORE", f"sintassi non valida dopo fix: {e}"
    backup = PATH.with_suffix(PATH.suffix + ".bak2")
    shutil.copy2(PATH, backup)
    PATH.write_text(new_src, encoding="utf-8")
    return "OK", f"check DST corretto (backup: {backup.name})"


def test_synthetic():
    """Testa la logica su date 21-26/10/2026."""
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("Europe/Rome")
    print()
    print("=" * 60)
    print("TEST SINTETICO LOGICA DST")
    print("=" * 60)
    print(f"{'Data':12s} {'Inizio (23:00)':22s} {'Fine (06:00)':22s} {'Warning':8s}")
    print("-" * 60)
    for d in ["2026-10-21", "2026-10-22", "2026-10-23",
              "2026-10-24", "2026-10-25", "2026-10-26"]:
        d1 = datetime.strptime(d, "%Y-%m-%d").replace(hour=23, minute=0, tzinfo=tz)
        d2 = d1 + timedelta(hours=7)
        warning = "SI" if d1.utcoffset() != d2.utcoffset() else "no"
        print(f"{d:12s} {d1.strftime('%Y-%m-%d %H:%M %z'):22s} "
              f"{d2.strftime('%Y-%m-%d %H:%M %z'):22s} {warning:8s}")
    print("=" * 60)


def main():
    print("=" * 60)
    print("DST-03: fix check (sessione 23:00 -> 06:00)")
    print("=" * 60)
    status, msg = apply_fix()
    print(f"  [{status:6s}] {msg}")
    print("=" * 60)
    test_synthetic()
    return 0 if status in ("OK", "SKIP") else 1


if __name__ == "__main__":
    sys.exit(main())

import os
try:
    os.remove(__file__)
except Exception:
    pass