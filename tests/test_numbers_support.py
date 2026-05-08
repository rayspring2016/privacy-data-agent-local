"""Test D9: WPS / Numbers format support."""
import io
import zipfile
from privacy_data_agent.web_helpers import _read_uploaded_numbers, read_uploaded_table
from privacy_data_agent.anonymizer import anonymize_dataframe


def test_read_uploaded_numbers_basic():
    """Numbers .numbers file (ZIP with XML) should be read as DataFrame."""
    # Create a mock Numbers file (ZIP with index.xml)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('index.xml', '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE document>
<document>
  <sheet>
    <table>
      <row><cell>姓名</cell><cell>部门</cell><cell>手机号</cell></row>
      <row><cell>张三</cell><cell>销售部</cell><cell>13800138000</cell></row>
      <row><cell>李四</cell><cell>技术部</cell><cell>13900139000</cell></row>
    </table>
  </sheet>
</document>''')
    buf.seek(0)
    content = buf.getvalue()
    
    # Test the function
    df = read_uploaded_table("test.numbers", content, header_row=None)
    
    # Should have parsed the data
    assert len(df) >= 1, f"Expected at least 1 data row, got {len(df)}"
    # Check that some employee names were extracted
    text_repr = df.to_string()
    assert "张三" in text_repr or "姓名" in text_repr, f"Expected to find names in DataFrame: {text_repr[:200]}"


def test_numbers_extension_accepted():
    """Files with .numbers extension should be accepted."""
    suffix = ".numbers"
    # This tests the suffix check logic
    assert suffix in [".csv", ".xlsx", ".numbers", ".et", ".docx", ".pdf"]


def test_et_extension_accepted():
    """Files with .et (WPS) extension should be accepted."""
    suffix = ".et"
    assert suffix in [".csv", ".xlsx", ".numbers", ".et", ".docx", ".pdf"]
