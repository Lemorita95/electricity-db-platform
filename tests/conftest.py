"""
Source clients are built lazily (on first fetch), so importing `managers`
needs no credentials, network, or cdsapi/eumdac stubs. Tests that build a
client patch its third-party dependency themselves.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
