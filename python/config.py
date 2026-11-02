"""Project paths and constants. Override the raw-data location with PXD_RAW if needed."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = Path(os.environ.get("PXD_RAW", ROOT / "data" / "raw"))
PROC = ROOT / "data" / "processed"
SYN = ROOT / "data" / "synthetic"
OUT_T = ROOT / "outputs" / "tables"
OUT_F = ROOT / "outputs" / "figures"
for p in (PROC, SYN, OUT_T, OUT_F):
    p.mkdir(parents=True, exist_ok=True)

SEED = 20261101  # one seed for every stochastic step -> fully reproducible

# Codes treated as "don't know / refused" in categorical items.
# 98 is "Other, specify" in these questionnaires and is NOT a don't-know.
DK_CODES = {99, -99, 999, -999}

# Arm labels. Raw PAD2 codes t1/t3 are ambiguous in the replication files (see docs/DATA_NOTES.md);
# we follow the cleaning code's *variable labels* and make the pooled any-SMS contrast the primary one.
PAD2_ARMS = {"control": "Control", "t1": "SMS+Call", "t2": "SMS+Call offer", "t3": "SMS"}
PAD1_ARMS = {"control": "Control", "general": "General SMS", "local": "Local SMS"}

# Palette used in every figure (colour-blind safe, validated for contrast)
PAL = {
    "ink": "#1f2933", "mute": "#6b7785", "grid": "#e4e7eb",
    "blue": "#1f6feb", "teal": "#0f9d8a", "amber": "#d98e04", "red": "#d1344b", "violet": "#7b5cd6",
}
