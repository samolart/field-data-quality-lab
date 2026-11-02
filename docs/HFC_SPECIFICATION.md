# High-Frequency Check (HFC) Specification

Version 1.0 · applies to `python/02_hfc_real.py` (real data) and `python/03_paradata_simulation.py` (simulated paradata)

**Principle.** A flag is a prompt to *back-check*, never a finding of misconduct. Every rule has a direction (what is concerning), a test, a minimum sample, and a known failure mode.

## A. Interview-level checks (real PAD2/PAD1 endline data)

| ID | Metric | Concerning direction | Test | Known failure mode |
|---|---|---|---|---|
| H1 | Path length (items answered) | shorter than peers | permutation vs. team, within location | Mechanically linked to respondent answers (e.g. "heard of lime = yes" opens extra questions); needs back-check, not assumption |
| H2 | Gate questions answered "No" (plant / fertiliser / heard of lime) | more than peers | permutation | Same as H1; grouped with H1 as one *family* so one behaviour is never counted twice |
| H3 | Don't-know share of categorical answers | fewer than peers | permutation | Rare events (0.75% base rate in PAD2): weak signal, hence corroboration rule |
| H4 | Straight-lining (≥6 yes/no answers identical) | more than peers | permutation | Low base rate (1.1%) |
| H5 | Skip-logic / consistency violations (7 rules) | any | exact count | **Zero violations in PAD2 and PAD1** = instrument enforces skip logic; rule kept as regression test |
| H6 | Exact duplicate answer vectors | more than peers | permutation | **Disabled when >5% of interviews duplicate by chance** (PAD2: 53%, uninformative for short binary questionnaires) |
| H7 | Survey vs. administrative record (coupon bought, survey says not used) | more than peers | permutation | Coupon purchase ≠ use; compare officers to each other, never to zero |
| H8 | Numeric heaping (share of quantities that are multiples of 5) | more than peers | descriptive (PAD1) | Farmers genuinely round |

All metrics are residualised on arm, baseline covariates and location fixed effects; labels are permuted **within location** (4,000 permutations); Benjamini–Hochberg q-values across officers within each metric.

**Flag levels (fixed in code, `THRESH`).**
Amber = concerning direction, q < 0.10, |effect| ≥ 0.25 SD, ≥5 interviews. Red = q < 0.05 on the same terms.
**Tier.** Red officer = ≥2 independent families at Red level or ≥3 families flagged. Amber = ≥1 family flagged. Officers with <30 interviews are "Insufficient data".
**Calibration.** The whole rule is run against pure-noise officer labels (300 permutations): see `outputs/tables/hfc_null_calibration_*.csv`.

## B. Paradata checks (simulated in this repo; implement against real SurveyCTO audit/duration data)

| ID | Rule | Trigger |
|---|---|---|
| R1 | Speed | Welch test on log duration vs. team, BH q < 0.05 **and** ≥20% shorter, n ≥ 20 |
| R2 | DK deficit | exact binomial lower tail p < 0.01 and < 50% of team rate, expected DK count ≥ 5 |
| R3 | Duplicates | ≥3 interviews share an answer signature |
| R4 | Off-hours | >10% of calls outside 07:00–20:00 and p < 0.001 |
| R5 | Impossible timing | >5% of interviews start <1 min after the previous ended, or last <5 min |
| R6 | Drift | slope of log duration over field days t < −3 and fitted decline >20% (n ≥ 40) |

**Escalation.** Red = R3, R4 or R5, or R1 corroborated by R2 or R6. Amber = any single rule (e.g. a fast but otherwise normal officer). Green otherwise.

## C. Cadence
Run daily after sync. Re-score cumulatively; require a flag to persist before escalating when n < 30. Document every flag, the action taken and the outcome in the HFC log.
