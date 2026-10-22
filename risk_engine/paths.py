"""Filesystem locations, resolved from the repo root so they work from any working directory."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]        # paths.py -> risk_engine -> repo root
RAW_PRICES_DIR = REPO_ROOT / "data" / "raw" / "prices"
POSITIONS_PATH = REPO_ROOT / "data" / "positions.json"