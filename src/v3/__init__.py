from .tables_builder import build_wikitable
from .v3_main import main
from .v3_update import update
from .worker import load_rows

__all__ = [
    "load_rows",
    "build_wikitable",
    "main",
    "update",
]
