"""09 - Generate report/report.tex from the output tables (every number is read, never typed), then compile with XeLaTeX."""
import sys, json, subprocess, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import numpy as np, pandas as pd
from config import OUT_T as T, ROOT, PROC

K = json.load(open(ROOT / "outputs" / "key_numbers.json"))
p2 = pd.read_csv(PROC / "pad2_panel.csv")
def esc(s): return str(s).replace("\\", "").replace("&", "\\&").replace("%", "\\%").replace("_", "\\_").replace("#", "\\#")
def fp(p): return "$<$0.001" if p < .001 else f"{p:.3f}"
def pp(x, d=1): return f"{x*100:.{d}f}"
def n(x): return f"{int(x):,}".replace(",", "\\,")
A = K["pad2"]; B = K["pad1"]; S = K["sim"]
itt2 = {r["outcome"]: r for r in A["itt"]}; itt1 = {r["outcome"]: r for r in B["itt"]}
pw = S["power"]; dl = S["delay"]
het = {(r["modifier"], r["outcome"]): r for r in A["het"]}
hrec = het[("Lime recommended (soil pH)", "used_lime_lr2017")]; hrec_a = het[("Lime recommended (soil pH)", "redeemed_lime")]
rob = {r["spec"]: r for r in A["robust"] if r["outcome"] == "used_lime_lr2017"}
icc = {r["outcome"]: r for r in A["icc"]}
fd = pd.read_csv(T / "sim_first_detection.csv").set_index("fo_id")
IS2 = pd.read_csv(T / "impact_summary_pad2.csv").iloc[0]; IS1 = pd.read_csv(T / "impact_summary_pad1.csv").iloc[0]
rec_share = p2.lime_recommended.mean()
V = dict(
 N2B=n(A["n_baseline"]), N2E=n(A["n_endline"]), FO2=A["n_fo"], N1B=n(B["n_baseline"]), N1E=n(B["n_endline"]), FO1=B["n_fo"],
 FILES=K["inventory"]["files"], ROWS=n(K["inventory"]["rows"]), CELLS=f"{K['inventory']['cells']/1e6:.1f}", LR=n(K["inventory"]["largest_rows"]), LC=K["inventory"]["largest_cols"],
 READ=f"{K['inventory']['scale_read_s']:.2f}", QA=f"{K['inventory']['scale_qa_s']:.2f}", BCHK=f"{K['build_checks']['passed']}/{K['build_checks']['total']}",
 R2=A["tiers"].get("Red", 0), A2=A["tiers"].get("Amber", 0), G2=A["tiers"].get("Green", 0), I2=A["tiers"].get("Insufficient", 0), FL2=A["tiers"].get("Red", 0) + A["tiers"].get("Amber", 0),
 R1=B["tiers"].get("Red", 0), A1=B["tiers"].get("Amber", 0), G1=B["tiers"].get("Green", 0), I1=B["tiers"].get("Insufficient", 0),
 NULL2=f"{A['null_mean_flagged']:.2f}", NULLANY2=f"{A['null_p_any_flag']*100:.0f}", NULL1=f"{B['null_mean_flagged']:.2f}", NULLANY1=f"{B['null_p_any_flag']*100:.0f}",
 DK2=pp(A["dk"], 2), SL2=pp(A["straight"]), DUP2=f"{A['dup']*100:.0f}", DK1=pp(B["dk"]), DUP1=pp(B["dup"]),
 ITTL=pp(itt2["used_lime_lr2017"]["itt"]), CML=pp(itt2["used_lime_lr2017"]["control_mean"], 0), ITTA=pp(itt2["redeemed_lime"]["itt"]), ITTK=pp(itt2["knows_lime"]["itt"]), CMK=pp(itt2["knows_lime"]["control_mean"], 0),
 ITTH=pp(itt2["heard_lime"]["itt"]), ITTU=pp(itt2["used_urea_lr2017"]["itt"]), CIL=f"{pp(itt2['used_lime_lr2017']['ci_lo'])} to {pp(itt2['used_lime_lr2017']['ci_hi'])}",
 RATIO=f"{itt2['used_lime_lr2017']['itt']/itt2['redeemed_lime']['itt']:.1f}", MDEL=pp(itt2["used_lime_lr2017"]["mde_80"]), MDEA=pp(itt2["redeemed_lime"]["mde_80"]),
 LEELO=pp(itt2["used_lime_lr2017"]["lee_lo"]), LEEHI=pp(itt2["used_lime_lr2017"]["lee_hi"]),
 P1S=pp(itt1["used_lime_sr2016"]["itt"]), P1L=pp(itt1["used_lime_lr2017"]["itt"]), P1PH=fp(itt1["used_lime_lr2017"]["p_holm"]),
 HREC1=pp(hrec["itt_h1"]), HREC0=pp(hrec["itt_h0"]), HINT=pp(hrec["interaction"]), RECSH=pp(rec_share, 0), HREC_A1=pp(hrec_a["itt_h1"]), HREC_A0=pp(hrec_a["itt_h0"]), HINT_A_P=fp(hrec_a["p_interaction"]),
 RB0=pp(rob["Baseline (all interviews)"]["b"]), RBC=pp(rob["SE clustered by field officer"]["se"]), RB0SE=pp(rob["Baseline (all interviews)"]["se"]), RBFE=pp(rob["+ field-officer fixed effects"]["b"]),
 RBDR=pp(rob["Drop Red-tier FOs"]["b"]), RBG=pp(rob["Green-tier FOs only"]["b"]), RBGN=n(rob["Green-tier FOs only"]["n"]), RBDRN=n(rob["Drop Red-tier FOs"]["n"]),
 ICCH=pp(icc["heard_lime"]["icc_fo"]), ICCK=pp(icc["knows_lime"]["icc_fo"]), ICCL=pp(icc["used_lime_lr2017"]["icc_fo"], 2), ICCU=pp(icc["used_urea_lr2017"]["icc_fo"], 2),
 ARMFO=f"{A['arm_by_fo_p']:.2f}", BALF=f"{IS2['balance_joint_F']:.2f}", BALP=f"{IS2['balance_joint_p']:.2f}", BALF1=f"{IS1['balance_joint_F']:.2f}", BALP1=f"{IS1['balance_joint_p']:.2f}",
 RESPC=pp(IS2["resp_control"]), RESPT=pp(IS2["resp_treated"]), ATTD=pp(IS2["attr_diff"]), ATTP=f"{IS2['attr_p']:.2f}", ATTSP=f"{IS2['attr_selective_p']:.2f}", RESP1=pp(IS1["resp_control"]), ATTP1=f"{IS1['attr_p']:.2f}",
 SPR=f"{A['fo_outcome_spearman'][1]['rho']:.2f}", SPP=f"{A['fo_outcome_spearman'][1]['p']:.3f}",
 PW40=pp(pw["speed|0.04|0.4"][0], 0), PWR40=pp(pw["red|0.04|0.4"][0], 0), PWR40L=pp(pw["red|0.0075|0.4"][0], 0), PWS40L=pp(pw["speed|0.0075|0.4"][0], 0), PWD40L=pp(pw["dk|0.0075|0.4"][0], 0),
 PW20=pp(pw["speed|0.04|0.2"][0], 0), PW10=pp(pw["speed|0.04|0.1"][0], 0), PW30=pp(pw["speed|0.04|0.3"][0], 0),
 FPN=pp(pw["naive|0.04|0.0"][1], 0), FPS=pp(pw["speed|0.04|0.0"][1], 1), FPR=pp(pw["red|0.04|0.0"][1], 1),
 DLI=f"{dl['median_interviews']:.0f}", DLD=f"{dl['median_day']:.0f}", DLP=f"{dl['persist_median_day']:.0f}", DLF=f"{dl['false_days']:.1f}", DLPF=f"{dl['persist_false_days']:.1f}", DLR=dl["reps"],
 DA=int(fd.loc["SIM-03", "red_first_day"]), DB=int(fd.loc["SIM-08", "red_first_day"]), DC=int(fd.loc["SIM-14", "red_first_day"]), DD=int(fd.loc["SIM-19", "red_first_day"]), DDA=int(fd.loc["SIM-19", "any_flag_first_day"]), DE=int(fd.loc["SIM-22", "any_flag_first_day"]),
 XFORM=f"{K['xlsform_checks_passed']}/{K['xlsform_checks_total']}", PLACE="",
)
def tab(df, cols, heads, align, fmt=None, small=True):
    fmt = fmt or {}
    out = ["\\begin{tabular}{" + align + "}", "\\toprule", " & ".join(heads) + " \\\\", "\\midrule"]
    for _, r in df.iterrows():
        out.append(" & ".join(fmt.get(c, esc)(r[c]) if c in fmt else esc(r[c]) for c in cols) + " \\\\")
    out += ["\\bottomrule", "\\end{tabular}"]
    return "\n".join(out)
