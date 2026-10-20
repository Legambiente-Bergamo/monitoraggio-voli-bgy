"""
bgy_core/bgy_version.py - Identità e versione della suite.
Unico punto di verità per nome, versione e data di rilascio.

Storico versioni:
- 2.10.2 (20/10/2026): Aggiunto limite di 5 km al fallback geometrico piste,
  per evitare falsi positivi su virate ampie.
- 2.10.1 (20/10/2026): Fix propagazione pista (stessa direzione D/A)
  e fallback geometrico per decolli N/D.
- 2.10.0 (19/10/2026): milestone Cantiere B chiuso...
- 2.9.0 (24/09/2026): baseline pre-Cantiere B.
"""
__version__ = "2.10.2"
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