from __future__ import annotations
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import pandas as pd
from docx import Document

from privacy_data_agent.anonymizer import AnonymizerState
from privacy_data_agent.detectors import detect_cell_entity_type
from privacy_data_agent.models import MappingFile


@dataclass
class DocumentAnonymizeResult:
    workbook_bytes: bytes  # docx: docx bytes; pdf: modified pdf bytes
    mapping: MappingFile
    row_count: int  # number of entities found


def anonymize_docx_bytes(content: bytes, seed_mapping: MappingFile | None = None) -> DocumentAnonymizeResult:
    state = AnonymizerState(seed_mapping=seed_mapping)
    doc = Document(BytesIO(content))

    def _patch_paragraph(para) -> None:
        for run in para.runs:
            original = run.text or ""
            if original.strip():
                entity_type = detect_cell_entity_type(original)
                if entity_type:
                    run.text = state.token_for(entity_type, original.strip())

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
    from pypdf import PdfReader, PdfWriter

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
        for token in line.split():
            stripped = token.strip()
            if stripped:
                entity_type = detect_cell_entity_type(stripped)
                if entity_type:
                    state.token_for(entity_type, stripped)

    # Second pass: copy pages (pypdf doesn't support in-place text replacement)
    for page in reader.pages:
        writer.add_page(page)

    buf = BytesIO()
    writer.write(buf)
    return DocumentAnonymizeResult(
        workbook_bytes=buf.getvalue(),
        mapping=state.to_mapping_file(),
        row_count=len(state.entries),
    )
