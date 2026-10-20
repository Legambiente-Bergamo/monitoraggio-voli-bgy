"""
bgy_core/bgy_version.py - Identità e versione della suite.
Unico punto di verità per nome, versione e data di rilascio.

Storico versioni:
- 2.10.8 (20/10/2026): QA-05 (script di igiene file Python). 74 file controllati.
- 2.10.7 (20/10/2026): Frontend WEB-13/13.B. Refactoring UI loader (frecce rimosse).
- 2.10.6 (20/10/2026): INFRA-16 (heartbeat) e INFRA-15 (rclone) chiusi.
- 2.10.5 (20/10/2026): Diagnostica match radar falliti. Scartato METAR per pista.
- 2.10.4 (20/10/2026): Scartata l'idea METAR per dedurre la pista.
- 2.10.3 (20/10/2026): Integrato radar_trace_enricher.py (RADAR-08).
- 2.10.2 (20/10/2026): Aggiunto limite di 5 km al fallback geometrico.
- 2.10.1 (20/10/2026): Fix propagazione pista.
- 2.10.0 (19/10/2026): milestone Cantiere B chiuso.
- 2.9.0 (24/09/2026): baseline pre-Cantiere B.
"""
__version__ = "2.10.8"
__release_date__ = "2026-10-20"
__suite_name__ = "BGY Monitoring Suite"
__author__ = "Circolo Legambiente Bergamo APS"
__license__ = "Custom (vedi Licenza.txt)"


def version_string():
    return f"{__suite_name__} v{__version__}"


def version_extended():
    return f"{__suite_name__} v{__version__} ({__release_date__})"


if __name__ == "__main__":
    print(version_string())
    print(version_extended())