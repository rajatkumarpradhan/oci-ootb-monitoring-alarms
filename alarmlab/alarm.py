"""Alarm definitions mirroring documented OCI Monitoring alarm fields.

Console fields (Oracle solution docs): metric namespace/name, interval,
statistic, trigger rule (operator + value(s)), trigger delay minutes,
severity, repeat notification frequency, suppression, destinations.
"""
from dataclasses import dataclass, field

from .mql import MQLError, parse

OPERATORS = ("gt", "gte", "lt", "lte", "between", "outside")
SEVERITIES = ("INFO", "WARNING", "ERROR", "CRITICAL")


@dataclass(frozen=True)
class TriggerRule:
    operator: str
    values: tuple  # one value for gt/gte/lt/lte, two for between/outside

    def breached(self, x: float) -> bool:
        if self.operator == "gt":
            return x > self.values[0]
        if self.operator == "gte":
            return x >= self.values[0]
        if self.operator == "lt":
            return x < self.values[0]
        if self.operator == "lte":
            return x <= self.values[0]
        lo, hi = self.values
        if self.operator == "between":
            return lo <= x <= hi
        return not (lo <= x <= hi)  # outside


@dataclass(frozen=True)
class Alarm:
    name: str
    severity: str
    query_text: str
    trigger: TriggerRule
    trigger_delay_minutes: int = 0
    repeat_minutes: int | None = None  # repeat notification frequency; None = once
    suppression_minutes: int | None = None
    destinations: tuple = field(default_factory=tuple)  # topic labels


class AlarmConfigError(ValueError):
    pass


def load_alarm(raw: dict) -> Alarm:
    if not isinstance(raw, dict):
        raise AlarmConfigError("alarm must be an object")
    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        raise AlarmConfigError("alarm needs a non-empty name")
    severity = str(raw.get("severity", "")).upper()
    if severity not in SEVERITIES:
        raise AlarmConfigError(f"{name}: severity must be one of {SEVERITIES}")
    query_text = raw.get("query")
    if not isinstance(query_text, str):
        raise AlarmConfigError(f"{name}: query must be a string")
    try:
        parse(query_text)
    except MQLError as exc:
        raise AlarmConfigError(f"{name}: bad query: {exc}") from exc
    rule = raw.get("trigger") or {}
    op = rule.get("operator")
    if op not in OPERATORS:
        raise AlarmConfigError(f"{name}: trigger operator must be one of {OPERATORS}")
    values = rule.get("values")
    want = 2 if op in ("between", "outside") else 1
    if not isinstance(values, list) or len(values) != want or not all(isinstance(v, (int, float)) for v in values):
        raise AlarmConfigError(f"{name}: operator {op} needs exactly {want} numeric value(s)")
    if want == 2 and values[0] > values[1]:
        raise AlarmConfigError(f"{name}: between/outside values must be low, high")
    delay = raw.get("trigger_delay_minutes", 0)
    repeat = raw.get("repeat_minutes")
    suppress = raw.get("suppression_minutes")
    for label, v in (("trigger_delay_minutes", delay), ("repeat_minutes", repeat), ("suppression_minutes", suppress)):
        if v is not None and (not isinstance(v, (int, float)) or v < 0):
            raise AlarmConfigError(f"{name}: {label} must be a non-negative number")
    destinations = raw.get("destinations", [])
    if not isinstance(destinations, list) or not all(isinstance(d, str) and d.strip() for d in destinations):
        raise AlarmConfigError(f"{name}: destinations must be a list of topic labels")
    return Alarm(name=name.strip(), severity=severity, query_text=query_text,
                 trigger=TriggerRule(op, tuple(values)),
                 trigger_delay_minutes=int(delay),
                 repeat_minutes=int(repeat) if repeat is not None else None,
                 suppression_minutes=int(suppress) if suppress is not None else None,
                 destinations=tuple(destinations))