# ---- tables
inv = pd.read_csv(T / "data_inventory.csv").sort_values("rows", ascending=False).head(8)
T_INV = tab(inv, ["study", "file", "rows", "cols"], ["Study", "File", "Rows", "Columns"], "llrr", {"rows": lambda x: n(x), "cols": lambda x: str(int(x))})
sc = pd.read_csv(T / "hfc_fo_scorecard_pad2.csv"); sc["tier_s"] = sc.tier.str.split(" ").str[0]
te = pd.read_csv(T / "hfc_fo_tests_pad2.csv")
def fams(fo):
    t = te[(te.fo_id == fo) & te.concerning]; return ", ".join(sorted(set(t.family))) or "--"
fl = sc[sc.tier_s.isin(["Red", "Amber"])].sort_values(["n_fam_red", "n_fam"], ascending=False).copy()
fl["fam"] = fl.fo_id.map(fams)
T_FO = tab(fl, ["fo_id", "n_interviews", "tier_s", "path_len", "dk_rate", "straightline", "fam"], ["Officer", "Interviews", "Tier", "Items/interview", "DK share (\\%)", "Straight-line (\\%)", "Families flagged"], "lrlrrrl",
           {"n_interviews": lambda x: str(int(x)), "path_len": lambda x: f"{x:.1f}", "dk_rate": lambda x: f"{x*100:.2f}", "straightline": lambda x: f"{x*100:.1f}"})
