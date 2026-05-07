from io import BytesIO
from pypdf import PdfReader
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


def test_anonymize_docx_embedded_phone_next_to_label():
    from docx import Document
    doc = Document()
    doc.add_paragraph("手机号：13800138000")
    buf = BytesIO()
    doc.save(buf)

    result = anonymize_docx_bytes(buf.getvalue())

    assert result.row_count == 1
    assert result.mapping.entries[0].original == "13800138000"


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
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    page = writer.add_blank_page(300, 300)
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})
    })
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 72 220 Td (phone:13800138000) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    buf = BytesIO()
    writer.write(buf)
    content = buf.getvalue()

    result = anonymize_pdf_bytes(content)

    assert result.workbook_bytes.startswith(b"%PDF")
    assert result.row_count == 1
    assert result.mapping.entries[0].original == "13800138000"
    output_text = PdfReader(BytesIO(result.workbook_bytes)).pages[0].extract_text()
    assert "13800138000" not in output_text
    assert "PDA_" in output_text


def test_anonymize_pdf_redacts_searchable_word_export_text():
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=420, height=240)
    page.insert_text((72, 72), "phone: 13800138000", fontsize=12)
    page.insert_text((72, 104), "email: zhangsan@example.com", fontsize=12)
    content = doc.tobytes()

    result = anonymize_pdf_bytes(content)

    assert result.row_count == 2
    assert {entry.original for entry in result.mapping.entries} == {
        "13800138000",
        "zhangsan@example.com",
    }
    output_doc = fitz.open(stream=result.workbook_bytes, filetype="pdf")
    output_text = output_doc[0].get_text()
    assert "13800138000" not in output_text
    assert "zhangsan@example.com" not in output_text
    assert output_text.count("PDA_") == 2
    assert b"13800138000" not in result.workbook_bytes
    assert b"zhangsan@example.com" not in result.workbook_bytes
