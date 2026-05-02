from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook
from pydantic import BaseModel, ConfigDict

from privacy_data_agent.anonymizer import AnonymizerState
from privacy_data_agent.detectors import detect_cell_entity_type, detect_column_entity_type
from privacy_data_agent.models import MappingFile


class WorkbookAnonymizeResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    workbook_bytes: bytes
    mapping: MappingFile
    row_count: int
    preview_dataframe: pd.DataFrame


def anonymize_xlsx_bytes(
    content: bytes,
    seed_mapping: MappingFile | None = None,
) -> WorkbookAnonymizeResult:
    workbook = load_workbook(BytesIO(content))
    state = AnonymizerState(seed_mapping=seed_mapping)
    row_count = 0

    for worksheet in workbook.worksheets:
        header_by_column = _header_by_column(worksheet)
        header_row = 1 if header_by_column else None

        for row in worksheet.iter_rows():
            if header_row is not None and row and row[0].row == header_row:
                continue
            if any(cell.value is not None for cell in row):
                row_count += 1
            for cell in row:
                if cell.value is None or cell.data_type == "f":
                    continue
                text = str(cell.value).strip()
                if not text:
                    continue
                column_type = detect_column_entity_type(header_by_column.get(cell.column, ""))
                entity_type = column_type or detect_cell_entity_type(text)
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
        preview_dataframe=_workbook_preview_dataframe(workbook_bytes),
    )


def anonymize_xlsx_file(
    input_path: str | Path,
    output_path: str | Path,
    seed_mapping: MappingFile | None = None,
) -> WorkbookAnonymizeResult:
    content = Path(input_path).read_bytes()
    result = anonymize_xlsx_bytes(content, seed_mapping=seed_mapping)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_bytes(result.workbook_bytes)
    return result


def _header_by_column(worksheet) -> dict[int, str]:
    first_row = next(worksheet.iter_rows(min_row=1, max_row=1), ())
    return {
        cell.column: str(cell.value).strip()
        for cell in first_row
        if cell.value is not None and str(cell.value).strip()
    }


def _workbook_preview_dataframe(workbook_bytes: bytes) -> pd.DataFrame:
    workbook = load_workbook(BytesIO(workbook_bytes), data_only=False, read_only=True)
    rows: list[dict[str, object]] = []
    for worksheet in workbook.worksheets:
        header_by_column = _header_by_column(worksheet)
        for index, row in enumerate(worksheet.iter_rows(values_only=True), start=1):
            if index == 1 and header_by_column:
                continue
            if not any(value is not None for value in row):
                continue
            item: dict[str, object] = {"sheet": worksheet.title}
            for column_index, value in enumerate(row, start=1):
                header = header_by_column.get(column_index) or f"column_{column_index}"
                item[str(header)] = value
            rows.append(item)
    return pd.DataFrame(rows)
