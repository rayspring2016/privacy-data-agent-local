from __future__ import annotations

import re
from uuid import uuid4
from zipfile import ZipFile, ZIP_DEFLATED
from xml.etree import ElementTree as ET
from io import BytesIO
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook
from openpyxl.formula.tokenizer import Tokenizer
from openpyxl.workbook.properties import CalcProperties
from openpyxl.utils.cell import get_column_letter, range_boundaries, coordinate_to_tuple
from pydantic import BaseModel, ConfigDict, Field

from privacy_data_agent.workbook_identifiers import linked_identifier_cells
from privacy_data_agent.external_snapshots import freeze_external_attributes, localize_external_lookups
from privacy_data_agent.anonymizer import AnonymizerState
from privacy_data_agent.detectors import (
    EMPLOYEE_EMAIL_HEADERS,
    EMPLOYEE_ID_HEADERS,
    SalaryGroup,
    detect_column_entity_type,
    detect_high_confidence_cell_entity_type,
    detect_header_row,
    detect_optional_column_entity_type,
    detect_weak_person_column,
    detect_label_value_layout,
    is_pass_through_column,
    resolve_entity_from_label,
    CHINESE_NAME_RE,
    looks_like_short_chinese_person_name,
    _looks_like_chinese_name,
    preserve_analysis_number,
)
from privacy_data_agent.models import EntityType, MappingFile
from privacy_data_agent.person_identity import IdentityReviewError, PRIMARY_NAME_HEADERS, is_identity_placeholder

# Delimiters used to split multi-name cells in person columns
_NAME_SPLIT_RE = re.compile(r"[、，；,;/|]+")

# Cells with ≥ this many name segments get SURNAME_SET validation (防止大列表误报)
_MULTI_NAME_SURNAME_CHECK_THRESHOLD = 5


def _split_person_cell(text: str) -> list[str]:
    """Return non-empty segments after splitting on name delimiters."""
    return [s.strip() for s in _NAME_SPLIT_RE.split(text) if s.strip()]


def _anonymize_person_segment(
    segment: str, validate_surname: bool, state: AnonymizerState, identity_key: str | None = None,
) -> str | None:
    """Return a token for segment, or None if it should be kept unchanged.

    Verified identities use their existing token. Other segments require 2-4
    Chinese characters and, when requested, a surname check.
    """
    if identity_key is not None:
        return state.token_for(EntityType.EMPLOYEE, segment, identity_key=identity_key)
    if not CHINESE_NAME_RE.match(segment):
        return None
    if validate_surname and not _looks_like_chinese_name(segment):
        return None
    return state.token_for(EntityType.EMPLOYEE, segment)


class WorkbookAnonymizeResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    workbook_bytes: bytes
    mapping: MappingFile
    row_count: int
    preview_dataframe: pd.DataFrame
    review_items: list[dict[str, str]] = Field(default_factory=list)
    formula_count: int = 0
    external_link_count: int = 0
    localized_external_formula_count: int = 0
    external_value_count: int = 0


