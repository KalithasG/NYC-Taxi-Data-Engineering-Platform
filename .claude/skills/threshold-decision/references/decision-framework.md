# Reference — Threshold Decision Framework

Read when proposing a specific threshold value.

## The four methods

### Business threshold
A number with pre-existing operational meaning — an SLA, a complaint trigger, a dispatch rule.
Strongest justification when it genuinely exists, because it connects the metric to a decision
someone already makes.

The trap: inventing one. "Over an hour feels long" is not a business threshold, it is a guess with
a confident tone. If nobody owns the claim, this method does not apply.

### Percentile
Set the cutoff at P90/P95/P99 of the observed distribution.

Honest about what it does — but note that it *defines* the flag rate rather than discovering it.
P99 flags 1% of trips whatever the data looks like. That is fine when you want a fixed review
volume, and misleading when presented as "we found that 1% of trips are anomalous."

Most useful when the distribution has a visible break near a percentile, which is evidence rather
than convention.

### IQR
`Upper bound = P75 + 1.5 × IQR`, where `IQR = P75 − P25`.

Assumes rough symmetry. Trip duration is expected to be strongly right-skewed (profiling spec §18),
so applied naively it flags a large share of perfectly ordinary long trips. Two repairs:

- Compute it on `log1p(trip_duration)` where the distribution is closer to symmetric, then
  transform the bound back.
- Use it as a *lower* bound on the candidate range and let business judgement set the final value.

### Hybrid
Statistical evidence bounded by business meaning — e.g. "P99, but never below 45 minutes, because
below that operations considers it normal traffic."

Best when the two approaches disagree. Requires saying explicitly which constraint binds and why;
otherwise it is just two numbers next to each other.

## Worked example — `long_trip_seconds`

*Illustrative shape only. Real values come from the profiling report; do not reuse these numbers.*

**Evidence**

| Statistic | Value |
|---|---|
| P50 | ~660s (11 min) |
| P75 | ~1,080s (18 min) |
| P90 | ~1,740s (29 min) |
| P95 | ~2,280s (38 min) |
| P99 | ~4,200s (70 min) |
| P99.9 | ~18,000s (5 h) |

**Candidates**

| # | Value | Method | Flags | Argument |
|---|---|---|---|---|
| A | 2,280s (P95) | Percentile | 5.0% | Fixed, predictable review volume. Flags many ordinary rush-hour trips. |
| B | 4,200s (P99) | Percentile | 1.0% | Distribution flattens here; a 70-minute NYC taxi trip is genuinely unusual. |
| C | 3,600s (1 h) | Business | ~1.6% | A round hour is legible to stakeholders and near the same break as B. |

**Recommendation:** B or C, with C preferred if operations will act on the flag — a threshold people
can state from memory gets used, and 3,600s sits close enough to the P99 break that the statistical
and business answers agree. That agreement is itself worth recording as evidence.

**What is not a recommendation:** "use 3600". Same number, no reasoning, nothing for a reviewer to
disagree with.

## Speed thresholds need extra care

A low estimated speed is **not** proof of congestion. Profiling spec §22 lists the candidate causes:
traffic, a real route much longer than the straight line, waiting time inside the duration, GPS or
coordinate quality, and legitimately unusual trips. `estimated_speed_kmh` is derived from geodesic
distance, so it systematically understates real road speed — by a factor that varies with route
shape, which means the error is not a constant you can correct for.

Consequences for KPI-017:

- The threshold identifies *candidates for investigation*, not confirmed congestion.
- Zero-distance trips (SPEED-001) need separate handling — the speed is 0 or undefined regardless
  of duration, and including them in a low-speed rate conflates a coordinate problem with an
  operational one.
- The KPI's presentation must carry the caveat. This is a wording rule BDD-07 checks.

## Recording the decision

Write into `docs/profiling/threshold-decisions.md` under a heading naming the threshold:

```markdown
### T1 — long_trip_seconds
- **Value:** 3600
- **Method:** hybrid (business, corroborated by the P99 distribution break)
- **Evidence:** P95 2,280s / P99 4,200s / P99.9 18,000s; density flattens between P99 and P99.5
- **Records affected:** ~1.6% of valid trips (n≈…)
- **Business rationale:** one hour is the point beyond which operations treats a trip as
  exceptional and worth review
- **Alternatives considered:** P95 (2,280s) flags 5% — too many ordinary rush-hour trips;
  P99 (4,200s) is defensible but harder to communicate
- **Approved by:** <named human>
- **Effective date:** 2026-09-15
- **Contract bump:** yes — KPI-016 interpretation changes materially; hand off to kpi-contract-guard
```

`scripts/check_thresholds.py` checks each field by name and rejects a placeholder approver.
