# Field Data Quality Lab

Automated high-frequency checks (HFCs), a simulation stress test and a randomised-trial analysis on two real Precision Development (formerly PAD/IPA) SMS-advice trials in Kenya.

- **Report (21 pages):** `report/report.pdf`
- **[Interactive Live Dashboard](https://samolart.github.io/field-data-quality-lab/dashboard/index.html)**
- **SurveyCTO/ODK instrument:** `xlsform/pxd_lime_midline_LR2017.xlsx`

## Headline results
- PAD2: 13 of 26 field officers flagged (4 red, 9 amber); shuffling officer labels flags 0.21 on average and never produces a red.
- Flags rest on process (path length, skip-trigger answers, don't-know deficit); skip-logic violations are zero in both trials.
- Simulation: a 40%-shorter interview style is caught in about 23 interviews; the don't-know deficit is weak at the real base rate (0.75%).
- Any SMS raised reported lime use by 4.9 pp (control 17.5%); stable across officer fixed effects and dropping red officers. Coupon records show a smaller, non-significant rise, so the survey figure is an upper reading.

## What was and was not executed
| Component | Status |
|---|---|
| Python pipeline (01-09) | Executed; every number in the report comes from its outputs |
| Paradata (call times, durations) | **Simulated**, labelled `SIM_`, `is_synthetic=1` |
| Stata do-files | Written, **not executed** here; run `stata/99_compare_python.do` before relying on them |
| XLSForm | Structurally validated (all checks pass); **not compiled** with pyxform/ODK/SurveyCTO; run `docs/XLSFORM_TEST_PLAN.csv` |
| Arm labels (t1/t3) | Ambiguous in source; primary contrast pools all SMS arms |

## Reproduce
1. Download openICPSR project 186241 (Fabregas, Kremer, Lowes, On & Zane 2024); put the PAD1/PAD2 CSVs in `data/raw/PAD1`, `data/raw/PAD2` (see `data/README.md`).
2. `pip install -r requirements.txt`
3. `./run_all.sh` (seed 20261101). The PDF needs XeLaTeX.

## Layout
`python/` pipeline · `stata/` mirror · `xlsform/` instrument · `docs/` spec, SOP, data protection · `outputs/` tables and figures · `dashboard/` · `report/`

## Limitations
A flag is a prompt to back-check, not evidence of misconduct. Officer assignment is not randomised. Heterogeneity analysis is exploratory. Raw data are not redistributed.

## Citation
Fabregas, R., Kremer, M., Lowes, M., On, R. & Zane, G. (2024). *Digital Information Provision and Behavior Change: Lessons from Six Experiments in East Africa.* openICPSR 186241.
