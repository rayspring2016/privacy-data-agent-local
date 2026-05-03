from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path

import pandas as pd

from privacy_data_agent.anonymizer import anonymize_dataframe
from privacy_data_agent.detectors import detect_header_row
from privacy_data_agent.mapping_store import load_local_mapping, save_mapping_table
from privacy_data_agent.models import MappingFile
from privacy_data_agent.restorer import restore_bytes, restore_report
from privacy_data_agent.workbook_anonymizer import anonymize_xlsx_bytes


def read_uploaded_table(filename: str, content: bytes, header_row: int | None = None) -> pd.DataFrame:
    suffix = Path(filename).suffix.lower()
    buffer = BytesIO(content)
    if suffix == ".csv":
        return _read_uploaded_csv(buffer, header_row)
    if suffix == ".xlsx":
        return _read_uploaded_excel(buffer, header_row)
    raise ValueError("Only .csv and .xlsx files are supported.")


def _read_uploaded_csv(buffer: BytesIO, header_row: int | None) -> pd.DataFrame:
    if header_row is None:
        header_row = _detect_csv_header_row(buffer)
        buffer.seek(0)
    return pd.read_csv(buffer, header=max(0, header_row - 1))


def _detect_csv_header_row(buffer: BytesIO) -> int:
    lines = []
    for _ in range(3):
        line = buffer.readline()
        if line:
            lines.append(line.decode("utf-8-sig").strip())
    if not lines:
        return 1
    raw_rows = [line.split(",") for line in lines]
    return detect_header_row(raw_rows)


def _read_uploaded_excel(buffer: BytesIO, header_row: int | None) -> pd.DataFrame:
    if header_row is None:
        raw = pd.read_excel(buffer, header=None, nrows=3, engine="openpyxl")
        buffer.seek(0)
        raw_rows = [
            [str(c) if pd.notna(c) else "" for c in raw.iloc[i].tolist()]
            for i in range(min(3, len(raw)))
        ]
        header_row = detect_header_row(raw_rows)
    return pd.read_excel(buffer, header=max(0, header_row - 1))


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


def create_zip_bundle(stem: str, anonymized_xlsx: bytes, mapping_json: str) -> bytes:
    readme = (
        "脱敏数据包说明\n"
        "==============\n\n"
        f"原始文件：{stem}\n\n"
        "文件清单：\n"
        "  anonymized.xlsx     — 脱敏后的数据文件，可安全发送给大模型或外部\n"
        "  mapping.local.json  — 匹配文件（含原始敏感信息，仅限本地保存）\n\n"
        "反脱敏步骤：\n"
        "  1. 打开脱敏工具，切换到「报告反脱敏」\n"
        "  2. 上传大模型返回的报告文件\n"
        "  3. 上传本包中的 mapping.local.json\n"
        "  4. 点击下载，即可还原真实姓名和信息\n\n"
        "注意：mapping.local.json 含原始敏感数据，请勿外传。\n"
    )
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("anonymized.xlsx", anonymized_xlsx)
        zf.writestr("mapping.local.json", mapping_json.encode("utf-8"))
        zf.writestr("README.txt", readme.encode("utf-8"))
    return buf.getvalue()


def anonymize_upload(
    filename: str,
    content: bytes,
    seed_mapping_filename: str | None = None,
    seed_mapping_content: bytes | None = None,
    header_row: int | None = None,
) -> dict[str, bytes | str | int]:
    seed: MappingFile | None = None
    if seed_mapping_filename and seed_mapping_content:
        seed_path = _write_temp_mapping(seed_mapping_filename, seed_mapping_content)
        seed = load_local_mapping(seed_path)
    suffix = Path(filename).suffix.lower()
    if suffix == ".xlsx":
        workbook_result = anonymize_xlsx_bytes(content, seed_mapping=seed, header_row=header_row)
        result_mapping = workbook_result.mapping
        row_count = workbook_result.row_count
        anonymized_csv = workbook_result.preview_dataframe.to_csv(index=False).encode("utf-8-sig")
        anonymized_xlsx = workbook_result.workbook_bytes
    else:
        df = read_uploaded_table(filename, content, header_row=header_row)
        result = anonymize_dataframe(df, seed_mapping=seed)
        result_mapping = result.mapping
        row_count = len(result.dataframe)
        anonymized_csv = result.dataframe.to_csv(index=False).encode("utf-8-sig")
        anonymized_xlsx = dataframe_to_xlsx_bytes(result.dataframe)
    mapping_json = result_mapping.model_dump_json(indent=2)
    stem = Path(filename).stem
    new_count = len(result_mapping.entries) - (len(seed.entries) if seed else 0)
    return {
        "row_count": row_count,
        "entity_count": len(result_mapping.entries),
        "new_entity_count": new_count,
        "stem": stem,
        "anonymized_csv": anonymized_csv,
        "anonymized_xlsx": anonymized_xlsx,
        "mapping_json": mapping_json,
        "mapping_table_csv": mapping_to_table_csv_bytes(result_mapping),
        "zip_bundle": create_zip_bundle(stem, anonymized_xlsx, mapping_json),
    }


def restore_report_upload(
    report_content: bytes,
    report_filename: str,
    mapping_filename: str,
    mapping_content: bytes,
) -> dict[str, bytes | str]:
    mapping_path = _write_temp_mapping(mapping_filename, mapping_content)
    mapping = load_local_mapping(mapping_path)
    restored = restore_bytes(report_content, report_filename, mapping)
    stem = Path(report_filename).stem
    suffix = Path(report_filename).suffix.lower()
    return {"content": restored, "filename": f"{stem}.restored{suffix}"}


def _write_temp_mapping(filename: str, content: bytes) -> Path:
    from tempfile import NamedTemporaryFile

    suffix = Path(filename).suffix.lower()
    with NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(content)
        return Path(temp_file.name)
