from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook
from pydantic import BaseModel, ConfigDict

from privacy_data_agent.anonymizer import AnonymizerState
from privacy_data_agent.detectors import (
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
)
from privacy_data_agent.models import EntityType, MappingFile

# Delimiters used to split multi-name cells in person columns
_NAME_SPLIT_RE = re.compile(r"[、，；,;/|]+")

# Cells with ≥ this many name segments get SURNAME_SET validation (防止大列表误报)
_MULTI_NAME_SURNAME_CHECK_THRESHOLD = 5


def _split_person_cell(text: str) -> list[str]:
    """Return non-empty segments after splitting on name delimiters."""
    return [s.strip() for s in _NAME_SPLIT_RE.split(text) if s.strip()]


def _anonymize_person_segment(
    segment: str, validate_surname: bool, state: AnonymizerState
) -> str | None:
    """Return a token for segment, or None if it should be kept unchanged.

    Always requires 2-4 Chinese characters. When validate_surname is True,
    also requires _looks_like_chinese_name() (surname check).
    """
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


def anonymize_xlsx_bytes(
    content: bytes,
    seed_mapping: MappingFile | None = None,
    header_row: int | None = None,
    anonymize_job_title: bool = False,
    anonymize_department: bool = True,
    anonymize_region: bool = True,
    keep_salary_groups: frozenset[SalaryGroup] = frozenset(),
) -> WorkbookAnonymizeResult:
    workbook = load_workbook(BytesIO(content))
    state = AnonymizerState(seed_mapping=seed_mapping)
    row_count = 0

    for worksheet in workbook.worksheets:
        resolved_header_row = header_row or _detect_xlsx_header_row(worksheet)
        header_by_column = _header_by_column(worksheet, header_row=resolved_header_row)
        is_label_value = detect_label_value_layout(worksheet, header_row=resolved_header_row)

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
                entity_type = resolve_entity_from_label(
                    label_text,
                    anonymize_job_title=anonymize_job_title,
                    anonymize_department=anonymize_department,
                    anonymize_region=anonymize_region,
                    keep_salary_groups=keep_salary_groups,
                )
                if entity_type is None:
                    continue
                if entity_type == EntityType.EMPLOYEE:
                    segments = _split_person_cell(value_text)
                    if len(segments) <= 1:
                        value_cell.value = state.token_for(EntityType.EMPLOYEE, value_text)
                    else:
                        validate = len(segments) >= _MULTI_NAME_SURNAME_CHECK_THRESHOLD
                        result = value_text
                        for seg in segments:
                            token = _anonymize_person_segment(seg, validate_surname=validate, state=state)
                            if token is not None:
                                result = result.replace(seg, token, 1)
                        value_cell.value = result
                else:
                    value_cell.value = state.token_for(entity_type, value_text)
        else:
            # 标准结构：列头在上
            for row in worksheet.iter_rows():
                if header_by_column and row and row[0].row <= resolved_header_row:
                    continue
                if any(cell.value is not None for cell in row):
                    row_count += 1
                for cell in row:
                    if cell.value is None or cell.data_type == "f":
                        continue
                    text = str(cell.value).strip()
                    if not text:
                        continue
                    column_name = header_by_column.get(cell.column, "")
                    if is_pass_through_column(
                        column_name,
                        anonymize_job_title=anonymize_job_title,
                        anonymize_department=anonymize_department,
                        anonymize_region=anonymize_region,
                        keep_salary_groups=keep_salary_groups,
                    ):
                        continue
                    column_type = detect_column_entity_type(column_name)
                    if column_type is None and anonymize_job_title:
                        column_type = detect_optional_column_entity_type(column_name)
                    is_weak_person_column = column_type is None and detect_weak_person_column(column_name)
                    if column_type == EntityType.EMPLOYEE:
                        segments = _split_person_cell(text)
                        if len(segments) <= 1:
                            cell.value = state.token_for(EntityType.EMPLOYEE, text)
                        else:
                            validate = len(segments) >= _MULTI_NAME_SURNAME_CHECK_THRESHOLD
                            result = text
                            for seg in segments:
                                token = _anonymize_person_segment(seg, validate_surname=validate, state=state)
                                if token is not None:
                                    result = result.replace(seg, token, 1)
                            cell.value = result
                    else:
                        # 列类型已知时：EMPLOYEE 已在上面处理；
                        # 其他类型（JOB_TITLE/DEPARTMENT 等）直接用 column_type，不做内容二次校验。
                        # 当 column_type=None 时，用 detect_high_confidence_cell_entity_type 做回退检测。
                        entity_type = (
                            None
                            if column_type == EntityType.DEPARTMENT and not anonymize_department
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

    output = BytesIO()
    workbook.save(output)
    workbook_bytes = output.getvalue()
    return WorkbookAnonymizeResult(
        workbook_bytes=workbook_bytes,
        mapping=state.to_mapping_file(),
        row_count=row_count,
        preview_dataframe=_workbook_preview_dataframe(workbook_bytes, header_row=resolved_header_row),
    )


def anonymize_xlsx_file(
    input_path: str | Path,
    output_path: str | Path,
    seed_mapping: MappingFile | None = None,
    header_row: int | None = None,
    anonymize_job_title: bool = False,
    anonymize_department: bool = True,
    anonymize_region: bool = True,
    keep_salary_groups: frozenset[SalaryGroup] = frozenset(),
) -> WorkbookAnonymizeResult:
    content = Path(input_path).read_bytes()
    result = anonymize_xlsx_bytes(
        content,
        seed_mapping=seed_mapping,
        header_row=header_row,
        anonymize_job_title=anonymize_job_title,
        anonymize_department=anonymize_department,
        anonymize_region=anonymize_region,
        keep_salary_groups=keep_salary_groups,
    )
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_bytes(result.workbook_bytes)
    return result


def _detect_xlsx_header_row(worksheet) -> int:
    raw_rows: list[list[str]] = []
    for row in worksheet.iter_rows(min_row=1, max_row=3, values_only=True):
        raw_rows.append([str(c) if c is not None else "" for c in row])
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


def _workbook_preview_dataframe(workbook_bytes: bytes, header_row: int = 1) -> pd.DataFrame:
    workbook = load_workbook(BytesIO(workbook_bytes), data_only=False, read_only=True)
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
