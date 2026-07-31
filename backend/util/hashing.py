# =============================================================
# hashing.py — File Content Hashing Utility
# =============================================================
# Uses SHA-256 to generate a unique fingerprint of file content.
# If two files have the same hash, their content is identical.
# =============================================================

import hashlib


def compute_sha256(content: bytes) -> str:
    """
    Takes raw file bytes and returns a 64-character hex string.
    Example: "a3f2b7c..." — unique for each unique file content.
    """
    return hashlib.sha256(content).hexdigest()
