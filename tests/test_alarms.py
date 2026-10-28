import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alarmlab.alarm import AlarmConfigError, TriggerRule, load_alarm
from alarmlab.evaluator import evaluate
from alarmlab.mql import MQLError, parse
from alarmlab.series import Datapoint, MetricSeries
from alarmlab.simulator import simulate
from alarmlab.__main__ import main, render

ROOT = Path(__file__).resolve().parents[1]


def series(values, metric="CpuUtilization", dims=None, start=1000, step=60):
    pts = tuple(Datapoint(start + i * step, v) for i, v in enumerate(values))
    return MetricSeries("oci_computeagent", metric, dims or {}, pts)


def alarm(**kw):
    raw = {"name": "t", "severity": "WARNING",
           "query": "CpuUtilization[1m].mean()",
           "trigger": {"operator": "gt", "values": [50]}}
    raw.update(kw)
    return load_alarm(raw)


class MQLTests(unittest.TestCase):
    def test_parse_full_shape(self):
        q = parse("CpuUtilization[5m]{resourceDisplayName=\"web-1\", compartment=\"lab\"}.max()")
        self.assertEqual((q.metric, q.interval_seconds, q.statistic), ("CpuUtilization", 300, "max"))
        self.assertEqual(q.filters, {"resourceDisplayName": "web-1", "compartment": "lab"})

    def test_rejections(self):
        for bad in ("", "CpuUtilization.mean()", "CpuUtilization[1m].p95()",
                    "CpuUtilization[1m]{k=v}.mean()", "Cpu Utilization[1m].mean()",
                    "CpuUtilization[1m]{resourceDisplayName=\"web-1\".mean()"):
            with self.subTest(bad=bad):
                with self.assertRaises(MQLError):
                    parse(bad)


class TriggerRuleTests(unittest.TestCase):
    def test_operators(self):
        self.assertTrue(TriggerRule("gt", (5,)).breached(6))
        self.assertFalse(TriggerRule("gt", (5,)).breached(5))
        self.assertTrue(TriggerRule("gte", (5,)).breached(5))
        self.assertTrue(TriggerRule("lt", (5,)).breached(4))
        self.assertTrue(TriggerRule("lte", (5,)).breached(5))
        self.assertTrue(TriggerRule("between", (60, 80)).breached(70))
        self.assertFalse(TriggerRule("between", (60, 80)).breached(81))
        self.assertTrue(TriggerRule("outside", (60, 80)).breached(81))
        self.assertFalse(TriggerRule("outside", (60, 80)).breached(70))

    def test_config_validation(self):
        for raw in ({"name": "", "severity": "WARNING", "query": "a[1m].mean()", "trigger": {"operator": "gt", "values": [1]}},
                    {"name": "x", "severity": "LOUD", "query": "a[1m].mean()", "trigger": {"operator": "gt", "values": [1]}},
                    {"name": "x", "severity": "WARNING", "query": "a[1m].mean()", "trigger": {"operator": "gt", "values": [1, 2]}},
                    {"name": "x", "severity": "WARNING", "query": "a[1m].mean()", "trigger": {"operator": "between", "values": [9, 2]}},
                    {"name": "x", "severity": "WARNING", "query": "bad query", "trigger": {"operator": "gt", "values": [1]}},
                    {"name": "x", "severity": "WARNING", "query": "a[1m].mean()", "trigger": {"operator": "gt", "values": [1]}, "repeat_minutes": -5}):
            with self.subTest(raw=raw):
                with self.assertRaises(AlarmConfigError):
                    load_alarm(raw)


