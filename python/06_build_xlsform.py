"""06 - Build and validate the SurveyCTO/ODK XLSForm for the LR2017 lime & fertiliser phone midline.

Based on the public PAD2 questionnaire (materials/PxD2). Quality controls live IN the instrument:
double entry of farmer ID, hard constraints with messages, consistent don't-know codes (99 / -99),
mutually-exclusive multi-select answers, skip logic mirrored from the paper form, and built-in paradata
(audit, durations, section timers, QA calculate fields feeding the HFC engine).

Validation here is STRUCTURAL (python, no external XLSForm compiler available in this build environment);
always upload to SurveyCTO's server (or run pyxform / ODK Validate) before field use. See docs/XLSFORM_TEST_PLAN.csv.
"""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from config import ROOT, OUT_T

S = []   # survey rows
def q(type_, name="", label="", **kw):
    S.append(dict(type=type_, name=name, label=label, **kw))
def begin(name, label, relevance="", kind="group", **kw): q(f"begin {kind}", name, label, relevance=relevance, **kw)
def end(kind="group"): q(f"end {kind}")

DK = "(. = -99 or ({lo} <= . and . <= {hi}))"
rng_ = lambda lo, hi: DK.format(lo=lo, hi=hi)

# ------------------------------------------------------------------ metadata
q("start", "start_time"); q("end", "end_time"); q("today", "today")
q("deviceid", "deviceid"); q("subscriberid", "subscriberid"); q("simserial", "simserial"); q("phonenumber", "enum_phone")
q("text audit", "audit", "", parameters="track-changes=true", publishable="no")
q("calculate", "form_version", "", calculation="'1.0.0'")

# ------------------------------------------------------------------ A: call status
begin("sec_a", "SECTION A - Call status")
q("select_one fo_list", "a3_fo", "A3. Field Officer name", required="yes")
q("integer", "a4_id", "A4. Farmer ID (from checklist)", required="yes", constraint=". >= 1000000 and . <= 9999999",
  constraint_message="Farmer ID must be 7 digits.")
q("integer", "a4a_id", "A4A. Re-enter Farmer ID", required="yes", constraint=". = ${a4_id}",
  constraint_message="IDs do not match - go back and re-enter A4.")
q("calculate", "p_first", "", calculation='pulldata("farmers","first_name","respid",${a4_id})')
q("calculate", "p_county", "", calculation='pulldata("farmers","county","respid",${a4_id})')
q("note", "n_prefill", "Respondent on checklist: **${p_first}** (${p_county})", relevance="${p_first} != ''")
q("select_one yesno", "a5_match", "A5. Do name, county and phone number match the checklist?", required="yes",
  constraint=". = 1", constraint_message="Records do not match: re-enter the Farmer ID (A4).")
q("select_one phone_status", "a6_phone", "A6. What is the phone status?", required="yes")
q("select_one a7_resp", "a7_speak", "A7. Am I speaking to ${p_first}? Do you have time to talk now?", required="yes", relevance="${a6_phone} = 1")
q("text", "a7_later", "A7.A Call-back date/time agreed", relevance="${a7_speak} = 3", required="yes")
end()
q("calculate", "call_ok", "", calculation="if(${a6_phone} = 1 and ${a7_speak} = 1, 1, 0)")

# ------------------------------------------------------------------ B: consent
begin("sec_b", "SECTION B - Consent", relevance="${call_ok} = 1")
q("note", "b_text", "Read the consent script: purpose, voluntary participation, free to skip any question, data kept confidential and encrypted, no payment, contact details of the research team.")
q("select_one yesno", "b1_consent", "B1. Do you consent to participate in this survey today?", required="yes")
q("select_one refuse_reason", "b2_refuse", "B2. [FO: do not read] Reason for refusal", relevance="${b1_consent} = 0", required="yes")
end()
q("calculate", "consent_ok", "", calculation="if(${call_ok} = 1 and ${b1_consent} = 1, 1, 0)")

# ------------------------------------------------------------------ D: demographics
begin("sec_d", "SECTION D - Demographics", relevance="${consent_ok} = 1")
q("select_one gender", "d3_gender", "D3. [FO: do not read] Respondent's gender", required="yes")
q("select_one phone_type", "d4_phone", "D4. Is your mobile phone a brick phone or a smartphone?", required="yes")
q("select_one freq5", "d5_send", "D5. How often do you send SMS messages?", required="yes")
q("select_one freq5", "d7_read", "D7. How often do you read SMS messages?", required="yes")
q("select_one yesno", "d9_oaf", "D9. Does anyone in your household CURRENTLY participate in One Acre Fund programs?", required="yes")
q("select_one marital", "d10_marital", "D10. What is your current marital status?", required="yes")
q("select_one yes01_2", "d11_manager", "D11. Are you the primary manager of your farm?", required="yes")
q("select_one yes01_2", "d12_buyer", "D12. Are you the person who buys most of the agricultural inputs for your shamba?", required="yes")
end()
q("calculate", "t_sec_d", "", calculation="once(decimal-date-time(now()))")

