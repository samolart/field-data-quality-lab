*===============================================================================
* 02_hfc_enumerator.do - automated high-frequency checks on the endline, by field officer
* Mirrors python/02_hfc_real.py. DIFFERENCE: Python uses permutation tests within location;
* here FO-vs-team tests are Welch t-tests on residuals (fast, runs daily inside a SurveyCTO workflow).
* Expect similar rankings, not identical p-values.
*===============================================================================
use "$proc/pad2_panel_stata.dta", clear
keep if responded == 1

* ---- item lists from the raw endline ---------------------------------------------
preserve
import delimited "$raw/PAD2/PAD2_endline_raw.csv", clear varnames(1) case(preserve)
ds respid a3_foname e16_lime_lr2017_agrovet_id, not
local items `r(varlist)'
local cat ""
local bin ""
foreach v of local items {
    cap confirm numeric variable `v'
    if !_rc {
        qui levelsof `v', local(lv)
        local k : word count `lv'
        if `k' <= 12 local cat `cat' `v'
        local isbin = 1
        foreach x of local lv {
            if !inlist(`x', 0, 1) local isbin = 0
        }
        if `isbin' & `k' >= 1 local bin `bin' `v'
    }
}
tempfile endraw
egen path_len = rownonmiss(`items'), strok
gen dk_n = 0
foreach v of local cat {
    replace dk_n = dk_n + inlist(`v', 99, -99)
}
egen cat_n = rownonmiss(`cat')
gen dk_rate = dk_n / cat_n if cat_n > 0
egen nbin = rownonmiss(`bin')
egen sdbin = rowsd(`bin')
gen straightline = (nbin >= 6 & sdbin == 0)
gen gate_no = (e2_plant_lr == 0) + (e4_chemical_fert == 0) + (e12_heard_lime == 0)
keep respid path_len dk_n cat_n dk_rate straightline gate_no
save `endraw'
restore
merge 1:1 respid using `endraw', keep(master match) nogen

* admin discordance: coupon says lime was bought, survey says it was not used
gen admin_mismatch = (used_lime_lr2017 == 0) if redeemed_lime == 1 & used_lime_lr2017 < .

* ---- residualise each metric on arm, baseline covariates, location FE -----------------
local metrics path_len gate_no dk_rate straightline admin_mismatch
foreach m of local metrics {
    qui areg `m' arm_SMS arm_SMSCalloffer arm_SMSCall female_b age_b ever_used_lime_b size_shamba_b english_b, absorb(location)
    predict r_`m' if e(sample), resid
}

* ---- FO vs rest-of-team test, BH across FOs within metric --------------------------------
tempname H
postfile `H' str16 metric double(fo n resid_mean z p) using "$out/hfc_fo_tests_stata.dta", replace
levelsof fo, local(fos)
foreach m of local metrics {
    foreach f of local fos {
        gen byte isf = (fo == `f')
        qui count if isf == 1 & r_`m' < .
        local n = r(N)
        if `n' >= 5 {
            qui ttest r_`m', by(isf) unequal
            post `H' ("`m'") (`f') (`n') (r(mu_2) - r(mu_1)) (-r(t)) (r(p))
        }
        drop isf
    }
}
postclose `H'

use "$out/hfc_fo_tests_stata.dta", clear
gen q = .
levelsof metric, local(ms)
foreach m of local ms {
    preserve
    keep if metric == "`m'"
    gsort -p
    gen mm = _N
    gen rank = mm - _n + 1
    gen qq = min(1, p * mm / rank)
    replace qq = min(qq, qq[_n-1]) if _n > 1
    keep metric fo qq
    tempfile qf
    save `qf'
    restore
    merge 1:1 metric fo using `qf', update replace nogen
}
replace q = qq if q == . & qq < .
cap drop qq
export delimited using "$out/hfc_fo_tests_stata.csv", replace
di as result "02 done: FO tests written to $out/hfc_fo_tests_stata.csv"
