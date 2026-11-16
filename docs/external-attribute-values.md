---
title: "Use saved values for external attributes"
type: decision
tags: [anonymization, xlsx, verification]
---

# Use saved values for external attributes

Accepted on 2026-11-16: external formulas returning identifiers and attributes such as employee IDs, names, departments and groups become their original saved results before anonymization. This keeps the output independent of another computer's source workbook without retaining a hidden lookup snapshot for personnel attributes. Internal salary and commission calculation formulas remain formulas. Their numeric results are retained in calculation-preserving mode.

Taking a value does not force numeric conversion. Preserve text IDs and their leading zeros. Run this step before identity registration so externally obtained IDs and names participate in the same cross-sheet matching rules. Department, job-title and other optional masking settings still apply after extraction.

Only a valid saved result is usable. An explicitly saved empty string is a valid blank; a missing result or an Excel error requires review with a worksheet ordinal and cell address. Do not replace either case with zero or invent a result. A failed file does not update the identity registry; batch processing continues with other files.

The output comment identifies the attribute as a historical saved result whose freshness is unverified. No real external path or original formula is copied into this comment. Exports, web results and CLI manifests expose `external_value_count`.

The implementation is in `external_snapshots.py`; tests are in `tests/test_external_values.py`. For remaining external business formulas see [[external-lookup-snapshots]]. Internal reference consistency follows [[formula-identifier-consistency]].
