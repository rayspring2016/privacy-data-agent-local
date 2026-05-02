from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd

from privacy_data_agent.anonymizer import anonymize_dataframe
from privacy_data_agent.mapping_store import load_local_mapping, save_mapping_table
from privacy_data_agent.models import MappingFile
from privacy_data_agent.restorer import restore_report


def read_uploaded_table(filename: str, content: bytes) -> pd.DataFrame:
    suffix = Path(filename).suffix.lower()
    buffer = BytesIO(content)
    if suffix == ".csv":
        return pd.read_csv(buffer)
    if suffix == ".xlsx":
        return pd.read_excel(buffer)
    raise ValueError("Only .csv and .xlsx files are supported.")


def dataframe_to_xlsx_bytes(df: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="anonymized")
    return buffer.getvalue()


def mapping_to_table_csv_bytes(mapping: MappingFile) -> bytes:
    buffer = BytesIO()
    rows = [
        {"entity_type": entry.entity_type.value, "token": entry.token, "original": entry.original}
        for entry in mapping.entries
    ]
    pd.DataFrame(rows, columns=["entity_type", "token", "original"]).to_csv(buffer, index=False)
    return buffer.getvalue()


def anonymize_upload(filename: str, content: bytes) -> dict[str, bytes | str | int]:
    df = read_uploaded_table(filename, content)
    result = anonymize_dataframe(df)
    anonymized_csv = result.dataframe.to_csv(index=False).encode("utf-8-sig")
    return {
        "row_count": len(result.dataframe),
        "entity_count": len(result.mapping.entries),
        "anonymized_csv": anonymized_csv,
        "anonymized_xlsx": dataframe_to_xlsx_bytes(result.dataframe),
        "mapping_json": result.mapping.model_dump_json(indent=2),
        "mapping_table_csv": mapping_to_table_csv_bytes(result.mapping),
    }


def restore_report_upload(report_content: bytes, mapping_filename: str, mapping_content: bytes) -> str:
    report_text = report_content.decode("utf-8-sig")
    mapping_path = _write_temp_mapping(mapping_filename, mapping_content)
    mapping = load_local_mapping(mapping_path)
    return restore_report(report_text, mapping)


def _write_temp_mapping(filename: str, content: bytes) -> Path:
    from tempfile import NamedTemporaryFile

    suffix = Path(filename).suffix.lower()
    with NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(content)
        return Path(temp_file.name)
