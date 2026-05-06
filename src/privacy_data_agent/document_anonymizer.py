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

    for page in reader.pages:
        writer.add_page(page)

    buf = BytesIO()
    writer.write(buf)
    return DocumentAnonymizeResult(
        workbook_bytes=buf.getvalue(),
        mapping=state.to_mapping_file(),
        row_count=0,
    )
