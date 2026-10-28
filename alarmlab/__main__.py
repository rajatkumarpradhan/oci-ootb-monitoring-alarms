"""CLI: evaluate OCI-style alarm definitions against metric series (offline).

Usage:
  python -m alarmlab demo                          # synthetic streams + bundled alarms
  python -m alarmlab evaluate ALARMS_JSON SERIES_JSON [--start EPOCH --end EPOCH]
Exit codes: 0 ok, 1 evaluation produced no firings at all, 2 usage/config error.
"""
import json
import sys
from pathlib import Path

from .alarm import AlarmConfigError, load_alarm
from .evaluator import evaluate_all
from .simulator import simulate


def _fmt_ts(ts: int) -> str:
    import datetime
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def render(evaluations) -> str:
    lines = []
    total_firings = 0
    total_notifications = 0
    for ev in evaluations:
        a = ev.alarm
        lines.append(f"alarm: {a.name} [{a.severity}] query={a.query_text}")
        lines.append(f"  windows evaluated: {ev.evaluated_windows} (no-data: {ev.skipped_windows})")
        if not ev.firings:
            lines.append("  result: OK - never fired")
        for f in ev.firings:
            total_firings += 1
            lines.append(f"  FIRING {_fmt_ts(f['start'])} .. {_fmt_ts(f['end'])}  peak={f['peak']}")
        for n in ev.notifications:
            total_notifications += 1
            dest = ", ".join(n["destinations"]) or "(no destinations)"
            lines.append(f"  notify {n['kind']:7s} {_fmt_ts(n['timestamp'])} -> {dest}")
        lines.append("")
    lines.append(f"summary: {len(evaluations)} alarms, {total_firings} firing(s), {total_notifications} notification(s)")
    return "\n".join(lines)


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] not in ("demo", "evaluate"):
        print(__doc__)
        return 2
    if args[0] == "demo":
        start, end = 1761696000, 1761696000 + 6 * 3600  # fixed 6h window (2025-10-29T00:00Z..)
        alarms_raw = json.loads((Path(__file__).resolve().parents[1] / "configs" / "alarms.json").read_text(encoding="utf-8"))
        try:
            alarms = [load_alarm(a) for a in alarms_raw["alarms"]]
        except AlarmConfigError as exc:
            print(f"config error: {exc}")
            return 2
        series = simulate(seed=42, start=start, end=end)
        print(f"synthetic series: {len(series)} streams x {len(series[0].datapoints)} points (seed 42, NOT live OCI telemetry)")
        print()
        evs = evaluate_all(alarms, series, start, end)
        print(render(evs))
        return 0 if any(e.firings for e in evs) else 1
    # evaluate
    if len(args) < 3:
        print("usage: python -m alarmlab evaluate ALARMS_JSON SERIES_JSON")
        return 2
    try:
        alarms = [load_alarm(a) for a in json.loads(Path(args[1]).read_text(encoding="utf-8"))["alarms"]]
        raw = json.loads(Path(args[2]).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, KeyError, AlarmConfigError) as exc:
        print(f"config error: {exc}")
        return 2
    from .series import Datapoint, MetricSeries
    series = []
    for s in raw.get("series", []):
        series.append(MetricSeries(s.get("namespace", ""), s["metric"], s.get("dimensions", {}),
                                   tuple(Datapoint(int(d[0]), float(d[1])) for d in s["datapoints"])))
    if not series:
        print("config error: series file has no series")
        return 2
    starts = [d.timestamp for s in series for d in s.datapoints]
    start = min(starts); end = max(starts)
    evs = evaluate_all(alarms, series, start, end)
    print(render(evs))
    return 0 if any(e.firings for e in evs) else 1


if __name__ == "__main__":
    raise SystemExit(main())