sp = pd.read_csv(T / "sim_first_detection.csv")
tmap = {"A_shortcutter": "Shortcutter", "B_fabricator": "Fabricator", "C_off_hours": "Off-hours caller", "D_drifter": "Drifter", "E_fast_but_honest": "Fast but honest"}
desc = {"A_shortcutter": "40\\% shorter, 70\\% fewer DK", "B_fabricator": "12\\% copy-paste, 2--4 min bursts", "C_off_hours": "30\\% of calls outside 07:00--20:00", "D_drifter": "up to 35\\% faster over time", "E_fast_but_honest": "25\\% faster, otherwise normal"}
sp["Problem"] = sp.planted.map(tmap); sp["Planted behaviour"] = sp.planted.map(desc)
def dd(x): return "never" if pd.isna(x) else f"day {int(x)}"
sp["any"] = sp.any_flag_first_day.map(dd); sp["red"] = sp.red_first_day.map(dd)
T_SIM = tab(sp, ["fo_id", "Problem", "Planted behaviour", "any", "red"], ["Officer", "Problem", "Planted behaviour", "First flagged", "First Red"], "lllll", {c: (lambda x: x) for c in ["Planted behaviour", "any", "red"]})
rows = []
for s in (0.0, 0.1, 0.2, 0.3, 0.4, 0.5):
    r = {"s": f"{int(s*100)}\\%"}
    for rule in ("naive", "speed", "red"):
        pwv, fpv = pw[f"{rule}|0.04|{s}"]; r[rule] = f"{pwv*100:.0f}" ; r[rule + "f"] = f"{fpv*100:.1f}"
    rows.append(r)
pdf = pd.DataFrame(rows)
T_POW = tab(pdf, ["s", "naive", "naivef", "speed", "speedf", "red", "redf"], ["Shorter", "Sig. pow.", "Sig. FP", "Speed pow.", "Speed FP", "Corr. pow.", "Corr. FP"], "lrrrrrr", {c: (lambda x: x) for c in pdf.columns})
bal = pd.read_csv(T / "balance_pad2.csv"); lab = {"age_b": "Age (years)", "female_b": "Female", "primary_b": "Completed primary", "secondary_b": "Completed secondary", "english_b": "Prefers English", "mention_lime_b": "Mentions lime for acidity", "size_shamba_b": "Land size (acres)", "ever_used_lime_b": "Ever used lime", "used_anyfert_b": "Used fertiliser last season", "lime_recommended": "Lime recommended for soil"}
bal["v"] = bal["var"].map(lab)
T_BAL = tab(bal, ["v", "control_mean", "treated_mean", "diff", "p"], ["Baseline variable", "Control", "Any SMS", "Difference", "p"], "lrrrr", {"control_mean": lambda x: f"{x:.2f}", "treated_mean": lambda x: f"{x:.2f}", "diff": lambda x: f"{x:+.3f}", "p": fp})
def ittt(tag):
    d = pd.read_csv(T / f"itt_{tag}.csv"); d["Cm"] = d.control_mean; return tab(d, ["label", "control_mean", "itt", "se", "p_holm", "n"], ["Outcome", "Control mean", "ITT (pp)", "SE (pp)", "Holm p", "N"], "lrrrrr",
        {"control_mean": lambda x: f"{x*100:.1f}\\%", "itt": lambda x: f"{x*100:+.2f}", "se": lambda x: f"{x*100:.2f}", "p_holm": fp, "n": lambda x: n(x)})
