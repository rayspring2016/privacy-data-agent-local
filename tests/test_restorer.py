from privacy_data_agent.models import EntityType, MappingEntry, MappingFile
from privacy_data_agent.restorer import restore_bytes, restore_report


def test_restores_tokens_in_report():
    mapping = MappingFile(
        entries=[
            MappingEntry(entity_type=EntityType.EMPLOYEE, original="张三", token="PDA_AAAAAAAAAAAAAAAA"),
            MappingEntry(entity_type=EntityType.DEPARTMENT, original="华东销售一部", token="PDA_BBBBBBBBBBBBBBBB"),
            MappingEntry(entity_type=EntityType.CUSTOMER, original="上海春雷科技有限公司", token="PDA_CCCCCCCCCCCCCCCC"),
        ]
    )
    report = "PDA_AAAAAAAAAAAAAAAA 在 PDA_BBBBBBBBBBBBBBBB 负责 PDA_CCCCCCCCCCCCCCCC，建议提高资源投入。"

    restored = restore_report(report, mapping)

    assert restored == "张三 在 华东销售一部 负责 上海春雷科技有限公司，建议提高资源投入。"


def _make_mapping() -> MappingFile:
    return MappingFile(
        entries=[
            MappingEntry(entity_type=EntityType.EMPLOYEE, original="张三", token="PDA_AAAA"),
            MappingEntry(entity_type=EntityType.CUSTOMER, original="春雷科技", token="PDA_BBBB"),
        ]
    )


def test_restore_bytes_html():
    html = b"<p>PDA_AAAA \xe8\xb4\x9f\xe8\xb4\xa3 PDA_BBBB\xe3\x80\x82</p>"
    result = restore_bytes(html, "report.html", _make_mapping())
    assert "张三" in result.decode("utf-8")
    assert "春雷科技" in result.decode("utf-8")


def test_restore_bytes_docx():
    from io import BytesIO

    from docx import Document

    doc = Document()
    doc.add_paragraph("PDA_AAAA 负责 PDA_BBBB 项目。")
    buf = BytesIO()
    doc.save(buf)

    result = restore_bytes(buf.getvalue(), "report.docx", _make_mapping())

    from docx import Document as D2

    restored_doc = D2(BytesIO(result))
    text = " ".join(p.text for p in restored_doc.paragraphs)
    assert "张三" in text
    assert "春雷科技" in text


def test_restore_bytes_pptx():
    from io import BytesIO

    from pptx import Presentation
    from pptx.util import Inches

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    txBox = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1))
    txBox.text_frame.text = "PDA_AAAA 负责 PDA_BBBB。"
    buf = BytesIO()
    prs.save(buf)

    result = restore_bytes(buf.getvalue(), "report.pptx", _make_mapping())

    from pptx import Presentation as P2

    restored = P2(BytesIO(result))
    texts = []
    for slide in restored.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                texts.append(shape.text_frame.text)
    combined = " ".join(texts)
    assert "张三" in combined
    assert "春雷科技" in combined
