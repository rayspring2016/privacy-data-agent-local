from __future__ import annotations
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import pandas as pd
from docx import Document

from privacy_data_agent.anonymizer import AnonymizerState
from privacy_data_agent.models import MappingFile
from privacy_data_agent.text_anonymizer import (
    LABELED_CHINESE_NAME_RE,  # 单独导入：_find_entity_in_span(下方)也直接用它，
                               # 不只是 register/replace_entities_in_text 内部用
    register_entities_in_text,
    replace_entities_in_text,
)


@dataclass
class DocumentAnonymizeResult:
    workbook_bytes: bytes  # docx: docx bytes; pdf: modified pdf bytes
    mapping: MappingFile
    row_count: int  # number of entities found


def _extract_page_text_multi(page) -> str:
    """Try every available method to extract text from a PDF page."""
    results: list[str] = []

    # Method 1: standard text extraction
    text = page.get_text("text") or ""
    if text.strip():
        results.append(text)

    # Method 2: raw dict — iterate all chars to reconstruct text
    try:
        raw = page.get_text("rawdict")
        chars: list[str] = []
        for block in raw.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    for char in span.get("chars", []):
                        c = char.get("c", "")
                        if c:
                            chars.append(c)
                chars.append("\n")
        raw_text = "".join(chars).strip()
        if raw_text:
            results.append(raw_text)
    except Exception:
        pass

    # Method 3: text as XML and extract text nodes
    try:
        xml = page.get_text("xml")
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml)
        xml_parts: list[str] = []
        for elem in root.iter():
            if elem.text and elem.text.strip():
                xml_parts.append(elem.text.strip())
        xml_text = "\n".join(xml_parts)
        if xml_text and xml_text not in results:
            results.append(xml_text)
    except Exception:
        pass

    return "\n".join(results)


def _find_entity_in_span(span_text: str, token_by_original: dict[str, str]) -> str | None:
    """Check if span_text (or a cleaned variant) matches a known entity."""
    if span_text in token_by_original:
        return span_text
    # Also try LABELED_CHINESE_NAME_RE to extract name from "姓名：张三"
    for match in LABELED_CHINESE_NAME_RE.finditer(span_text):
        name = match.group(1)
        if name in token_by_original:
            return name
    return None


def _locate_entity_chars(
    span_chars: list[tuple[str, object]],
    span_text: str,
    original: str,
) -> list[tuple[str, object]]:
    """Find the character subset in span_chars that corresponds to original text."""
    pos = span_text.find(original)
    if pos < 0:
        return []
    return span_chars[pos : pos + len(original)]


