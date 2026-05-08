"""诊断工具：检查 PDF 文本提取是否正常。

用法:
    .venv/bin/python tools/pdf_diag.py <your_file.pdf>
"""
import sys
import fitz


def diagnose(pdf_path: str) -> None:
    doc = fitz.open(pdf_path)
    print(f"PDF: {pdf_path}")
    print(f"页数: {doc.page_count}")
    print()

    for i, page in enumerate(doc):
        print(f"=== Page {i + 1} ===")

        # Method 1: text
        text = page.get_text("text") or ""
        print(f"[get_text('text')] {len(text)} chars:")
        print(text[:500])

        # Method 2: rawdict chars
        print()
        print(f"[get_text('rawdict') chars]:")
        raw = page.get_text("rawdict")
        chars = []
        for block in raw.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    for char in span.get("chars", []):
                        c = char.get("c", "")
                        if c:
                            chars.append(c)
        char_text = "".join(chars)
        print(char_text[:500])

        # Method 3: xml text nodes
        print()
        print(f"[get_text('xml') text nodes]:")
        try:
            xml = page.get_text("xml")
            import xml.etree.ElementTree as ET
            root = ET.fromstring(xml)
            parts = [elem.text.strip() for elem in root.iter() if elem.text and elem.text.strip()]
            print("\n".join(parts[:20]))
        except Exception as e:
            print(f"  XML extraction failed: {e}")

        # Entity detection test
        from privacy_data_agent.document_anonymizer import _entity_spans
        all_text = text + "\n" + char_text
        spans = _entity_spans(all_text)
        print()
        print(f"[实体检测] 找到 {len(spans)} 个实体:")
        for start, end, etype, original in spans:
            print(f"  offset={start}-{end} type={etype.value} text={original!r}")

        print()

    doc.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: .venv/bin/python tools/pdf_diag.py <pdf文件路径>")
        sys.exit(1)
    diagnose(sys.argv[1])
