import os
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

DATA_DIR = BASE_DIR / "data"
SCRIPTS_DIR = BASE_DIR / "scripts"


def run_script(name: str) -> None:
    path = SCRIPTS_DIR / name
    subprocess.run([sys.executable, str(path)], check=True)


def main() -> None:
    kb_path = DATA_DIR / "full_kbs.json"
    if not kb_path.exists() or kb_path.stat().st_size == 0:
        raise SystemExit(
            "full_kbs.json not found or empty. Run 'python scripts/paloalto_kb_crawler.py' first."
        )
    run_script("process_kb_chunks.py")
    run_script("build_full_index.py")


if __name__ == "__main__":
    main()
