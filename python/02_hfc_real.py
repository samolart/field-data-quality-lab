"""02 - Automated high-frequency checks (HFC) on REAL endline interviews (PAD2 primary, PAD1 replication).

What this does, per dataset
  1. Item-level profile: answered / missing / don't-know share for every questionnaire item.
  2. Interview-level metrics: path length, don't-know rate, straight-lining, gate-"No" count,
     skip-logic / consistency violations, exact duplicate answer vectors, survey-vs-admin discrepancies,
     numeric heaping.
  3. Field-officer (FO) scorecard: each metric is residualised on arm, baseline covariates and location
     fixed effects, then tested against the rest of the team (Welch z), BH-adjusted across FOs.
  4. Pre-specified tiering (thresholds fixed in THRESH *before* looking at results).

A flag is a prompt to BACK-CHECK, never a finding of misconduct. See docs/HFC_SPECIFICATION.md.
"""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import numpy as np
import pandas as pd
from scipy import stats
from config import RAW, PROC, OUT_T, DK_CODES
from pxdlib import design, ols, bh

THRESH = dict(min_n=30, q_amber=0.10, q_red=0.05, min_effect_sd=0.25, dup_max_baseline=0.05, n_perm=4000, seed=7)
# Correlated metrics are grouped into families so one behaviour is never counted twice.
FAMILY = {"path_len": "shortcut", "gate_no": "shortcut", "dk_rate": "dk", "straightline": "straightline",
          "logic_viol": "logic", "dup_vector": "duplicate", "admin_mismatch": "admin"}

# direction that is CONCERNING for each metric: -1 = lower than peers is concerning, +1 = higher
METRICS = {
    "path_len":        dict(label="Questionnaire path length (items answered)", bad=-1),
    "dk_rate":         dict(label="Don't-know share of categorical answers",      bad=-1),
    "straightline":    dict(label="Straight-lining on yes/no items",              bad=+1),
    "gate_no":         dict(label="Gate questions answered 'No' (skip triggers)", bad=+1),
    "logic_viol":      dict(label="Skip-logic / consistency violation",           bad=+1),
    "dup_vector":      dict(label="Exact duplicate answer vector",                bad=+1),
    "admin_mismatch":  dict(label="Survey says no lime, coupon records say bought", bad=+1),
}


# ------------------------------------------------------------------ item-level machinery
def classify_items(en: pd.DataFrame, id_cols: list[str], qty_cols: list[str], skip_cols: list[str]):
    items = [c for c in en.columns if c not in id_cols + skip_cols]
    cat, qty, multi = [], [], []
    for c in items:
        s = en[c]
        if c in qty_cols:
            qty.append(c)
        elif s.dtype == object or str(s.dtype).startswith("str"):
            multi.append(c)
        elif s.nunique(dropna=True) <= 12:
            cat.append(c)
        else:
            qty.append(c)
    return items, cat, qty, multi


def is_dk_multi(v) -> bool:
    if pd.isna(v):
        return False
    toks = str(v).split()
    return any(t.lstrip("-").isdigit() and int(t) in DK_CODES for t in toks)


def interview_metrics(en: pd.DataFrame, items, cat, qty, multi, gates) -> pd.DataFrame:
    m = pd.DataFrame({"respid": en.respid})
    m["path_len"] = en[items].notna().sum(axis=1)
    cat_ans = en[cat].notna().sum(axis=1) + en[multi].notna().sum(axis=1)
    dk_cat = en[cat].isin(DK_CODES).sum(axis=1)
    dk_mul = en[multi].apply(lambda col: col.map(is_dk_multi)).sum(axis=1)
    dk_qty = (en[qty] == -99).sum(axis=1)
    m["dk_n"] = dk_cat + dk_mul + dk_qty
    m["dk_rate"] = m.dk_n / cat_ans.replace(0, np.nan)
    # straight-lining on binary items
    binary = [c for c in cat if set(en[c].dropna().unique()) <= {0, 1, 0.0, 1.0}]
    nb = en[binary].notna().sum(axis=1)
    same = en[binary].nunique(axis=1, dropna=True) == 1
    m["straightline"] = ((nb >= 6) & same).astype(float)
    # gates: count of "No" among asked gates
    g = [c for c in gates if c in en.columns]
    m["gate_no"] = (en[g] == 0).sum(axis=1)
    # exact duplicate vectors among long-path interviews
    vec = pd.util.hash_pandas_object(en[items].astype(object).where(en[items].notna(), "NA").astype(str), index=False)
    long_ = m.path_len >= 10
    dup = vec.duplicated(keep=False) & long_
    m["dup_vector"] = dup.astype(float)
    return m


