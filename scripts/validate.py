"""Offline consistency check: alarm configs must parse and carry no placeholders."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from alarmlab.alarm import AlarmConfigError, load_alarm

PLACEHOLDERS = ("TODO", "FIXME", "CHANGEME", "REPLACE_ME", "<your", "xxx")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    problems = 0
    for path in sorted(root.glob("configs/*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            alarms = [load_alarm(a) for a in data.get("alarms", [])]
            text = path.read_text(encoding="utf-8").upper()
            bad = [p for p in PLACEHOLDERS if p in text]
            if bad:
                print(f"FAIL {path.name}: placeholder markers {bad}")
                problems += 1
            else:
                print(f"ok   {path.name}: {len(alarms)} alarm definitions valid")
        except (json.JSONDecodeError, AlarmConfigError) as exc:
            print(f"FAIL {path.name}: {exc}")
            problems += 1
    print(f"validate: {'OK' if not problems else f'{problems} problem(s)'}")
    return 2 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
