---
name: threshold-decision
description: "Governs the six TBD_PENDING_PROFILING thresholds in configs/kpi_config.yml and the pending domains in configs/quality_rules.yml. Use this whenever a numeric cutoff needs choosing or defending — long-trip duration, low-speed cutoff, extreme duration or distance, geographic bounds, passenger-count anomaly, the vendor_id domain — or when asked to set, pick, choose, guess, estimate or 'just use a sensible' threshold, cutoff, limit, bound or outlier rule, and when a build fails because a threshold is unresolved. Also use when someone proposes filtering a KPI by a magic number, or asks what counts as a long trip, a slow trip, or an anomaly. Trigger even when the request sounds trivially reasonable ('just use 2 hours') — a plausible number chosen without evidence is precisely the failure this prevents."
---

# Threshold Decision

A threshold looks like a number and behaves like a policy. Choose 3600 for "long trip" and you have
defined what this business considers abnormal — silently, with no evidence, no alternatives weighed,
and nobody's name on it. Every downstream rate, chart and operational conclusion then inherits a
decision nobody remembers making.

KPI contract §18 and profiling spec §31 exist to stop that. This skill is how they get applied.

## First: what is actually blocked?

```bash
python3 .claude/skills/threshold-decision/scripts/check_thresholds.py          # what is pending
python3 .claude/skills/threshold-decision/scripts/check_thresholds.py --gate   # build-time check
```

Nine distinct thresholds are unresolved today. Two of them block Gold builds outright:

| Threshold | Blocks | Because |
|---|---|---|
| `long_trip_seconds` | **KPI-016 Long Trip Rate** | The rate is undefined without a definition of "long" |
| `low_speed_kmh` | **KPI-017 Low-Speed Trip Rate** | Same |
| `extreme_duration_seconds` | `is_duration_outlier` | Flagging, not filtering |
| `extreme_distance_km` | GEO-006 | |
| `geographic_outlier_bounds` / `nyc_bounds` | DQ-009, DQ-010 | Worldwide lat/lon bounds are necessary but insufficient |
| `passenger_count_anomaly` / `passenger_count_domain` | DQ-008 | Blocked on OQ-5 — zero-count semantics |
| `vendor_domain` | DQ-003 | Do not hard-code before profiling confirms the source |

**Being unresolved is the correct current state, not a bug to fix.** The profiling run has not
happened. The script therefore never fails merely because thresholds are pending — it fails when one
gets *set* without a record.

## The bar for setting one

A threshold may be proposed only with all of this in hand. If the profiling report does not exist
yet, the honest answer is "this cannot be decided yet" — say that and stop. Refusing here is the
skill working, not the skill failing.

1. **Distribution evidence** — the relevant percentiles (P50/P75/P90/P95/P99, and P99.5/P99.9 for
   duration), from `docs/profiling/profiling-report.md`. Not recalled, not assumed.
2. **Records affected** — how many rows and what percentage fall beyond the candidate, and what
   that does to the KPI.
3. **Business interpretation** — what the number *means* operationally, not just where it sits in
   the distribution.
4. **Alternatives considered** — at least two candidates with the tradeoff between them stated.
5. **A named human approver.** This is the one that cannot be delegated.

## The decision tree (profiling spec §31)

```
Observed anomaly
      ↓
Is it logically impossible?  ──YES──▶  Reject (hard rule, quarantine)
      │ NO
      ▼
Is it statistically extreme? ──NO───▶  Normal — no threshold needed
      │ YES
      ▼
    Flag  ──▶  Business evidence it is valid? ──YES──▶ Retain (flagged)
                                              └─NO───▶ Review / flag
```

The order matters, and it is what stops the dataset being over-cleaned. Only *logically impossible*
records get rejected — a dropoff before its pickup, a negative duration. Statistically extreme is
not the same thing: a very long trip, a very slow trip and a zero-distance trip can all be real.
Profiling spec §2 is explicit that an outlier is not automatically a bad record, which is why
`is_duration_outlier` and `is_speed_outlier` are flags rather than filters.

## Choosing a method

`references/decision-framework.md` has the detail and a worked example. In brief:

| Method | Fits when | Watch out for |
|---|---|---|
| **Business** | An operational meaning already exists ("over an hour is a complaint") | Someone must actually own the claim; do not invent it |
| **Percentile** | The distribution is smooth and you want a fixed proportion flagged | P99 always flags 1% — that is a definition, not a discovery |
| **IQR** (`P75 + 1.5×IQR`) | Roughly symmetric distributions | Trip duration is strongly right-skewed, so plain IQR over-flags; consider log space |
| **Hybrid** | The statistical and business answers disagree | Say which one bounds which, and why |

Trip duration is expected to be heavily right-skewed, so examine `log1p(trip_duration)` before
trusting any symmetric-distribution method (profiling spec §18-19).

## Presenting the decision

Present two or three candidates with their tradeoffs and a recommendation. Do not pick one.

The distinction is not pedantic: proposing is analysis, approving is accountability, and strategy
doc §28 lists approving thresholds among the things an agent must not do independently. A human
reads the options, chooses, and signs.

Once chosen, write the record into `docs/profiling/threshold-decisions.md` under a heading naming
the threshold, with: **Value, Method, Evidence, Records affected, Business rationale, Alternatives
considered, Approved by, Effective date, Contract bump**. The script checks each by name and rejects
a placeholder approver.

## After approval

Setting `long_trip_seconds` or `low_speed_kmh` changes how KPI-016/017 are computed, which under
KPI contract §20 is a material change. Hand off to **`kpi-contract-guard`** for the version bump and
changelog entry. Re-run `--gate` to confirm the build is unblocked.
