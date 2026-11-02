*===============================================================================
* 01_clean_pad2.do - import, merge, validate, construct analysis variables (PAD2)
* Every step that could silently drop or duplicate observations is asserted.
*===============================================================================

* ---- helper: 1/0 if a space-separated multi-select answer contains a code ----
cap program drop hastok
program define hastok
    syntax varname , Token(string) Gen(name)
    cap confirm string variable `varlist'
    if _rc tostring `varlist', replace force
    gen `gen' = strpos(" " + `varlist' + " ", " `token' ") > 0 if trim(`varlist') != ""
end

* ---- import each raw file to a tempfile --------------------------------------
tempfile rz rec en lc fc

import delimited "$raw/PAD2/PAD2_randomization_raw.csv", clear varnames(1) case(preserve)
isid respid
save `rz'
import delimited "$raw/PAD2/PAD2_lime_rec.csv", clear varnames(1) case(preserve)
isid respid
save `rec'
import delimited "$raw/PAD2/PAD2_endline_raw.csv", clear varnames(1) case(preserve)
isid respid
save `en'
import delimited "$raw/PAD2/PAD2_lime_coupon_raw.csv", clear varnames(1) case(preserve)
isid respid
save `lc'
import delimited "$raw/PAD2/PAD2_fert_coupon_raw.csv", clear varnames(1) case(preserve)
isid respid
save `fc'

import delimited "$raw/PAD2/PAD2_baseline_raw.csv", clear varnames(1) case(preserve)
isid respid
count
assert r(N) == 5890                                  // baseline sample size

merge 1:1 respid using `rz',  keep(master match) nogen
merge 1:1 respid using `rec', keep(master match) nogen
merge 1:1 respid using `en',  keep(master match) gen(_m_end)
gen attrit = (_m_end == 1)
gen responded = 1 - attrit
drop _m_end
merge 1:1 respid using `lc',  keep(master match) nogen
merge 1:1 respid using `fc',  keep(master match) nogen
count if responded == 1
assert r(N) == 4933                                  // endline respondents

* ---- treatment arms (raw t1/t3 labelling is ambiguous: see docs/DATA_NOTES.md) ----
gen arm = ""
replace arm = "Control"        if treat_overall == "control"
replace arm = "SMS+Call"       if treat_overall == "t1"
replace arm = "SMS+Call offer" if treat_overall == "t2"
replace arm = "SMS"            if treat_overall == "t3"
assert arm != ""
gen treated = (treat_overall != "control")
sum treated
assert abs(r(mean) - 0.75) < 0.01
gen arm_SMS       = (arm == "SMS")
gen arm_SMSCalloffer = (arm == "SMS+Call offer")
gen arm_SMSCall   = (arm == "SMS+Call")

* ---- baseline covariates (PAD2: gender==1 is female; PAD1 uses the opposite) ----
gen age_b          = b32_age
gen female_b       = (b33_gender == 1)
gen primary_b      = (b31_education >= 8)
gen secondary_b    = (b31_education >= 14)
gen english_b      = (d2_language == 1)
gen size_shamba_b  = b10_size_of_land
gen ever_used_lime_b = (b28_lime_usage == 1)
gen used_anyfert_b = (b24_fertilizer_use == 1)
hastok c1_acidity, token(2) gen(mention_lime_b)
replace mention_lime_b = 0 if mention_lime_b == .
gen lime_recommended = (lime_bt_plant_ph_med != 0)
rename agrovet_id agrovet
rename location_PAD2 location
gen fo = a3_foname

* ---- survey outcomes (missing for non-respondents) ------------------------------
gen heard_lime = e12_heard_lime if responded == 1
hastok f4_soil_acidity_solution, token(2) gen(knows_lime)
replace knows_lime = 0 if knows_lime == . & responded == 1
replace knows_lime = . if responded == 0

gen used_lime_lr2017 = e15_use_lime_lr2017
replace used_lime_lr2017 = 0 if e12_heard_lime == 0 | e14_applied_lime == 0 | e2_plant_lr == 0
replace used_lime_lr2017 = . if responded == 0

hastok e5_chemical_fert_type, token(6) gen(used_urea_lr2017)
replace used_urea_lr2017 = 0 if e2_plant_lr == 0 | e4_chemical_fert == 0
replace used_urea_lr2017 = . if responded == 0

* ---- administrative outcomes: observed for the whole baseline sample ---------------
replace bags_lime_clean = 0 if bags_lime_clean == .
gen redeemed_lime = (bags_lime_clean > 0)
foreach v in redeemed_can_lb redeemed_urea_lb redeemed_mavuno_lb {
    replace `v' = 0 if `v' == .
}
gen redeemed_fert = (redeemed_can_lb + redeemed_urea_lb + redeemed_mavuno_lb > 0)

* ---- logic / skip-pattern violations in the endline ---------------------------------
gen v1 = (e12_heard_lime == 0 & e14_applied_lime == 1)
gen v2 = (e14_applied_lime == 0 & e15_use_lime_lr2017 == 1)
gen v3 = (e4_chemical_fert == 0 & trim(e5_chemical_fert_type) != "")
gen v4 = (e4_chemical_fert == 1 & trim(e5_chemical_fert_type) == "")
gen v5 = (e2_plant_lr == 0 & e4_chemical_fert < .)
gen v6 = (h1_plant_maize_sr2017 == 0 & h7_applied_lime_sr2017 < .)
gen v7 = (e2_plant_lr == 1 & e4_chemical_fert == .)
egen n_logic_viol = rowtotal(v1-v7) if responded == 1
gen logic_viol = (n_logic_viol > 0) if responded == 1

foreach v of varlist age_b size_shamba_b {
    qui sum `v', detail
    replace `v' = r(p50) if `v' == .
}
label data "PAD2 analysis panel (Stata build)"
save "$proc/pad2_panel_stata.dta", replace
di as result "01 done: " _N " baseline obs; " 4933 " endline respondents"
