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


def test_unknown_column_only_uses_high_confidence_detection():
    content = _make_xlsx(
        ["备注"],
        [["张三"], ["技术部"], ["13800138000"], ["zhangsan@example.com"]],
    )
    result = anonymize_xlsx_bytes(content)
    originals = {e.original for e in result.mapping.entries}
    assert "张三" not in originals
    assert "技术部" not in originals
    assert "13800138000" in originals
    assert "zhangsan@example.com" in originals


def test_departure_reason_and_job_title_default_to_pass_through():
    content = _make_xlsx(
        ["姓名", "岗位名称", "离职原因"],
        [["张三", "技术部", "被动"], ["李四", "销售经理", "主动"]],
    )
    result = anonymize_xlsx_bytes(content)
    wb = openpyxl.load_workbook(BytesIO(result.workbook_bytes))
    ws = wb.active
    originals = {e.original for e in result.mapping.entries}
    assert "张三" in originals
    assert "李四" in originals
    assert "技术部" not in originals
    assert "销售经理" not in originals
    assert "被动" not in originals
    assert "主动" not in originals
    assert ws.cell(row=2, column=2).value == "技术部"
    assert ws.cell(row=2, column=3).value == "被动"


def test_job_title_can_be_anonymized_when_enabled():
    content = _make_xlsx(["岗位名称"], [["技术部"], ["销售经理"]])
    result = anonymize_xlsx_bytes(content, anonymize_job_title=True)
    wb = openpyxl.load_workbook(BytesIO(result.workbook_bytes))
    ws = wb.active
    originals = {e.original for e in result.mapping.entries}
    assert "技术部" in originals
    assert "销售经理" in originals
    assert TOKEN_RE.fullmatch(str(ws.cell(row=2, column=1).value))
    assert TOKEN_RE.fullmatch(str(ws.cell(row=3, column=1).value))


def test_job_allowlist_does_not_hide_salary_columns_with_job_prefix():
    content = _make_xlsx(["岗位补贴"], [[1200]])
    result = anonymize_xlsx_bytes(content)
    originals = {e.original for e in result.mapping.entries}
    assert "1200" in originals


def test_member_and_member_department_columns_anonymized_in_xlsx():
    content = _make_xlsx(
        ["成员", "成员所属部门"],
        [["张三", "产品中心-设计部"], ["李四", "产品中心/研发部"]],
    )
    result = anonymize_xlsx_bytes(content)
    originals = {e.original: e.entity_type for e in result.mapping.entries}
    assert originals["张三"] == "employee"
    assert originals["李四"] == "employee"
    assert originals["产品中心-设计部"] == "department"
    assert originals["产品中心/研发部"] == "department"


def test_weak_person_object_column_anonymized_in_xlsx():
    content = _make_xlsx(
        ["对象", "备注"],
        [["张三", "李四"], ["欧阳婷婷", "王五"], ["技术部", "赵六"], ["张主管", "陈七"]],
    )
    result = anonymize_xlsx_bytes(content)
    originals = {e.original: e.entity_type for e in result.mapping.entries}
    assert originals["张三"] == "employee"
    assert originals["欧阳婷婷"] == "employee"
    assert "技术部" not in originals
    assert "张主管" not in originals
    assert "李四" not in originals


def test_subject_columns_are_anonymized_as_customer_in_xlsx():
    content = _make_xlsx(
        ["所属主体", "法人主体"],
        [["上海春雷科技有限公司", "深圳远山科技有限公司"]],
    )
    result = anonymize_xlsx_bytes(content)
    originals = {e.original: e.entity_type for e in result.mapping.entries}
    assert originals["上海春雷科技有限公司"] == "customer"
    assert originals["深圳远山科技有限公司"] == "customer"


# ── v1.13.0: Merged header cells ──────────────────────────────────────────────

def _make_xlsx_with_merged_header(headers: list[str], merge_range: str, rows: list[list]) -> bytes:
    """Create xlsx with merged cells in the header row."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(headers)
    ws.merge_cells(merge_range)
    for row in rows:
        ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_merged_header_slave_column_gets_column_type():
    """When header has merged cells, slave columns inherit master's column type."""
    # A1 merged with B1: "姓名" covers both columns; add "部门" so row1 has >1
    # non-empty cell and detect_header_row doesn't mistake it for a title row.
    content = _make_xlsx_with_merged_header(
        ["姓名", None, "部门"], "A1:B1", [["张三", "李四", "技术部"]]
    )
    result = anonymize_xlsx_bytes(content)
    originals = {e.original for e in result.mapping.entries}
    assert "张三" in originals
    assert "李四" in originals, "B2 (slave column) should inherit 姓名 column type"


