# Wiring these alarms in the OCI console

This repo's configs are **prepared, not deployed**. To set up the same alarms in a real tenancy (all within free allowances per Oracle's pricing pages):

1. **Prerequisites**: an OCI tenancy with resources emitting metrics (compute instances emit `oci_computeagent` metrics out of the box once the Oracle Cloud Agent monitoring plugin is enabled; VCNs emit `oci_vcn` metrics; load balancers emit `oci_lbaas` metrics). IAM policy allowing your user to manage alarms and ons-topics in the target compartment.
2. **Create a Notifications topic**: Observability & Management > Notifications > Topics > Create Topic (e.g. `operations-team`). Add an **email subscription** and confirm it from the mailbox - subscriptions stay pending until confirmed.
3. **Create each alarm**: Observability & Management > Monitoring > Alarm Definitions > Create Alarm. For each entry in `configs/alarms.json`:
   - Metric namespace / name / interval / statistic from the parsed query (e.g. `CpuUtilization[1m].mean()` -> namespace `oci_computeagent`, metric `CpuUtilization`, interval 1m, statistic Mean).
   - Trigger rule: operator and value(s) as given (`gt` = greater than, `between`/`outside` use two values).
   - Trigger delay minutes, severity, repeat notification frequency (`repeat_minutes`), and any suppression window.
   - Destination: the topic created in step 2 (map the config's topic labels to real topic names).
4. **Validate**: use Metrics Explorer to confirm the metric streams exist for your resources, then trigger a test condition (e.g. CPU load on a test instance) and watch the alarm transition. The offline evaluator in this repo lets you rehearse what a firing timeline and notification schedule look like before touching the console.

No alarm, topic, or subscription was created from this repo; these are manual console steps you perform in your own tenancy.
