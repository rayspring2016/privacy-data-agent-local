---
title: "Formula identifier consistency"
type: pattern
tags: [anonymization, xlsx, verification]
---

# Formula identifier consistency

In calculation-preserving mode, retaining formula text and cached numeric results is insufficient to prove that a lookup still joins the same rows. Compare the matching row positions before and after masking for supported internal exact VLOOKUP expressions. Preserve existing misses as well as existing matches.

Formula discovery and lookup type propagation run in both ordinary and calculation-preserving modes, independently of unified/new numbering. Preservation only controls numeric/cache handling. `tests/test_leave_lookups.py` covers all numbering/preservation combinations and single/batch web routes.

Employee IDs and bank accounts are identifiers even when stored as numbers. A salary-retention setting must not retain a salary bank account. Bank-account column detection takes priority over salary detection. Preserve business amounts, percentages and coefficients.

Use explicit field headers, verified same-row employee identity, and local formula references as evidence for additional identifier cells. An exact lookup's first source column can inherit the lookup key's type. A single direct reference or lookup result applies to that cell, not every value in its output column. Keep department options effective on inferred fields. Unrelated periods and amounts must not be replaced merely because their values also occur as employee IDs.

`workbook_identifiers.py` propagates types across supported local single-cell references and exact VLOOKUP links. Workbook dimensions are cached once for this scan: openpyxl's `max_row` scans cell storage and is expensive to call for each formula.

Regression coverage is in `tests/test_lookup_identifiers.py`, including numeric and textual bank accounts, grouped headers, source keys with custom headers, formula-result caches, mixed result columns, department options and the single/batch web routes. External attribute fields follow [[external-attribute-values]]. Remaining verified external business lookups can use [[external-lookup-snapshots]]. Other external and complex expressions still require their original sources or further evaluation; cached output and structural checks do not constitute Excel recalculation.
