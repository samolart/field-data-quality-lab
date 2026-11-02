"""04 - Experimental analysis: balance, attrition, ITT with multiple-testing control, enumerator effects,
and whether data-quality flags change the substantive conclusions.

PAD2 is primary (4 arms: Control / SMS / SMS+Call offer / SMS+Call; individual randomisation stratified
on gender, past lime use, agrovet). PAD1 (3 arms) is a second, independent replication.
Primary contrast: ANY SMS vs Control (robust to the t1/t3 labelling ambiguity - see docs/DATA_NOTES.md).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import numpy as np
import pandas as pd
from scipy import stats
from config import PROC, OUT_T, SEED
from pxdlib import design, ols, coef, wald_joint, holm, bh, lee_bounds, icc_anova

rng = np.random.default_rng(SEED)

P2 = dict(
    name="PAD2", panel="pad2_panel.csv", metrics="pad2_interview_metrics.csv", tests="hfc_fo_tests_pad2.csv",
    fe=["agrovet"], ctrl=["female_b", "ever_used_lime_b", "age_b", "size_shamba_b", "english_b"],
    bal=["age_b", "female_b", "primary_b", "secondary_b", "english_b", "mention_lime_b", "size_shamba_b",
         "ever_used_lime_b", "used_anyfert_b", "lime_recommended"],
    survey=["heard_lime", "knows_lime", "used_lime_lr2017", "used_urea_lr2017"],
    admin=["redeemed_lime", "redeemed_fert"],
    arms=["SMS", "SMS+Call offer", "SMS+Call"],
    labels={"heard_lime": "Heard of lime (survey)", "knows_lime": "Names lime as acidity remedy (survey)",
            "used_lime_lr2017": "Used lime, LR2017 (survey)", "used_urea_lr2017": "Used urea, LR2017 (survey)",
            "redeemed_lime": "Redeemed lime coupon (admin)", "redeemed_fert": "Redeemed fertiliser coupon (admin)"},
)
P1 = dict(
    name="PAD1", panel="pad1_panel.csv", metrics="pad1_interview_metrics.csv", tests="hfc_fo_tests_pad1.csv",
    fe=["location"], ctrl=["female_b", "ever_used_lime_b", "age_b", "primary_b", "english_b"],
    bal=["age_b", "female_b", "primary_b", "english_b", "size_shamba_b", "ever_used_lime_b"],
    survey=["heard_lime", "used_lime_sr2016", "used_lime_lr2017"],
    admin=["redeemed_lime"],
    arms=["General SMS", "Local SMS"],
    labels={"heard_lime": "Heard of lime (survey)", "used_lime_sr2016": "Used lime, SR2016 (survey)",
            "used_lime_lr2017": "Used lime, LR2017 (survey)", "redeemed_lime": "Redeemed lime coupon, SR2016 (admin)"},
)


def itt(d, y, cfg, extra_fe=None, sample=None, arms=False, cluster=None):
    s = d if sample is None else d[sample]
    s = s.dropna(subset=[y]).copy()
    xcols = (["arm_" + a for a in cfg["arms"]] if arms else ["treated"]) + cfg["ctrl"]
    X = design(s, xcols, cfg["fe"] + (extra_fe or []))
    return ols(s[y].to_numpy(), X, cluster=s[cluster] if cluster else None), s


def run(cfg):
    d = pd.read_csv(PROC / cfg["panel"])
    for a in cfg["arms"]:
        d["arm_" + a] = (d.arm == a).astype(float)
    for c in cfg["ctrl"] + ["size_shamba_b", "age_b"]:
        if d[c].isna().any():
            d[c] = d[c].fillna(d[c].median())
    tag = cfg["name"].lower()
    out = {}

    # ---------------------------------------------------------------- balance
    rows = []
    for v in cfg["bal"]:
        x = d.dropna(subset=[v])
        res = ols(x[v].to_numpy(), design(x, ["treated"], cfg["fe"]))
        b, se, p = coef(res, "treated")
        rows.append(dict(var=v, control_mean=x.loc[x.treated == 0, v].mean(), treated_mean=x.loc[x.treated == 1, v].mean(),
                         diff=b, se=se, p=p, n=len(x)))
    bal = pd.DataFrame(rows)
    res = ols(d.treated.to_numpy(), design(d, cfg["bal"], cfg["fe"]))
    F, pF = wald_joint(res, [c for c in cfg["bal"] if c in res["names"]])
    bal.attrs["joint"] = (F, pF)
    bal.to_csv(OUT_T / f"balance_{tag}.csv", index=False)
    out["balance_joint_F"], out["balance_joint_p"] = F, pF
    out["balance_min_p"] = bal.p.min()
    out["balance_n_sig05"] = int((bal.p < 0.05).sum())

    # ---------------------------------------------------------------- attrition
    res = ols(d.responded.to_numpy(), design(d, ["treated"], cfg["fe"]))
    b, se, p = coef(res, "treated")
    out.update(resp_control=d.loc[d.treated == 0, "responded"].mean(), resp_treated=d.loc[d.treated == 1, "responded"].mean(),
               attr_diff=b, attr_se=se, attr_p=p)
    inter = d.copy()
    cols = []
    for c in cfg["bal"]:
        if c in inter and inter[c].notna().all():
            inter["tx_" + c] = inter.treated * (inter[c] - inter[c].mean()); cols.append("tx_" + c)
    res = ols(inter.responded.to_numpy(), design(inter, ["treated"] + [c for c in cfg["bal"] if inter[c].notna().all()] + cols, cfg["fe"]))
    F2, p2 = wald_joint(res, cols)
    out.update(attr_selective_F=F2, attr_selective_p=p2)
    arm_resp = d.groupby("arm").responded.agg(["mean", "size"]).reset_index()
    arm_resp.to_csv(OUT_T / f"response_by_arm_{tag}.csv", index=False)

    # ---------------------------------------------------------------- ITT, any-SMS vs control
    rows = []
    for y in cfg["survey"] + cfg["admin"]:
        res, s = itt(d, y, cfg)
        b, se, p = coef(res, "treated")
        cm = s.loc[s.treated == 0, y].mean()
        lo, hi, lo_ci, hi_ci = (np.nan,) * 4
        if y in cfg["survey"]:
            full = d.copy(); full["_y"] = full[y].fillna(0)
            lo, hi, lo_ci, hi_ci = lee_bounds(full["_y"].where(full.responded == 1, 0).to_numpy(), full.treated.to_numpy(), full.responded.to_numpy(), n_boot=300)
        rows.append(dict(outcome=y, label=cfg["labels"][y], source="admin" if y in cfg["admin"] else "survey",
                         control_mean=cm, itt=b, se=se, ci_lo=b - 1.96 * se, ci_hi=b + 1.96 * se, p=p, n=int(res["n"]),
                         mde_80=2.8 * se, rel_effect=b / cm if cm > 0 else np.nan,
                         lee_lo=lo, lee_hi=hi, lee_ci_lo=lo_ci, lee_ci_hi=hi_ci))
    t = pd.DataFrame(rows)
    t["p_holm"] = holm(t.p.to_numpy()); t["q_bh"] = bh(t.p.to_numpy())
    t.to_csv(OUT_T / f"itt_{tag}.csv", index=False)
    out["itt"] = t

    # ---------------------------------------------------------------- arm-level ITT
    rows = []
    for y in cfg["survey"] + cfg["admin"]:
        res, s = itt(d, y, cfg, arms=True)
        r = dict(outcome=y, label=cfg["labels"][y])
        for a in cfg["arms"]:
            b, se, p = coef(res, "arm_" + a)
            r[f"{a}_b"], r[f"{a}_se"], r[f"{a}_p"] = b, se, p
        F, pF = wald_joint({**res, "b": res["b"]}, ["arm_" + a for a in cfg["arms"]])
        # equality of arms: test differences via contrast on V
        idx = [res["names"].index("arm_" + a) for a in cfg["arms"]]
        Rm = np.zeros((len(idx) - 1, len(res["names"])))
        for k in range(len(idx) - 1):
            Rm[k, idx[0]] = 1; Rm[k, idx[k + 1]] = -1
        dlt = Rm @ res["b"]
        Fe = float(dlt @ np.linalg.pinv(Rm @ res["V"] @ Rm.T) @ dlt) / len(dlt)
        r["p_arms_equal"] = float(stats.f.sf(Fe, len(dlt), res["df"]))
        rows.append(r)
    pd.DataFrame(rows).to_csv(OUT_T / f"itt_arms_{tag}.csv", index=False)

    # ---------------------------------------------------------------- heterogeneity (exploratory, no MHT)
    het = []
    for hv in ([("lime_recommended", "Lime recommended (soil pH)")] if "lime_recommended" in d else []) + [("female_b", "Female"), ("ever_used_lime_b", "Used lime before baseline")]:
        for y in ["used_lime_lr2017"] + cfg["admin"][:1]:
            s = d.dropna(subset=[y]).copy()
            s["_h"] = s[hv[0]].astype(float); s["_tx"] = s.treated * s._h
            ctrl = [c for c in cfg["ctrl"] if c != hv[0]]
            res = ols(s[y].to_numpy(), design(s, ["treated", "_h", "_tx"] + ctrl, cfg["fe"]))
            b0, se0, _ = coef(res, "treated"); bi, sei, pi = coef(res, "_tx")
            het.append(dict(modifier=hv[1], outcome=y, itt_h0=b0, itt_h1=b0 + bi, interaction=bi, se_interaction=sei, p_interaction=pi, n=int(res["n"])))
    pd.DataFrame(het).to_csv(OUT_T / f"heterogeneity_{tag}.csv", index=False)

    # ---------------------------------------------------------------- is treatment orthogonal to FO?
    rr = d[d.responded == 1].merge(pd.read_csv(PROC / cfg["metrics"])[["respid", "fo_id"]].rename(columns={"fo_id": "fo_"}), on="respid")
    chi2, pchi, dof, _ = stats.chi2_contingency(pd.crosstab(rr.fo_, rr.arm))
    pd.DataFrame([dict(test="arm x field officer chi-square", chi2=chi2, dof=dof, p=pchi)]).to_csv(OUT_T / f"arm_by_fo_{tag}.csv", index=False)

    # ---------------------------------------------------------------- enumerator effects
    m = pd.read_csv(PROC / cfg["metrics"])[["respid", "fo_id"]].rename(columns={"fo_id": "fo"})
    dm = d.merge(m, on="respid", how="inner")
    rows = []
    for y in cfg["survey"]:
        s = dm.dropna(subset=[y]).copy()
        res, _ = itt(s, y, cfg)
        icc, F, p = icc_anova(pd.Series(res["resid"], index=s.index), s.fo)
        rows.append(dict(outcome=y, label=cfg["labels"][y], icc_fo=icc, F=F, p=p, n=len(s), n_fo=s.fo.nunique(),
                         design_effect=1 + (len(s) / s.fo.nunique() - 1) * max(icc, 0)))
    pd.DataFrame(rows).to_csv(OUT_T / f"fo_icc_{tag}.csv", index=False)

    # ---------------------------------------------------------------- robustness to enumerator quality
    tests = pd.read_csv(OUT_T / cfg["tests"])
    fo_tier = pd.read_csv(OUT_T / f"hfc_fo_scorecard_{tag}.csv")[["fo_id", "tier"]]
    dm = dm.merge(fo_tier, left_on="fo", right_on="fo_id", how="left")
    rows = []
    for y in [c for c in cfg["survey"] if c.startswith("used_lime")]:
        base, _ = itt(dm, y, cfg)
        b0, se0, p0 = coef(base, "treated")
        fe_res, _ = itt(dm, y, cfg, extra_fe=["fo"])
        b1, se1, p1 = coef(fe_res, "treated")
        nored = ~dm.tier.fillna("").str.startswith("Red")
        r2, _ = itt(dm, y, cfg, sample=nored)
        b2, se2, p2 = coef(r2, "treated")
        green = dm.tier.fillna("").isin(["Green"])
        r3, _ = itt(dm, y, cfg, sample=green)
        b3, se3, p3 = coef(r3, "treated")
        cl, _ = itt(dm, y, cfg, cluster="fo")
        bc, sec, pc = coef(cl, "treated")
        rows += [dict(outcome=y, spec="Baseline (all interviews)", b=b0, se=se0, p=p0, n=int(base["n"])),
                 dict(outcome=y, spec="SE clustered by field officer", b=bc, se=sec, p=pc, n=int(cl["n"])),
                 dict(outcome=y, spec="+ field-officer fixed effects", b=b1, se=se1, p=p1, n=int(fe_res["n"])),
                 dict(outcome=y, spec="Drop Red-tier FOs", b=b2, se=se2, p=p2, n=int(r2["n"])),
                 dict(outcome=y, spec="Green-tier FOs only", b=b3, se=se3, p=p3, n=int(r3["n"]))]
    pd.DataFrame(rows).to_csv(OUT_T / f"robustness_fo_{tag}.csv", index=False)

    # do FOs with 'worse' process metrics report different outcomes? (FO-level, Spearman + permutation p)
    fo_eff = []
    for y in [c for c in cfg["survey"] if c.startswith("used_lime")][:1] + ["knows_lime" if "knows_lime" in cfg["survey"] else "heard_lime"]:
        s = dm.dropna(subset=[y]).copy()
        res, _ = itt(s, y, cfg)
        s["_r"] = res["resid"]
        eff = s.groupby("fo").agg(fo_effect=("_r", "mean"), n=("_r", "size")).reset_index()
        z = tests[tests.metric == "path_len"][["fo_id", "effect_sd"]].rename(columns={"fo_id": "fo", "effect_sd": "path_len_effect_sd"})
        eff = eff.merge(z, on="fo")
        rho, pr = stats.spearmanr(eff.path_len_effect_sd, eff.fo_effect)
        # permutation p for the Spearman rho
        perm = [stats.spearmanr(eff.path_len_effect_sd, rng.permutation(eff.fo_effect))[0] for _ in range(5000)]
        pp = (1 + sum(abs(x) >= abs(rho) for x in perm)) / 5001
        eff["outcome"] = y
        fo_eff.append(eff.assign(rho=rho, perm_p=pp))
    pd.concat(fo_eff).to_csv(OUT_T / f"fo_effect_vs_pathlen_{tag}.csv", index=False)
    pd.DataFrame([{k: v for k, v in out.items() if k != 'itt'}]).to_csv(OUT_T / f'impact_summary_{tag}.csv', index=False)
    return out


if __name__ == "__main__":
    for cfg in (P2, P1):
        o = run(cfg)
        print(f"\n=========== {cfg['name']}")
        print(f"balance: joint F={o['balance_joint_F']:.2f} p={o['balance_joint_p']:.3f}; min single p={o['balance_min_p']:.3f}; n<.05: {o['balance_n_sig05']}")
        print(f"response: control {o['resp_control']:.3f} treated {o['resp_treated']:.3f}; diff {o['attr_diff']:.3f} (se {o['attr_se']:.3f}, p={o['attr_p']:.3f}); selective-attrition F p={o['attr_selective_p']:.3f}")
        print(o["itt"][["label", "control_mean", "itt", "se", "p", "p_holm", "q_bh", "n", "mde_80", "lee_lo", "lee_hi"]].round(4).to_string(index=False))
    tag = "pad2"
    for f in ("itt_arms", "heterogeneity", "fo_icc", "robustness_fo", "fo_effect_vs_pathlen"):
        print(f"\n--- {f}_{tag}"); x = pd.read_csv(OUT_T / f"{f}_{tag}.csv")
        print(x.head(16).round(4).to_string(index=False))
