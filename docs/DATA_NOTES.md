# Data notes, decisions and limitations (read before citing any number)

## Source
Fabregas, Kremer, Lowes, On & Zane (2024), *Digital Information Provision and Behavior Change: Lessons from Six Experiments in East Africa*, AEJ replication package, openICPSR project 186241 (doi:10.3886/E186241V1). This repo uses the two PAD (now PxD) lime-and-fertiliser SMS trials: **PAD2** (5,890 farmers, 4,933 endline interviews, 26 field officers) and **PAD1** (1,897 / 1,511 / 23). Raw data are **not** redistributed here (see `.gitignore`); download them yourself and respect the repository terms.

## Decisions a reviewer should know about
1. **Arm labels are ambiguous in the replication code.** Variable labels (and the "fix order" comment) imply raw `t1` = SMS+Call and raw `t3` = SMS, but the later `treatment` string variable assigns them the other way round. The primary contrast is therefore **any SMS vs control**, which does not depend on the mapping. Arm-level estimates are secondary and flagged; confirm the mapping with the authors before interpreting them.
2. **Gender coding differs across surveys** (PAD2 gender==1 is female; PAD1 gender==2 is female). Harmonised explicitly and asserted.
3. **Attriters and `knows_lime`.** A pattern-matching command returns 0 for blank strings, so non-respondents can silently become "does not know lime". Here non-respondents are set to missing.
4. **Survey vs administrative outcomes measure different things.** Coupon redemption is not lime use (lime can be bought without a coupon). The survey-based lime-use effect (+4.9 pp) is roughly three times the administrative redemption effect (+1.7 pp); treat the survey figure as an upper-bound reading.
5. **The duplicate-vector check is disabled for PAD2** (informativeness gate): 53% of interviews share an answer vector by chance.
6. **Path length is partly mechanical** (answers open or close modules). Officer flags justify back-checks; they do not prove anything.
7. **Method change after a first look.** A first pass used Welch tests and flagged 6 of 25 PAD2 officers Red. Welch is unreliable for rare events and double-counted correlated metrics, so it was replaced by within-location permutation tests, metric families, and a pure-noise calibration *before* the numbers in the report were produced. The reason was statistical validity, not the outcome, but it is disclosed here.

## What is real and what is simulated
Real: all PAD1/PAD2 survey, coupon and randomisation data and every estimate in Sections 4–6 of the report.
**Simulated (labelled `SIM_`, `is_synthetic=1`)**: all timestamps, durations, call times and planted problems in `data/synthetic/SIM_paradata.csv`. The survey files carry no paradata, so only the *workload per officer* mirrors the real data.

## What was not executed in the build environment
* **Stata do-files** were written but **not run** (no Stata licence). `stata/99_compare_python.do` asserts they reproduce the Python ITT table; run it before claiming Stata results.
* **XLSForm** was checked with a structural validator (`python/06_build_xlsform.py`), not compiled by pyxform/ODK Validate or SurveyCTO. Upload it to a SurveyCTO test server and run `docs/XLSFORM_TEST_PLAN.csv` before field use.
* Package installation from PyPI was blocked in the build sandbox, so regression and multiple-testing routines are implemented directly in NumPy/SciPy (`python/pxdlib.py`).

## Limitations
Field-officer assignment is not randomised; effects of officers are separated from respondent mix only up to observables (arm, baseline covariates, location). Arms are orthogonal to officers (χ² p = 0.26), so officer effects add noise to, but do not bias, the ITT. Heterogeneity tests are exploratory and unadjusted.