def test_merged_header_multi_column():
    """Header with 3-column merge: all slave columns inherit master."""
    content = _make_xlsx_with_merged_header(
        ["姓名", None, None, "部门"],
        "A1:C1",
        [["张三", "李四", "王五", "技术部"]],
    )
    result = anonymize_xlsx_bytes(content)
    originals = {e.original for e in result.mapping.entries}
    assert "张三" in originals
    assert "李四" in originals
    assert "王五" in originals
    assert "技术部" in originals


# ── v1.13.0: Label-value layout ───────────────────────────────────────────────

def _make_label_value_xlsx(pairs: list[tuple[str, str]]) -> bytes:
    """Create xlsx with A=field labels, B=values (左右结构)."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["字段", "值"])  # header row so label-value detection works
    for label, value in pairs:
        ws.append([label, value])
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_label_value_layout_name_anonymized():
    """Label '姓名' in A → value in B anonymized as EMPLOYEE."""
    content = _make_label_value_xlsx([
        ("姓名", "张三"),
        ("部门", "技术部"),
        ("手机号", "13800138000"),
        ("工号", "EMP00123"),
    ])
    result = anonymize_xlsx_bytes(content)
    originals = {e.original for e in result.mapping.entries}
    assert "张三" in originals
    assert "技术部" in originals
    assert "13800138000" in originals
    assert "EMP00123" in originals

    # Verify cell values are tokenized
    wb = openpyxl.load_workbook(BytesIO(result.workbook_bytes))
    ws = wb.active
    assert TOKEN_RE.fullmatch(str(ws.cell(row=2, column=2).value))  # 张三→token
    assert TOKEN_RE.fullmatch(str(ws.cell(row=3, column=2).value))  # 技术部→token


def test_label_value_layout_multi_name():
    """Label-value layout with multi-name cell (e.g. '张三、李四') splits correctly."""
    content = _make_label_value_xlsx([
        ("姓名", "张三"),
        ("部门", "技术部"),
        ("负责人", "张三、李四"),
        ("手机号", "13800138000"),
    ])
    result = anonymize_xlsx_bytes(content)
    originals = {e.original for e in result.mapping.entries}
    assert "张三" in originals
    assert "李四" in originals
    assert "张三、李四" not in originals


def test_label_value_layout_non_keyword_label_skipped():
    """Label not in keywords → value is NOT anonymized."""
    content = _make_label_value_xlsx([
        ("备注", "这是一段备注"),
        ("地址", "苏州工业园区"),
    ])
    result = anonymize_xlsx_bytes(content)
    originals = {e.original for e in result.mapping.entries}
    assert len(originals) == 0, f"Non-keyword labels should not trigger anonymization, got: {originals}"


def test_label_value_layout_job_title_default_pass_through_can_opt_in():
    content = _make_label_value_xlsx([
        ("姓名", "张三"),
        ("部门", "技术部"),
        ("岗位", "产品部"),
        ("离职原因", "被动"),
    ])
    default_result = anonymize_xlsx_bytes(content)
    default_originals = {e.original for e in default_result.mapping.entries}
    assert "张三" in default_originals
    assert "技术部" in default_originals
    assert "产品部" not in default_originals
    assert "被动" not in default_originals

    opt_in_result = anonymize_xlsx_bytes(content, anonymize_job_title=True)
    opt_in_originals = {e.original for e in opt_in_result.mapping.entries}
    assert "产品部" in opt_in_originals
    assert "被动" not in opt_in_originals


def test_label_value_layout_skips_header_row():
    """Label-value layout: header row ('字段'/'值') is skipped, data rows processed."""
    content = _make_label_value_xlsx([
        ("姓名", "张三"),
        ("部门", "技术部"),
    ])
    result = anonymize_xlsx_bytes(content, header_row=1)
    originals = {e.original for e in result.mapping.entries}
    assert "张三" in originals, "Row 2 (姓名/张三) should be processed"
    assert "技术部" in originals, "Row 3 (部门/技术部) should be processed"
