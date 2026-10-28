# oci-ootb-monitoring-alarms

An **OOTB (out-of-the-box) OCI project** built around Monitoring, a built-in OCI observability feature: OCI resources emit metrics without any custom agent work, you define **Alarms** over Monitoring Query Language (MQL) queries, and alarms route to **Notifications** topics (email and other protocols). This repo contains:

1. **Prepared alarm definitions** (`configs/alarms.json`) that mirror the documented OCI console fields - metric, interval, statistic, trigger rule (operator + values), trigger delay, severity, repeat notification frequency, suppression, and destination topics - following Oracle's own alarm examples (CPU threshold, VCN egress security-list drops, load-balancer unhealthy backends).
2. **A real offline alarm evaluator** (`alarmlab/`): a strict MQL-subset parser, an evaluation engine with sliding windows, trigger-delay persistence, suppression and repeat-notification scheduling, plus a deterministic simulator that generates synthetic metric streams shaped like the documented namespaces (`oci_computeagent`, `oci_vcn`, `oci_lbaas`). Run it to see exactly which alarms would fire, when, and what notification schedule each destination topic would receive.

> **Portfolio project.** Everything runs offline on synthetic, locally generated data. No OCI tenancy was connected, no alarms or topics were actually created, and no notifications were sent. The evaluator models documented alarm semantics for learning and pre-deployment review; it is not a substitute for OCI's real alarm service, and MQL support is a documented subset, not the full language.

## Quickstart

```bash
python scripts/demo.py        # synthetic streams -> firing timeline + notification schedule
python scripts/validate.py    # config consistency + placeholder check
python -m unittest discover -s tests -v
```

Evaluate your own data (offline export shaped as JSON):

```bash
python -m alarmlab evaluate configs/alarms.json your-series.json
# series file: {"series":[{"metric":"CpuUtilization","dimensions":{...},"datapoints":[[epoch, value], ...]}]}
```

Exit codes: `0` evaluated with at least one firing, `1` evaluated with no firings, `2` usage/config error.

## What the demo shows

Four bundled alarms evaluated over six hours of synthetic 1-minute data: a sustained CPU spike fires the saturation alarm (with a repeat after suppression lifts), a packet-drop burst fires the VCN alarm once, and a brief unhealthy-backend flap fires the load-balancer alarm. The `between 60,80` warning alarm deliberately stays OK because the spike jumps straight past 80 - the output demonstrates real operator semantics, not canned matches.

## Cost grounding (from Oracle's own pages, checked 2026-10-29)

- [OCI Monitoring pricing](https://www.oracle.com/cloud/cloud-native/monitoring/pricing/): "Monitoring - Ingestion - First 500 million datapoints: **Free**" and "Retrieval - First 1 billion datapoints: **Free**" per month.
- [OCI Monitoring overview](https://www.oracle.com/cloud/cloud-native/monitoring/): "Monitoring does not charge for alarms and stored data."
- [OCI Notifications pricing](https://www.oracle.com/manageability/pricing/): "First 1 million delivery operations per month: **Free**" and "First 1,000 emails per month: **Free**".

Wiring the bundled alarm definitions in a real tenancy within these allowances costs nothing beyond the always-free tier. That is a pricing-page reading, not a deployed-configuration claim.

## Structure

```
alarmlab/    MQL parser, series model, alarm model, evaluator, simulator, CLI
configs/     alarm definitions (documented OCI console fields)
docs/        setup guide for wiring the same alarms in the OCI console
scripts/     demo + config validator
tests/       unit tests (parser, trigger rules, evaluator, simulator, CLI)
```

## References

- Oracle, [Monitoring Query Language (MQL)](https://docs.oracle.com/en-us/iaas/Content/Monitoring/Tasks/monitoringquery.htm) - query shape `metric[interval]{filters}.statistic()`.
- Oracle, [Configure alarms and notifications](https://docs.oracle.com/en/solutions/implement-oci-observability-monitoring/configure-alarms-and-notifications1.html) - the console alarm fields these configs mirror.
- Oracle, [Managing Alarms](https://docs.oracle.com/en-us/iaas/Content/Monitoring/Tasks/managing-alarms.htm) - trigger delay, repeat notifications, suppression.