T_ITT2, T_ITT1 = ittt("pad2"), ittt("pad1")
ar = pd.read_csv(T / "itt_arms_pad2.csv")
T_ARM = tab(ar[ar.outcome.isin(["knows_lime", "used_lime_lr2017", "used_urea_lr2017", "redeemed_lime"])], ["label", "SMS_b", "SMS+Call offer_b", "SMS+Call_b", "p_arms_equal"], ["Outcome", "SMS", "SMS+Call offer", "SMS+Call", "p (arms equal)"], "lrrrr",
            {"SMS_b": lambda x: f"{x*100:+.1f}", "SMS+Call offer_b": lambda x: f"{x*100:+.1f}", "SMS+Call_b": lambda x: f"{x*100:+.1f}", "p_arms_equal": fp})
rb = pd.read_csv(T / "robustness_fo_pad2.csv"); rb = rb[rb.outcome == "used_lime_lr2017"]
T_ROB = tab(rb, ["spec", "b", "se", "p", "n"], ["Specification", "ITT (pp)", "SE (pp)", "p", "N"], "lrrrr", {"b": lambda x: f"{x*100:.2f}", "se": lambda x: f"{x*100:.2f}", "p": fp, "n": lambda x: n(x)})
ic = pd.read_csv(T / "fo_icc_pad2.csv")
T_ICC = tab(ic, ["label", "icc_fo", "design_effect", "p"], ["Outcome", "ICC (\\%)", "Design effect", "p"], "lrrr", {"icc_fo": lambda x: f"{x*100:.2f}", "design_effect": lambda x: f"{x:.1f}", "p": fp})
hg = pd.read_csv(T / "heterogeneity_pad2.csv"); hg = hg[hg.outcome == "used_lime_lr2017"]
T_HET = tab(hg, ["modifier", "itt_h0", "itt_h1", "interaction", "p_interaction"], ["Modifier", "Group = 0", "Group = 1", "Interaction", "p"], "lrrrr", {"itt_h0": lambda x: f"{x*100:+.1f}", "itt_h1": lambda x: f"{x*100:+.1f}", "interaction": lambda x: f"{x*100:+.1f}", "p_interaction": fp})
bl = pd.read_csv(T / "build_log.csv")
T_BUILD = tab(bl, ["check"], ["Integrity check (all passed)"], "l")
V.update({k: v for k, v in dict(T_INV=T_INV, T_FO=T_FO, T_SIM=T_SIM, T_POW=T_POW, T_BAL=T_BAL, T_ITT2=T_ITT2, T_ITT1=T_ITT1, T_ARM=T_ARM, T_ROB=T_ROB, T_ICC=T_ICC, T_HET=T_HET, T_BUILD=T_BUILD).items()})
tex = (ROOT / "report" / "template.tex").read_text()
for k, v in V.items(): tex = tex.replace(f"@@{k}@@", str(v))
left = re.findall(r"@@(\w+)@@", tex)
assert not left, f"unfilled placeholders: {set(left)}"
(ROOT / "report" / "report.tex").write_text(tex)
for _ in range(2):
    r = subprocess.run(["xelatex", "-interaction=nonstopmode", "-halt-on-error", "report.tex"], cwd=ROOT / "report", capture_output=True, text=True)
    if r.returncode: print(r.stdout[-3000:]); sys.exit(1)
pages = re.search(r"Output written on report.pdf \((\d+) pages", r.stdout)
print("compiled; pages:", pages.group(1) if pages else "?")