# ------------------------------------------------------------------ E: farming practices
begin("sec_e", "SECTION E - LR2017 farming practices", relevance="${consent_ok} = 1")
q("decimal", "e1_size", "E1. Total size of ALL land farmed by the household (acres)", required="yes", constraint=rng_(0.1, 100),
  constraint_message="Enter acres between 0.1 and 100, or -99 if the respondent does not know.")
q("select_one yesno", "e2_plant", "E2. Did you plant maize in the Long Rain 2017 season?", required="yes")
q("decimal", "e3_planted", "E3. Acres planted with maize in LR2017", required="yes", relevance="${e2_plant} = 1",
  constraint="(. = -99) or (${e1_size} = -99) or (. > 0 and . <= ${e1_size} + 0.001)", constraint_message="Planted acres cannot exceed total land (E1).")
q("select_one yesno", "e4_fert", "E4. Did you apply chemical fertiliser on your maize plots in LR2017?", required="yes", relevance="${e2_plant} = 1")
q("select_multiple fert_type", "e5_type", "E5. Which chemical fertilisers did you apply? [FO: mark all that apply]", required="yes",
  relevance="${e2_plant} = 1 and ${e4_fert} = 1")
begin("rep_e5", "E5 detail by fertiliser", relevance="${e2_plant} = 1 and ${e4_fert} = 1", kind="repeat", repeat_count="count-selected(${e5_type})")
q("calculate", "e5_code", "", calculation="selected-at(${e5_type}, position(..) - 1)")
q("decimal", "e5_kg", "E5. Total kilograms of ${e5_code} applied (fertiliser code)", required="yes", constraint=rng_(0.1, 2000),
  constraint_message="Enter kg between 0.1 and 2000, or -99 for don't know.")
end("repeat")
q("select_one seed", "e6_seed", "E6. What type of seeds did you use in LR2017?", required="yes", relevance="${e2_plant} = 1")
q("select_one yesno", "e8_pest", "E8. Did you use chemical pesticides on your maize in LR2017?", required="yes", relevance="${e2_plant} = 1")
q("select_one yesno", "e12_heard", "E12. Have you heard of agricultural lime?", required="yes", relevance="${e2_plant} = 1")
q("select_multiple lime_use", "e13_use", "E13. What is the main use of agricultural lime? [FO: do not read; mark all that apply]", required="yes",
  relevance="${e12_heard} = 1", constraint="not(selected(., '99') and count-selected(.) > 1)",
  constraint_message="'Don't know' cannot be combined with other answers.")
q("select_one yesno", "e14_ever", "E14. Have you ever applied agricultural lime on your maize shamba?", required="yes", relevance="${e12_heard} = 1")
q("select_one yesno", "e15_lr17", "E15. Did you apply lime on your maize in LR2017?", required="yes", relevance="${e14_ever} = 1")
begin("sec_lime", "Lime application detail", relevance="${e15_lr17} = 1")
q("select_multiple lime_src", "e16_src", "E16. Where did you acquire the lime? [FO: do not read; mark all that apply]", required="yes")
q("select_one extent", "e17_extent", "E17. Did you apply lime on the entire maize shamba or just one part?", required="yes")
q("decimal", "e18_area", "E18. Total size of the area where you applied lime (acres)", required="yes", relevance="${e17_extent} = 2",
  constraint="(. = -99) or (${e3_planted} = -99) or (. > 0 and . <= ${e3_planted} + 0.001)", constraint_message="Lime area must be <= acres planted (E3).")
q("calculate", "lime_area", "", calculation="if(${e17_extent} = 1, ${e3_planted}, ${e18_area})")  # -99 propagates; rate warning guards on >0
q("decimal", "e19_kg", "E19. How much lime did you apply in total (kg)?", required="yes", constraint=rng_(1, 20000),
  constraint_message="Enter kg between 1 and 20,000, or -99 for don't know.")
q("calculate", "lime_kg_acre", "", calculation="if(${e19_kg} > 0 and ${lime_area} > 0, ${e19_kg} div ${lime_area}, '')")
q("note", "w_lime_rate", "WARNING: ${lime_kg_acre} kg per acre is unusually high. Re-confirm quantity and area with the respondent before continuing.",
  relevance="${lime_kg_acre} != '' and ${lime_kg_acre} > 4000")
