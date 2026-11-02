"""01 - Build analysis panels for PAD2 (primary) and PAD1 (replication) from the raw survey files.

Mirrors the logic of the original Stata cleaning code (1b/1c) but is re-implemented from scratch and
adds explicit, logged integrity checks (unique keys, merge diagnostics, skip-logic reconciliation).
Writes:  data/processed/pad2_panel.csv, pad1_panel.csv   (farmer-level, coded IDs only, no names/phones)
         outputs/tables/build_log.csv                     (every integrity check, pass/fail)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import numpy as np
import pandas as pd
from config import RAW, PROC, OUT_T, PAD2_ARMS, PAD1_ARMS
from pxdlib import has_token

LOG = []


def check(name, ok, detail=""):
    LOG.append(dict(check=name, passed=bool(ok), detail=detail))
    print(("PASS " if ok else "FAIL ") + name, detail)


def build_pad2() -> pd.DataFrame:
    d = RAW / "PAD2"
    bl = pd.read_csv(d / "PAD2_baseline_raw.csv")
    rz = pd.read_csv(d / "PAD2_randomization_raw.csv")
    rec = pd.read_csv(d / "PAD2_lime_rec.csv")
    en = pd.read_csv(d / "PAD2_endline_raw.csv")
    lc = pd.read_csv(d / "PAD2_lime_coupon_raw.csv")
    fc = pd.read_csv(d / "PAD2_fert_coupon_raw.csv")

    for nm, df in dict(baseline=bl, randomization=rz, lime_rec=rec, endline=en, lime_coupon=lc, fert_coupon=fc).items():
        check(f"PAD2 {nm}: respid unique", df.respid.is_unique, f"n={len(df)}")
    check("PAD2 randomization covers baseline", set(bl.respid) == set(rz.respid))
    check("PAD2 endline respondents all in baseline", set(en.respid) <= set(bl.respid))

    p = bl.merge(rz, on="respid", how="left").merge(rec, on="respid", how="left")
    p = p.merge(en, on="respid", how="left", indicator="_m")
    p["attrit"] = (p["_m"] == "left_only").astype(int)
    p["responded"] = 1 - p["attrit"]
    p = p.drop(columns="_m")
    p = p.merge(lc, on="respid", how="left").merge(fc, on="respid", how="left", suffixes=("", "_fc"))

    # ---- treatment
    p["arm"] = p.treat_overall.map(PAD2_ARMS)
    check("PAD2 all arms mapped", p.arm.notna().all(), str(p.arm.value_counts().to_dict()))
    p["treated"] = (p.treat_overall != "control").astype(int)

    # ---- baseline covariates (coding as in the original cleaning code; PAD2: gender==1 is female)
    p["age_b"] = p.b32_age
    p["female_b"] = (p.b33_gender == 1).astype(int)
    p["primary_b"] = (p.b31_education >= 8).astype(int)
    p["secondary_b"] = (p.b31_education >= 14).astype(int)
    p["english_b"] = (p.d2_language == 1).astype(int)
    p["size_shamba_b"] = p.b10_size_of_land
    p["ever_used_lime_b"] = (p.b28_lime_usage == 1).astype(int)
    p["used_anyfert_b"] = (p.b24_fertilizer_use == 1).astype(int)
    p["mention_lime_b"] = has_token(p.c1_acidity, 2).fillna(0)
    p["lime_recommended"] = (p.lime_bt_plant_ph_med != 0).astype(int)
    p["agrovet"] = p.agrovet_id
    p["location"] = p.location_PAD2
    p["fo_id"] = p.a3_foname.map(lambda v: f"P2-{int(v):02d}" if pd.notna(v) else np.nan)

    # ---- endline outcomes (survey-reported), NaN for non-respondents
    r = p.responded == 1
    p["heard_lime"] = p.e12_heard_lime.where(r)
    p["knows_lime"] = has_token(p.f4_soil_acidity_solution, 2).fillna(0).where(r)
    ul = p.e15_use_lime_lr2017.copy()
    ul[(p.e12_heard_lime == 0) | (p.e14_applied_lime == 0) | (p.e2_plant_lr == 0)] = 0
    p["used_lime_lr2017"] = ul.where(r)
    uu = has_token(p.e5_chemical_fert_type, 6)
    uu[(p.e2_plant_lr == 0) | (p.e4_chemical_fert == 0)] = 0
    p["used_urea_lr2017"] = uu.where(r)
    p["planted_maize_lr2017"] = p.e2_plant_lr.where(r)

    # ---- administrative (coupon) outcomes: observed for EVERYONE, immune to survey attrition
    p["redeemed_lime"] = (p.bags_lime_clean.fillna(0) > 0).astype(int)
    p["redeemed_fert"] = ((p[["redeemed_can_lb", "redeemed_urea_lb", "redeemed_mavuno_lb"]].fillna(0)).sum(axis=1) > 0).astype(int)
    p["redeemed_urea"] = p.redeemed_urea_lb.fillna(0).astype(int)

    # ---- cross-source consistency flags (survey vs. coupon records) ----
    p["rep_lime_no_admin"] = np.where(p.used_lime_lr2017 == 1, (p.redeemed_lime == 0).astype(float), np.nan)
    p["admin_lime_rep_no"] = np.where(p.redeemed_lime == 1, (p.used_lime_lr2017 == 0).astype(float), np.nan)
    p.loc[~r, ["rep_lime_no_admin", "admin_lime_rep_no"]] = np.nan

    # ---- logic / skip-pattern violations in the endline (computed on raw answers)
    v = pd.DataFrame(index=p.index)
    v["v_heard0_applied1"] = ((p.e12_heard_lime == 0) & (p.e14_applied_lime == 1)).astype(float)
    v["v_applied0_used1"] = ((p.e14_applied_lime == 0) & (p.e15_use_lime_lr2017 == 1)).astype(float)
    v["v_nofert_but_type"] = ((p.e4_chemical_fert == 0) & p.e5_chemical_fert_type.notna()).astype(float)
    v["v_fert_no_type"] = ((p.e4_chemical_fert == 1) & p.e5_chemical_fert_type.isna()).astype(float)
    v["v_plant0_but_fert"] = ((p.e2_plant_lr == 0) & p.e4_chemical_fert.notna()).astype(float)
    v["v_noplant_lime_qty"] = ((p.h1_plant_maize_sr2017 == 0) & p.h7_applied_lime_sr2017.notna()).astype(float)
    v["v_plant_miss_gate"] = ((p.e2_plant_lr == 1) & p.e4_chemical_fert.isna()).astype(float)
    v.loc[~r, :] = np.nan
    p = pd.concat([p, v], axis=1)
    p["n_logic_viol"] = v.sum(axis=1, min_count=1)

    # ---- integrity checks that must hold
    check("PAD2 endline N matches raw", int(p.responded.sum()) == len(en), f"{int(p.responded.sum())}")
    check("PAD2 responders have FO id", p.loc[r, "fo_id"].notna().all())
    check("PAD2 treated share ~75%", abs(p.treated.mean() - 0.75) < 0.01, f"{p.treated.mean():.3f}")
    check("PAD2 outcomes binary", all(set(p[c].dropna().unique()) <= {0.0, 1.0} for c in
          ["heard_lime", "knows_lime", "used_lime_lr2017", "used_urea_lr2017"]))
    return p


def build_pad1() -> pd.DataFrame:
    d = RAW / "PAD1"
    bl = pd.read_csv(d / "PAD1_baseline_raw.csv")
    tr = pd.read_csv(d / "PAD1_treatment_raw.csv")
    en = pd.read_csv(d / "PAD1_endline_raw.csv")
    cp = pd.read_csv(d / "PAD1_coupon2016_raw.csv").rename(columns={"farmer_id": "respid"})
    for nm, df in dict(baseline=bl, treatment=tr, endline=en, coupon=cp).items():
        check(f"PAD1 {nm}: respid unique", df.respid.is_unique, f"n={len(df)}")
    p = bl.merge(tr, on="respid", how="left").merge(en, on="respid", how="left", indicator="_m", suffixes=("", "_e"))
    p["attrit"] = (p["_m"] == "left_only").astype(int)
    p["responded"] = 1 - p["attrit"]
    p = p.drop(columns="_m").merge(cp, on="respid", how="left", suffixes=("", "_cp"))
    p["arm"] = p.treat_overall.map(PAD1_ARMS)
    p["treated"] = (p.treat_overall != "control").astype(int)
    p["age_b"] = p.b23_age
    p["female_b"] = (p.gender == 2).astype(int)         # NB: opposite coding to PAD2 (see DATA_NOTES)
    p["primary_b"] = (p.b22_education_level >= 8).astype(int)
    p["english_b"] = (p.d0_language == 1).astype(int)
    p["size_shamba_b"] = p.b7_size_shamba
    p["ever_used_lime_b"] = (p.b19_lime_used == 1).astype(int)
    p["location"] = p.area_id
    p["fo_id"] = p.a3_fo_id.map(lambda v: f"P1-{int(v):02d}" if pd.notna(v) else np.nan)
    r = p.responded == 1
    p["heard_lime"] = p.d6_heard_lime.where(r)
    p["used_lime_sr2016"] = p.used_lime_SR2016.where(r)
    ul = p.d9_apply_lime_lr.copy()
    ul[(p.d2_plant_lr == 0) | (p.d6_heard_lime == 0) | (p.d8_applied_lime == 0)] = 0
    p["used_lime_lr2017"] = ul.where(r)
    p["redeemed_lime"] = p.lime_redemption.fillna(0).astype(int)
    p["rep_lime_no_admin"] = np.where(p.used_lime_sr2016 == 1, (p.redeemed_lime == 0).astype(float), np.nan)
    check("PAD1 endline N matches raw", int(p.responded.sum()) == len(en), f"{int(p.responded.sum())}")
    check("PAD1 responders have FO id", p.loc[r, "fo_id"].notna().all())
    return p


if __name__ == "__main__":
    p2, p1 = build_pad2(), build_pad1()
    p2.to_csv(PROC / "pad2_panel.csv", index=False)
    p1.to_csv(PROC / "pad1_panel.csv", index=False)
    pd.DataFrame(LOG).to_csv(OUT_T / "build_log.csv", index=False)
    print(f"\nPAD2 panel {p2.shape}  PAD1 panel {p1.shape}")
    print("PAD2 attrition by arm:\n", p2.groupby("arm").responded.agg(["mean", "size"]).round(3))
    print("PAD1 attrition by arm:\n", p1.groupby("arm").responded.agg(["mean", "size"]).round(3))
    print("failed checks:", [l["check"] for l in LOG if not l["passed"]])