def heaping_by_fo(en, qty, fo):
    """Share of answered numeric quantities >=5 that are multiples of 5, by FO."""
    rows = []
    for f, g in en.groupby(fo):
        vals = pd.concat([g[c] for c in qty]).dropna()
        vals = vals[(vals >= 5) & (vals != -99)]
        rows.append(dict(fo_id=f, heap5=float((vals % 5 == 0).mean()) if len(vals) >= 15 else np.nan, n_qty=len(vals)))
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ FO scoring (permutation inference)
def residualise(d, metric, covars, fe):
    x = d.dropna(subset=[metric])
    res = ols(x[metric].to_numpy(), design(x, covars, fe))
    r = pd.Series(np.nan, index=d.index)
    r.loc[x.index] = res["resid"]
    return r


def perm_labels(fo_codes, grp_codes, B, rng):
    """B label vectors: FO labels shuffled WITHIN location (keeps FO-by-location mix under the null)."""
    n = len(fo_codes)
    ord0 = np.argsort(grp_codes, kind="stable")
    out = np.empty((B, n), dtype=np.int16)
    for b in range(B):
        ordp = np.lexsort((rng.random(n), grp_codes))
        row = np.empty(n, dtype=np.int16)
        row[ord0] = fo_codes[ordp]
        out[b] = row
    return out


def fo_means(labels, R, M, F):
    """labels (n,), R (n,m) residuals with NaN->0, M (n,m) valid mask -> (F,m) means and counts."""
    cnt = np.stack([np.bincount(labels, weights=M[:, j], minlength=F) for j in range(M.shape[1])], 1)
    sm = np.stack([np.bincount(labels, weights=R[:, j], minlength=F) for j in range(R.shape[1])], 1)
    with np.errstate(invalid="ignore", divide="ignore"):
        return sm / cnt, cnt


def score_fos(df, covars, fe, metric_cols):
    """Permutation test of every FO against the null of exchangeable FOs within location, per metric."""
    rng = np.random.default_rng(THRESH["seed"])
    fos = np.array(sorted(df.fo_id.dropna().unique()))
    F = len(fos)
    fo_codes = pd.Categorical(df.fo_id, categories=fos).codes.astype(np.int16)
    grp = pd.factorize(df.location)[0]
    B = THRESH["n_perm"]
    labs = perm_labels(fo_codes, grp, B, rng)

    use, R, M, notes = [], [], [], {}
    for mc in metric_cols:
        v = df[mc]
        prev = float(v.mean())
        if v.notna().sum() == 0 or v.std() == 0:
            notes[mc] = "no variation (rule never fires)" if prev == 0 else "constant"; continue
        if mc == "dup_vector" and prev > THRESH["dup_max_baseline"]:
            notes[mc] = f"uninformative: {prev:.0%} of interviews share a vector by chance"; continue
        r = residualise(df, mc, covars, fe)
        use.append(mc); R.append(r.fillna(0).to_numpy()); M.append(r.notna().to_numpy().astype(float))
    R, M = np.stack(R, 1), np.stack(M, 1)
    obs, cnt = fo_means(fo_codes, R, M, F)
    ref = np.empty((B, F, len(use)))
    for b in range(B):
        ref[b], _ = fo_means(labs[b].astype(np.int64), R, M, F)
    sd_ref = np.nanstd(ref, axis=0)
    p = (1 + (np.abs(ref) >= np.abs(obs)[None]).sum(0)) / (B + 1)

    rows = []
    for j, mc in enumerate(use):
        sd_r = np.nanstd(R[M[:, j] == 1, j])
        q = bh(p[:, j])
        for i, f in enumerate(fos):
            n_f = int(cnt[i, j])
            eff = obs[i, j] / sd_r
            bad = METRICS[mc]["bad"]
            conc = (np.sign(obs[i, j]) == bad) and abs(eff) >= THRESH["min_effect_sd"] and n_f >= 5
            rows.append(dict(fo_id=f, metric=mc, n=n_f, resid_mean=obs[i, j], effect_sd=eff,
                             z=obs[i, j] / sd_ref[i, j], p=p[i, j], q=q[i],
                             concerning=bool(conc and q[i] < THRESH["q_amber"]),
                             red=bool(conc and q[i] < THRESH["q_red"])))
    sc = pd.DataFrame(rows)
    sc["family"] = sc.metric.map(FAMILY)
    # omnibus: between-FO sum of squares vs permutation null
    omni = []
    for j, mc in enumerate(use):
        ss = lambda m_, c_: np.nansum(c_[:, j] * m_[:, j] ** 2)
        s_obs = ss(obs, cnt)
        s_ref = np.array([ss(ref[b], cnt) for b in range(B)])  # approx: counts held at observed
        omni.append(dict(metric=mc, omnibus_p=(1 + (s_ref >= s_obs).sum()) / (B + 1)))
    return sc, pd.DataFrame(omni), notes, (labs, R, M, obs, ref, fos, use, p, cnt)