q("select_one method", "e20_method", "E20. Which method did you use for applying lime?", required="yes")
q("select_one yesno", "e22_fert_area", "E22. Did you apply chemical fertiliser in the area where you used lime?", required="yes", relevance="${e17_extent} = 2")
q("select_one rate5", "e27_rate", "E27. From 1 to 5, how would you rate your experience with agricultural lime?", required="yes")
end()
q("decimal", "e29_harvest", "E29. How much dry, shelled maize do you expect to harvest at the end of LR2017?", required="yes", relevance="${e2_plant} = 1",
  constraint=rng_(0, 5000), constraint_message="Enter amount 0-5000, or -99 for don't know.")
q("select_one h_unit", "e29_unit", "E29.A Unit", required="yes", relevance="${e2_plant} = 1 and ${e29_harvest} != -99")
q("select_one yesno", "e30_plant_sr", "E30. Are you planning to plant maize in the next short rains (SR2017)?", required="yes")
q("select_one yesno", "e32_lime_sr", "E32. Are you planning to apply lime in SR2017?", required="yes", relevance="${e30_plant_sr} = 1 and ${e12_heard} = 1")
end()

# ------------------------------------------------------------------ Z: close + QA
begin("sec_z", "SECTION Z - Close")
q("text", "z_comments", "Z1. Enumerator comments (call-back times, anything unusual)", relevance="")
q("calculate", "end_ts", "", calculation="decimal-date-time(now())")
end()
q("calculate", "duration_min", "", calculation="round((decimal-date-time(${end_time}) - decimal-date-time(${start_time})) * 1440, 1)")
q("calculate", "qa_dk_count", "", calculation="if(selected(${e13_use}, '99'), 1, 0) + if(${e1_size} = -99, 1, 0) + if(${e19_kg} = -99, 1, 0) + if(${e29_harvest} = -99, 1, 0)")
q("calculate", "qa_gate_no", "", calculation="if(${e2_plant} = 0, 1, 0) + if(${e4_fert} = 0, 1, 0) + if(${e12_heard} = 0, 1, 0)")
q("calculate", "qa_fast_flag", "", calculation="if(${consent_ok} = 1 and ${duration_min} < 6, 1, 0)")

# ------------------------------------------------------------------ choices
def ch(list_name, items):
    return [dict(list_name=list_name, name=str(n), label=l) for n, l in items]
C = []
C += ch("yesno", [(1, "Yes"), (0, "No")])
C += ch("yes01_2", [(0, "No"), (1, "Yes"), (2, "Yes, jointly with my spouse")])
C += ch("phone_status", [(1, "Call answered"), (2, "Phone off"), (3, "Not answering"), (4, "Busy"), (5, "Wrong number"), (6, "No longer in service"), (7, "Out of service")])
C += ch("a7_resp", [(1, "Now"), (2, "Deceased respondent"), (3, "Later"), (4, "Phone belongs to someone else"), (5, "Hang up")])
C += ch("refuse_reason", [(1, "No time"), (2, "Not interested"), (3, "Does not trust the call"), (4, "Phone cost / airtime"), (98, "Other")])
C += ch("gender", [(1, "Female"), (2, "Male")])
C += ch("phone_type", [(1, "Brick phone"), (2, "Smartphone")])
C += ch("freq5", [(1, "Every day"), (2, "Every week"), (3, "Less than once a week"), (4, "Less than once a month"), (5, "Never")])
C += ch("marital", [(1, "Married"), (2, "Widowed"), (3, "Divorced / separated"), (4, "Cohabiting"), (5, "Never married"), (98, "Other")])
C += ch("fert_type", [(1, "DAP"), (2, "NPK"), (3, "Mavuno (planting)"), (4, "CAN"), (5, "Mavuno (topdressing)"), (6, "Urea"), (98, "Other")])
C += ch("seed", [(1, "Local seeds"), (2, "Hybrid seeds"), (3, "Mix of local and hybrid")])
C += ch("lime_use", [(1, "Reduce soil acidity"), (2, "Reduce striga"), (3, "Increase productivity"), (4, "Improve soil fertility"), (5, "Pest control"), (98, "Other"), (99, "Don't know")])
C += ch("lime_src", [(1, "Agrovet"), (2, "Open market"), (3, "OAF"), (4, "County government"), (5, "PALWECO"), (98, "Other")])
C += ch("extent", [(1, "Entire maize shamba"), (2, "Just one part")])
C += ch("method", [(1, "Broadcasting"), (2, "Microdosing (spot)"), (3, "Both")])
C += ch("rate5", [(1, "Very poor"), (2, "Poor"), (3, "Fair / average"), (4, "Good"), (5, "Very good"), (99, "Don't know")])
C += ch("h_unit", [(1, "gorogoro"), (2, "kg"), (3, "50 kg bag"), (4, "90 kg bag"), (5, "100 kg bag")])
C += ch("fo_list", [(i, f"FO {i:02d} (replace with names)") for i in range(1, 27)])

