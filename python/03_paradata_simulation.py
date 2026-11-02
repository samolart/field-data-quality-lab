"""03 - SIMULATED paradata: stress-testing the HFC rules with planted, known problems.

*** Everything produced here is SYNTHETIC. File names start with SIM_ and every row has is_synthetic=1. ***
Real survey files in this project carry no timestamps, so durations/call times are simulated; only the
interview counts per field officer (FO) mirror the real PAD2 workload. Purpose: measure how fast and how
reliably standard HFC rules catch specific problems, and what they wrongly flag.

Planted FOs (ground truth is stored in `planted`):
  A  shortcutter  - interviews 40% shorter AND 70% fewer don't-knows (the application question's scenario)
  B  fabricator   - 12% of interviews are copy-paste: 2-4 min, duplicate answer vector, back-to-back bursts
  C  off-hours    - 30% of calls start before 07:00 or after 20:00
  D  drifter      - starts normal, interviews get steadily shorter (up to -35%)
  E  fast-but-honest - 25% faster throughout, normal DK / answers  (the false-positive trap)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import numpy as np
import pandas as pd
from scipy import stats
from config import SYN, OUT_T, SEED, PROC
from pxdlib import bh

DAYS = 30
DK_BASE = 0.04           # assumed baseline don't-know rate for this synthetic instrument (sensitivity-tested below)
PLANTED = {"SIM-03": "A_shortcutter", "SIM-08": "B_fabricator", "SIM-14": "C_off_hours",
           "SIM-19": "D_drifter", "SIM-22": "E_fast_but_honest"}
R = dict(z_alpha=0.05, min_n=20, shorter=0.80, dk_p=0.01, dk_ratio=0.5, dup_n=3, off_p=1e-3, off_share=0.10,
         imp_p=1e-3, imp_share=0.05, drift_t=-3.0, drift_drop=0.20)


# ------------------------------------------------------------------ generator
def simulate(loads, rng, dk_base=DK_BASE, planted=PLANTED, path_pool=None):
    rows = []
    for k, n in enumerate(loads, start=1):
        fo = f"SIM-{k:02d}"
        kind = planted.get(fo, "clean")
        speed = np.exp(rng.normal(0, 0.08))
        day = np.sort(rng.integers(1, DAYS + 1, n))
        L = rng.choice(path_pool, n) if path_pool is not None else rng.integers(6, 22, n)
        base = (4.0 + 1.45 * L) * speed * np.exp(rng.normal(0, 0.22, n))
        n_cat = np.maximum((0.8 * L).round().astype(int), 1)
        dkp = np.full(n, dk_base)
        if kind == "A_shortcutter":
            base *= 0.60; dkp *= 0.30
        if kind == "D_drifter":
            base *= 1 - 0.35 * (day - 1) / (DAYS - 1)
        if kind == "E_fast_but_honest":
            base *= 0.75
        fab = np.zeros(n, bool)
        if kind == "B_fabricator":
            fab = rng.random(n) < 0.12
            base[fab] = rng.uniform(2.0, 4.0, fab.sum())
        dk = rng.binomial(n_cat, dkp)
        sig = rng.integers(0, 2**62, n)
        # start times: sequential within day
        start = np.zeros(n)
        for d in np.unique(day):
            ix = np.where(day == d)[0]
            t = 8 * 60 + rng.uniform(0, 60)
            for j in ix:
                start[j] = t
                t += base[j] + 1.5 + rng.exponential(6.5)   # >=1.5 min to dial/log the next case
        if kind == "B_fabricator":
            for j in np.where(fab)[0]:        # back-to-back bursts with the previous interview's answers
                if j > 0:
                    sig[j] = sig[j - 1]
                    start[j] = start[j - 1] + base[j - 1] + rng.uniform(0.1, 0.8)
        if kind == "C_off_hours":
            off = rng.random(n) < 0.30
            start[off] = np.where(rng.random(off.sum()) < 0.5, rng.uniform(5 * 60, 7 * 60 - 1, off.sum()),
                                  rng.uniform(20 * 60 + 15, 23 * 60, off.sum()))
        rows.append(pd.DataFrame(dict(fo_id=fo, planted=kind, day=day, start_min=start, duration_min=base,
                                      path_len=L, n_cat=n_cat, dk_n=dk, ans_sig=sig, fabricated=fab.astype(int))))
    d = pd.concat(rows, ignore_index=True)
    d["is_synthetic"] = 1
    d["interview_id"] = np.arange(1, len(d) + 1)
    d["end_min"] = d.start_min + d.duration_min
    d["hour"] = (d.start_min // 60).astype(int)
    d["off_hours"] = ((d.start_min < 7 * 60) | (d.start_min >= 20 * 60)).astype(int)
    d = d.sort_values(["fo_id", "day", "start_min"]).reset_index(drop=True)
    prev_end = d.groupby(["fo_id", "day"]).end_min.shift(1)
    d["gap_prev"] = d.start_min - prev_end
    d["impossible"] = ((d.gap_prev < 1.0) | (d.duration_min < 5.0)).astype(int)
    d["log_dur"] = np.log(d.duration_min)
    return d


# ------------------------------------------------------------------ rules
def evaluate(d: pd.DataFrame) -> pd.DataFrame:
    """Apply every HFC rule to the data supplied (i.e. to-date). One row per FO."""
    fos = sorted(d.fo_id.unique())
    out = []
    pool_dk, pool_n = d.dk_n.sum(), d.n_cat.sum()
    sig_counts = d.ans_sig.value_counts()
    p_speed, eff = {}, {}
    for f in fos:
        a, b = d.loc[d.fo_id == f, "log_dur"], d.loc[d.fo_id != f, "log_dur"]
        if len(a) < R["min_n"]:
            p_speed[f], eff[f] = 1.0, 0.0; continue
        t, p2 = stats.ttest_ind(a, b, equal_var=False)
        p_speed[f] = p2 / 2 if t < 0 else 1 - p2 / 2
        eff[f] = float(np.exp(a.mean() - b.mean()))
    q = dict(zip(fos, bh(np.array([p_speed[f] for f in fos]))))
    for f in fos:
        g = d[d.fo_id == f]
        n = len(g)
        o = {"fo_id": f, "n": n}
        o["R1_speed"] = bool(n >= R["min_n"] and q[f] < R["z_alpha"] and eff[f] <= R["shorter"])
        o["speed_ratio"] = eff[f]
        k, N = int(g.dk_n.sum()), int(g.n_cat.sum())
        p0 = (pool_dk - k) / max(pool_n - N, 1)
        o["dk_rate"] = k / max(N, 1)
        o["R2_dk_deficit"] = bool(N * p0 >= 5 and stats.binomtest(k, N, max(p0, 1e-9), alternative="less").pvalue < R["dk_p"]
                                   and o["dk_rate"] < R["dk_ratio"] * p0)
        o["dup_n"] = int((sig_counts.reindex(g.ans_sig).to_numpy() > 1).sum())
        o["R3_duplicates"] = o["dup_n"] >= R["dup_n"]
        o["off_share"] = float(g.off_hours.mean())
        o["R4_off_hours"] = bool(n >= R["min_n"] and g.off_hours.mean() > R["off_share"] and
                                 stats.binomtest(int(g.off_hours.sum()), n, 0.01, alternative="greater").pvalue < R["off_p"])
        o["imp_share"] = float(g.impossible.mean())
        o["R5_impossible"] = bool(n >= R["min_n"] and g.impossible.mean() > R["imp_share"] and
                                  stats.binomtest(int(g.impossible.sum()), n, 0.005, alternative="greater").pvalue < R["imp_p"])
        if n >= 40 and g.day.nunique() > 5:
            sl = stats.linregress(g.day, g.log_dur)
            o["drift_t"] = sl.slope / sl.stderr if sl.stderr > 0 else 0
            o["drift_drop"] = 1 - float(np.exp(sl.slope * (g.day.max() - g.day.min())))
            o["R6_drift"] = bool(o["drift_t"] < R["drift_t"] and o["drift_drop"] > R["drift_drop"])
        else:
            o["drift_t"], o["drift_drop"], o["R6_drift"] = 0.0, 0.0, False
        rules = ["R1_speed", "R2_dk_deficit", "R3_duplicates", "R4_off_hours", "R5_impossible", "R6_drift"]
        o["n_rules"] = int(sum(o[r] for r in rules))
        # decision logic: corroboration beats a single signal
        o["tier"] = ("Red" if (o["R3_duplicates"] or o["R5_impossible"] or o["R4_off_hours"] or (o["R1_speed"] and (o["R2_dk_deficit"] or o["R6_drift"])))
                     else "Amber" if o["n_rules"] >= 1 else "Green")
        out.append(o)
    return pd.DataFrame(out)


def daily_monitor(sim, checkpoints=range(3, DAYS + 1)):
    rows = []
    for dd in checkpoints:
        e = evaluate(sim[sim.day <= dd]); e["day"] = dd; rows.append(e)
    return pd.concat(rows, ignore_index=True)


# ------------------------------------------------------------------ Monte Carlo: power & false positives
def mc_power(loads, path_pool, reps=300, seed=SEED):
    """One shortcutter (FO 3) among clean FOs; sweep how much shorter and the baseline DK rate."""
    rng = np.random.default_rng(seed)
    grid = []
    fo_names = [f"SIM-{k:02d}" for k in range(1, len(loads) + 1)]
    n_arr = np.array(loads)
    for dk_base in (0.0075, 0.02, 0.04):
        for s in (0.0, 0.1, 0.2, 0.3, 0.4, 0.5):
            hit = dict(speed=0, dk=0, both=0, naive=0, red=0)
            fp = dict(speed=0, dk=0, naive=0, red=0); n_clean = 0
            for _ in range(reps):
                logd, dkn, ncat = [], [], []
                for k, n in enumerate(loads):
                    L = rng.choice(path_pool, n)
                    mu = np.log(4.0 + 1.45 * L) + rng.normal(0, 0.08) + rng.normal(0, 0.22, n)
                    nc = np.maximum((0.8 * L).round().astype(int), 1)
                    dp = dk_base
                    if k == 2:
                        mu = mu + np.log(1 - s); dp = dk_base * (1 - 0.7 * min(s / 0.4, 1))   # DK deficit scales with shortcutting
                    logd.append(mu); ncat.append(nc); dkn.append(rng.binomial(nc, dp))
                alld = np.concatenate(logd); fid = np.repeat(np.arange(len(loads)), loads)
                ps, eff, naive = np.ones(len(loads)), np.ones(len(loads)), np.zeros(len(loads), bool)
                for f in range(len(loads)):
                    a, b = alld[fid == f], alld[fid != f]
                    t, p2 = stats.ttest_ind(a, b, equal_var=False)
                    ps[f] = p2 / 2 if t < 0 else 1 - p2 / 2
                    eff[f] = np.exp(a.mean() - b.mean())
                    naive[f] = (t < -2)
                q = bh(ps)
                speed = (q < R["z_alpha"]) & (eff <= R["shorter"])
                tot_dk, tot_n = sum(x.sum() for x in dkn), sum(x.sum() for x in ncat)
                dkf = np.zeros(len(loads), bool)
                for f in range(len(loads)):
                    kk, NN = int(dkn[f].sum()), int(ncat[f].sum())
                    p0 = (tot_dk - kk) / (tot_n - NN)
                    if NN * p0 >= 5:
                        dkf[f] = (stats.binom.cdf(kk, NN, p0) < R["dk_p"]) and (kk / NN < R["dk_ratio"] * p0)
                red = speed & dkf
                tgt = 2
                hit["speed"] += speed[tgt]; hit["dk"] += dkf[tgt]; hit["naive"] += naive[tgt]; hit["red"] += red[tgt]
                m = np.ones(len(loads), bool); m[tgt] = False
                fp["speed"] += speed[m].sum(); fp["dk"] += dkf[m].sum(); fp["naive"] += naive[m].sum(); fp["red"] += red[m].sum()
                n_clean += m.sum()
            for rule in ("naive", "speed", "dk", "red"):
                grid.append(dict(dk_base=dk_base, shorter=s, rule=rule, power=hit[rule] / reps, false_pos=fp[rule] / n_clean))
    return pd.DataFrame(grid)


def mc_delay(loads, path_pool, reps=200, seed=SEED + 1, s=0.4, dk_base=0.04):
    """Days until a 40%-shorter shortcutter is flagged by the speed rule, running the monitor daily."""
    rng = np.random.default_rng(seed)
    res = []
    for r in range(reps):
        planted = {"SIM-03": "A_shortcutter"}
        sim = simulate(loads, rng, dk_base, planted, path_pool)
        flagged_day, flag2, fp_day, fp2 = None, None, 0, 0
        prev_a, prev_fp = False, set()
        for dd in range(3, DAYS + 1):
            e = evaluate(sim[sim.day <= dd])
            a = bool(e[e.fo_id == "SIM-03"].iloc[0].R1_speed)
            n_now = int(e[e.fo_id == "SIM-03"].iloc[0].n)
            if flagged_day is None and a:
                flagged_day, n_at = dd, n_now
            if flag2 is None and a and prev_a:
                flag2, n_at2 = dd, n_now
            fps = set(e[(e.fo_id != "SIM-03") & e.R1_speed].fo_id)
            fp_day += int(len(fps) > 0)
            fp2 += int(len(fps & prev_fp) > 0)           # same clean FO flagged two days running
            prev_a, prev_fp = a, fps
        res.append(dict(rep=r, detected=flagged_day is not None, day=flagged_day if flagged_day else np.nan,
                        interviews=n_at if flagged_day else np.nan, days_with_false_flag=fp_day,
                        detected_persist=flag2 is not None, day_persist=flag2 if flag2 else np.nan,
                        interviews_persist=n_at2 if flag2 else np.nan, days_with_false_flag_persist=fp2))
    return pd.DataFrame(res)


def assign_planted_loads(loads):
    """Give each planted FO a workload close to a realistic target; the rest keep the remaining real loads."""
    targets = {3: 200, 8: 200, 14: 120, 19: 240, 22: 290}
    pool = list(loads); out = [None] * len(loads)
    for pos, tgt in targets.items():
        j = int(np.argmin([abs(x - tgt) for x in pool])); out[pos - 1] = pool.pop(j)
    for i in range(len(out)):
        if out[i] is None:
            out[i] = pool.pop(0)
    return out


if __name__ == "__main__":
    rng = np.random.default_rng(SEED)
    real = pd.read_csv(PROC / "pad2_interview_metrics.csv")
    loads = real.groupby("fo_id").size().tolist()   # real PAD2 workloads, anonymised order
    rng.shuffle(loads)
    loads = assign_planted_loads(loads)
    pool = real.path_len.to_numpy()
    sim = simulate(loads, rng, DK_BASE, PLANTED, pool)
    sim.to_csv(SYN / "SIM_paradata.csv", index=False)
    mon = daily_monitor(sim)
    mon.to_csv(OUT_T / "sim_daily_monitor.csv", index=False)
    final = mon[mon.day == DAYS]
    final.to_csv(OUT_T / "sim_final_scorecard.csv", index=False)

    # first-detection day per planted FO and rule
    fd = []
    for fo, kind in PLANTED.items():
        sub = mon[mon.fo_id == fo].sort_values("day")
        row = dict(fo_id=fo, planted=kind)
        for r_ in ["R1_speed", "R2_dk_deficit", "R3_duplicates", "R4_off_hours", "R5_impossible", "R6_drift"]:
            hit = sub[sub[r_]]
            row[r_ + "_first_day"] = int(hit.day.min()) if len(hit) else None
        rt = sub[sub.tier == "Red"]; row["red_first_day"] = int(rt.day.min()) if len(rt) else None
        at = sub[sub.tier != "Green"]; row["any_flag_first_day"] = int(at.day.min()) if len(at) else None
        fd.append(row)
    pd.DataFrame(fd).to_csv(OUT_T / "sim_first_detection.csv", index=False)
    clean = mon[~mon.fo_id.isin(PLANTED)]
    fpsum = clean.groupby("day").agg(false_red=("tier", lambda s: (s == "Red").sum()),
                                     false_amber=("tier", lambda s: (s == "Amber").sum())).reset_index()
    fpsum.to_csv(OUT_T / "sim_false_flags_by_day.csv", index=False)
    print("FINAL-DAY TIERS (planted):\n", final[final.fo_id.isin(PLANTED)][["fo_id", "n", "speed_ratio", "dk_rate", "dup_n", "off_share", "imp_share", "drift_drop", "n_rules", "tier"]].round(3).to_string(index=False))
    print("\nFIRST DETECTION:\n", pd.DataFrame(fd).to_string(index=False))
    print("\nFalse flags among 21 clean FOs at day 30: red=%d amber=%d" % (fpsum.false_red.iloc[-1], fpsum.false_amber.iloc[-1]))
    print("Max false-red over any day:", fpsum.false_red.max(), " max false-amber:", fpsum.false_amber.max())

    import time; t0 = time.time()
    grid = mc_power(loads, pool, reps=150)
    grid.to_csv(OUT_T / "sim_power_grid.csv", index=False)
    print(f"\nPOWER (dk_base=0.04, rule=speed/red/naive), {time.time()-t0:.0f}s")
    print(grid[(grid.dk_base == 0.04) & (grid.rule.isin(["speed", "red", "naive"]))].pivot_table(index="shorter", columns="rule", values=["power", "false_pos"]).round(3))
    t0 = time.time()
    dl = mc_delay(loads, pool, reps=100)
    dl.to_csv(OUT_T / "sim_detection_delay.csv", index=False)
    print(f"\nDELAY ({time.time()-t0:.0f}s): detected {dl.detected.mean():.2f}; median day {dl.day.median()}; median interviews {dl.interviews.median()}; false-flag days/28 (single) {dl.days_with_false_flag.mean():.2f}; persist: detected {dl.detected_persist.mean():.2f} median day {dl.day_persist.median()} median interviews {dl.interviews_persist.median()} false-flag days {dl.days_with_false_flag_persist.mean():.2f}")
