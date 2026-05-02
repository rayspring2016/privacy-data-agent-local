from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path

import pandas as pd

from privacy_data_agent.anonymizer import anonymize_dataframe
from privacy_data_agent.mapping_store import load_local_mapping, save_mapping_table
from privacy_data_agent.models import MappingFile
from privacy_data_agent.restorer import restore_bytes, restore_report


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
) -> dict[str, bytes | str | int]:
    df = read_uploaded_table(filename, content)
    seed: MappingFile | None = None
    if seed_mapping_filename and seed_mapping_content:
        seed_path = _write_temp_mapping(seed_mapping_filename, seed_mapping_content)
        seed = load_local_mapping(seed_path)
    result = anonymize_dataframe(df, seed_mapping=seed)
    anonymized_csv = result.dataframe.to_csv(index=False).encode("utf-8-sig")
    anonymized_xlsx = dataframe_to_xlsx_bytes(result.dataframe)
    mapping_json = result.mapping.model_dump_json(indent=2)
    stem = Path(filename).stem
    new_count = len(result.mapping.entries) - (len(seed.entries) if seed else 0)
    return {
        "row_count": len(result.dataframe),
        "entity_count": len(result.mapping.entries),
        "new_entity_count": new_count,
        "stem": stem,
        "anonymized_csv": anonymized_csv,
        "anonymized_xlsx": anonymized_xlsx,
        "mapping_json": mapping_json,
        "mapping_table_csv": mapping_to_table_csv_bytes(result.mapping),
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
