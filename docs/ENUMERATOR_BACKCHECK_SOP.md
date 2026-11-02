# Enumerator performance: flag → back-check → action (SOP)

**Scenario this answers:** one enumerator's interviews are ~40% shorter than the team average with unusually few "don't know" answers.

| Step | Owner | Timing | What happens |
|---|---|---|---|
| 1. Verify the signal | Research Associate | same day | Re-run the HFC on the latest synced data. Compare against peers on the same questionnaire path, language and area. Rule out a data/sync problem and a legitimately fast, experienced enumerator (fast but normal DK, answers and timing patterns is *Amber*, not Red). |
| 2. Look at the paradata | RA | same day | Per-question timing (text audit), call times, gaps between interviews, duplicate answer signatures, share of skip-triggering "No" answers, recordings if consented. |
| 3. Brief the supervisor | RA → Field Manager | same day | Share the flag neutrally (a pattern, not an accusation). Agree a plan; no confrontation before verification. |
| 4. Back-check | Independent back-checker | within 48 h | Call a random sample (≥15 or 20% of the enumerator's completed interviews, whichever is larger), re-asking 8–10 stable, factual items; for flagged interviews verify that the call happened and the key answers match. Use the same sample size for two comparison enumerators. |
| 5. Decide | PI / Field Manager | on results | **Consistent** → no action, tighten the HFC, note the enumerator as fast. **Minor discrepancies** → retraining, shadowing for 2–3 days, closer monitoring. **Fabrication/serious shortcutting** → suspend, re-interview or drop the affected cases per protocol, document. |
| 6. Close the loop | RA | within a week | Log flag, evidence, action, outcome; add or tighten an automated check (e.g. duration-by-enumerator, DK deficit); rerun estimates excluding affected cases as a robustness check. |

**Back-check discrepancy rule of thumb.** >10% mismatches on key items in the back-checked sample escalates; 3–10% triggers retraining and a second back-check; <3% is within normal noise. (Calibrate to the study; this repository's simulation shows a 40% shortcut is flagged after ≈23 interviews.)
