# =============================================================
# file_utils.py — Filename Disambiguation Utility
# =============================================================
# When a user uploads "report.pdf" but that name already exists,
# this function renames it to "report (1).pdf", "report (2).pdf", etc.
# =============================================================

import os
from typing import Set


def get_disambiguated_filename(original_filename: str, existing_filenames: Set[str]) -> str:
    """
    If the filename doesn't exist yet, return it as-is.
    If it already exists, add (1), (2), etc. until we find a free name.

    Example:
        original = "report.pdf", existing = {"report.pdf"}
        returns  = "report (1).pdf"
    """
    if original_filename not in existing_filenames:
        return original_filename

    # Split "report.pdf" into name="report" and ext=".pdf"
    name_part, ext = os.path.splitext(original_filename)
    counter = 1

    while True:
        new_filename = f"{name_part} ({counter}){ext}"
        if new_filename not in existing_filenames:
            return new_filename
        counter += 1
