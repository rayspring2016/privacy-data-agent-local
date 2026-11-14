from __future__ import annotations

import zipfile
import csv
from io import BytesIO, StringIO
from pathlib import Path

import pandas as pd
from cryptography.fernet import Fernet

from privacy_data_agent.anonymizer import anonymize_dataframe
from privacy_data_agent.detectors import SalaryGroup
from privacy_data_agent.identity_store import UnifiedIdentityStore
from privacy_data_agent.person_identity import IdentityReviewError


def encrypt_mapping_json(mapping_json: str, key: str) -> bytes:
    """Encrypt a plain mapping JSON string into Fernet-encrypted bytes."""
    return Fernet(key.encode("utf-8")).encrypt(mapping_json.encode("utf-8"))


def decrypt_mapping_json(encrypted_bytes: bytes, key: str) -> str:
    """Decrypt Fernet-encrypted bytes back to a plain mapping JSON string."""
    return Fernet(key.encode("utf-8")).decrypt(encrypted_bytes).decode("utf-8")


def create_encrypted_zip_bundle(
    stem: str, anonymized_bytes: bytes, mapping_json: str, suffix: str, key: str, review_csv: bytes = b"",
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
    if review_csv:
        readme += "\nidentity_review.csv 为待核验清单。PDA_REVIEW_ 是按出现位置生成的临时编号，不能用于跨项目人员合并。\n"
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(anonymized_name, anonymized_bytes)
        zf.writestr("mapping.local.json", encrypted_mapping)
        zf.writestr("README.txt", readme.encode("utf-8"))
        if review_csv:
            zf.writestr("identity_review.csv", review_csv)
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
    if suffix == ".numbers":  # Apple Numbers
        return _read_uploaded_numbers(buffer, header_row)
    if suffix == ".docx":
        from docx import Document
        doc = Document(BytesIO(content))
        texts = []
        for para in doc.paragraphs:
            if para.text.strip():
                texts.append(para.text.strip())
        return pd.DataFrame({"text": texts})
    raise ValueError("Only .csv, .xlsx, .numbers, and .docx files are supported.")


def _read_uploaded_csv(buffer: BytesIO, header_row: int | None) -> pd.DataFrame:
    text = _decode_csv_bytes(buffer.getvalue())
    if header_row is None:
        header_row = _detect_csv_header_row(text)
    return pd.read_csv(StringIO(text), header=max(0, header_row - 1), dtype=object)


def _decode_csv_bytes(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk", "big5"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8-sig", errors="replace")


def _detect_csv_header_row(text: str) -> int:
    lines = []
    reader = csv.reader(StringIO(text))
    for row in reader:
        if row:
            lines.append(row)
        if len(lines) >= 3:
            break
    if not lines:
        return 1
    return detect_header_row(lines)


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


def _read_uploaded_numbers(buffer: BytesIO, header_row: int | None) -> pd.DataFrame:
    """
    Read Apple Numbers .numbers file (ZIP containing index.xml).
    Extracts table data from the Numbers document XML structure.
    """
    import zipfile
    from xml.etree import ElementTree as ET

    buffer.seek(0)
    try:
        with zipfile.ZipFile(buffer) as zf:
            # Find the main table data file
            names = zf.namelist()
            # Numbers may store data in various places - look for table XML files
            table_file = None
            for name in names:
                if "Table" in name and name.endswith(".xml"):
                    table_file = name
                    break

            if table_file:
                with zf.open(table_file) as f:
                    tree = ET.parse(f)
                    root = tree.getroot()
                    rows = []
                    # Navigate XML structure (Numbers format varies, extract all text cells)
                    for elem in root.iter():
                        if elem.tag.endswith("}row") or elem.tag == "row":
                            row_data = []
                            for cell in elem:
                                text_parts = []
                                for t in cell.iter():
                                    if t.tag.endswith("}string") or t.tag == "string":
                                        if t.text:
                                            text_parts.append(t.text)
                                    elif t.tag.endswith("}real") or t.tag == "real":
                                        if t.text:
                                            row_data.append(t.text)
                                            break
                                if text_parts:
                                    row_data.append("".join(text_parts))
                            if row_data:
                                rows.append(row_data)
            else:
                # Fallback: try index.xml
                with zf.open("index.xml") as f:
                    tree = ET.parse(f)
                    root = tree.getroot()
                    rows = []
                    for elem in root.iter():
                        if elem.text and elem.text.strip():
                            # Simple text extraction
                            pass

            if rows:
                # Detect header row
                if header_row is None:
                    raw_rows = rows[:3]
                    header_row = detect_header_row(raw_rows)
                # Return as DataFrame
                max_cols = max(len(r) for r in rows) if rows else 0
                df_rows = []
                for i, row in enumerate(rows):
                    if i < header_row - 1:
                        continue
                    row_padded = row + [""] * (max_cols - len(row))
                    df_rows.append(row_padded)
                if df_rows:
                    # Use first row as header if header_row > 0
                    if header_row > 1:
                        df = pd.DataFrame(df_rows[1:], columns=df_rows[0])
                    else:
                        df = pd.DataFrame(df_rows)
                    return df

            # Final fallback: try to extract any tabular data
            with zf.open("index.xml") as f:
                content = f.read().decode("utf-8")
                # Parse as simple CSV-like structure
                lines = content.replace("><", ">\n<").split("\n")
                data_rows = []
                for line in lines:
                    if "<cell" in line:
                        # Extract cell values
                        import re
                        cells = re.findall(r'<cell[^>]*>(.*?)</cell>', line, re.DOTALL)
                        row = []
                        for cell in cells:
                            text = re.sub(r'<[^>]+>', '', cell).strip()
                            row.append(text)
                        if row:
                            data_rows.append(row)
                if data_rows:
                    if header_row is None:
                        raw_rows = data_rows[:3]
                        header_row = detect_header_row(raw_rows)
                    max_cols = max(len(r) for r in data_rows) if data_rows else 0
                    df_rows = []
                    for i, row in enumerate(data_rows):
                        if i < header_row - 1:
                            continue
                        row_padded = row + [""] * (max_cols - len(row))
                        df_rows.append(row_padded)
                    if df_rows:
                        if header_row > 1:
                            df = pd.DataFrame(df_rows[1:], columns=df_rows[0])
                        else:
                            df = pd.DataFrame(df_rows)
                        return df

    except Exception:
        pass

    # If all else fails, return empty DataFrame
    return pd.DataFrame()


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


def create_zip_bundle(stem: str, anonymized_bytes: bytes, mapping_json: str, suffix: str, review_csv: bytes = b"") -> bytes:
    anonymized_name = f"{stem}_anonymized{suffix}"
    if suffix == ".xlsx":
        file_desc = "脱敏后的 Excel 数据文件"
    elif suffix == ".numbers":
        file_desc = "脱敏后的 Numbers 数据文件"
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
    if review_csv:
        readme += "\nidentity_review.csv 为待核验清单。PDA_REVIEW_ 是按出现位置生成的临时编号，不能用于跨项目人员合并。\n"
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(anonymized_name, anonymized_bytes)
        zf.writestr("mapping.local.json", mapping_json.encode("utf-8"))
        if review_csv:
            zf.writestr("identity_review.csv", review_csv)
        zf.writestr("README.txt", readme.encode("utf-8"))
    return buf.getvalue()


def anonymize_upload(
    filename: str,
    content: bytes,
    seed_mapping_filename: str | None = None,
    seed_mapping_content: bytes | None = None,
    header_row: int | None = None,
    encryption_key: str | None = None,
    anonymize_job_title: bool = False,
    anonymize_department: bool = True,
    anonymize_salary: bool = True,
    keep_salary_groups: frozenset[SalaryGroup] = frozenset(),
    consistent_ids: bool = False,
    seed_mapping: MappingFile | None = None,
    require_unique_people: bool = False,
    allow_unverified_people: bool = False,
    preserve_calculations: bool = False,
) -> dict[str, bytes | str | int]:
    if preserve_calculations and Path(filename).suffix.lower() in {".docx", ".pdf"}:
        raise ValueError("分析核验模式需要结构化表格，不支持 DOCX/PDF。")
    seed: MappingFile | None = seed_mapping
    if seed is None and seed_mapping_filename and seed_mapping_content:
        seed_path = _write_temp_mapping(seed_mapping_filename, seed_mapping_content)
        seed = load_local_mapping(seed_path)
    if consistent_ids:
        if Path(filename).suffix.lower() in {".docx", ".pdf"}:
            raise ValueError("统一人员编号需要结构化表格，DOCX/PDF 请使用新编号模式。")
        with UnifiedIdentityStore(seed) as identities:
            result = anonymize_upload(
                filename, content, header_row=header_row, encryption_key=encryption_key,
                anonymize_job_title=anonymize_job_title,
                anonymize_department=anonymize_department,
                anonymize_salary=anonymize_salary, keep_salary_groups=keep_salary_groups,
                seed_mapping=identities.mapping, require_unique_people=True,
                allow_unverified_people=allow_unverified_people,
                preserve_calculations=preserve_calculations,
            )
            identities.save(MappingFile.model_validate_json(result["mapping_json"]))
            return result
    review_items = []
    formula_count = 0
    external_link_count = 0
    suffix = Path(filename).suffix.lower()
    if suffix == ".xlsx":
        workbook_result = anonymize_xlsx_bytes(
            content,
            seed_mapping=seed,
            header_row=header_row,
            anonymize_job_title=anonymize_job_title,
            anonymize_department=anonymize_department,
            anonymize_salary=anonymize_salary,
            keep_salary_groups=keep_salary_groups,
            require_unique_people=require_unique_people,
            allow_unverified_people=allow_unverified_people,
            preserve_calculations=preserve_calculations,
        )
        result_mapping = workbook_result.mapping
        review_items = workbook_result.review_items
        formula_count = workbook_result.formula_count
        external_link_count = workbook_result.external_link_count
        row_count = workbook_result.row_count
        anonymized_csv = workbook_result.preview_dataframe.to_csv(index=False).encode("utf-8-sig")
        anonymized_xlsx = workbook_result.workbook_bytes
    elif suffix == ".numbers":  # Apple Numbers - treat as CSV
        df = read_uploaded_table(filename, content, header_row=header_row)
        result = anonymize_dataframe(df, seed_mapping=seed, anonymize_job_title=anonymize_job_title, anonymize_department=anonymize_department, anonymize_salary=anonymize_salary, keep_salary_groups=keep_salary_groups, require_unique_people=require_unique_people, allow_unverified_people=allow_unverified_people, preserve_calculations=preserve_calculations)
        result_mapping = result.mapping
        review_items = result.review_items
        row_count = len(result.dataframe)
        anonymized_csv = result.dataframe.to_csv(index=False).encode("utf-8-sig")
        anonymized_xlsx = dataframe_to_xlsx_bytes(result.dataframe)
    elif suffix == ".et":  # WPS Spreadsheet (older .xls format via pandas)
        # .et is essentially a compressed format - try openpyxl first, fallback to pandas xlrd
        try:
            workbook_result = anonymize_xlsx_bytes(
                content,
                seed_mapping=seed,
                header_row=header_row,
                anonymize_job_title=anonymize_job_title,
                anonymize_department=anonymize_department,
                anonymize_salary=anonymize_salary,
                keep_salary_groups=keep_salary_groups,
                require_unique_people=require_unique_people,
                allow_unverified_people=allow_unverified_people,
                preserve_calculations=preserve_calculations,
            )
            result_mapping = workbook_result.mapping
            review_items = workbook_result.review_items
            formula_count = workbook_result.formula_count
            external_link_count = workbook_result.external_link_count
            row_count = workbook_result.row_count
            anonymized_csv = workbook_result.preview_dataframe.to_csv(index=False).encode("utf-8-sig")
            anonymized_xlsx = workbook_result.workbook_bytes
        except Exception:
            # Fallback: try pandas with xlrd (for older .xls format)
            buffer = BytesIO(content)
            xls_df = pd.read_excel(buffer, engine="xlrd")
            buffer.seek(0)
            result = anonymize_dataframe(xls_df, seed_mapping=seed, anonymize_job_title=anonymize_job_title, anonymize_department=anonymize_department, anonymize_salary=anonymize_salary, keep_salary_groups=keep_salary_groups, require_unique_people=require_unique_people, allow_unverified_people=allow_unverified_people, preserve_calculations=preserve_calculations)
            result_mapping = result.mapping
            review_items = result.review_items
            row_count = len(result.dataframe)
            anonymized_csv = result.dataframe.to_csv(index=False).encode("utf-8-sig")
            anonymized_xlsx = dataframe_to_xlsx_bytes(result.dataframe)
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
        result = anonymize_dataframe(df, seed_mapping=seed, anonymize_job_title=anonymize_job_title, anonymize_department=anonymize_department, anonymize_salary=anonymize_salary, keep_salary_groups=keep_salary_groups, require_unique_people=require_unique_people, allow_unverified_people=allow_unverified_people, preserve_calculations=preserve_calculations)
        result_mapping = result.mapping
        review_items = result.review_items
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
    review_csv = _review_csv_bytes(review_items)
    stem = Path(filename).stem
    new_count = len(result_mapping.entries) - (len(seed.entries) if seed else 0)

    # Use encrypted ZIP bundle if a key is provided; plain bundle otherwise.
    zip_bundle = (
        create_encrypted_zip_bundle(stem, anonymized_file, mapping_json, file_suffix, encryption_key, review_csv=review_csv)
        if encryption_key
        else create_zip_bundle(stem, anonymized_file, mapping_json, file_suffix, review_csv=review_csv)
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
        "review_count": len(review_items),
        "review_csv": review_csv,
        "formula_count": formula_count,
        "external_link_count": external_link_count,
        "preserve_calculations": preserve_calculations,
    }


def _review_csv_bytes(items: list[dict[str, str]]) -> bytes:
    if not items:
        return b""
    return pd.DataFrame(items, columns=["location", "token", "status", "reason"]).to_csv(index=False).encode("utf-8-sig")


def merge_mapping_jsons(base_json: str, incoming_json: str) -> str:
    """
    Merge identity-aware mappings, preserving homonyms and employee ID/email links.
    Conflicting historical identifiers are rejected.
    """
    from privacy_data_agent.identity_store import merge_identity_mappings

    merged = merge_identity_mappings(
        MappingFile.model_validate_json(base_json),
        MappingFile.model_validate_json(incoming_json),
    )
    return merged.model_dump_json(indent=2)



def anonymize_batch(
    files: list[tuple[str, bytes]],
    first_seed_filename: str | None = None,
    first_seed_content: bytes | None = None,
    header_row: int | None = None,
    encryption_key: str | None = None,
    anonymize_job_title: bool = False,
    anonymize_department: bool = True,
    anonymize_salary: bool = True,
    keep_salary_groups: frozenset[SalaryGroup] = frozenset(),
    consistent_ids: bool = False,
    seed_mapping: MappingFile | None = None,
    require_unique_people: bool = False,
    allow_unverified_people: bool = False,
    preserve_calculations: bool = False,
) -> dict:
    """
    Process multiple files sequentially, accumulating mapping across all files.
    Each file inherits the cumulative mapping from all previous files.
    Returns aggregate stats + final merged mapping + per-file results.
    """
    from privacy_data_agent.models import MappingFile

    # Load initial seed if provided
    accumulated: MappingFile | None = seed_mapping
    if accumulated is None and first_seed_filename and first_seed_content:
        seed_path = _write_temp_mapping(first_seed_filename, first_seed_content)
        accumulated = load_local_mapping(seed_path)
    if consistent_ids:
        with UnifiedIdentityStore(accumulated) as identities:
            result = anonymize_batch(
                files, header_row=header_row, encryption_key=encryption_key,
                anonymize_job_title=anonymize_job_title,
                anonymize_department=anonymize_department,
                anonymize_salary=anonymize_salary, keep_salary_groups=keep_salary_groups,
                seed_mapping=identities.mapping, require_unique_people=True,
                allow_unverified_people=allow_unverified_people,
                preserve_calculations=preserve_calculations,
            )
            if result["files_processed"]:
                identities.save(MappingFile.model_validate_json(result["final_mapping_json"]))
            return result

    results: list[dict] = []
    failures: list[dict] = []
    used_output_names: set[str] = set()
    total_rows = 0
    total_new = 0
    total_all = 0

    for index, (filename, content) in enumerate(files, start=1):
        review_items = []
        formula_count = 0
        external_link_count = 0
        suffix = Path(filename).suffix.lower()
        output_suffix = suffix

        try:
            if preserve_calculations and suffix in {".docx", ".pdf"}:
                raise IdentityReviewError("分析核验模式需要结构化表格，不支持 DOCX/PDF。")
            if require_unique_people and suffix in {".docx", ".pdf"}:
                raise IdentityReviewError("统一人员编号需要结构化表格，DOCX/PDF 请使用新编号模式。")
            if suffix == ".xlsx":
                from privacy_data_agent.workbook_anonymizer import anonymize_xlsx_bytes

                wb_result = anonymize_xlsx_bytes(
                    content,
                    seed_mapping=accumulated,
                    header_row=header_row,
                    anonymize_job_title=anonymize_job_title,
                    anonymize_department=anonymize_department,
                    anonymize_salary=anonymize_salary,
                    keep_salary_groups=keep_salary_groups,
                    require_unique_people=require_unique_people,
                    allow_unverified_people=allow_unverified_people,
                    preserve_calculations=preserve_calculations,
                )
                mapping = wb_result.mapping
                review_items = wb_result.review_items
                formula_count = wb_result.formula_count
                external_link_count = wb_result.external_link_count
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
                result = anonymize_dataframe(
                    df,
                    seed_mapping=accumulated,
                    anonymize_job_title=anonymize_job_title,
                    anonymize_department=anonymize_department,
                    anonymize_salary=anonymize_salary,
                    keep_salary_groups=keep_salary_groups,
                    require_unique_people=require_unique_people,
                    allow_unverified_people=allow_unverified_people,
                    preserve_calculations=preserve_calculations,
                )
                mapping = result.mapping
                review_items = result.review_items
                row_count = len(result.dataframe)
                preview_csv = result.dataframe.to_csv(index=False).encode("utf-8-sig")
                anonymized_bytes = dataframe_to_xlsx_bytes(result.dataframe)
                output_suffix = ".xlsx"
        except Exception as exc:
            reason = str(exc) if isinstance(exc, IdentityReviewError) else f"无法处理文件（{type(exc).__name__}）。"
            failures.append({"index": index, "name": filename, "reason": reason})
            continue

        new_count = len(mapping.entries) - (len(accumulated.entries) if accumulated else 0)
        total_rows += row_count
        total_new += new_count
        total_all = len(mapping.entries)

        mapping_json = mapping.model_dump_json(indent=2)
        review_csv = _review_csv_bytes(review_items)
        download_name = _unique_output_name(Path(filename).stem, output_suffix, used_output_names)

        results.append({
            "stem": Path(filename).stem,
            "suffix": output_suffix,
            "download_name": download_name,
            "row_count": row_count,
            "new_entity_count": new_count,
            "entity_count": len(mapping.entries),
            "anonymized_csv": preview_csv,
            "anonymized_bytes": anonymized_bytes,
            "mapping_json": mapping_json,
            "mapping_table_csv": mapping_to_table_csv_bytes(mapping),
            "review_count": len(review_items),
            "review_csv": review_csv,
            "formula_count": formula_count,
            "external_link_count": external_link_count,
            "zip_bundle": (
                create_encrypted_zip_bundle(
                    Path(filename).stem, anonymized_bytes, mapping_json, output_suffix, encryption_key, review_csv=review_csv,
                )
                if encryption_key
                else create_zip_bundle(Path(filename).stem, anonymized_bytes, mapping_json, output_suffix, review_csv=review_csv)
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
            zf.writestr(r["download_name"], r["anonymized_bytes"])
            if r["review_csv"]:
                zf.writestr(Path(r["download_name"]).stem + "_identity_review.csv", r["review_csv"])
        mapping_bytes = (
            encrypt_mapping_json(final_mapping_json, encryption_key)
            if encryption_key
            else final_mapping_json.encode("utf-8")
        )
        zf.writestr("mapping.local.json", mapping_bytes)
        zf.writestr(
            "README.txt",
            (
                "批量脱敏数据包\n包含所有文件及统一匹配文件。\n"
                + ("mapping.local.json 已加密，反脱敏时请输入同一密钥。\n" if encryption_key else "")
            ).encode("utf-8"),
        )
    consolidated_zip = buf.getvalue()

    return {
        "files_processed": len(results),
        "failures": failures,
        "total_rows": total_rows,
        "total_new_entities": total_new,
        "total_entities": total_all,
        "final_mapping_json": final_mapping_json,
        "consolidated_zip": consolidated_zip,
        "results": results,
        "review_count": sum(result["review_count"] for result in results),
        "formula_count": sum(result["formula_count"] for result in results),
        "external_link_count": sum(result["external_link_count"] for result in results),
        "preserve_calculations": preserve_calculations,
    }


def _unique_output_name(stem: str, suffix: str, used_names: set[str]) -> str:
    base = f"{stem}_anonymized"
    name = f"{base}{suffix}"
    index = 2
    while name in used_names:
        name = f"{base}_{index}{suffix}"
        index += 1
    used_names.add(name)
    return name


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
