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
    from pypdf.generic import ArrayObject

    state = AnonymizerState(seed_mapping=seed_mapping)
    reader = PdfReader(BytesIO(content))
    writer = PdfWriter()

    # First pass: extract text from all pages and detect entities
    all_text = ""
    for page in reader.pages:
        try:
            if "/Contents" in page:
                contents = page["/Contents"]
                if isinstance(contents, ArrayObject):
                    data = b"".join(item.get_object().get_data() for item in contents if hasattr(item, 'get_object'))
                else:
                    data = contents.get_object().get_data()
                all_text += data.decode("latin-1", errors="replace") + "\n"
        except Exception:
            pass

    # Detect entities in extracted text
    for line in all_text.split("\n"):
        text = line.strip()
        if text:
            entity_type = detect_cell_entity_type(text)
            if entity_type:
                state.token_for(entity_type, text)

    # Second pass: copy pages with no text modification (pypdf doesn't support in-place text replacement)
    # The mapping is built above; actual text replacement in PDF requires low-level stream editing
    # For now, build mapping only (entities are still detected and token-mapped)
    for page in reader.pages:
        writer.add_page(page)

    buf = BytesIO()
    writer.write(buf)
    return DocumentAnonymizeResult(
        workbook_bytes=buf.getvalue(),
        mapping=state.to_mapping_file(),
        row_count=len(state.entries),
    )
