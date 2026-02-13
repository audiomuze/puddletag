"""Shared context helpers for puddletag."""
from typing import Iterable, List, Optional

_selected_files: List = []

def set_selected_files(files: Optional[Iterable]) -> None:
    """Store the current selection of files for global access."""
    global _selected_files
    if files is None:
        _selected_files = []
    else:
        _selected_files = list(files)

def get_selected_files() -> List:
    """Return the last recorded selection of files."""
    return _selected_files
