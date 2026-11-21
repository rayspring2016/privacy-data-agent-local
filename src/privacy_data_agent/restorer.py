from __future__ import annotations

from io import BytesIO
from pathlib import Path

from privacy_data_agent.models import MappingFile
from privacy_data_agent.workbook_metadata import replace_workbook_metadata


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


def _restore_xlsx(content: bytes, mapping: MappingFile) -> bytes:
    from openpyxl import load_workbook

    workbook = load_workbook(BytesIO(content))
    preserve = workbook.calculation is not None and workbook.calculation.calcMode == "manual"
    cached = load_workbook(BytesIO(content), data_only=True, read_only=True) if preserve else None
    formulas = {}
    for number, worksheet in enumerate(workbook.worksheets):
        cache_rows = iter(cached.worksheets[number].iter_rows(values_only=True)) if cached else None
        for row in worksheet.iter_rows():
            values = next(cache_rows) if cache_rows else None
            for cell in row:
                if isinstance(cell.value, str):
                    replaced = _replace_all(cell.value, mapping)
                    if preserve and cell.data_type == "f":
                        formulas.setdefault(worksheet.title, {})[cell.coordinate] = replaced
                        value = values[cell.column - 1]
                        cell.value = _replace_all(value, mapping) if isinstance(value, str) else value
                        if cell.data_type == "f":
                            cell.data_type = "s"
                    elif replaced != cell.value:
                        cell.value = replaced

    replace_workbook_metadata(workbook, lambda text: _replace_all(text, mapping))
    buf = BytesIO()
    workbook.save(buf)
    if cached:
        cached.close()
        from privacy_data_agent.workbook_anonymizer import _restore_formulas

        return _restore_formulas(buf.getvalue(), formulas)
    return buf.getvalue()


def _restore_pdf(content: bytes, mapping: MappingFile) -> bytes:
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import ArrayObject, ContentStream, TextStringObject

    reader = PdfReader(BytesIO(content))
    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(page)
        contents = page.get_contents()
        if contents is None:
            continue
        content_stream = ContentStream(contents, reader)
        changed = False
        for operands, operator in content_stream.operations:
            if operator in (b"Tj", b"'") and operands:
                if isinstance(operands[0], TextStringObject):
                    new_text = _replace_all(str(operands[0]), mapping)
                    if new_text != str(operands[0]):
                        operands[0] = TextStringObject(new_text)
                        changed = True
            elif operator == b"TJ" and operands and isinstance(operands[0], ArrayObject):
                for index, item in enumerate(operands[0]):
                    if isinstance(item, TextStringObject):
                        new_text = _replace_all(str(item), mapping)
                        if new_text != str(item):
                            operands[0][index] = TextStringObject(new_text)
                            changed = True
        if changed:
            writer.pages[-1].replace_contents(content_stream)

    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def restore_bytes(content: bytes, filename: str, mapping: MappingFile) -> bytes:
    suffix = Path(filename).suffix.lower()
    if suffix == ".xlsx":
        return _restore_xlsx(content, mapping)
    if suffix == ".docx":
        return _restore_docx(content, mapping)
    if suffix == ".pptx":
        return _restore_pptx(content, mapping)
    if suffix == ".pdf":
        return _restore_pdf(content, mapping)
    # Text-based: md, txt, html, htm
    return _replace_all(content.decode("utf-8-sig"), mapping).encode("utf-8")
