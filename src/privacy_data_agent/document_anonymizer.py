from __future__ import annotations
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import re

import pandas as pd
from docx import Document

from privacy_data_agent.anonymizer import AnonymizerState
from privacy_data_agent.detectors import detect_cell_entity_type
from privacy_data_agent.models import EntityType, MappingFile


@dataclass
class DocumentAnonymizeResult:
    workbook_bytes: bytes  # docx: docx bytes; pdf: modified pdf bytes
    mapping: MappingFile
    row_count: int  # number of entities found


DOCUMENT_ENTITY_PATTERNS: tuple[tuple[re.Pattern[str], EntityType], ...] = (
    (re.compile(r"(?<!\d)\d{17}[\dXx](?![\dXx])"), EntityType.ID_NUMBER),
    (re.compile(r"(?<![\dA-Za-z])(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)"), EntityType.PHONE),
    (
        re.compile(r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![A-Za-z])"),
        EntityType.EMAIL,
    ),
    (
        re.compile(r"(?<![A-Z0-9一-龥])[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉贵粤青藏川宁琼使领][A-Z][A-Z0-9]{5}(?![A-Z0-9])"),
        EntityType.LICENSE_PLATE,
    ),
    (re.compile(r"(?<![A-Za-z0-9])[A-Za-z]{1,3}\d{4,10}(?![A-Za-z0-9])"), EntityType.EMPLOYEE_ID),
)
LABELED_CHINESE_NAME_RE = re.compile(
    r"(?:姓名|员工|人员|负责人|联系人|对接人|客户经理|顾问|name|employee|owner|manager)(?:\s*[:：=]\s*|\s+)([一-龥]{2,4})",
    re.IGNORECASE,
)


def _entity_spans(text: str) -> list[tuple[int, int, EntityType, str]]:
    if not text:
        return []

    candidates: list[tuple[int, int, EntityType, str]] = []
    stripped = text.strip()
    if stripped:
        entity_type = detect_cell_entity_type(stripped)
        if entity_type:
            start = len(text) - len(text.lstrip())
            candidates.append((start, start + len(stripped), entity_type, stripped))

    for pattern, entity_type in DOCUMENT_ENTITY_PATTERNS:
        for match in pattern.finditer(text):
            candidates.append((match.start(), match.end(), entity_type, match.group(0)))

    for match in LABELED_CHINESE_NAME_RE.finditer(text):
        candidates.append((match.start(1), match.end(1), EntityType.EMPLOYEE, match.group(1)))

    accepted: list[tuple[int, int, EntityType, str]] = []
    for candidate in sorted(candidates, key=lambda item: (item[0], -(item[1] - item[0]))):
        start, end, _, _ = candidate
        if any(start < accepted_end and end > accepted_start for accepted_start, accepted_end, _, _ in accepted):
            continue
        accepted.append(candidate)
    return sorted(accepted, key=lambda item: item[0])


def _register_entities_in_text(text: str, state: AnonymizerState) -> None:
    for _, _, entity_type, original in _entity_spans(text):
        state.token_for(entity_type, original)


def _replace_entities_in_text(text: str, state: AnonymizerState) -> tuple[str, bool]:
    spans = _entity_spans(text)
    if not spans:
        return text, False

    parts: list[str] = []
    cursor = 0
    for start, end, entity_type, original in spans:
        parts.append(text[cursor:start])
        parts.append(state.token_for(entity_type, original))
        cursor = end
    parts.append(text[cursor:])
    return "".join(parts), True


def _anonymize_pdf_with_pymupdf(content: bytes, seed_mapping: MappingFile | None = None) -> DocumentAnonymizeResult:
    import fitz

    state = AnonymizerState(seed_mapping=seed_mapping)
    doc = fitz.open(stream=content, filetype="pdf")
    redactions_by_page: dict[int, list[tuple[object, str]]] = {}

    for page_index, page in enumerate(doc):
        text = page.get_text("text") or ""
        _register_entities_in_text(text, state)

        for entry in state.entries:
            rects = page.search_for(entry.original)
            if not rects:
                continue
            redactions_by_page.setdefault(page_index, [])
            for rect in rects:
                redactions_by_page[page_index].append((rect, entry.token))
                page.add_redact_annot(rect, fill=(1, 1, 1))

    for page_index, redactions in redactions_by_page.items():
        page = doc[page_index]
        page.apply_redactions()
        for rect, token in redactions:
            token_rect = fitz.Rect(rect.x0, rect.y0 - 1, max(rect.x1 + 80, rect.x0 + 140), rect.y1 + 8)
            page.insert_textbox(token_rect, token, fontsize=7, fontname="helv", color=(0, 0, 0), align=0)

    return DocumentAnonymizeResult(
        workbook_bytes=doc.tobytes(garbage=4, deflate=True),
        mapping=state.to_mapping_file(),
        row_count=len(state.entries),
    )


