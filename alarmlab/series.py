"""Metric datapoint series shaped like OCI Monitoring records (offline)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Datapoint:
    timestamp: int  # epoch seconds
    value: float


@dataclass(frozen=True)
class MetricSeries:
    namespace: str
    metric: str
    dimensions: dict
    datapoints: tuple  # tuple[Datapoint], sorted by timestamp


def filter_series(series_list, metric: str, filters: dict):
    """Return series matching metric name and all equality filters."""
    out = []
    for s in series_list:
        if s.metric != metric:
            continue
        if all(s.dimensions.get(k) == v for k, v in filters.items()):
            out.append(s)
    return out


def aggregate(datapoints, statistic: str) -> float | None:
    values = [d.value for d in datapoints]
    if not values:
        return None
    if statistic == "mean":
        return sum(values) / len(values)
    if statistic == "max":
        return max(values)
    if statistic == "min":
        return min(values)
    if statistic == "sum":
        return sum(values)
    if statistic == "count":
        return float(len(values))
    raise ValueError(f"unsupported statistic {statistic!r}")


def windowed(datapoints, interval_seconds: int, end: int):
    """Datapoints in the trailing window (end-interval, end]."""
    start = end - interval_seconds
    return [d for d in datapoints if start < d.timestamp <= end]
