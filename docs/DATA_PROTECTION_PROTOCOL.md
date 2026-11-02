# Data protection & secure handling of personal data (template protocol)

Applies to any survey data collected with the XLSForm in `xlsform/`. Adapt to the study's IRB/ethics approval and contracts. Kenya's Data Protection Act (2019) and the study's institutional requirements govern; this template is not legal advice.

1. **Classify.** Direct identifiers (name, phone number, GPS, farmer name, voice recordings), quasi-identifiers (location + age + land size), and non-identifying analysis variables. Record the class of every variable in the codebook.
2. **Minimise.** Collect only what the research questions need. Pre-load names/phones through an encrypted attachment only when required for the call; never store them in the analysis dataset.
3. **Encrypt at source.** Generate a SurveyCTO key pair; put the public key in `settings.public_key`; keep the private key offline with two named custodians. Devices use full-disk encryption and screen-lock.
4. **Separate.** Keep a `crosswalk` (ID ↔ identifiers) in a restricted location with a different access list from the analysis data. Analysis files contain coded IDs only.
5. **Access control.** Named users, least privilege, no shared accounts, MFA. Quarterly access review. Log downloads.
6. **De-identify before sharing.** Remove direct identifiers, coarsen location to ward/area, top-code extreme land sizes, drop free text, test for re-identification risk. This repository ships **no** raw or identified data.
7. **Transfer.** Only through approved encrypted channels; never by personal email or messaging apps.
8. **Retention & deletion.** Delete identified data at the end of the retention period set in the consent form; document deletion.
9. **Incident response.** Lost device or suspected breach → report within 24 h to the data lead; remote-wipe the device; assess whether notification to the Data Commissioner and participants is required; keep an incident log.
10. **Enumerator conduct.** Training on confidentiality, signed agreements, no personal recording of calls, back-checks use only the minimum identifiers.
