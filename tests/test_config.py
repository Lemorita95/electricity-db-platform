"""
Basic sanity checks on managers/config.py's hand-maintained lookup tables.
"""
import re

from managers.config import EIC_CODES


def test_eic_codes_are_16_characters():
    for zone, entry in EIC_CODES.items():
        assert re.fullmatch(r"[0-9A-Z\-]{16}", entry["eic"]), f"{zone}: malformed EIC {entry['eic']!r}"
