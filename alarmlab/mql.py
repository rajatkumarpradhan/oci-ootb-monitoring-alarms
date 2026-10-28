"""Strict parser for a documented subset of OCI Monitoring Query Language (MQL).

Documented shape: <metric>[<interval>]{dimension="value", ...}.<statistic>()
e.g. CpuUtilization[1m]{resourceDisplayName="web-1"}.mean()
Oracle docs: https://docs.oracle.com/en-us/iaas/Content/Monitoring/Tasks/monitoringquery.htm
Unsupported shapes raise MQLError - callers must not guess intent.
"""

class MQLError(ValueError):
    pass

STATISTICS = ("mean", "max", "min", "sum", "count")
_INTERVAL_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


class Query:
    def __init__(self, metric: str, interval_seconds: int, filters: dict, statistic: str):
        self.metric = metric
        self.interval_seconds = interval_seconds
        self.filters = filters
        self.statistic = statistic

    def __repr__(self):
        return f"Query({self.metric}[{self.interval_seconds}s]{self.filters}.{self.statistic}())"


def _parse_interval(token: str) -> int:
    if len(token) < 2 or not token[:-1].isdigit() or token[-1] not in _INTERVAL_UNITS:
        raise MQLError(f"bad interval {token!r}; use forms like 1m, 5m, 1h")
    seconds = int(token[:-1]) * _INTERVAL_UNITS[token[-1]]
    if seconds <= 0:
        raise MQLError("interval must be positive")
    return seconds


def parse(text: str) -> Query:
    if not isinstance(text, str) or not text.strip():
        raise MQLError("empty query")
    t = text.strip()
    if '"' in t and t.count('"') % 2:
        raise MQLError("unbalanced quotes")
    # metric[interval]{filters}.statistic()
    i = t.find("[")
    if i <= 0:
        raise MQLError("expected metric[interval] shape")
    metric = t[:i]
    if not metric.replace("_", "").replace("-", "").isalnum():
        raise MQLError(f"bad metric name {metric!r}")
    j = t.find("]", i)
    if j == -1:
        raise MQLError("missing ']' after interval")
    interval = _parse_interval(t[i + 1:j])
    rest = t[j + 1:]
    filters = {}
    if rest.startswith("{"):
        k = rest.find("}")
        if k == -1:
            raise MQLError("missing '}' after filters")
        body = rest[1:k].strip()
        if body:
            for part in body.split(","):
                if "=" not in part:
                    raise MQLError(f"bad filter {part!r}; expected key=\"value\"")
                key, _, value = part.partition("=")
                key = key.strip()
                value = value.strip()
                if not key or not key.replace("_", "").isalnum():
                    raise MQLError(f"bad filter key {key!r}")
                if len(value) < 2 or not value.startswith('"') or not value.endswith('"'):
                    raise MQLError("filter values must be double-quoted strings")
                filters[key] = value[1:-1]
        rest = rest[k + 1:]
    if not rest.startswith(".") or not rest.endswith("()"):
        raise MQLError("expected .statistic() at the end")
    statistic = rest[1:-2]
    if statistic not in STATISTICS:
        raise MQLError(f"unsupported statistic {statistic!r}; supported: {', '.join(STATISTICS)}")
    return Query(metric, interval, filters, statistic)