def _parallel_identity_tables(worksheet, header_row, headers, rows):
    """Find independent horizontal tables using header structure, never employee values."""
    width = len(headers)
    whole = [(0, width)]
    normalized = [header.lower() for header in headers]
    ids = {i for i, header in enumerate(normalized) if header in EMPLOYEE_ID_HEADERS}
    if len(ids) < 2:
        return whole
    names = {i for i, header in enumerate(normalized) if header in PRIMARY_NAME_HEADERS}
    emails = {i for i, header in enumerate(normalized) if header in EMPLOYEE_EMAIL_HEADERS}

    def independent(spans):
        if len(spans) < 2:
            return False
        covered = set()
        for start, end in spans:
            columns = set(range(start, end))
            if len(ids & columns) > 1 or len(names & columns) > 1:
                return False
            if covered & columns:
                return False
            covered.update(columns)
        return sum(bool(ids & set(range(start, end))) for start, end in spans) >= 2 and (ids | names | emails) <= covered

    # Each merged title above the headers can define a separate block.
    if header_row > 1:
        titles = sorted(
            (merged.min_col - 1, merged.max_col)
            for merged in worksheet.merged_cells.ranges
            if merged.max_row == header_row - 1 and merged.min_col < merged.max_col
            and worksheet.cell(merged.min_row, merged.min_col).value
            and any(merged.min_col - 1 <= i < merged.max_col for i in ids)
        )
        if independent(titles):
            boundaries = sorted({0, width, *(bound for span in titles for bound in span)})
            return list(zip(boundaries, boundaries[1:]))

    # A fully empty separator column is another clear table boundary.
    has_values = [bool(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            if cell.value is not None:
                has_values[index] = True
    runs = []
    start = None
    for index, occupied in enumerate([*has_values, False]):
        if occupied and start is None:
            start = index
        elif not occupied and start is not None:
            runs.append((start, index))
            start = None
    if independent(runs):
        return runs

    # Adjacent copies of exactly the same header also form separate tables.
    first = next((i for i, header in enumerate(normalized) if header), 0)
    last = max((i + 1 for i, header in enumerate(normalized) if header), default=0)
    for size in range(2, (last - first) // 2 + 1):
        if (last - first) % size:
            continue
        repeats = [(i, i + size) for i in range(first, last, size)]
        if (all(normalized[i:j] == normalized[first:first + size] for i, j in repeats)
                and independent(repeats)):
            return repeats
    return whole


def _pivot_identity_tables(worksheet, sheet_number):
    tables = []
    for pivot in worksheet._pivots:
        left, top, right, bottom = range_boundaries(pivot.location.ref)
        for field in (*pivot.colFields, *pivot.pageFields):
            index = field.x if hasattr(field, "x") else field.fld
            if index >= 0 and detect_column_entity_type(pivot.cache.cacheFields[index].name) in {
                EntityType.EMPLOYEE, EntityType.EMPLOYEE_ID, EntityType.EMAIL,
            }:
                raise IdentityReviewError(
                    f"待核验：第 {sheet_number} 张工作表的透视表（{pivot.location.ref}）"
                    "将人员字段放在列标签或筛选器中。请移到行标签后重新处理。"
                )
        first_data_row = top + pivot.location.firstDataRow
        header_row = first_data_row - 1
        headers = [str(worksheet.cell(header_row, col).value or "").strip() for col in range(left, right + 1)]
        row_fields = [field.x for field in pivot.rowFields if field.x >= 0]
        row_columns = pivot.location.firstDataCol
        if len(row_fields) > row_columns:
            raise IdentityReviewError(
                f"待核验：第 {sheet_number} 张工作表的透视表（{pivot.location.ref}）"
                "在一列中显示多个行字段。请在 Excel 中改为表格形式，重复所有项目标签后重新处理。"
            )
        # Excel 的“行标签”或自定义标题不一定等于源字段名。
        for index, field in enumerate(row_fields):
            headers[index] = pivot.cache.cacheFields[field].name
        if len(pivot.dataFields) == 1:
            source_name = pivot.cache.cacheFields[pivot.dataFields[0].fld].name
            headers[row_columns:] = [source_name] * len(headers[row_columns:])
        tables.append((left, top, right, bottom, first_data_row, headers))
    return tables


def _identity_location(sheet_number, start, field_rows):
    def describe(row_index, columns):
        if field_rows:
            cells = "、".join(f"B{field_rows[i]}" for i in columns)
            return f"第 {sheet_number} 张工作表（{cells}）"
        letters = "、".join(get_column_letter(start + i + 1) for i in columns)
        return f"第 {sheet_number} 张工作表第 {row_index} 行（{letters} 列）"

    return describe


def _restore_formulas(content: bytes, formulas: dict[str, dict[str, str]]) -> bytes:
    """Attach original formulas to the already anonymized cached values."""
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    relationship_ns = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
    output = BytesIO()
    with ZipFile(BytesIO(content)) as source, ZipFile(output, "w", ZIP_DEFLATED) as target:
        metadata = ET.fromstring(source.read("xl/workbook.xml"))
        metadata.find(ns + "workbookPr").set("updateLinks", "never")
        relationships = {item.get("Id"): item.get("Target") for item in ET.fromstring(source.read("xl/_rels/workbook.xml.rels"))}
        by_path = {}
        for sheet in metadata.find(ns + "sheets"):
            if sheet.get("name") in formulas:
                path = relationships[sheet.get(relationship_ns + "id")]
                by_path[path.lstrip("/") if path.startswith("/") else "xl/" + path] = formulas[sheet.get("name")]
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename == "xl/workbook.xml":
                data = ET.tostring(metadata, encoding="utf-8", xml_declaration=True)
            elif item.filename in by_path:
                root = ET.fromstring(data); rows = root.find(ns + "sheetData")
                row_map = {int(row.get("r")): row for row in rows}
                for address, formula in by_path[item.filename].items():
                    number, _ = coordinate_to_tuple(address)
                    row = row_map.get(number)
                    if row is None:
                        row = ET.SubElement(rows, ns + "row", {"r": str(number)}); row_map[number] = row
                    cell = row.find(f"{ns}c[@r='{address}']")
                    if cell is None:
                        cell = ET.SubElement(row, ns + "c", {"r": address})
                    if cell.get("t") == "inlineStr":
                        text = "".join(part.text or "" for part in cell.findall(".//" + ns + "t"))
                        cell.remove(cell.find(ns + "is")); cell.set("t", "str")
                        ET.SubElement(cell, ns + "v").text = text
                    elif cell.find(ns + "v") is None:
                        cell.set("t", "str"); ET.SubElement(cell, ns + "v")
                    ET.SubElement(cell, ns + "f").text = formula[1:]
                    cell[:] = sorted(cell, key=lambda node: node.tag != ns + "f")
                    row[:] = sorted(row, key=lambda node: coordinate_to_tuple(node.get("r"))[1])
                rows[:] = sorted(rows, key=lambda row: int(row.get("r")))
                data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            target.writestr(item, data)
    return output.getvalue()


def anonymize_xlsx_bytes(
    content: bytes,
    seed_mapping: MappingFile | None = None,
    header_row: int | None = None,
    anonymize_job_title: bool = False,
    anonymize_department: bool = True,
    anonymize_region: bool = True,
    anonymize_salary: bool = True,
    keep_salary_groups: frozenset[SalaryGroup] = frozenset(),
    require_unique_people: bool = False,
    allow_unverified_people: bool = False,
    preserve_calculations: bool = False,
) -> WorkbookAnonymizeResult:
    workbook = load_workbook(BytesIO(content))
    if preserve_calculations:
        anonymize_salary = False
    formula_count = 0
    has_external = bool(workbook._external_links) or any(
        cell.data_type == "f" and isinstance(cell.value, str) and "[" in cell.value
        for sheet in workbook for row in sheet for cell in row
    )
    cached = load_workbook(BytesIO(content), data_only=True, read_only=True, keep_links=False) if preserve_calculations or has_external else None
    localized_external_formula_count = 0
    external_value_count = 0
    if has_external:
        headers = {sheet.title: _header_by_column(sheet, header_row or _detect_xlsx_header_row(sheet)) for sheet in workbook}
        external_value_count = freeze_external_attributes(workbook, cached, headers)
        localized_external_formula_count = localize_external_lookups(workbook, cached, headers)
    # Lookup source discovery applies to both modes, independently of cache preservation.
    original_formulas = {
        sheet.title: {cell.coordinate: cell.value for row in sheet.iter_rows() for cell in row
                      if cell.data_type == "f" and isinstance(cell.value, str)}
        for sheet in workbook.worksheets
    }
    external_link_count = len(workbook._external_links)
    for index, link in enumerate(workbook._external_links, 1):
        link.externalBook.sheetDataSet = None
        link.file_link.Target = f"external-source-{index:02d}.xlsx"
    if preserve_calculations:
        workbook.calculation = CalcProperties(calcMode="manual", fullCalcOnLoad=False, forceFullCalc=False, calcOnSave=False)
        for sheet_number, (sheet, values) in enumerate(zip(workbook.worksheets, cached.worksheets), 1):
            for row, value_row in zip(sheet.iter_rows(), values.iter_rows()):
                for cell, value in zip(row, value_row):
                    if cell.data_type != "f":
                        continue
                    if not isinstance(cell.value, str):
                        raise ValueError(f"第 {sheet_number} 张工作表 {cell.coordinate} 的公式类型暂不支持核验保留。")
                    if value.value is None and value.data_type not in {"s", "str", "inlineStr"}:
                        raise ValueError(f"第 {sheet_number} 张工作表 {cell.coordinate} 缺少已保存的计算结果，请用 Excel 重新计算并保存原文件后再处理。")
                    original_formulas.setdefault(sheet.title, {})[cell.coordinate] = cell.value
                    cell.value = value.value
                    if isinstance(value.value, str) and value.data_type != "e":
                        cell.data_type = "s"
                    formula_count += 1
    if cached:
        cached.close()
    state = AnonymizerState(seed_mapping=seed_mapping, require_unique_people=require_unique_people, allow_unverified_people=allow_unverified_people)
    row_count = 0
    customer_names = set()
    customer_name_headers = {
        "客户", "客户名称", "客户名", "客户全称", "客户简称", "公司", "公司名称", "公司全称",
        "企业名称", "单位名称", "主体", "签约主体", "用工主体", "合同主体", "甲方", "乙方",
    }
    for sheet in workbook.worksheets:
        first_header = header_row or _detect_xlsx_header_row(sheet)
        headers = _header_by_column(sheet, first_header)
        name_columns = {column for column, name in headers.items() if name.strip() in customer_name_headers}
        label_value = detect_label_value_layout(sheet, header_row=first_header)
        for row in sheet.iter_rows():
            for cell in row:
                if not isinstance(cell.value, str) or cell.data_type == "f":
                    continue
                text = cell.value.strip()
                title = re.fullmatch(r"(?:单位|公司|客户|企业)名称\s*[：:]\s*(.+)", text)
                if title:
                    customer_names.add(title.group(1).strip())
                if (cell.row > first_header and cell.column in name_columns and text not in customer_name_headers
                        and not is_identity_placeholder(text) and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*\(", text)):
                    customer_names.add(text)
            if label_value and len(row) >= 2 and str(row[0].value).strip() in customer_name_headers:
                if isinstance(row[1].value, str) and row[1].data_type != "f" and not is_identity_placeholder(row[1].value):
                    customer_names.add(row[1].value.strip())

    pivots_by_sheet = {
        sheet.title: _pivot_identity_tables(sheet, number)
        for number, sheet in enumerate(workbook.worksheets, start=1)
    }
    identifier_cells = linked_identifier_cells(workbook, original_formulas, header_row, pivots_by_sheet)
    identity_tables = {}
    if state.require_unique_people:
        for sheet_number, sheet in enumerate(workbook.worksheets, start=1):
            header_row_number = header_row or _detect_xlsx_header_row(sheet)
            headers = _header_by_column(sheet, header_row=header_row_number)
            rows = [row for row in sheet.iter_rows() if row and row[0].row > header_row_number]
            tables = []
            pivots = pivots_by_sheet[sheet.title]
            if not pivots and detect_label_value_layout(sheet, header_row=header_row_number):
                pairs = [(row[0], row[1]) for row in rows if len(row) >= 2 and row[0].value is not None]
                table_headers = [str(label.value).strip() for label, _ in pairs]
                table_rows = [(0, [value.value if value.data_type != "f" else None for _, value in pairs])]
                field_rows = [value.row for _, value in pairs]
                tables.append((0, table_headers, table_rows, field_rows))
            else:
                table_headers = [headers.get(i, "") for i in range(1, sheet.max_column + 1)]
                if pivots:
                    # 先单独提取透视表，其他单元格仍按普通表头处理。
                    for left, _, right, bottom, first_data, pivot_headers in pivots:
                        pivot_rows = [
                            (number, [sheet.cell(number, column).value if sheet.cell(number, column).data_type != "f" else None
                                      for column in range(left, right + 1)])
                            for number in range(first_data, bottom + 1)
                        ]
                        tables.append((left - 1, pivot_headers, pivot_rows, []))
                    pivot_header_columns = {
                        column for left, top, right, bottom, _, _ in pivots
                        if top <= header_row_number <= bottom
                        for column in range(left, right + 1)
                    }
                    table_headers = [
                        "" if i in pivot_header_columns else value
                        for i, value in enumerate(table_headers, start=1)
                    ]
                for start, end in _parallel_identity_tables(sheet, header_row_number, table_headers, rows):
                    table_rows = [
                        (row[0].row, [
                            None if cell.data_type == "f" or any(left <= cell.column <= right and top <= cell.row <= bottom
                                        for left, top, right, bottom, _, _ in pivots)
                            else cell.value
                            for cell in row[start:end]
                        ])
                        for row in rows
                    ]
                    tables.append((start, table_headers[start:end], table_rows, []))
            if preserve_calculations:
                tables = [(start, names, [(number, [None if preserve_analysis_number(value, names[i]) else value
                                                    for i, value in enumerate(values)]) for number, values in rows], fields)
                          for start, names, rows, fields in tables]
            identity_tables[sheet.title] = (sheet_number, tables)
        # 先从全部工作表登记工号，再检查仅有邮箱的记录。
        for defer_email_only in (True, False):
            for sheet_number, tables in identity_tables.values():
                for start, table_headers, table_rows, field_rows in tables:
                    location = _identity_location(sheet_number, start, field_rows)
                    state.person_resolver.register(
                        table_headers, table_rows, defer_email_only=defer_email_only, location=location,
                    )

    people_by_key = {person.key: person for person in state.people}
    for worksheet in workbook.worksheets:
        resolved_header_row = header_row or _detect_xlsx_header_row(worksheet)
        header_by_column = _header_by_column(worksheet, header_row=resolved_header_row)
        pivots = pivots_by_sheet[worksheet.title]
        is_label_value = not pivots and detect_label_value_layout(worksheet, header_row=resolved_header_row)
        person_keys = {}
        if state.require_unique_people:
            sheet_number, tables = identity_tables[worksheet.title]
            for start, table_headers, table_rows, field_rows in tables:
                keys = state.person_resolver.keys(
                    table_headers, table_rows, location=_identity_location(sheet_number, start, field_rows),
                )
                person_keys.update({(position[0], start + position[1], *position[2:]): key
                                    for position, key in keys.items()})

        row_ids = {}
        for position, key in person_keys.items():
            person = people_by_key.get(key)
            if person and person.employee_id:
                row_ids.setdefault(position[0], set()).add(person.employee_id)

        if is_label_value:
            # 左右结构：A列=标签，B列=值，用标签决定值的实体类型
            for row in worksheet.iter_rows():
                if row and row[0].row <= resolved_header_row:
                    continue
                cells = list(row)
                if len(cells) < 2:
                    continue
                label_cell, value_cell = cells[0], cells[1]
                if label_cell.value is None or value_cell.value is None:
                    continue
                label_text = str(label_cell.value).strip()
                value_text = str(value_cell.value).strip()
                if not label_text or not value_text:
                    continue
                if preserve_calculations and preserve_analysis_number(value_cell.value, label_text):
                    continue
                entity_type = resolve_entity_from_label(
                    label_text,
                    anonymize_job_title=anonymize_job_title,
                    anonymize_department=anonymize_department,
                    anonymize_region=anonymize_region,
                    anonymize_salary=anonymize_salary,
                    keep_salary_groups=keep_salary_groups,
                )
                if entity_type is None:
                    continue
                if entity_type == EntityType.EMPLOYEE:
                    segments = _split_person_cell(value_text)
                    if len(segments) <= 1 or (state.require_unique_people and (0, table_headers.index(label_text)) in person_keys):
                        identity_key = None
                        if state.require_unique_people and label_text in table_headers:
                            identity_key = person_keys.get((0, table_headers.index(label_text)))
                        value_cell.value = state.token_for(EntityType.EMPLOYEE, value_text, identity_key=identity_key)
                    else:
                        validate = len(segments) >= _MULTI_NAME_SURNAME_CHECK_THRESHOLD
                        result = value_text
                        for i, seg in enumerate(segments):
                            identity_key = person_keys.get((0, table_headers.index(label_text), i)) if state.require_unique_people else None
                            token = _anonymize_person_segment(seg, validate_surname=validate, state=state, identity_key=identity_key)
                            if token is not None:
                                result = result.replace(seg, token, 1)
                        value_cell.value = result
                else:
                    value_cell.value = state.token_for(entity_type, value_text)
        else:
            # 标准结构：列头在上
            for row in worksheet.iter_rows():
                if not pivots and header_by_column and row and row[0].row <= resolved_header_row:
                    continue
                if any(cell.value is not None for cell in row) and (not header_by_column or row[0].row > resolved_header_row):
                    row_count += 1
                for cell in row:
                    if cell.value is None or cell.data_type == "f":
                        continue
                    text = str(cell.value).strip()
                    if not text:
                        continue
                    pivot_headers = next(
                        ((left, first_data, headers) for left, top, right, bottom, first_data, headers in pivots
                         if left <= cell.column <= right and top <= cell.row <= bottom),
                        None,
                    )
                    if pivot_headers is not None:
                        left, first_data, headers = pivot_headers
                        if cell.row < first_data:
                            continue
                        column_name = headers[cell.column - left]
                    else:
                        if header_by_column and cell.row <= resolved_header_row:
                            continue
                        column_name = header_by_column.get(cell.column, "")
                    inferred_type = identifier_cells.get((worksheet.title, cell.row, cell.column))
                    if inferred_type == EntityType.DEPARTMENT and not anonymize_department:
                        inferred_type = None
                    if (inferred_type is None and text in row_ids.get(cell.row, set())
                            and detect_column_entity_type(column_name) is None
                            and not any(term in column_name for term in ("期", "金额", "提成", "比例", "系数", "数", "率"))):
                        inferred_type = EntityType.EMPLOYEE_ID
                    if (preserve_calculations and preserve_analysis_number(cell.value, column_name)
                            and inferred_type not in {EntityType.EMPLOYEE_ID, EntityType.ID_NUMBER, EntityType.BANK_ACCOUNT, EntityType.EMAIL}):
                        continue
                    if is_pass_through_column(
                        column_name,
                        anonymize_job_title=anonymize_job_title,
                        anonymize_department=anonymize_department,
                        anonymize_region=anonymize_region,
                        anonymize_salary=anonymize_salary,
                        keep_salary_groups=keep_salary_groups,
                    ):
                        continue
                    column_type = inferred_type or detect_column_entity_type(column_name)
                    if text.lower() == column_name.lower() and column_type in {
                        EntityType.EMPLOYEE, EntityType.EMPLOYEE_ID, EntityType.EMAIL,
                    }:
                        continue
                    if (cell.row, cell.column - 1) in person_keys or any(
                        (cell.row, cell.column - 1, i) in person_keys for i in range(len(_split_person_cell(text)))
                    ):
                        column_type = EntityType.EMPLOYEE
                    if column_type is None and anonymize_job_title:
                        column_type = detect_optional_column_entity_type(column_name)
                    is_weak_person_column = column_type is None and detect_weak_person_column(column_name)
                    if column_type == EntityType.EMPLOYEE:
                        segments = _split_person_cell(text)
                        if len(segments) <= 1 or (
                            state.require_unique_people and (cell.row, cell.column - 1) in person_keys
                        ):
                            cell.value = state.token_for(
                                EntityType.EMPLOYEE, text,
                                identity_key=person_keys.get((cell.row, cell.column - 1)),
                            )
                        else:
                            validate = len(segments) >= _MULTI_NAME_SURNAME_CHECK_THRESHOLD
                            result = text
                            for i, seg in enumerate(segments):
                                token = _anonymize_person_segment(
                                    seg, validate_surname=validate, state=state,
                                    identity_key=person_keys.get((cell.row, cell.column - 1, i)),
                                )
                                if token is not None:
                                    result = result.replace(seg, token, 1)
                            cell.value = result
                    else:
                        # 列类型已知时：EMPLOYEE 已在上面处理；
                        # 其他类型（JOB_TITLE/DEPARTMENT/SALARY 等）直接用 column_type，不做内容二次校验。
                        # 当 column_type=None 时，用 detect_high_confidence_cell_entity_type 做回退检测。
                        entity_type = (
                            None
                            if (column_type == EntityType.DEPARTMENT and not anonymize_department)
                            or (column_type == EntityType.SALARY and not anonymize_salary)
                            else column_type
                        ) or detect_high_confidence_cell_entity_type(text)
                        if (
                            entity_type is None
                            and is_weak_person_column
                            and looks_like_short_chinese_person_name(text)
                        ):
                            entity_type = EntityType.EMPLOYEE
                        if entity_type is None:
                            continue
                        cell.value = state.token_for(entity_type, text)

        # 导出已脱敏的可见结果，移除可能携带原始数据的透视缓存与定义。
        worksheet._pivots.clear()

    if customer_names:
        customer_tokens = {name: state.token_for(EntityType.CUSTOMER, name) for name in customer_names}
        alternatives = []
        for name in sorted(customer_names, key=len, reverse=True):
            escaped = re.escape(name)
            if re.match(r"[A-Za-z0-9_]", name):
                escaped = r"(?<![A-Za-z0-9_])" + escaped
            if re.search(r"[A-Za-z0-9_]$", name):
                escaped += r"(?![A-Za-z0-9_])"
            alternatives.append(escaped)
        customer_pattern = re.compile(r"PDA_(?:REVIEW_)?[0-9A-F]{16}|" + "|".join(alternatives))
        def replace_customer(match):
            return customer_tokens.get(match.group(0), match.group(0))
        for sheet_number, sheet in enumerate(workbook.worksheets, 1):
            if customer_pattern.sub(replace_customer, sheet.title) != sheet.title:
                raise IdentityReviewError(f"待核验：第 {sheet_number} 张工作表名称含客户名称，请先改用不含客户名称的表名。")
            for row in sheet.iter_rows():
                for cell in row:
                    if isinstance(cell.value, str):
                        if cell.data_type == "f" and customer_pattern.sub(replace_customer, cell.value) != cell.value:
                            formula = Tokenizer(cell.value)
                            for token in formula.items:
                                if token.subtype == "TEXT":
                                    literal = token.value[1:-1].replace('""', '"')
                                    token.value = '"' + customer_pattern.sub(replace_customer, literal).replace('"', '""') + '"'
                                elif token.subtype == "RANGE" and customer_pattern.sub(replace_customer, token.value) != token.value:
                                    raise IdentityReviewError(f"待核验：第 {sheet_number} 张工作表 {cell.coordinate} 的公式引用名称含客户名称，请先调整引用名称。")
                            cell.value = formula.render()
                        elif cell.data_type != "f":
                            replaced = customer_pattern.sub(replace_customer, cell.value)
                            if replaced != cell.value:
                                cell.value = replaced
                                if preserve_calculations and cell.data_type == "f":
                                    cell.data_type = "s"
                    if cell.comment:
                        cell.comment.text = customer_pattern.sub(replace_customer, cell.comment.text)
                        if cell.comment.author:
                            cell.comment.author = customer_pattern.sub(replace_customer, cell.comment.author)

    if preserve_calculations:
        bindings = {}
        for entry in state.entries:
            if (entry.entity_type, entry.original, entry.identity_key) in state.current_entry_keys:
                bindings.setdefault(entry.original, set()).add((entry.entity_type, entry.token))
        person_names = {entry.original for entry in state.entries
                        if entry.entity_type == EntityType.EMPLOYEE and looks_like_short_chinese_person_name(entry.original)}

        def text_pattern(originals):
            alternatives = []
            for original in sorted(originals, key=len, reverse=True):
                escaped = re.escape(original)
                if re.match(r"[A-Za-z0-9_]", original):
                    escaped = r"(?<![A-Za-z0-9_])" + escaped
                if re.search(r"[A-Za-z0-9_]$", original):
                    escaped += r"(?![A-Za-z0-9_])"
                alternatives.append(escaped)
            return re.compile(r"PDA_(?:REVIEW_)?[0-9A-F]{16}|" + "|".join(alternatives)) if alternatives else None

        def identity_token(original, location):
            candidates = bindings.get(original, set())
            tokens = {token for _, token in candidates}
            if len(tokens) == 1 and not next(iter(tokens)).startswith("PDA_REVIEW_"):
                return next(iter(tokens))
            if candidates:
                if not state.person_resolver.allow_unverified_people:
                    raise IdentityReviewError(f"待核验：{location}中的文本条件无法唯一关联身份。")
                key = "unverified:" + uuid4().hex
                state.person_resolver.review_items[key] = {
                    "location": location, "reason": "文字或公式条件对应多个身份或待核验编号，请核对后再重算。",
                }
                kind = EntityType.EMPLOYEE if any(kind == EntityType.EMPLOYEE for kind, _ in candidates) else next(iter(candidates))[0]
            else:
                kind = EntityType.EMPLOYEE
                key = state.person_resolver.keys(["姓名"], [(0, [original])], location=lambda row, columns: location)[0, 0]
            token = state.token_for(kind, original, identity_key=key)
            bindings.setdefault(original, set()).add((kind, token))
            return token

        names_pattern = text_pattern(person_names)
        if names_pattern:
            for number, sheet in enumerate(workbook.worksheets, 1):
                for row in sheet.iter_rows():
                    for cell in row:
                        location = f"第 {number} 张工作表 {cell.coordinate}（文字中的姓名）"
                        replace_name = lambda match: identity_token(match.group(0), location) if match.group(0) in person_names else match.group(0)
                        if isinstance(cell.value, str):
                            replaced = names_pattern.sub(replace_name, cell.value)
                            if replaced != cell.value:
                                cell.value = replaced
                                if cell.data_type == "f":
                                    cell.data_type = "s"
                        if cell.comment:
                            cell.comment.text = names_pattern.sub(replace_name, cell.comment.text)
                            if cell.comment.author:
                                cell.comment.author = names_pattern.sub(replace_name, cell.comment.author)
        identities_pattern = text_pattern({original for original in bindings if len(original) >= 2 and not original.isdigit()})
        for number, sheet in enumerate(workbook.worksheets, 1):
            for address, original in original_formulas.get(sheet.title, {}).items():
                formula = Tokenizer(original)
                location = f"第 {number} 张工作表 {address}（公式文本条件）"
                for token in formula.items:
                    if token.subtype != "TEXT":
                        continue
                    literal = token.value[1:-1].replace('""', '"')
                    if preserve_analysis_number(literal, "金额"):
                        continue
                    if literal.strip() in bindings:
                        literal = identity_token(literal.strip(), location)
                    elif identities_pattern:
                        literal = identities_pattern.sub(lambda match: identity_token(match.group(0), location)
                                                         if match.group(0) in bindings else match.group(0), literal)
                    token.value = '"' + literal.replace('"', '""') + '"'
                original_formulas[sheet.title][address] = formula.render()

    output = BytesIO()
    workbook.save(output)
    workbook_bytes = output.getvalue()
    if preserve_calculations:
        workbook_bytes = _restore_formulas(workbook_bytes, original_formulas)
    return WorkbookAnonymizeResult(
        workbook_bytes=workbook_bytes,
        mapping=state.to_mapping_file(),
        review_items=state.review_items,
        formula_count=formula_count,
        external_link_count=external_link_count,
        localized_external_formula_count=localized_external_formula_count,
        external_value_count=external_value_count,
        row_count=row_count,
        preview_dataframe=_workbook_preview_dataframe(workbook_bytes, header_row=resolved_header_row, data_only=preserve_calculations),
    )


def anonymize_xlsx_file(
    input_path: str | Path,
    output_path: str | Path,
    seed_mapping: MappingFile | None = None,
    header_row: int | None = None,
    anonymize_job_title: bool = False,
    anonymize_department: bool = True,
    anonymize_region: bool = True,
    anonymize_salary: bool = True,
    keep_salary_groups: frozenset[SalaryGroup] = frozenset(),
    require_unique_people: bool = False,
    allow_unverified_people: bool = False,
    preserve_calculations: bool = False,
) -> WorkbookAnonymizeResult:
    content = Path(input_path).read_bytes()
    result = anonymize_xlsx_bytes(
        content,
        seed_mapping=seed_mapping,
        header_row=header_row,
        anonymize_job_title=anonymize_job_title,
        anonymize_department=anonymize_department,
        anonymize_region=anonymize_region,
        anonymize_salary=anonymize_salary,
        keep_salary_groups=keep_salary_groups,
        require_unique_people=require_unique_people,
        allow_unverified_people=allow_unverified_people,
        preserve_calculations=preserve_calculations,
    )
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_bytes(result.workbook_bytes)
    return result


def _detect_xlsx_header_row(worksheet) -> int:
    raw_rows: list[list[str]] = []
    for row in worksheet.iter_rows(min_row=1, max_row=3, values_only=True):
        raw_rows.append([str(c) if c is not None else "" for c in row])
    # Group titles may contain many entity keywords; prefer an actual identity header.
    for index, values in enumerate(raw_rows, 1):
        normalized = {value.strip().lower() for value in values}
        if normalized & EMPLOYEE_ID_HEADERS and normalized & (PRIMARY_NAME_HEADERS | EMPLOYEE_EMAIL_HEADERS):
            return index
    return detect_header_row(raw_rows)


def _header_by_column(worksheet, header_row: int = 1) -> dict[int, str]:
    """返回 {列号: 表头文本}，补齐合并单元格的 slave 列。"""
    header_iter = worksheet.iter_rows(min_row=header_row, max_row=header_row)
    first_row = next(header_iter, ())
    header = {
        cell.column: str(cell.value).strip()
        for cell in first_row
        if cell.value is not None and str(cell.value).strip()
    }
    # 补齐表头行的合并单元格：slave 列复用 master 列的文本
    if not hasattr(worksheet, "merged_cells"):
        return header
    for merged_range in worksheet.merged_cells.ranges:
        if not (merged_range.min_row <= header_row <= merged_range.max_row):
            continue
        master_col = merged_range.min_col
        master_text = None
        for cell in first_row:
            if cell.column == master_col and cell.value is not None:
                master_text = str(cell.value).strip()
                break
        if not master_text:
            continue
        for col in range(merged_range.min_col, merged_range.max_col + 1):
            if col not in header:
                header[col] = master_text
    return header


def _workbook_preview_dataframe(workbook_bytes: bytes, header_row: int = 1, data_only: bool = False) -> pd.DataFrame:
    workbook = load_workbook(BytesIO(workbook_bytes), data_only=data_only, read_only=True)
    rows: list[dict[str, object]] = []
    for worksheet in workbook.worksheets:
        header_by_column = _header_by_column(worksheet, header_row=header_row)
        for index, row in enumerate(worksheet.iter_rows(values_only=True), start=1):
            if header_by_column and index <= header_row:
                continue
            if not any(value is not None for value in row):
                continue
            item: dict[str, object] = {"sheet": worksheet.title}
            for column_index, value in enumerate(row, start=1):
                header = header_by_column.get(column_index) or f"column_{column_index}"
                item[str(header)] = value
            rows.append(item)
    return pd.DataFrame(rows)