settings = [dict(form_title="PxD LR2017 Lime & Fertiliser Midline (phone)", form_id="pxd_lime_midline_lr2017", version="2026110101",
                 default_language="English", public_key="", submission_url="", instance_name="concat(${a4_id}, '-', ${a3_fo})")]

# ------------------------------------------------------------------ write workbook
cols = ["type", "name", "label", "hint", "required", "relevance", "constraint", "constraint_message", "calculation", "repeat_count", "parameters", "publishable", "appearance"]
wb = Workbook(); ws = wb.active; ws.title = "survey"
ws.append(cols)
for r in S: ws.append([r.get(c, "") for c in cols])
wc = wb.create_sheet("choices"); wc.append(["list_name", "name", "label"])
for r in C: wc.append([r["list_name"], r["name"], r["label"]])
wsn = wb.create_sheet("settings"); wsn.append(list(settings[0].keys())); wsn.append(list(settings[0].values()))
for w in (ws, wc, wsn):
    for c in w[1]: c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor="1F6FEB")
    w.freeze_panes = "A2"
for col, wd in zip("ABCDEFGHIJK", (22, 18, 70, 12, 10, 40, 48, 44, 52, 24, 22)): ws.column_dimensions[col].width = wd
out = ROOT / "xlsform" / "pxd_lime_midline_LR2017.xlsx"; wb.save(out)
pd.DataFrame([dict(respid=1234567, first_name="TEST_A", county="Busia"), dict(respid=1234568, first_name="TEST_B", county="Kakamega")]).to_csv(ROOT / "xlsform" / "farmers_template.csv", index=False)

# ------------------------------------------------------------------ structural validator
def validate():
    s = pd.read_excel(out, sheet_name="survey").fillna(""); c = pd.read_excel(out, sheet_name="choices").fillna("")
    res = []
    def add(n, ok, d=""): res.append(dict(check=n, passed=bool(ok), detail=d))
    types_ok = {"start", "end", "today", "deviceid", "subscriberid", "simserial", "phonenumber", "text audit", "calculate", "note", "integer", "decimal", "text"}
    names = [n for n in s.name if n]
    dup = [n for n in set(names) if names.count(n) > 1 and n not in ("e5_code", "e5_kg")]
    add("field names unique", not dup, str(dup))
    add("field names valid (letters/digits/_ only, start with letter)", all(re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", n) for n in names))
    stack = []
    for t in s.type:
        if t.startswith("begin "): stack.append(t.split()[1])
        elif t.startswith("end "):
            if not stack or stack.pop() != t.split()[1]: add("begin/end balanced", False, t); break
    else: add("begin/end groups & repeats balanced", not stack, str(stack))
    lists = set(c.list_name)
    refs = [t.split()[1] for t in s.type if t.startswith(("select_one", "select_multiple"))]
    add("every select list exists in choices", all(r in lists for r in refs), str([r for r in refs if r not in lists]))
    add("unknown field types", all((t.split()[0] in {"select_one", "select_multiple", "begin", "end"} or t in types_ok) for t in s.type),
        str([t for t in s.type if not (t.split()[0] in {"select_one", "select_multiple", "begin", "end"} or t in types_ok)]))
    dupc = c.groupby("list_name").name.apply(lambda x: x.duplicated().any())
    add("choice names unique within each list", not dupc.any(), str(list(dupc[dupc].index)))
    # references defined before use
    defined, bad = set(), []
    for _, r in s.iterrows():
        for col in ("relevance", "constraint", "calculation", "label", "repeat_count"):
            for ref in re.findall(r"\$\{([A-Za-z0-9_]+)\}", str(r[col])):
                if ref not in defined and ref != r["name"]: bad.append((r["name"], col, ref))
        if r["name"]: defined.add(r["name"])
    add("every ${field} reference points to an earlier field", not bad, str(bad[:5]))
    paren = [r["name"] for _, r in s.iterrows() for col in ("relevance", "constraint", "calculation") if str(r[col]).count("(") != str(r[col]).count(")")]
    add("balanced parentheses in all expressions", not paren, str(paren))
    sel_val = []
    for _, r in s.iterrows():
        for lst, val in re.findall(r"\$\{(\w+)\}\s*=\s*(\d+)", str(r["relevance"])): pass
    add("required fields have hard constraints where numeric", all(r["constraint"] for _, r in s.iterrows() if r["type"] in ("decimal", "integer") and r["name"] not in ()), "")
    add("paradata present (audit, duration, start/end)", {"audit", "duration_min", "start_time", "end_time"} <= set(names))
    add("encryption key slot present in settings (fill public_key before fieldwork)", "public_key" in pd.read_excel(out, sheet_name="settings").columns)
    v = pd.DataFrame(res); v.to_csv(OUT_T / "xlsform_validation.csv", index=False)
    print(v.to_string(index=False)); print(f"\nrows: survey={len(s)} choices={len(c)}  fields={len(names)}")
    return v
validate()
