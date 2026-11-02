#!/usr/bin/env bash
# Reproduce every table and figure. Needs data/raw/PAD1 and data/raw/PAD2 (see data/README.md).
set -euo pipefail
cd "$(dirname "$0")"
python python/01_build_panel.py
python python/02_hfc_real.py
python python/03_paradata_simulation.py     # ~5 min (Monte Carlo)
python python/04_impact.py
python python/06_build_xlsform.py
# optional, needs the full openICPSR package: PXD_PACKAGE="/path/to/Replication Package 2024" python python/00_inventory_scale.py
python python/05_figures.py
python python/07_key_numbers.py
python python/08_dashboard.py
python3 -I python/09_report.py
