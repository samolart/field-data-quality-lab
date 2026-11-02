"""00 - Inventory every raw file in the full openICPSR package and benchmark generic QA checks at scale.

Usage: PXD_PACKAGE="/path/to/Replication Package 2024" python python/00_inventory_scale.py
(The PAD1/PAD2 files used by the main pipeline are a subset of this package.)
"""
import os, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import numpy as np, pandas as pd
from config import OUT_T

pkg = Path(os.environ.get("PXD_PACKAGE", ""))
if not (pkg / "data" / "raw").exists():
    sys.exit("Set PXD_PACKAGE to the unzipped 'Replication Package 2024' folder.")

rows = []
for f in sorted((pkg / "data" / "raw").glob("*/*.csv")):
    df = pd.read_csv(f, low_memory=False, encoding_errors="replace")
    rows.append(dict(study=f.parent.name, file=f.name, rows=len(df), cols=df.shape[1],
                     cells_nonmissing=int(df.notna().sum().sum()), size_mb=round(f.stat().st_size / 1e6, 2)))
inv = pd.DataFrame(rows)
inv.to_csv(OUT_T / "data_inventory.csv", index=False)
print(inv.sort_values("rows", ascending=False).head(8).to_string(index=False))
print("TOTAL files", len(inv), " rows", inv.rows.sum(), " non-missing cells", inv.cells_nonmissing.sum())

# --- generic QA suite on the largest file
f = pkg / "data" / "raw" / "OAF3" / "OAF3_admin_sample_raw.csv"
t0 = time.time()
df = pd.read_csv(f, low_memory=False)
t_read = time.time() - t0
t0 = time.time()
miss = df.isna().mean()
num = df.select_dtypes("number")
q1, q3 = num.quantile(.25), num.quantile(.75)
iqr = q3 - q1
out = ((num < q1 - 3 * iqr) | (num > q3 + 3 * iqr)).sum()
cands = [c for c in df.columns if df[c].is_unique and df[c].notna().all()]
idcol = cands[0] if cands else None          # a real key is unique and never missing
dups_id = int(df[idcol].duplicated().sum()) if idcol else "no unique key column in file"
dups_row = int(df.duplicated().sum())
const_cols = [c for c in df.columns if df[c].nunique(dropna=True) <= 1]
t_qa = time.time() - t0
res = pd.DataFrame([
    ("file", f.name), ("rows", len(df)), ("columns", df.shape[1]),
    ("cells (rows x cols)", len(df) * df.shape[1]), ("unique key column detected", idcol or "none"),
    ("duplicate IDs", dups_id), ("fully duplicated rows", dups_row),
    ("columns >50% missing", int((miss > .5).sum())), ("constant columns", len(const_cols)),
    ("numeric cols with >0 extreme outliers (3xIQR)", int((out > 0).sum())),
    ("seconds to read", round(t_read, 2)), ("seconds for generic QA suite", round(t_qa, 2))], columns=["metric", "value"])
res.to_csv(OUT_T / "scale_benchmark.csv", index=False)
print(res.to_string(index=False))
