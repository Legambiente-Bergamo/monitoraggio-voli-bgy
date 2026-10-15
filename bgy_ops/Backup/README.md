# Backup cifrato BGY Monitoring Suite

Script di backup giornaliero cifrato dei file sensibili della suite.

## Cosa fa

`bgy_backup_encrypted.ps1` (v1.0.0, SEC-04):

1. Legge la password da `C:\Users\ncremaschi\.bgy_backup_pwd`
2. Crea due archivi `.7z` in `bgy_data/bgy_backup_encrypted_tmp/`:

   | Archivio | Cifratura | Contenuto |
   |---|---|---|
   | `bgy_config_YYYY-MM-DD.7z` | **AES-256 + header encrypted** | `bgy_config/*.json` + `bgy_docs/tasks_windows/*.xml` |
   | `bgy_suite_YYYY-MM-DD.7z` | **nessuna** | Codice, script, docs, `config_data.json` (pubblica) |

3. Carica entrambi su `gdrive:BGY_Backup_Encrypted/`
4. Elimina dal Drive i file più vecchi di 7 giorni
5. Rimuove la cartella temporanea locale

## Cosa NON fa

- Non tocca `bgy_config/config_*.json` locali
- Non modifica il DB
- Non tocca la produzione
- Non cancella mai file locali di valore (solo la temp dir)

## Requisiti

- 7-Zip installato (`C:\Program Files\7-Zip\7z.exe`)
- rclone configurato (`gdrive:` remote)
- File password `C:\Users\ncremaschi\.bgy_backup_pwd` con la password in chiaro
- Permessi ristretti sul file password

## Esecuzione

### Manuale

```powershell
powershell -ExecutionPolicy Bypass -File "bgy_ops\backup\bgy_backup_encrypted.ps1"