def tier_from(sc, n_by_fo):
    g = sc.groupby(["fo_id", "family"]).agg(c=("concerning", "max"), r=("red", "max")).reset_index()
    t = g.groupby("fo_id").agg(n_fam=("c", "sum"), n_fam_red=("r", "sum")).reset_index()
    t["n"] = t.fo_id.map(n_by_fo)

    def lab(r):
        if r.n < THRESH["min_n"]:
            return "Insufficient data"
        if r.n_fam_red >= 2 or r.n_fam >= 3:
            return "Red - back-check now"
        if r.n_fam >= 1:
            return "Amber - review"
        return "Green"
    t["tier"] = t.apply(lab, axis=1)
    return t


def null_calibration(pack, n_by_fo, n_pseudo=300):
    """How often would the tiering rule flag FOs if FO labels were pure noise? Uses permuted datasets
    as pseudo-observed data, scored against the same reference distribution."""
    labs, R, M, obs, ref, fos, use, p_obs, cnt = pack
    B = ref.shape[0]
    abs_ref_sorted = np.sort(np.abs(ref), axis=0)
    sd_r = [np.nanstd(R[M[:, j] == 1, j]) for j in range(len(use))]
    rows = []
    for b in range(n_pseudo):
        o = ref[b]
        recs = []
        for j, mc in enumerate(use):
            for i in range(len(fos)):
                ge = B - np.searchsorted(abs_ref_sorted[:, i, j], abs(o[i, j]), side="left")
                recs.append((i, mc, (1 + ge) / (B + 1), o[i, j]))
        d = pd.DataFrame(recs, columns=["i", "metric", "p", "val"])
        out = []
        for mc, g in d.groupby("metric"):
            j = use.index(mc)
            q = bh(g.p.to_numpy())
            for (_, r_), qq in zip(g.iterrows(), q):
                eff = r_.val / sd_r[j]
                conc = (np.sign(r_.val) == METRICS[mc]["bad"]) and abs(eff) >= THRESH["min_effect_sd"]
                out.append(dict(fo_id=fos[int(r_.i)], metric=mc, concerning=bool(conc and qq < THRESH["q_amber"]),
                                red=bool(conc and qq < THRESH["q_red"])))
        o = pd.DataFrame(out); o["family"] = o.metric.map(FAMILY)
        tt = tier_from(o, n_by_fo)
        rows.append(dict(b=b, red=(tt.tier.str.startswith("Red")).sum(), amber=(tt.tier.str.startswith("Amber")).sum()))
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ dataset runners
def run_pad2():
    panel = pd.read_csv(PROC / "pad2_panel.csv")
    en = pd.read_csv(RAW / "PAD2" / "PAD2_endline_raw.csv")
    id_cols = ["respid", "a3_foname"]
    items, cat, qty, multi = classify_items(en, id_cols, ["h11_lime_quantity_sr2017"], ["e16_lime_lr2017_agrovet_id"])
    gates = ["e2_plant_lr", "e4_chemical_fert", "e12_heard_lime"]
    return panel, en, items, cat, qty, multi, gates, "a3_foname", "PAD2"


