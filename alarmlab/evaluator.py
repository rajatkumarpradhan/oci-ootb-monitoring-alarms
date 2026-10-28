"""Evaluate alarms over offline metric series.

Produces a firing timeline (OK -> FIRING transitions with trigger-delay
persistence), applies suppression windows, and derives the notification
schedule (initial + repeats) per destination topic. Pure offline evaluation;
no OCI calls.
"""
from dataclasses import dataclass, field

from .alarm import Alarm
from .mql import parse
from .series import aggregate, filter_series, windowed


@dataclass
class Evaluation:
    alarm: Alarm
    firings: list = field(default_factory=list)      # [{start, end, peak, evaluations}]
    notifications: list = field(default_factory=list) # [{timestamp, kind, destinations}]
    evaluated_windows: int = 0
    skipped_windows: int = 0  # windows with no datapoints


def evaluate(alarm: Alarm, series_list, start: int, end: int, step_seconds: int = 60) -> Evaluation:
    query = parse(alarm.query_text)
    matched = filter_series(series_list, query.metric, query.filters)
    ev = Evaluation(alarm)
    if not matched:
        return ev
    delay_seconds = alarm.trigger_delay_minutes * 60
    firing_since = None          # timestamp the breach streak began
    breach_streak = 0            # consecutive breached window-ends
    suppressed_until = None
    last_notification = None

    t = start
    while t <= end:
        points = []
        for s in matched:
            points.extend(windowed(s.datapoints, query.interval_seconds, t))
        points.sort(key=lambda d: d.timestamp)
        value = aggregate(points, query.statistic) if points else None
        ev.evaluated_windows += 1
        if value is None:
            ev.skipped_windows += 1
            breach_streak = 0
        elif alarm.trigger.breached(value):
            breach_streak += 1
            persisted = (breach_streak - 1) * step_seconds
            if firing_since is None and persisted >= delay_seconds:
                # trigger delay: the breach must persist for the delay before firing
                firing_since = t - persisted
                ev.firings.append({"start": firing_since, "end": None, "peak": value, "evaluations": breach_streak})
        else:
            breach_streak = 0
            if firing_since is not None:
                ev.firings[-1]["end"] = t - step_seconds
                firing_since = None
        # notifications for an active firing
        if firing_since is not None:
            if suppressed_until is not None and t <= suppressed_until:
                pass
            elif last_notification is None:
                ev.notifications.append({"timestamp": firing_since, "kind": "FIRING",
                                         "destinations": list(alarm.destinations)})
                last_notification = firing_since
                if alarm.suppression_minutes:
                    suppressed_until = firing_since + alarm.suppression_minutes * 60
            elif alarm.repeat_minutes and t - last_notification >= alarm.repeat_minutes * 60:
                ev.notifications.append({"timestamp": t, "kind": "REPEAT",
                                         "destinations": list(alarm.destinations)})
                last_notification = t
        if firing_since is not None and value is not None:
            ev.firings[-1]["peak"] = max(ev.firings[-1]["peak"], value)
        t += step_seconds
    if firing_since is not None:
        ev.firings[-1]["end"] = end
    return ev


def evaluate_all(alarms, series_list, start: int, end: int, step_seconds: int = 60):
    return [evaluate(a, series_list, start, end, step_seconds) for a in alarms]
