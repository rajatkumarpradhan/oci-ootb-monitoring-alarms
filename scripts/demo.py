"""Demo entry: synthetic streams -> offline alarm evaluation -> printed timeline."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from alarmlab.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main(["demo"]))