def _anonymize_pdf_with_pymupdf(content: bytes, seed_mapping: MappingFile | None = None) -> DocumentAnonymizeResult:
    import fitz

    state = AnonymizerState(seed_mapping=seed_mapping)
    doc = fitz.open(stream=content, filetype="pdf")

    # Pass 1: register all entities across all pages using multi-method extraction
    for page in doc:
        text = _extract_page_text_multi(page)
        if text:
            register_entities_in_text(text, state)

    # Build lookup: token by original text
    token_by_original: dict[str, str] = {}
    for entry in state.entries:
        token_by_original[entry.original] = entry.token

    # Pass 2: position-driven redaction. Use direct text matching:
    # for each span, check if its text (exact or cleaned) matches
    # a known entity from Pass 1. Also check line-level for
    # entities that span across multiple spans.
    redactions_by_page: dict[int, list[tuple[fitz.Rect, str]]] = {}
    _redacted: set[tuple[int, float, float, float, float]] = set()

    for page_index, page in enumerate(doc):
        try:
            raw = page.get_text("rawdict")
        except Exception:
            continue

        for block in raw.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                # --- Span-level: direct text lookup ---
                for span in line.get("spans", []):
                    span_chars = []
                    for char in span.get("chars", []):
                        c = char.get("c", "")
                        bbox = char.get("bbox")
                        if c and bbox:
                            span_chars.append((c, fitz.Rect(bbox)))
                    if not span_chars:
                        continue

                    span_text = "".join(c for c, _ in span_chars)
                    original = _find_entity_in_span(span_text, token_by_original)
                    if original is None:
                        continue

                    token = token_by_original[original]
                    entity_chars = _locate_entity_chars(span_chars, span_text, original)
                    if not entity_chars:
                        continue
                    x0 = min(bbox.x0 for _, bbox in entity_chars)
                    y0 = min(bbox.y0 for _, bbox in entity_chars)
                    x1 = max(bbox.x1 for _, bbox in entity_chars)
                    y1 = max(bbox.y1 for _, bbox in entity_chars)
                    _key = (page_index, x0, y0, x1, y1)
                    if _key in _redacted:
                        continue
                    _redacted.add(_key)
                    redact_rect = fitz.Rect(x0, y0 - 1, x1, y1 + 1)
                    redactions_by_page.setdefault(page_index, []).append((redact_rect, token))
                    page.add_redact_annot(redact_rect, fill=(1, 1, 1))

                # --- Line-level: for entities spanning multiple spans ---
                line_chars = []
                for span in line.get("spans", []):
                    for char in span.get("chars", []):
                        c = char.get("c", "")
                        bbox = char.get("bbox")
                        if c and bbox:
                            line_chars.append((c, fitz.Rect(bbox)))
                if not line_chars:
                    continue

                line_text = "".join(c for c, _ in line_chars)
                for orig_text, token in token_by_original.items():
                    pos = line_text.find(orig_text)
                    if pos < 0:
                        continue
                    entity_chars = line_chars[pos:pos + len(orig_text)]
                    x0 = min(bbox.x0 for _, bbox in entity_chars)
                    y0 = min(bbox.y0 for _, bbox in entity_chars)
                    x1 = max(bbox.x1 for _, bbox in entity_chars)
                    y1 = max(bbox.y1 for _, bbox in entity_chars)
                    _key = (page_index, x0, y0, x1, y1)
                    if _key in _redacted:
                        continue
                    _redacted.add(_key)
                    redact_rect = fitz.Rect(x0, y0 - 1, x1, y1 + 1)
                    redactions_by_page.setdefault(page_index, []).append((redact_rect, token))
                    page.add_redact_annot(redact_rect, fill=(1, 1, 1))

    # Pass 3: apply redactions and insert replacement tokens
    for page_index, redactions in redactions_by_page.items():
        page = doc[page_index]
        page.apply_redactions()
        page_width = page.rect.width
        for rect, token in redactions:
            token_width = min(len(token) * 4.2 + 10, page_width - rect.x0 - 4)
            token_rect = fitz.Rect(
                rect.x0, rect.y0 - 1,
                rect.x0 + token_width, rect.y1 + 8,
            )
            page.insert_textbox(
                token_rect, token, fontsize=7, fontname="helv",
                color=(0, 0, 0), align=0,
            )

    return DocumentAnonymizeResult(
        workbook_bytes=doc.tobytes(garbage=4, deflate=True),
        mapping=state.to_mapping_file(),
        row_count=len(state.entries),
    )


def anonymize_docx_bytes(content: bytes, seed_mapping: MappingFile | None = None) -> DocumentAnonymizeResult:
    state = AnonymizerState(seed_mapping=seed_mapping)
    doc = Document(BytesIO(content))

    # Build a flat list of every paragraph-like element and its runs
    para_runs: list[list[object]] = []
    for para in doc.paragraphs:
        para_runs.append(list(para.runs))
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    para_runs.append(list(para.runs))

    # Pass 1: register entities from full paragraph text
    for runs in para_runs:
        full_text = "".join(run.text or "" for run in runs)
        if full_text.strip():
            register_entities_in_text(full_text, state)

    # Build token lookup
    token_by_original: dict[str, str] = {}
    for entry in state.entries:
        token_by_original[entry.original] = entry.token

    # Pass 2: replace entities in individual runs
    for runs in para_runs:
        _replace_in_runs(runs, token_by_original)

    buf = BytesIO()
    doc.save(buf)
    return DocumentAnonymizeResult(
        workbook_bytes=buf.getvalue(),
        mapping=state.to_mapping_file(),
        row_count=len(state.entries),
    )


def _replace_in_runs(runs: list[object], token_by_original: dict[str, str]) -> None:
    """Replace known entity text with tokens across a paragraph's runs.

    Works on the paragraph-level full text first (so entities split across
    runs like "AI" + "数据部" are caught), then writes the result back
    into the first run, preserving the paragraph content.
    """
    if not runs or not token_by_original:
        return

    full_text = "".join(run.text or "" for run in runs)
    for orig_text, token in token_by_original.items():
        full_text = full_text.replace(orig_text, token)

    runs[0].text = full_text
    for run in runs[1:]:
        run.text = ""


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
        register_entities_in_text(line, state)

    def _replace_pdf_text_operand(operand):
        if isinstance(operand, TextStringObject):
            replaced, changed = replace_entities_in_text(str(operand), state)
            return TextStringObject(replaced), changed
        if isinstance(operand, ByteStringObject):
            try:
                text = bytes(operand).decode("latin-1")
            except Exception:
                return operand, False
            replaced, changed = replace_entities_in_text(text, state)
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
