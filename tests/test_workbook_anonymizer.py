from __future__ import annotations

import re
from io import BytesIO

import openpyxl

from privacy_data_agent.workbook_anonymizer import anonymize_xlsx_bytes

TOKEN_RE = re.compile(r"PDA_[A-F0-9]{16}")


def _make_xlsx(headers: list[str], rows: list[list]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ── Single-name cells (existing behavior unchanged) ──────────────────────────

def test_single_name_cell_anonymized():
    """Single-name cell in person column → one token."""
    content = _make_xlsx(["姓名"], [["张三"], ["李四"]])
    result = anonymize_xlsx_bytes(content)
    wb = openpyxl.load_workbook(BytesIO(result.workbook_bytes))
    ws = wb.active
    t1 = ws.cell(row=2, column=1).value
    t2 = ws.cell(row=3, column=1).value
    assert TOKEN_RE.fullmatch(t1), f"Expected token, got: {t1!r}"
    assert TOKEN_RE.fullmatch(t2), f"Expected token, got: {t2!r}"
    assert t1 != t2


def test_single_name_no_surname_check():
    """Single-name cell: anonymized even if surname not in SURNAME_SET."""
    content = _make_xlsx(["负责人"], [["阿牛"]])
    result = anonymize_xlsx_bytes(content)
    wb = openpyxl.load_workbook(BytesIO(result.workbook_bytes))
    token = wb.active.cell(row=2, column=1).value
    assert TOKEN_RE.fullmatch(token), f"Expected token, got: {token!r}"


# ── Multi-name cells: < 5 segments (no surname check) ────────────────────────

def test_two_name_cell_split_into_separate_tokens():
    """Cell 'A、B' in person column → A and B each get their own token."""
    content = _make_xlsx(["负责人"], [["张三、李四"]])
    result = anonymize_xlsx_bytes(content)
    originals = {e.original for e in result.mapping.entries}
    assert "张三" in originals
    assert "李四" in originals
    assert "张三、李四" not in originals, "Whole cell should not be a single entry"


def test_multi_name_cell_various_delimiters():
    """All supported delimiters split correctly."""
    for delim in ["、", "，", "；", ",", ";", "/"]:
        content = _make_xlsx(["归属人"], [[f"张三{delim}李四"]])
        result = anonymize_xlsx_bytes(content)
        originals = {e.original for e in result.mapping.entries}
        assert "张三" in originals, f"张三 missing with delimiter {delim!r}"
        assert "李四" in originals, f"李四 missing with delimiter {delim!r}"


def test_multi_name_below_threshold_no_surname_check():
    """< 5 segments: non-traditional names anonymized without surname validation."""
    content = _make_xlsx(["跟进人"], [["阿牛、张三、李四"]])
    result = anonymize_xlsx_bytes(content)
    originals = {e.original for e in result.mapping.entries}
    assert "阿牛" in originals, "阿牛 should be anonymized even without a surname"


def test_token_reuse_across_single_and_multi_name_cells():
    """Same name in single-name cell and multi-name cell → same token."""
    content = _make_xlsx(
        ["姓名", "负责人"],
        [["张三", "张三、李四"]],
    )
    result = anonymize_xlsx_bytes(content)
    zhang_entries = [e for e in result.mapping.entries if e.original == "张三"]
    assert len(zhang_entries) == 1, f"张三 should map to exactly one token, got: {zhang_entries}"


def test_four_name_cell_all_anonymized():
    """4 names (just under threshold): all anonymized."""
    content = _make_xlsx(["负责人"], [["张三、李四、王五、赵六"]])
    result = anonymize_xlsx_bytes(content)
    originals = {e.original for e in result.mapping.entries}
    for name in ["张三", "李四", "王五", "赵六"]:
        assert name in originals


def test_cell_value_no_longer_contains_originals():
    """After anonymisation, original names must not appear in cell value."""
    content = _make_xlsx(["姓名"], [["张三、李四"]])
    result = anonymize_xlsx_bytes(content)
    wb = openpyxl.load_workbook(BytesIO(result.workbook_bytes))
    cell_value = str(wb.active.cell(row=2, column=1).value)
    assert "张三" not in cell_value
    assert "李四" not in cell_value
    assert TOKEN_RE.search(cell_value), f"Expected at least one token in: {cell_value!r}"


# ── Multi-name cells: ≥ 5 segments (surname check applied) ───────────────────

def test_five_name_cell_all_valid_surnames_anonymized():
    """≥ 5 names, all valid: all anonymized."""
    content = _make_xlsx(["负责人"], [["张三、李四、王五、赵六、陈七"]])
    result = anonymize_xlsx_bytes(content)
    originals = {e.original for e in result.mapping.entries}
    for name in ["张三", "李四", "王五", "赵六", "陈七"]:
        assert name in originals


def test_five_name_cell_invalid_segment_skipped():
    """≥ 5 names: segment with no known surname is skipped."""
    # 呵呵呵呵 — 呵 is not a Chinese surname
    content = _make_xlsx(["负责人"], [["张三、李四、王五、赵六、呵呵呵呵"]])
    result = anonymize_xlsx_bytes(content)
    originals = {e.original for e in result.mapping.entries}
    assert "呵呵呵呵" not in originals
    assert "张三" in originals  # valid ones still processed


# ── Edge cases ────────────────────────────────────────────────────────────────

def test_empty_cell_in_person_column_skipped():
    content = _make_xlsx(["姓名"], [[""], [None]])
    result = anonymize_xlsx_bytes(content)
    assert result.mapping.entries == []


def test_non_person_column_still_uses_cell_detection():
    """Non-hint column: cell detection path unchanged (phone number detected)."""
    content = _make_xlsx(["手机号"], [["13800138000"]])
    result = anonymize_xlsx_bytes(content)
    originals = {e.original for e in result.mapping.entries}
    assert "13800138000" in originals
