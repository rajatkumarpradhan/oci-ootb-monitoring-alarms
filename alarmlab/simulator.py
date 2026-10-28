"""Deterministic synthetic metric streams shaped like documented OCI namespaces.

Namespaces mirror Oracle-documented ones (oci_computeagent, oci_vcn,
oci_lbaas) so alarm definitions read like real console alarms. All data is
generated locally with a fixed seed - this is NOT telemetry from a tenancy.
"""
import random

from .series import Datapoint, MetricSeries


def simulate(seed: int, start: int, end: int, step: int = 60) -> list:
    rng = random.Random(seed)
    span = (end - start) // step
    series = []

    def base_wave(i, low, high, wobble):
        mid = (low + high) / 2
        amp = (high - low) / 2
        import math
        return mid + amp * math.sin(i / max(span // 6, 1) * 2 * math.pi) + rng.uniform(-wobble, wobble)

    # oci_computeagent CpuUtilization for two instances; web-1 spikes mid-window
    cpu1, cpu2 = [], []
    for i in range(span):
        t = start + i * step
        v1 = base_wave(i, 20, 45, 3)
        if span // 2 <= i < span // 2 + span // 6:  # incident: sustained spike
            v1 = 88 + rng.uniform(0, 8)
        cpu1.append(Datapoint(t, round(v1, 2)))
        cpu2.append(Datapoint(t, round(base_wave(i, 15, 35, 3), 2)))
    series.append(MetricSeries("oci_computeagent", "CpuUtilization",
                               {"resourceDisplayName": "web-1"}, tuple(cpu1)))
    series.append(MetricSeries("oci_computeagent", "CpuUtilization",
                               {"resourceDisplayName": "web-2"}, tuple(cpu2)))
    # oci_vcn VNIC egress security-list drops: quiet, then a burst late in window
    drops = []
    for i in range(span):
        t = start + i * step
        v = 0.0
        if int(span * 0.75) <= i < int(span * 0.75) + span // 8:
            v = float(rng.randint(4, 15))
        drops.append(Datapoint(t, v))
    series.append(MetricSeries("oci_vcn", "VnicEgressSecurityListDrops",
                               {"vnic": "app-vnic-1"}, tuple(drops)))
    # oci_lbaas unhealthy backend servers: one backend flaps briefly
    unhealthy = []
    for i in range(span):
        t = start + i * step
        v = 0.0
        if int(span * 0.55) <= i < int(span * 0.55) + 3:
            v = 1.0
        unhealthy.append(Datapoint(t, v))
    series.append(MetricSeries("oci_lbaas", "UnHealthyBackendServers",
                               {"backendSetName": "app-bes"}, tuple(unhealthy)))
    return series
