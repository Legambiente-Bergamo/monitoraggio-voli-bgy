"""
bgy_core/bgy_version.py - Identità e versione della suite.
Unico punto di verità per nome, versione e data di rilascio.

Storico versioni:
- 2.10.0 (19/10/2026): milestone Cantiere B chiuso (B.1+B.2+B.3),
  pagina Ritardi H24 riscritta (5 fasce, top ricorrenti, top peggiori,
  timeline semplificata), pagina Notturna arricchita (3 widget nuovi),
  INFRA-08-D (retry 404 loader), circuit breaker adsb.lol,
  fix bgy_reports/__init__.py (generate_h24_report), SCHEMA_VERSION=7.
- 2.9.0 (24/09/2026): baseline pre-Cantiere B.

Nota (DOC-12): il changelog completo è nella Relazione Tecnica v3.8 §19
e negli Addendum 1-12. Qui si tiene solo una sintesi per orientarsi.
"""
__version__ = "2.10.0"
__release_date__ = "2026-10-19"
__suite_name__ = "BGY Monitoring Suite"
__author__ = "Circolo Legambiente Bergamo APS"
__license__ = "Custom (vedi Licenza.txt)"


def version_string():
    """Ritorna una stringa compatta per footer, email e log."""
    return f"{__suite_name__} v{__version__}"


def version_extended():
    """Ritorna una stringa estesa con la data di rilascio."""
    return f"{__suite_name__} v{__version__} ({__release_date__})"


if __name__ == "__main__":
    print(version_string())
    print(version_extended())