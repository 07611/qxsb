"""Compatibility seed entrypoint. Run from project root:
    python database/seeds/seed.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.seed import run_seed  # noqa: E402

if __name__ == "__main__":
    run_seed()
    print("Seed completed.")