def anonymize_docx_bytes(content: bytes, seed_mapping: MappingFile | None = None) -> DocumentAnonymizeResult:
    state = AnonymizerState(seed_mapping=seed_mapping)
    doc = Document(BytesIO(content))

    def _patch_paragraph(para) -> None:
        for run in para.runs:
            original = run.text or ""
            if original.strip():
                replaced, changed = _replace_entities_in_text(original, state)
                if changed:
                    run.text = replaced

    for para in doc.paragraphs:
        _patch_paragraph(para)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    _patch_paragraph(para)

    buf = BytesIO()
    doc.save(buf)
    return DocumentAnonymizeResult(
        workbook_bytes=buf.getvalue(),
        mapping=state.to_mapping_file(),
        row_count=len(state.entries),
    )


def anonymize_pdf_bytes(content: bytes, seed_mapping: MappingFile | None = None) -> DocumentAnonymizeResult:
    try:
        return _anonymize_pdf_with_pymupdf(content, seed_mapping=seed_mapping)
    except ImportError:
        pass

    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import ArrayObject, ByteStringObject, ContentStream, TextStringObject

    state = AnonymizerState(seed_mapping=seed_mapping)
    reader = PdfReader(BytesIO(content))
    writer = PdfWriter()

    # First pass: extract text properly and detect entities
    all_lines: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            all_lines.extend(text.split("\n"))
        else:
            # Fallback: raw stream for text-based PDFs where extract_text fails
            try:
                if "/Contents" in page:
                    from pypdf.generic import ArrayObject

                    contents = page["/Contents"]
                    if isinstance(contents, ArrayObject):
                        for item in contents:
                            obj = item.get_object() if hasattr(item, "get_object") else item
                            raw = obj.get_data()
                            # Try utf-8-sig first (common for Chinese PDFs)
                            decoded = raw.decode("utf-8-sig", errors="")
                            if decoded.strip():
                                all_lines.extend(decoded.split("\n"))
                            else:
                                decoded = raw.decode("latin-1", errors="")
                                if decoded.strip():
                                    all_lines.extend(decoded.split("\n"))
            except Exception:
                pass

    for line in all_lines:
        _register_entities_in_text(line, state)

    def _replace_pdf_text_operand(operand):
        if isinstance(operand, TextStringObject):
            replaced, changed = _replace_entities_in_text(str(operand), state)
            return TextStringObject(replaced), changed
        if isinstance(operand, ByteStringObject):
            try:
                text = bytes(operand).decode("latin-1")
            except Exception:
                return operand, False
            replaced, changed = _replace_entities_in_text(text, state)
            return TextStringObject(replaced), changed
        return operand, False

    def _replace_page_text(page) -> None:
        contents = page.get_contents()
        if contents is None:
            return
        content_stream = ContentStream(contents, reader)
        changed = False
        for operands, operator in content_stream.operations:
            if operator in (b"Tj", b"'") and operands:
                operands[0], operand_changed = _replace_pdf_text_operand(operands[0])
                changed = changed or operand_changed
            elif operator == b'"' and operands:
                operands[-1], operand_changed = _replace_pdf_text_operand(operands[-1])
                changed = changed or operand_changed
            elif operator == b"TJ" and operands and isinstance(operands[0], ArrayObject):
                for index, item in enumerate(operands[0]):
                    operands[0][index], operand_changed = _replace_pdf_text_operand(item)
                    changed = changed or operand_changed
        if changed:
            page.replace_contents(content_stream)

    # Second pass: copy pages and replace text in parseable PDF content streams.
    for page in reader.pages:
        writer.add_page(page)
        _replace_page_text(writer.pages[-1])

    buf = BytesIO()
    writer.write(buf)
    return DocumentAnonymizeResult(
        workbook_bytes=buf.getvalue(),
        mapping=state.to_mapping_file(),
        row_count=len(state.entries),
    )
