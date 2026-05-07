from __future__ import annotations

import json
import zipfile
from io import BytesIO
from pathlib import Path

import pandas as pd
from cryptography.fernet import Fernet

from privacy_data_agent.anonymizer import anonymize_dataframe


def encrypt_mapping_json(mapping_json: str, key: str) -> bytes:
    """Encrypt a plain mapping JSON string into Fernet-encrypted bytes."""
    return Fernet(key.encode("utf-8")).encrypt(mapping_json.encode("utf-8"))


def decrypt_mapping_json(encrypted_bytes: bytes, key: str) -> str:
    """Decrypt Fernet-encrypted bytes back to a plain mapping JSON string."""
    return Fernet(key.encode("utf-8")).decrypt(encrypted_bytes).decode("utf-8")


def create_encrypted_zip_bundle(
    stem: str, anonymized_bytes: bytes, mapping_json: str, suffix: str, key: str
) -> bytes:
    """Create a ZIP bundle with the mapping inside encrypted."""
    anonymized_name = f"{stem}_anonymized{suffix}"
    if suffix == ".xlsx":
        file_desc = "脱敏后的 Excel 数据文件"
    elif suffix == ".docx":
        file_desc = "脱敏后的 Word 文档"
    elif suffix == ".pdf":
        file_desc = "脱敏后的 PDF 文档"
    else:
        file_desc = "脱敏后的数据文件"
    encrypted_mapping = encrypt_mapping_json(mapping_json, key)
    readme = (
        "脱敏数据包说明\n"
        "==============\n\n"
        f"原始文件：{stem}\n\n"
        "文件清单：\n"
        f"  {anonymized_name}  — {file_desc}，可安全发送给大模型或外部\n"
        "  mapping.local.json  — 加密匹配文件（含原始敏感信息，仅限本地保存）\n\n"
        "反脱敏步骤：\n"
        "  1. 打开脱敏工具，切换到「报告反脱敏」\n"
        "  2. 上传大模型返回的报告文件\n"
        "  3. 上传本包中的 mapping.local.json\n"
        "  4. 输入加密密钥（工具会自动生成并显示在界面）\n"
        "  5. 点击下载，即可还原真实姓名和信息\n\n"
        "注意：mapping.local.json 已加密，需使用相同密钥解密。\n"
        "      密钥请务必与 mapping.local.json 一起保存在本地，勿外传。\n"
    )
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(anonymized_name, anonymized_bytes)
        zf.writestr("mapping.local.json", encrypted_mapping)
        zf.writestr("README.txt", readme.encode("utf-8"))
    return buf.getvalue()
from privacy_data_agent.detectors import detect_header_row
from privacy_data_agent.mapping_store import load_local_mapping, save_mapping_table
from privacy_data_agent.models import MappingFile
from privacy_data_agent.restorer import restore_bytes, restore_report
from privacy_data_agent.workbook_anonymizer import anonymize_xlsx_bytes
from privacy_data_agent.document_anonymizer import (
    anonymize_docx_bytes,
    anonymize_pdf_bytes,
)


def read_uploaded_table(filename: str, content: bytes, header_row: int | None = None) -> pd.DataFrame:
    suffix = Path(filename).suffix.lower()
    buffer = BytesIO(content)
    if suffix == ".csv":
        return _read_uploaded_csv(buffer, header_row)
    if suffix == ".xlsx":
        return _read_uploaded_excel(buffer, header_row)
    if suffix == ".docx":
        from docx import Document
        doc = Document(BytesIO(content))
        texts = []
        for para in doc.paragraphs:
            if para.text.strip():
                texts.append(para.text.strip())
        return pd.DataFrame({"text": texts})
    raise ValueError("Only .csv, .xlsx, and .docx files are supported.")


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


