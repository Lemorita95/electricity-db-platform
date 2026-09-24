"""
Basic sanity checks on managers/config.py's hand-maintained lookup tables.
"""
import re

from managers.config import EIC_CODES, LINKS


def test_eic_codes_are_16_characters():
    for zone, entry in EIC_CODES.items():
        assert re.fullmatch(r"[0-9A-Z\-]{16}", entry["eic"]), f"{zone}: malformed EIC {entry['eic']!r}"


def test_links_are_reciprocal():
    pairs = {(v["origin"], v["destination"]) for v in LINKS.values()}
    for origin, destination in pairs:
        assert (destination, origin) in pairs, f"{origin}-{destination} has no reverse link"