class EvaluatorTests(unittest.TestCase):
    def test_fires_on_breach_and_recovers(self):
        s = series([10, 10, 90, 90, 10])
        ev = evaluate(alarm(), [s], 1000, 1000 + 4 * 60)
        self.assertEqual(len(ev.firings), 1)
        self.assertEqual(ev.firings[0]["start"], 1000 + 2 * 60)
        self.assertEqual(ev.firings[0]["end"], 1000 + 3 * 60)
        self.assertEqual(ev.notifications[0]["kind"], "FIRING")

    def test_trigger_delay_requires_persistence(self):
        s = series([10, 90, 10, 90, 90, 90, 10])
        ev = evaluate(alarm(trigger_delay_minutes=2), [s], 1000, 1000 + 6 * 60)
        self.assertEqual(len(ev.firings), 1)
        self.assertEqual(ev.firings[0]["start"], 1000 + 3 * 60)

    def test_repeat_notifications(self):
        s = series([90] * 200)
        ev = evaluate(alarm(repeat_minutes=30), [s], 1000, 1000 + 199 * 60)
        kinds = [n["kind"] for n in ev.notifications]
        self.assertEqual(kinds[0], "FIRING")
        self.assertTrue(all(k == "REPEAT" for k in kinds[1:]))
        self.assertEqual(len(kinds), 1 + (199 * 60) // (30 * 60))

    def test_suppression_blocks_repeats(self):
        s = series([90] * 100)
        ev = evaluate(alarm(repeat_minutes=30, suppression_minutes=180), [s], 1000, 1000 + 99 * 60)
        self.assertEqual(len(ev.notifications), 1)

    def test_repeats_resume_after_suppression_lifts(self):
        s = series([90] * 200)
        ev = evaluate(alarm(repeat_minutes=30, suppression_minutes=180), [s], 1000, 1000 + 199 * 60)
        self.assertEqual(len(ev.notifications), 2)
        self.assertEqual(ev.notifications[1]["kind"], "REPEAT")

    def test_dimension_filtering(self):
        a = series([90] * 10, dims={"resourceDisplayName": "web-1"})
        b = series([5] * 10, dims={"resourceDisplayName": "web-2"})
        q_alarm = alarm(query="CpuUtilization[1m]{resourceDisplayName=\"web-2\"}.mean()")
        ev = evaluate(q_alarm, [a, b], 1000, 1000 + 9 * 60)
        self.assertEqual(ev.firings, [])

    def test_empty_data_windows_never_fire(self):
        s = series([])
        ev = evaluate(alarm(), [s], 1000, 2000)
        self.assertEqual(ev.firings, [])
        self.assertGreater(ev.skipped_windows, 0)

    def test_statistic_aggregation(self):
        s = series([0, 100, 0, 100])
        ev = evaluate(alarm(query="CpuUtilization[4m].max()", trigger={"operator": "gte", "values": [100]}), [s], 1000, 1000 + 3 * 60)
        self.assertEqual(len(ev.firings), 1)


class SimulatorTests(unittest.TestCase):
    def test_deterministic_and_documented_namespaces(self):
        a = simulate(42, 0, 3600)
        b = simulate(42, 0, 3600)
        self.assertEqual([s.datapoints for s in a], [s.datapoints for s in b])
        self.assertEqual({s.namespace for s in a},
                         {"oci_computeagent", "oci_vcn", "oci_lbaas"})


class CliTests(unittest.TestCase):
    def test_demo_runs_and_reports(self):
        self.assertEqual(main(["demo"]), 0)

    def test_evaluate_custom_series(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            series_path = Path(d) / "s.json"
            series_path.write_text(json.dumps({"series": [
                {"metric": "CpuUtilization", "dimensions": {},
                 "datapoints": [[1000 + i * 60, v] for i, v in enumerate([10, 95, 95, 10])]}]}))
            self.assertEqual(main(["evaluate", str(ROOT / "configs" / "alarms.json"), str(series_path)]), 1)
            self.assertEqual(main(["evaluate", str(ROOT / "configs" / "alarms.json"), str(Path(d) / "missing.json")]), 2)

    def test_render_includes_summary(self):
        s = series([90] * 5)
        out = render([evaluate(alarm(), [s], 1000, 1000 + 4 * 60)])
        self.assertIn("summary: 1 alarms, 1 firing(s), 1 notification(s)", out)


if __name__ == "__main__":
    unittest.main()
