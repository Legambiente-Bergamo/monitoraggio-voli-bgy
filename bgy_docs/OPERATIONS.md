

---

## TODO / Evoluzioni architetturali pianificate

- [ ] **Split `bgy_core/bgy_export_web.py` (aggregazione dati vs pubblicazione WordPress):** separare il calcolo delle metriche SQL e dei controlli qualit? dati (`build_*`) dal client di upload API verso WordPress (`export_and_publish`, `export_delays_and_publish`), integrando contestualmente il box di riconciliazione mensile con i dati ufficiali **Assaeroporti** (`bgy_utils/bgy_utils_assaeroporti.py`).
