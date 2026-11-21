---
title: "Grouped pivot compatibility with openpyxl"
type: issue
tags: [excel, openpyxl, pivot, compatibility]
---

# Grouped pivot compatibility

Verified with openpyxl 3.1.5 on 2026-11-21. Loading a pivot cache containing
`fieldGroup/discretePr/x` raises `Nested.from_tree() missing 1 required positional argument: 'node'`.
`FieldGroup.discretePr` incorrectly expects the `NestedInteger` descriptor class,
whose `from_tree` requires an instance, rather than a serialisable index object.

Before loading workbooks, `anonymize_xlsx_bytes` changes that expected type to
openpyxl's existing `Index` type only if it is still `NestedInteger`. This retains
the `<x v="..."/>` indices and supports both reading and writing. It does not
suppress parsing errors or remove grouping XML before the existing pivot checks.
The existing anonymization flow retains masked visible results and removes raw
pivot definitions and caches from exported workbooks.

`tests/test_grouped_pivots.py` covers the original exception, both calculation
modes, grouping index round trips, raw-cache removal, and the Streamlit upload
flow. A user's original file still needs a retry to confirm it has this trigger.
