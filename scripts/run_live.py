"""Repo convenience wrapper for `djoker-run` (live.runner). Uses config/dev.json unless --config is given."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from live.runner import main  # noqa: E402

if __name__ == '__main__':
    main()
