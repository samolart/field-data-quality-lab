# Data

`raw/` and `processed/` are git-ignored. To reproduce:

1. Download the replication package from openICPSR project 186241 (free account): https://www.openicpsr.org/openicpsr/project/186241/version/V1/view
2. Copy `data/raw/PAD1/*.csv` and `data/raw/PAD2/*.csv` from the package into this folder's `raw/PAD1` and `raw/PAD2`.
3. Run `./run_all.sh`.

`synthetic/SIM_paradata.csv` is fully simulated (see `docs/DATA_NOTES.md`) and is committed.
