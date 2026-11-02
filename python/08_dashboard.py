"""08 - Build the self-contained HTML dashboard (no external libraries, works offline, no personal data)."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import numpy as np, pandas as pd
from config import OUT_T as T, ROOT

def clean(o):
    if isinstance(o, dict): return {k: clean(v) for k, v in o.items()}
    if isinstance(o, list): return [clean(v) for v in o]
    if isinstance(o, (np.floating, float)): return None if (o != o) else round(float(o), 5)
    if isinstance(o, (np.integer,)): return int(o)
    if isinstance(o, (np.bool_,)): return bool(o)
    return o

K = json.load(open(ROOT / "outputs" / "key_numbers.json"))
D = {"key": K, "fo": {}}
mets = {"pad2": ["path_len", "gate_no", "dk_rate", "straightline", "admin_mismatch"], "pad1": ["path_len", "gate_no", "dk_rate", "straightline", "admin_mismatch"]}
for tag in ("pad2", "pad1"):
    sc = pd.read_csv(T / f"hfc_fo_scorecard_{tag}.csv"); te = pd.read_csv(T / f"hfc_fo_tests_{tag}.csv")
    rows = []
    for r in sc.itertuples():
        m = {}
        for mm in mets[tag]:
            t = te[(te.fo_id == r.fo_id) & (te.metric == mm)]
            if len(t):
                t = t.iloc[0]; m[mm] = dict(eff=t.effect_sd, q=t.q, conc=bool(t.concerning), red=bool(t.red), raw=getattr(r, mm))
            else: m[mm] = dict(eff=None, q=None, conc=False, red=False, raw=getattr(r, mm))
        rows.append(dict(fo=r.fo_id, n=int(r.n_interviews), tier=r.tier, nfam=int(r.n_fam), nred=int(r.n_fam_red), m=m))
    D["fo"][tag] = rows
mon = pd.read_csv(T / "sim_daily_monitor.csv")
keep = ["fo_id", "day", "n", "tier", "speed_ratio", "dk_rate", "dup_n", "off_share", "imp_share", "drift_drop", "R1_speed", "R2_dk_deficit", "R3_duplicates", "R4_off_hours", "R5_impossible", "R6_drift"]
m2 = mon[keep].copy()
for c in [c for c in keep if c.startswith("R")]: m2[c] = m2[c].astype(int)
D["sim"] = dict(rows=m2.round(3).to_dict("records"), planted={"SIM-03": "Shortcutter: 40% shorter, 70% fewer don't-knows", "SIM-08": "Fabricator: 12% copy-paste, 2-4 min bursts",
                "SIM-14": "Off-hours: 30% of calls before 07:00 or after 20:00", "SIM-19": "Drifter: interviews get up to 35% shorter over the field period",
                "SIM-22": "Fast but honest: 25% faster, otherwise normal"}, power=pd.read_csv(T / "sim_power_grid.csv").round(4).to_dict("records"))
D["itt"] = {t: pd.read_csv(T / f"itt_{t}.csv").round(5).to_dict("records") for t in ("pad2", "pad1")}
D["rob"] = pd.read_csv(T / "robustness_fo_pad2.csv").round(5).to_dict("records")
D["het"] = pd.read_csv(T / "heterogeneity_pad2.csv").round(5).to_dict("records")
D["icc"] = pd.read_csv(T / "fo_icc_pad2.csv").round(5).to_dict("records")
html = (ROOT / "dashboard" / "template.html").read_text().replace("__DATA__", json.dumps(clean(D), separators=(",", ":")))
(ROOT / "dashboard" / "index.html").write_text(html)
print("dashboard bytes:", len(html))
