"""07 - Collect every headline number into outputs/key_numbers.json (single source of truth for report + dashboard)."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import numpy as np, pandas as pd
from config import OUT_T as T, ROOT, PROC

K = {}
inv = pd.read_csv(T / "data_inventory.csv"); sb = pd.read_csv(T / "scale_benchmark.csv").set_index("metric").value
K["inventory"] = dict(files=len(inv), rows=int(inv.rows.sum()), cells=int(inv.cells_nonmissing.sum()),
                      largest_rows=int(inv.rows.max()), largest_file=inv.sort_values("rows").iloc[-1].file,
                      largest_cols=int(inv.sort_values("rows").iloc[-1].cols), scale_read_s=float(sb["seconds to read"]), scale_qa_s=float(sb["seconds for generic QA suite"]))
for tag in ("pad2", "pad1"):
    sc = pd.read_csv(T / f"hfc_fo_scorecard_{tag}.csv"); nl = pd.read_csv(T / f"hfc_null_calibration_{tag}.csv")
    om = pd.read_csv(T / f"hfc_omnibus_{tag}.csv"); sm = pd.read_csv(T / f"hfc_summary_{tag}.csv").set_index("check").value
    tiers = sc.tier.str.split(" ").str[0].value_counts().to_dict()
    p = pd.read_csv(PROC / f"{tag}_panel.csv")
    K[tag] = dict(n_baseline=int(len(p)), n_endline=int(p.responded.sum()), n_fo=int(sc.shape[0]), tiers=tiers,
                  red_fos=sc[sc.tier.str.startswith("Red")].fo_id.tolist(), amber_fos=sc[sc.tier.str.startswith("Amber")].fo_id.tolist(),
                  null_mean_red=float(nl.red.mean()), null_p_any_red=float((nl.red >= 1).mean()),
                  null_mean_flagged=float((nl.red + nl.amber).mean()), null_p_any_flag=float(((nl.red + nl.amber) >= 1).mean()),
                  omnibus={r.metric: (None if pd.isna(r.omnibus_p) else float(r.omnibus_p)) for r in om.itertuples()},
                  logic_viol=float(sm["Share with >=1 skip-logic/consistency violation"]), dk=float(sm["Mean don't-know share of categorical answers"]),
                  dup=float(sm["Share exact-duplicate answer vector (path>=10)"]), straight=float(sm["Share straight-lining (>=6 yes/no items identical)"]),
                  arms=p.arm.value_counts().to_dict(), resp_by_arm=p.groupby("arm").responded.mean().round(4).to_dict())
    K[tag]["itt"] = pd.read_csv(T / f"itt_{tag}.csv").round(5).to_dict("records")
    K[tag]["balance"] = pd.read_csv(T / f"balance_{tag}.csv").round(4).to_dict("records")
    K[tag]["icc"] = pd.read_csv(T / f"fo_icc_{tag}.csv").round(5).to_dict("records")
    K[tag]["robust"] = pd.read_csv(T / f"robustness_fo_{tag}.csv").round(5).to_dict("records")
    K[tag]["arms_itt"] = pd.read_csv(T / f"itt_arms_{tag}.csv").round(5).to_dict("records")
    K[tag]["het"] = pd.read_csv(T / f"heterogeneity_{tag}.csv").round(5).to_dict("records")
    K[tag]["arm_by_fo_p"] = float(pd.read_csv(T / f"arm_by_fo_{tag}.csv").p.iloc[0])
    fe = pd.read_csv(T / f"fo_effect_vs_pathlen_{tag}.csv"); K[tag]["fo_outcome_spearman"] = [dict(outcome=o, rho=float(g.rho.iloc[0]), p=float(g.perm_p.iloc[0])) for o, g in fe.groupby("outcome")]
K["pad2"]["fo_tests_red"] = pd.read_csv(T / "hfc_fo_tests_pad2.csv").query("red").round(3)[["fo_id", "metric", "effect_sd", "q"]].to_dict("records")
g = pd.read_csv(T / "sim_power_grid.csv")
K["sim"] = dict(power={f"{r.rule}|{r.dk_base}|{r.shorter}": [round(r.power, 3), round(r.false_pos, 4)] for r in g.itertuples()})
dl = pd.read_csv(T / "sim_detection_delay.csv")
K["sim"]["delay"] = dict(reps=len(dl), detected=float(dl.detected.mean()), median_day=float(dl.day.median()), median_interviews=float(dl.interviews.median()),
                         false_days=float(dl.days_with_false_flag.mean()), persist_detected=float(dl.detected_persist.mean()), persist_median_day=float(dl.day_persist.median()),
                         persist_false_days=float(dl.days_with_false_flag_persist.mean()))
K["sim"]["first_detection"] = pd.read_csv(T / "sim_first_detection.csv").where(lambda x: x.notna(), None).to_dict("records")
fs = pd.read_csv(T / "sim_final_scorecard.csv"); K["sim"]["final"] = fs.round(3).to_dict("records")
K["xlsform_checks_passed"] = int(pd.read_csv(T / "xlsform_validation.csv").passed.sum()); K["xlsform_checks_total"] = int(len(pd.read_csv(T / "xlsform_validation.csv")))
K["build_checks"] = dict(passed=int(pd.read_csv(T / "build_log.csv").passed.sum()), total=int(len(pd.read_csv(T / "build_log.csv"))))
json.dump(K, open(ROOT / "outputs" / "key_numbers.json", "w"), indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
print(json.dumps({k: K[k] for k in ("inventory", "build_checks")}, indent=1))
print("PAD2 tiers", K["pad2"]["tiers"], "red", K["pad2"]["red_fos"], "amber", K["pad2"]["amber_fos"])
print("PAD2 null", {k: round(v, 3) for k, v in K["pad2"].items() if k.startswith("null")}, "omnibus", K["pad2"]["omnibus"])
print("PAD1 tiers", K["pad1"]["tiers"], "red", K["pad1"]["red_fos"])
print("sim delay", K["sim"]["delay"])
print("power @40% dk4%:", {r: K["sim"]["power"][f"{r}|0.04|0.4"] for r in ("naive", "speed", "dk", "red")}, " dk0.75%:", {r: K["sim"]["power"][f"{r}|0.0075|0.4"] for r in ("speed", "dk", "red")})
print("fo_tests_red:", K["pad2"]["fo_tests_red"])
print("spearman", K["pad2"]["fo_outcome_spearman"])
