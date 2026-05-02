import zipfile
from io import BytesIO

from openpyxl import Workbook, load_workbook
from openpyxl.styles import PatternFill

from privacy_data_agent.web_helpers import anonymize_upload, restore_report_upload


def test_anonymize_upload_returns_downloadable_files():
    content = open("tests/fixtures/hr_sample.csv", "rb").read()

    result = anonymize_upload("hr_sample.csv", content)

    assert result["row_count"] == 3
    assert result["entity_count"] > 0
    assert b"PDA_" in result["anonymized_csv"]
    assert b"EMP_" not in result["anonymized_csv"]
    assert b"CUSTOMER_" not in result["anonymized_csv"]
    assert "张三" in result["mapping_json"]
    assert result["anonymized_xlsx"]
    assert result["mapping_table_csv"]
    assert result["stem"] == "hr_sample"
    # ZIP bundle contains the expected files
    zf = zipfile.ZipFile(BytesIO(result["zip_bundle"]))
    assert set(zf.namelist()) == {"anonymized.xlsx", "mapping.local.json", "README.txt"}
    readme = zf.read("README.txt").decode("utf-8")
    assert "hr_sample" in readme
    assert "mapping.local.json" in readme


def test_restore_report_upload_with_json_mapping():
    content = open("tests/fixtures/hr_sample.csv", "rb").read()
    anonymized = anonymize_upload("hr_sample.csv", content)
    mapping = anonymized["mapping_json"]
    import json

    entries = json.loads(str(mapping))["entries"]
    employee_token = next(entry["token"] for entry in entries if entry["original"] == "张三")
    customer_token = next(entry["token"] for entry in entries if entry["original"] == "上海春雷科技有限公司")

    result = restore_report_upload(
        report_content=f"{employee_token} 负责 {customer_token}。".encode("utf-8"),
        report_filename="report.md",
        mapping_filename="mapping.local.json",
        mapping_content=str(anonymized["mapping_json"]).encode("utf-8"),
    )

    text = result["content"].decode("utf-8")
    assert "张三" in text
    assert "上海春雷科技有限公司" in text
    assert result["filename"] == "report.restored.md"


def test_anonymize_upload_preserves_xlsx_sheets_hidden_state_and_styles():
    workbook = Workbook()
    active = workbook.active
    active.title = "员工"
    active["A1"] = "姓名"
    active["B1"] = "部门"
    active["A2"] = "张三"
    active["B2"] = "销售一部"
    active["A2"].fill = PatternFill("solid", fgColor="FFCC00")
    active.column_dimensions["A"].width = 28

    hidden = workbook.create_sheet("隐藏客户")
    hidden.sheet_state = "hidden"
    hidden["A1"] = "客户名称"
    hidden["A2"] = "上海春雷科技有限公司"

    buffer = BytesIO()
    workbook.save(buffer)

    result = anonymize_upload("multi.xlsx", buffer.getvalue())
    output = load_workbook(BytesIO(result["anonymized_xlsx"]))

    assert output.sheetnames == ["员工", "隐藏客户"]
    assert output["隐藏客户"].sheet_state == "hidden"
    assert output["员工"]["A2"].value.startswith("PDA_")
    assert output["员工"]["B2"].value.startswith("PDA_")
    assert output["隐藏客户"]["A2"].value.startswith("PDA_")
    assert output["员工"]["A2"].fill.fgColor.rgb == "00FFCC00"
    assert output["员工"].column_dimensions["A"].width == 28
    assert "张三" in result["mapping_json"]
    assert "上海春雷科技有限公司" in result["mapping_json"]