def run_pad1():
    panel = pd.read_csv(PROC / "pad1_panel.csv")
    en = pd.read_csv(RAW / "PAD1" / "PAD1_endline_raw.csv")
    id_cols = ["respid", "a3_fo_id"]
    qty_named = [c for c in en.columns if c.endswith("_total_amount") or c.endswith("_total_amt") or c == "d15_lime_quantity"]
    skip = ["complete_survey2", "d5_other_total_amount"]  # completion flag is metadata; 'other' amount is free-form
    items, cat, qty, multi = classify_items(en, id_cols, qty_named, skip)
    gates = ["d2_plant_lr", "d4_chemical_fert", "d6_heard_lime"]
    return panel, en, items, cat, qty, multi, gates, "a3_fo_id", "PAD1"


def pad1_violations(en):
    v = pd.DataFrame({"respid": en.respid})
    v["a"] = ((en.d2_plant_lr == 0) & en.d4_chemical_fert.notna()).astype(float)
    v["b"] = ((en.d4_chemical_fert == 0) & en.d5_chemical_fert_type.notna()).astype(float)
    v["c"] = ((en.d6_heard_lime == 0) & (en.d8_applied_lime == 1)).astype(float)
    v["d"] = ((en.d8_applied_lime == 0) & (en.d9_apply_lime_lr == 1) & False).astype(float)
    v["e"] = ((en.d2_plant_lr == 1) & en.d4_chemical_fert.isna()).astype(float)
    v["logic_viol"] = (v[["a", "b", "c", "e"]].sum(axis=1) > 0).astype(float)
    return v[["respid", "logic_viol"]]


