---
title: "External lookup snapshots"
type: component
tags: [anonymization, xlsx, verification]
---

# External lookup snapshots

External identifiers and attributes first follow [[external-attribute-values]]. This snapshot fallback applies to remaining business formulas.

`external_snapshots.py` handles supported exact VLOOKUP references to external workbooks before ordinary anonymization. It reads the external data cache already embedded in the input XLSX. It never opens the external file or follows its path.

Localize only when the key and return field have supported types, the cached source contains a matching key and return value, and that return value equals the original formula's saved result. Select the original first matching row. Import only the required key and return cells into a hidden local sheet with generic typed headers. Cached text remains literal text when imported. Anonymize that sheet with the rest of the workbook, then use the same VLOOKUP function, column index and exact-match flag with a local source range.

The hidden sheet and formula comments label the data as a historical cached snapshot. It supports offline lookup for the captured records; it does not validate the external source's current data or substitute for missing source evidence.

Remove external-link metadata when no external cell formulas or defined names remain. Unsupported, incomplete, conflicting or stale cache data is not used to invent a source table. Those references retain the existing anonymized external-link handling and the UI reports that a source file is still required. Single/batch exports and CLI manifests report localized formula counts separately from remaining external links and directly taken attribute values.

Tests: `tests/test_external_snapshots.py`. Related verification: [[formula-identifier-consistency]].
