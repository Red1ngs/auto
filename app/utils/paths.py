# utils/paths.py
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ACCOUNTS_DIR = PROJECT_ROOT / "profiles/accounts"
PROXY_DIR = PROJECT_ROOT / "proxy"