def main(which):
    runner = {"PAD2": run_pad2, "PAD1": run_pad1}[which]
    t0 = time.time()
    panel, en, items, cat, qty, multi, gates, fo_col, tag = runner()
    m = interview_metrics(en, items, cat, qty, multi, gates)
    if tag == "PAD2":
        m = m.merge(panel[["respid", "n_logic_viol"]], on="respid")
        m["logic_viol"] = (m.n_logic_viol > 0).astype(float)
        m = m.drop(columns="n_logic_viol")
    else:
        m = m.merge(pad1_violations(en), on="respid")
    base_cols = ["respid", "fo_id", "arm", "female_b", "age_b", "ever_used_lime_b", "size_shamba_b", "english_b",
                 "location", "redeemed_lime", "used_lime_lr2017", "rep_lime_no_admin"]
    d = m.merge(panel[base_cols], on="respid", how="left")
    # admin mismatch: survey reports NO lime use in LR2017 although coupon records show lime was bought
    svy = "used_lime_lr2017" if tag == "PAD2" else "used_lime_sr2016"   # season must match the coupon record
    d = d.merge(panel[["respid", svy]].rename(columns={svy: "svy_lime"}), on="respid", how="left")
    d["admin_mismatch"] = np.where((d.redeemed_lime == 1) & d.svy_lime.notna(), (d.svy_lime == 0).astype(float), np.nan)
    for a in d.arm.dropna().unique():
        if a != "Control":
            d[f"arm_{a}"] = (d.arm == a).astype(float)
    arm_cols = [c for c in d.columns if c.startswith("arm_")]
    covars = arm_cols + ["female_b", "age_b", "ever_used_lime_b", "size_shamba_b", "english_b"]
    d["age_b"] = d.age_b.fillna(d.age_b.median())
    d["size_shamba_b"] = d.size_shamba_b.fillna(d.size_shamba_b.median())

    metric_cols = list(METRICS)
    sc, omni, notes, pack = score_fos(d, covars, ["location"], metric_cols)
    n_by_fo = d.groupby("fo_id").size()
    tr = tier_from(sc, n_by_fo)
    nullc = null_calibration(pack, n_by_fo)
    nullc.to_csv(OUT_T / f"hfc_null_calibration_{tag.lower()}.csv", index=False)
    omni["note"] = ""
    pd.DataFrame([dict(metric=k, omnibus_p=np.nan, note=v) for k, v in notes.items()]).pipe(
        lambda x: pd.concat([omni, x], ignore_index=True)).to_csv(OUT_T / f"hfc_omnibus_{tag.lower()}.csv", index=False)
    print("metric notes:", notes)
    print(omni.round(4).to_string(index=False))
    print(f"NULL calibration: mean Red={nullc.red.mean():.2f}  P(>=1 Red)={(nullc.red>=1).mean():.2f}  "
          f"mean Amber={nullc.amber.mean():.2f}  P(>=1 Amber/Red)={((nullc.red+nullc.amber)>=1).mean():.2f}")

    fo_tab = (d.groupby("fo_id").agg(n_interviews=("respid", "size"),
                                     path_len=("path_len", "mean"), dk_rate=("dk_rate", "mean"),
                                     straightline=("straightline", "mean"), gate_no=("gate_no", "mean"),
                                     logic_viol=("logic_viol", "mean"), dup_vector=("dup_vector", "mean"),
                                     admin_mismatch=("admin_mismatch", "mean")).reset_index())
    if tag == "PAD1" and qty:
        h = heaping_by_fo(en.assign(fo_id=en[fo_col].map(lambda v: f"P1-{int(v):02d}")), qty, "fo_id")
        fo_tab = fo_tab.merge(h, on="fo_id", how="left")
    fo_tab = fo_tab.merge(tr.drop(columns="n"), on="fo_id")
    fo_tab["n_flags"] = fo_tab.n_fam
    sc.to_csv(OUT_T / f"hfc_fo_tests_{tag.lower()}.csv", index=False)
    fo_tab.to_csv(OUT_T / f"hfc_fo_scorecard_{tag.lower()}.csv", index=False)

    # item profile
    prof = pd.DataFrame({
        "item": items,
        "n_answered": [int(en[c].notna().sum()) for c in items],
        "miss_share": [float(en[c].isna().mean()) for c in items],
        "dk_share_of_answered": [
            float((en[c].isin(DK_CODES)).sum() / max(en[c].notna().sum(), 1)) if c in cat else
            float(en[c].map(is_dk_multi).sum() / max(en[c].notna().sum(), 1)) if c in multi else
            float((en[c] == -99).sum() / max(en[c].notna().sum(), 1)) for c in items],
        "type": ["categorical" if c in cat else "multi-select" if c in multi else "quantity" for c in items]})
    prof.to_csv(OUT_T / f"hfc_item_profile_{tag.lower()}.csv", index=False)

    # global check summary
    rows = [
        ("Interviews in endline file", len(en)),
        ("Distinct field officers", d.fo_id.nunique()),
        ("Median interviews per FO", int(d.groupby("fo_id").size().median())),
        ("Share with >=1 skip-logic/consistency violation", float(d.logic_viol.mean())),
        ("Share exact-duplicate answer vector (path>=10)", float(d.dup_vector.mean())),
        ("Share straight-lining (>=6 yes/no items identical)", float(d.straightline.mean())),
        ("Mean don't-know share of categorical answers", float(d.dk_rate.mean())),
        ("Survey 'no lime' but coupon bought (share of redeemers)", float(d.admin_mismatch.mean())),
        ("FOs Red / Amber / Green / Insufficient", " / ".join(str((tr.tier.str.startswith(k)).sum()) for k in ["Red", "Amber", "Green", "Insuff"])),
        ("Runtime (s)", round(time.time() - t0, 2)),
    ]
    pd.DataFrame(rows, columns=["check", "value"]).to_csv(OUT_T / f"hfc_summary_{tag.lower()}.csv", index=False)
    d.to_csv(PROC / f"{tag.lower()}_interview_metrics.csv", index=False)
    print(f"\n===== {tag}: {len(en)} interviews, {d.fo_id.nunique()} FOs  ({time.time()-t0:.1f}s)")
    for r in rows:
        print(f"  {r[0]:62s} {r[1]}")
    print(fo_tab.sort_values(["n_fam_red","n_fam"], ascending=False).head(8).round(3).to_string(index=False))
    return d, sc, fo_tab


if __name__ == "__main__":
    for w in ("PAD2", "PAD1"):
        main(w)
