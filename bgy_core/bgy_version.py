"""
bgy_core/bgy_version.py - Identità e versione della suite.
Unico punto di verità per nome, versione e data di rilascio.
"""
__version__ = "2.5.0"
__release_date__ = "2026-09-15"
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