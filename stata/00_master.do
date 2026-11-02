*===============================================================================
* 00_master.do  -  PxD Field Data Quality Lab (Stata implementation)
* Runs: clean -> HFC -> balance/attrition -> ITT -> field-officer effects -> compare with Python
*
* STATUS: authored alongside the Python pipeline; NOT executed in the build environment
*         (no Stata licence). Run on your machine and then run 99_compare_python.do:
*         it asserts that Stata reproduces the Python tables. Fix any difference before relying on it.
*===============================================================================
clear all
set more off
version 15
set seed 20261101

* ---- 1. paths (edit only this line) ----------------------------------------
global root "C:/path/to/pxd-field-data-quality-lab"        // <- CHANGE ME
global raw  "$root/data/raw"
global proc "$root/data/processed"
global out  "$root/outputs/stata"
cap mkdir "$out"
cap mkdir "$proc"

* ---- 2. covariate / strata globals (mirror python/04_impact.py) ------------
global ctrl_pad2 "female_b ever_used_lime_b age_b size_shamba_b english_b"
global bal_pad2  "age_b female_b primary_b secondary_b english_b mention_lime_b size_shamba_b ever_used_lime_b used_anyfert_b lime_recommended"

* ---- 3. pipeline -----------------------------------------------------------
do "$root/stata/01_clean_pad2.do"
do "$root/stata/02_hfc_enumerator.do"
do "$root/stata/03_balance_attrition.do"
do "$root/stata/04_itt.do"
do "$root/stata/05_fo_effects.do"
do "$root/stata/99_compare_python.do"
