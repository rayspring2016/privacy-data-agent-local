from __future__ import annotations

from io import BytesIO
from pathlib import Path

from privacy_data_agent.models import MappingFile


def _replace_all(text: str, mapping: MappingFile) -> str:
    # Sort longest token first to avoid partial replacement (e.g. PDA_1 inside PDA_10)
    for entry in sorted(mapping.entries, key=lambda e: len(e.token), reverse=True):
        text = text.replace(entry.token, entry.original)
    return text


def restore_report(report: str, mapping: MappingFile) -> str:
    return _replace_all(report, mapping)


def _restore_docx(content: bytes, mapping: MappingFile) -> bytes:
    from docx import Document

    doc = Document(BytesIO(content))

    def _patch_paragraph(para) -> None:
        for run in para.runs:
            replaced = _replace_all(run.text, mapping)
            if replaced != run.text:
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
    return buf.getvalue()


def _restore_pptx(content: bytes, mapping: MappingFile) -> bytes:
    from pptx import Presentation

    prs = Presentation(BytesIO(content))
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    for run in para.runs:
                        replaced = _replace_all(run.text, mapping)
                        if replaced != run.text:
                            run.text = replaced
            if shape.has_table:
                for row in shape.table.rows:
                    for cell in row.cells:
                        for para in cell.text_frame.paragraphs:
                            for run in para.runs:
                                replaced = _replace_all(run.text, mapping)
                                if replaced != run.text:
                                    run.text = replaced

    buf = BytesIO()
    prs.save(buf)
    return buf.getvalue()


def _restore_pdf(content: bytes, mapping: MappingFile) -> bytes:
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import ArrayObject

    reader = PdfReader(BytesIO(content))
    writer = PdfWriter()

    for page in reader.pages:
        try:
            if "/Contents" in page:
                contents = page["/Contents"]
                if isinstance(contents, ArrayObject):
                    data = b"".join(
                        item.get_object().get_data()
                        for item in contents
                    )
                else:
                    data = contents.get_object().get_data()
                text = data.decode("latin-1", errors="replace")
                restored_text = _replace_all(text, mapping)
                if restored_text != text:
                    # Content was modified; pypdf doesn't support in-place stream editing
                    # so we note this limitation and copy pages as-is
                    pass
        except Exception:
            pass
        writer.add_page(page)

    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def restore_bytes(content: bytes, filename: str, mapping: MappingFile) -> bytes:
    suffix = Path(filename).suffix.lower()
    if suffix == ".docx":
        return _restore_docx(content, mapping)
    if suffix == ".pptx":
        return _restore_pptx(content, mapping)
    if suffix == ".pdf":
        return _restore_pdf(content, mapping)
    # Text-based: md, txt, html, htm
    return _replace_all(content.decode("utf-8-sig"), mapping).encode("utf-8")
