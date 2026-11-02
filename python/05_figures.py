"""05 - All report figures (one consistent style)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from config import OUT_T as T, OUT_F as F, PAL, SYN, PROC, ROOT

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": PAL["mute"], "axes.labelcolor": PAL["ink"],
                     "xtick.color": PAL["ink"], "ytick.color": PAL["ink"], "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": PAL["grid"], "grid.linewidth": .7, "figure.dpi": 150, "savefig.bbox": "tight"})
REP = ROOT / "report" / "figures"; REP.mkdir(parents=True, exist_ok=True)
def save(fig, name):
    fig.savefig(F / f"{name}.png"); fig.savefig(REP / f"{name}.png"); plt.close(fig)

# 1 heatmap of FO effects (PAD2)
t = pd.read_csv(T / "hfc_fo_tests_pad2.csv"); sc = pd.read_csv(T / "hfc_fo_scorecard_pad2.csv")
order = sc.sort_values(["n_fam_red", "n_fam", "n_interviews"], ascending=[False, False, False]).fo_id.tolist()
mets = ["path_len", "gate_no", "dk_rate", "straightline", "admin_mismatch"]
names = {"path_len": "Path length", "gate_no": "Gate 'No' answers", "dk_rate": "Don't-know rate", "straightline": "Straight-lining", "admin_mismatch": "Survey vs coupon"}
E = t.pivot(index="fo_id", columns="metric", values="effect_sd").reindex(order)[mets]
C = t.pivot(index="fo_id", columns="metric", values="concerning").reindex(order)[mets]
Rd = t.pivot(index="fo_id", columns="metric", values="red").reindex(order)[mets]
fig, ax = plt.subplots(figsize=(6.6, 7.4))
im = ax.imshow(E.values, cmap="RdBu_r", vmin=-1.2, vmax=1.2, aspect="auto")
ax.set_xticks(range(len(mets))); ax.set_xticklabels([names[m] for m in mets], rotation=25, ha="right")
ax.set_yticks(range(len(order))); ax.set_yticklabels([f"{o}  ({sc.set_index('fo_id').loc[o,'tier'].split(' ')[0][:3]})" for o in order], fontsize=7.5)
ax.grid(False)
for i in range(E.shape[0]):
    for j in range(E.shape[1]):
        v = E.values[i, j]
        if np.isnan(v): continue
        mark = "●" if Rd.values[i, j] == True else ("○" if C.values[i, j] == True else "")
        ax.text(j, i, f"{v:+.2f}{mark}", ha="center", va="center", fontsize=6.8, color="white" if abs(v) > .75 else PAL["ink"])
cb = fig.colorbar(im, ax=ax, shrink=.5, pad=.02); cb.set_label("Effect vs team (SD, adjusted)")
ax.set_title("PAD2 field-officer scorecard   ● red flag   ○ amber flag", loc="left", fontsize=9.5)
save(fig, "fig01_fo_heatmap")

# 2 null calibration
nl = pd.read_csv(T / "hfc_null_calibration_pad2.csv")
fig, ax = plt.subplots(figsize=(5.8, 3.2))
bins = np.arange(-.5, 14.5, 1)
ax.hist(nl.red + nl.amber, bins=bins, color=PAL["grid"], edgecolor=PAL["mute"], label="Pure-noise labels (300 permutations)")
obs = int(((sc.tier.str.startswith("Red")) | (sc.tier.str.startswith("Amber"))).sum())
ax.axvline(obs, color=PAL["red"], lw=2); ax.text(obs + .2, ax.get_ylim()[1] * .85, f"Observed: {obs}\nofficers flagged", color=PAL["red"], fontsize=8.5)
ax.set_xlabel("Number of field officers flagged Amber or Red"); ax.set_ylabel("Permutations"); ax.legend(frameon=False, fontsize=8)
ax.set_title("Flags far exceed what chance alone produces", loc="left", fontsize=9.5)
save(fig, "fig02_null_calibration")

# 3 power curves
g = pd.read_csv(T / "sim_power_grid.csv")
fig, axs = plt.subplots(1, 3, figsize=(8.6, 2.9), sharey=True)
col = {"naive": PAL["amber"], "speed": PAL["blue"], "dk": PAL["violet"], "red": PAL["teal"]}
lab = {"naive": "Significance only (t<-2)", "speed": "Speed rule (BH + >=20% shorter)", "dk": "DK-deficit rule", "red": "Corroborated (speed AND DK)"}
for ax, dk in zip(axs, (0.0075, 0.02, 0.04)):
    for r in ("naive", "speed", "dk", "red"):
        s = g[(g.dk_base == dk) & (g.rule == r)]
        ax.plot(s.shorter * 100, s.power, marker="o", ms=3.5, color=col[r], label=lab[r])
    ax.set_title(f"Baseline DK rate {dk*100:.2g}%", fontsize=9); ax.set_xlabel("Interviews shorter by (%)")
    ax.axvline(40, color=PAL["mute"], ls=":", lw=1)
axs[0].set_ylabel("Detection power")
h_, l_ = axs[0].get_legend_handles_labels(); fig.legend(h_, l_, loc="lower center", ncol=4, frameon=False, fontsize=7.2, bbox_to_anchor=(.5, -.12))
fig.suptitle("Power to catch one shortcutting officer among 26 (simulation)", x=.01, y=1.04, ha="left", fontsize=9.5)
save(fig, "fig03_power")

# 4 false positives
fp = g[(g.dk_base == 0.04) & (g.shorter == 0)].set_index("rule").false_pos
fig, ax = plt.subplots(figsize=(4.6, 3))
ks = ["naive", "speed", "dk", "red"]
ax.bar([lab[k].replace(" (", "\n(") for k in ks], [fp[k] * 100 for k in ks], color=[col[k] for k in ks])
ax.set_ylabel("Honest officers wrongly flagged (%)"); plt.setp(ax.get_xticklabels(), fontsize=6.3)
ax.set_title("Why an effect-size floor and BH control matter", loc="left", fontsize=9.5)
for i, k in enumerate(ks): ax.text(i, fp[k] * 100 + .5, f"{fp[k]*100:.1f}%", ha="center", fontsize=8)
save(fig, "fig04_false_positives")

# 5 sim daily durations
sim = pd.read_csv(SYN / "SIM_paradata.csv")
fig, axs = plt.subplots(1, 2, figsize=(8.4, 3), sharey=True)
daily = sim.groupby(["fo_id", "day"]).duration_min.median().reset_index()
clean = daily[~daily.fo_id.isin(["SIM-03", "SIM-08", "SIM-14", "SIM-19", "SIM-22"])]
band = clean.groupby("day").duration_min.quantile([.1, .5, .9]).unstack()
for ax, fo, nm, c in zip(axs, ["SIM-03", "SIM-19"], ["Shortcutter (A): 40% shorter from day 1", "Drifter (D): gradually faster"], [PAL["red"], PAL["violet"]]):
    ax.fill_between(band.index, band[.1], band[.9], color=PAL["grid"], label="Clean officers (10-90%)")
    ax.plot(band.index, band[.5], color=PAL["mute"], lw=1)
    s = daily[daily.fo_id == fo]; ax.plot(s.day, s.duration_min, color=c, marker="o", ms=3, lw=1.2, label=fo)
    ax.set_title(nm, fontsize=9); ax.set_xlabel("Field day"); ax.legend(frameon=False, fontsize=7)
axs[0].set_ylabel("Median interview minutes (simulated)")
save(fig, "fig05_sim_durations")

# 6 forest ITT
fig, axs = plt.subplots(2, 1, figsize=(6.8, 6.4), gridspec_kw={"height_ratios": [6, 4]})
fmt = lambda p: "<0.001" if p < .001 else f"{p:.3f}"
for ax, tag, nm in zip(axs, ["pad2", "pad1"], ["PAD2 (n=5,890)", "PAD1 (n=1,897)"]):
    d = pd.read_csv(T / f"itt_{tag}.csv").iloc[::-1]
    y = np.arange(len(d))
    c = [PAL["teal"] if s_ == "admin" else PAL["blue"] for s_ in d.source]
    ax.errorbar(d.itt * 100, y, xerr=[(d.itt - d.ci_lo) * 100, (d.ci_hi - d.itt) * 100], fmt="none", ecolor=PAL["mute"], lw=1.3)
    ax.scatter(d.itt * 100, y, c=c, s=34, zorder=3)
    ax.axvline(0, color=PAL["ink"], lw=.8)
    ax.set_yticks(y); ax.set_yticklabels(d.label, fontsize=7.6); ax.set_xlabel("Effect of any SMS vs control (percentage points, 95% CI)")
    ax.set_xlim(-4, 19.5); ax.set_ylim(-.6, len(d) - .4)
    ax.set_title(nm, loc="left", fontsize=9)
    for yi, p_ in enumerate(d.p_holm): ax.text(19.3, yi, f"Holm p {fmt(p_)}", va="center", ha="right", fontsize=6.8, color=PAL["mute"])
fig.suptitle("Intention-to-treat effects (blue = survey-reported, green = administrative)", x=.01, y=1.0, ha="left", fontsize=9.5)
fig.tight_layout()
save(fig, "fig06_itt_forest")

# 7 heterogeneity
h = pd.read_csv(T / "heterogeneity_pad2.csv"); h = h[(h.outcome == "used_lime_lr2017")]
fig, ax = plt.subplots(figsize=(5.4, 3))
x = np.arange(len(h)); w = .36
ax.bar(x - w/2, h.itt_h0 * 100, w, color=PAL["amber"], label="Group = 0"); ax.bar(x + w/2, h.itt_h1 * 100, w, color=PAL["blue"], label="Group = 1")
ax.set_xticks(x); ax.set_xticklabels([m.replace(" (", "\n(") for m in h.modifier], fontsize=7.4); ax.axhline(0, color=PAL["ink"], lw=.8)
ax.set_ylabel("Effect on lime use (pp)"); ax.legend(frameon=False, fontsize=8)
ax.set_title("Targeting: SMS helps where lime is advised, lowers use where it is not", loc="left", fontsize=9)
save(fig, "fig07_heterogeneity")

# 8 robustness
r = pd.read_csv(T / "robustness_fo_pad2.csv"); r = r[r.outcome == "used_lime_lr2017"].iloc[::-1]
fig, ax = plt.subplots(figsize=(5.8, 2.8)); y = np.arange(len(r))
ax.errorbar(r.b * 100, y, xerr=1.96 * r.se * 100, fmt="o", color=PAL["blue"], ecolor=PAL["mute"], ms=5)
ax.set_yticks(y); ax.set_yticklabels(r.spec, fontsize=7.6); ax.axvline(0, color=PAL["ink"], lw=.8); ax.set_xlabel("ITT on lime use (pp, 95% CI)")
ax.set_title("Effect is stable to enumerator-quality choices", loc="left", fontsize=9.5)
save(fig, "fig08_robustness")

# 9 ICC
ic = pd.read_csv(T / "fo_icc_pad2.csv")
fig, ax = plt.subplots(figsize=(5.2, 2.8))
ax.barh(ic.label[::-1], ic.icc_fo[::-1] * 100, color=PAL["violet"]); ax.set_xlabel("Intra-officer correlation (%)"); ax.tick_params(axis="y", labelsize=7.4)
ax.set_title("Officer effects on answers (after arm, covariates, location)", loc="left", fontsize=9)
save(fig, "fig09_icc")

# 10 path length by FO
m = pd.read_csv(PROC / "pad2_interview_metrics.csv")
o = m.groupby("fo_id").path_len.median().sort_values().index
fig, ax = plt.subplots(figsize=(8.2, 3))
ax.boxplot([m[m.fo_id == f].path_len for f in o], showfliers=False, patch_artist=True, boxprops=dict(facecolor=PAL["grid"], color=PAL["mute"]), medianprops=dict(color=PAL["red"]))
ax.set_xticklabels([f.replace("P2-", "") for f in o], fontsize=7); ax.set_xlabel("Field officer"); ax.set_ylabel("Items answered per interview")
ax.axhline(m.path_len.median(), color=PAL["blue"], ls=":"); ax.set_title("Questionnaire path length by officer (PAD2, real data)", loc="left", fontsize=9.5)
save(fig, "fig10_pathlen_fo")

# 11 detection timeline
fd = pd.read_csv(T / "sim_first_detection.csv")
fig, ax = plt.subplots(figsize=(6.4, 2.8))
rules = ["R1_speed", "R2_dk_deficit", "R3_duplicates", "R4_off_hours", "R5_impossible", "R6_drift"]
for i, row in fd.iterrows():
    ax.plot([0, 30], [i, i], color=PAL["grid"], lw=6, solid_capstyle="butt")
    if pd.notna(row.red_first_day): ax.scatter(row.red_first_day, i, c=PAL["red"], s=70, zorder=3, label="Red" if i == 0 else None)
    elif pd.notna(row.any_flag_first_day): ax.scatter(row.any_flag_first_day, i, c=PAL["amber"], s=70, zorder=3, label="Amber only")
ax.set_yticks(range(len(fd))); ax.set_yticklabels([f"{a} - {b[2:]}" for a, b in zip(fd.fo_id, fd.planted)], fontsize=7.6); ax.invert_yaxis()
ax.set_xlabel("Field day first flagged"); ax.set_xlim(0, 30); ax.set_title("Time to detection for each planted problem", loc="left", fontsize=9.5)
h_, l_ = ax.get_legend_handles_labels(); ax.legend(dict(zip(l_, h_)).values(), dict(zip(l_, h_)).keys(), frameon=False, fontsize=7.5)
save(fig, "fig11_detection_timeline")
print("figures:", sorted(p.name for p in F.glob("*.png")))
