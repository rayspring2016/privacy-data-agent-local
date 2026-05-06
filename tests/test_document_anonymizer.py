from io import BytesIO
from privacy_data_agent.document_anonymizer import anonymize_docx_bytes, anonymize_pdf_bytes
from privacy_data_agent.models import EntityType

def test_anonymize_docx_basic():
    from docx import Document
    doc = Document()
    doc.add_paragraph("13800138000")  # matches PHONE_RE pattern exactly
    buf = BytesIO()
    doc.save(buf)
    content = buf.getvalue()

    result = anonymize_docx_bytes(content)
    assert result.workbook_bytes.startswith(b"PK")  # valid docx
    assert result.row_count == 1
    assert any(e.entity_type == EntityType.PHONE for e in result.mapping.entries)

def test_anonymize_pdf_basic():
    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(100, 100)
    buf = BytesIO()
    writer.write(buf)
    content = buf.getvalue()
    result = anonymize_pdf_bytes(content)
    assert result.workbook_bytes.startswith(b"%PDF")

def test_anonymize_pdf_with_text():
    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(100, 100)
    buf = BytesIO()
    writer.write(buf)
    content = buf.getvalue()
    result = anonymize_pdf_bytes(content)
    assert result.workbook_bytes.startswith(b"%PDF")