def create_zip_bundle(stem: str, anonymized_bytes: bytes, mapping_json: str, suffix: str) -> bytes:
    anonymized_name = f"{stem}_anonymized{suffix}"
    if suffix == ".xlsx":
        file_desc = "脱敏后的 Excel 数据文件"
    elif suffix == ".docx":
        file_desc = "脱敏后的 Word 文档"
    elif suffix == ".pdf":
        file_desc = "脱敏后的 PDF 文档"
    else:
        file_desc = "脱敏后的数据文件"
    readme = (
        "脱敏数据包说明\n"
        "==============\n\n"
        f"原始文件：{stem}\n\n"
        "文件清单：\n"
        f"  {anonymized_name}  — {file_desc}，可安全发送给大模型或外部\n"
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
        zf.writestr(anonymized_name, anonymized_bytes)
        zf.writestr("mapping.local.json", mapping_json.encode("utf-8"))
        zf.writestr("README.txt", readme.encode("utf-8"))
    return buf.getvalue()


def anonymize_upload(
    filename: str,
    content: bytes,
    seed_mapping_filename: str | None = None,
    seed_mapping_content: bytes | None = None,
    header_row: int | None = None,
    encryption_key: str | None = None,
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
    elif suffix == ".docx":
        docx_result = anonymize_docx_bytes(content, seed_mapping=seed)
        result_mapping = docx_result.mapping
        row_count = docx_result.row_count
        preview_df = pd.DataFrame({"token": [e.token for e in result_mapping.entries]})
        anonymized_csv = preview_df.to_csv(index=False).encode("utf-8-sig")
        anonymized_docx = docx_result.workbook_bytes
    elif suffix == ".pdf":
        pdf_result = anonymize_pdf_bytes(content, seed_mapping=seed)
        result_mapping = pdf_result.mapping
        row_count = pdf_result.row_count
        preview_df = pd.DataFrame({"token": [e.token for e in result_mapping.entries]})
        anonymized_csv = preview_df.to_csv(index=False).encode("utf-8-sig")
        anonymized_pdf = pdf_result.workbook_bytes
    else:
        df = read_uploaded_table(filename, content, header_row=header_row)
        result = anonymize_dataframe(df, seed_mapping=seed)
        result_mapping = result.mapping
        row_count = len(result.dataframe)
        anonymized_csv = result.dataframe.to_csv(index=False).encode("utf-8-sig")
        anonymized_xlsx = dataframe_to_xlsx_bytes(result.dataframe)

    # Determine which anonymized file to use and its suffix
    if suffix == ".docx":
        anonymized_file = anonymized_docx
        file_suffix = ".docx"
    elif suffix == ".pdf":
        anonymized_file = anonymized_pdf
        file_suffix = ".pdf"
    else:
        anonymized_file = anonymized_xlsx
        file_suffix = ".xlsx"

    mapping_json = result_mapping.model_dump_json(indent=2)
    stem = Path(filename).stem
    new_count = len(result_mapping.entries) - (len(seed.entries) if seed else 0)

    # Use encrypted ZIP bundle if a key is provided; plain bundle otherwise.
    zip_bundle = (
        create_encrypted_zip_bundle(stem, anonymized_file, mapping_json, file_suffix, encryption_key)
        if encryption_key
        else create_zip_bundle(stem, anonymized_file, mapping_json, file_suffix)
    )

    # Also expose encrypted mapping JSON when key is provided (for direct download).
    encrypted_mapping_json = (
        encrypt_mapping_json(mapping_json, encryption_key) if encryption_key else None
    )

    return {
        "row_count": row_count,
        "entity_count": len(result_mapping.entries),
        "new_entity_count": new_count,
        "stem": stem,
        "file_suffix": file_suffix,
        "anonymized_csv": anonymized_csv,
        "anonymized_xlsx": anonymized_file,
        "mapping_json": mapping_json,
        "mapping_table_csv": mapping_to_table_csv_bytes(result_mapping),
        "zip_bundle": zip_bundle,
        "encrypted_mapping_json": encrypted_mapping_json,
    }


def merge_mapping_jsons(base_json: str, incoming_json: str) -> str:
    """
    Merge two mapping JSONs by original value, avoiding duplicate tokens.
    If the same original value appears in both, the base (earlier) token is kept.
    """
    base = json.loads(base_json)
    incoming = json.loads(incoming_json)

    # Build lookup: original → token (from base)
    seen: dict[str, dict] = {e["original"]: e for e in base["entries"]}

    for entry in incoming["entries"]:
        if entry["original"] not in seen:
            seen[entry["original"]] = entry

    base["entries"] = list(seen.values())
    return json.dumps(base, ensure_ascii=False, indent=2)


def anonymize_batch(
    files: list[tuple[str, bytes]],
    first_seed_filename: str | None = None,
    first_seed_content: bytes | None = None,
    header_row: int | None = None,
    encryption_key: str | None = None,
) -> dict:
    """
    Process multiple files sequentially, accumulating mapping across all files.
    Each file inherits the cumulative mapping from all previous files.
    Returns aggregate stats + final merged mapping + per-file results.
    """
    from privacy_data_agent.models import MappingFile

    # Load initial seed if provided
    accumulated: MappingFile | None = None
    if first_seed_filename and first_seed_content:
        seed_path = _write_temp_mapping(first_seed_filename, first_seed_content)
        accumulated = load_local_mapping(seed_path)

    results: list[dict] = []
    total_rows = 0
    total_new = 0
    total_all = 0

    for filename, content in files:
        suffix = Path(filename).suffix.lower()

        if suffix == ".xlsx":
            from privacy_data_agent.workbook_anonymizer import anonymize_xlsx_bytes

            wb_result = anonymize_xlsx_bytes(content, seed_mapping=accumulated, header_row=header_row)
            mapping = wb_result.mapping
            row_count = wb_result.row_count
            anonymized_bytes = wb_result.workbook_bytes
            preview_csv = wb_result.preview_dataframe.to_csv(index=False).encode("utf-8-sig")
        elif suffix == ".docx":
            from privacy_data_agent.document_anonymizer import anonymize_docx_bytes

            doc_result = anonymize_docx_bytes(content, seed_mapping=accumulated)
            mapping = doc_result.mapping
            row_count = doc_result.row_count
            anonymized_bytes = doc_result.workbook_bytes
            preview_df = pd.DataFrame({"token": [e.token for e in mapping.entries]})
            preview_csv = preview_df.to_csv(index=False).encode("utf-8-sig")
        elif suffix == ".pdf":
            from privacy_data_agent.document_anonymizer import anonymize_pdf_bytes

            pdf_result = anonymize_pdf_bytes(content, seed_mapping=accumulated)
            mapping = pdf_result.mapping
            row_count = pdf_result.row_count
            anonymized_bytes = pdf_result.workbook_bytes
            preview_df = pd.DataFrame({"token": [e.token for e in mapping.entries]})
            preview_csv = preview_df.to_csv(index=False).encode("utf-8-sig")
        else:
            df = read_uploaded_table(filename, content, header_row=header_row)
            result = anonymize_dataframe(df, seed_mapping=accumulated)
            mapping = result.mapping
            row_count = len(result.dataframe)
            preview_csv = result.dataframe.to_csv(index=False).encode("utf-8-sig")
            anonymized_bytes = dataframe_to_xlsx_bytes(result.dataframe)

        new_count = len(mapping.entries) - (len(accumulated.entries) if accumulated else 0)
        total_rows += row_count
        total_new += new_count
        total_all = len(mapping.entries)

        mapping_json = mapping.model_dump_json(indent=2)

        results.append({
            "stem": Path(filename).stem,
            "suffix": suffix,
            "row_count": row_count,
            "new_entity_count": new_count,
            "entity_count": len(mapping.entries),
            "anonymized_csv": preview_csv,
            "anonymized_bytes": anonymized_bytes,
            "mapping_json": mapping_json,
            "mapping_table_csv": mapping_to_table_csv_bytes(mapping),
            "zip_bundle": (
                create_encrypted_zip_bundle(
                    Path(filename).stem, anonymized_bytes, mapping_json, suffix, encryption_key
                )
                if encryption_key
                else create_zip_bundle(Path(filename).stem, anonymized_bytes, mapping_json, suffix)
            ),
            "encrypted_mapping_json": (
                encrypt_mapping_json(mapping_json, encryption_key) if encryption_key else None
            ),
        })

        # Accumulate mapping for next file
        if accumulated is None:
            accumulated = mapping
        else:
            merged = merge_mapping_jsons(accumulated.model_dump_json(indent=2), mapping_json)
            accumulated = MappingFile.model_validate_json(merged)

    final_mapping_json = accumulated.model_dump_json(indent=2) if accumulated else '{"version":1,"entries":[]}'

    # Build consolidated ZIP with all anonymized files + final mapping
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for r in results:
            zf.writestr(f"{r['stem']}_anonymized{r['suffix']}", r["anonymized_bytes"])
        zf.writestr("mapping.local.json", final_mapping_json.encode("utf-8"))
        zf.writestr(
            "README.txt",
            "批量脱敏数据包\n包含所有文件及统一匹配文件。\n".encode("utf-8"),
        )
    consolidated_zip = buf.getvalue()

    return {
        "files_processed": len(files),
        "total_rows": total_rows,
        "total_new_entities": total_new,
        "total_entities": total_all,
        "final_mapping_json": final_mapping_json,
        "consolidated_zip": consolidated_zip,
        "results": results,
    }


def restore_report_upload(
    report_content: bytes,
    report_filename: str,
    mapping_filename: str,
    mapping_content: bytes,
    decryption_key: str | None = None,
) -> dict[str, bytes | str]:
    # Attempt encrypted JSON first (Fernet-encrypted .json file), fall back to plain.
    mapping_path = _write_temp_mapping(mapping_filename, mapping_content)
    if decryption_key:
        try:
            mapping_json_str = decrypt_mapping_json(mapping_content, decryption_key)
            from privacy_data_agent.models import MappingFile

            mapping = MappingFile.model_validate_json(mapping_json_str)
        except Exception:
            # Not a valid encrypted JSON — fall back to plain load.
            mapping = load_local_mapping(mapping_path)
    else:
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
