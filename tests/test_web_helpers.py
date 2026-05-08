import zipfile
from io import BytesIO

from openpyxl import Workbook, load_workbook
from openpyxl.styles import PatternFill
from cryptography.fernet import Fernet

from privacy_data_agent.web_helpers import (
    anonymize_batch,
    anonymize_upload,
    decrypt_mapping_json,
    restore_report_upload,
)


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
    assert set(zf.namelist()) == {"hr_sample_anonymized.xlsx", "mapping.local.json", "README.txt"}
    readme = zf.read("README.txt").decode("utf-8")
    assert "hr_sample" in readme
    assert "mapping.local.json" in readme


def test_anonymize_batch_csv_outputs_xlsx_extension_and_workbook_bytes():
    content = open("tests/fixtures/hr_sample.csv", "rb").read()

    result = anonymize_batch([("hr_sample.csv", content)])

    assert result["results"][0]["suffix"] == ".xlsx"
    zf = zipfile.ZipFile(BytesIO(result["consolidated_zip"]))
    assert "hr_sample_anonymized.xlsx" in zf.namelist()
    output = load_workbook(BytesIO(zf.read("hr_sample_anonymized.xlsx")))
    assert output.active["A2"].value.startswith("PDA_")


def test_anonymize_batch_encrypted_zip_encrypts_consolidated_mapping():
    content = open("tests/fixtures/hr_sample.csv", "rb").read()
    key = Fernet.generate_key().decode("utf-8")

    result = anonymize_batch([("hr_sample.csv", content)], encryption_key=key)

    zf = zipfile.ZipFile(BytesIO(result["consolidated_zip"]))
    encrypted_mapping = zf.read("mapping.local.json")
    assert b"entries" not in encrypted_mapping
    decrypted = decrypt_mapping_json(encrypted_mapping, key)
    assert "张三" in decrypted
    assert "mapping.local.json 已加密" in zf.read("README.txt").decode("utf-8")


def test_anonymize_upload_csv_respects_job_title_option():
    content = (
        "姓名,岗位名称,离职原因,备注\r\n"
        "张三,技术部,被动,运营部\r\n"
    ).encode("utf-8")

    default_result = anonymize_upload("jobs.csv", content)
    assert "张三" in default_result["mapping_json"]
    assert "技术部" not in default_result["mapping_json"]
    assert "被动" not in default_result["mapping_json"]
    assert "运营部" not in default_result["mapping_json"]

    opt_in_result = anonymize_upload("jobs.csv", content, anonymize_job_title=True)
    assert "技术部" in opt_in_result["mapping_json"]
    assert "被动" not in opt_in_result["mapping_json"]
    assert "运营部" not in opt_in_result["mapping_json"]


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


def test_anonymize_upload_csv_with_title_row():
    content = (
        "2024年度员工信息统计表\r\n"
        "员工姓名,身份证号,部门,客户名称,手机号,邮箱,销售额,备注\r\n"
        "张三,11010119900307001X,华东销售一部,上海春雷科技有限公司,13800138000,zhangsan@example.com,120000,客户续费稳定\r\n"
    ).encode("utf-8")

    result = anonymize_upload("hr_with_title.csv", content)

    assert result["row_count"] == 1
    assert b"PDA_" in result["anonymized_csv"]
    assert "2024年度" not in result["anonymized_csv"].decode("utf-8")
    assert "张三" in result["mapping_json"]


def test_anonymize_upload_csv_explicit_header_row_2():
    content = (
        "2024年度员工信息统计表\r\n"
        "员工姓名,身份证号,部门,客户名称\r\n"
        "张三,11010119900307001X,华东销售一部,上海春雷科技有限公司\r\n"
    ).encode("utf-8")

    result = anonymize_upload("hr_with_title.csv", content, header_row=2)

    assert result["row_count"] == 1
    assert b"PDA_" in result["anonymized_csv"]
    assert "张三" in result["mapping_json"]


def test_anonymize_upload_xlsx_with_title_row():
    wb = Workbook()
    ws = wb.active
    ws["A1"] = "2024年度员工信息统计表"
    ws.merge_cells("A1:D1")
    ws["A2"] = "员工姓名"
    ws["B2"] = "部门"
    ws["C2"] = "客户名称"
    ws["D2"] = "手机号"
    ws["A3"] = "张三"
    ws["B3"] = "销售一部"
    ws["C3"] = "上海春雷科技有限公司"
    ws["D3"] = "13800138000"
    buf = BytesIO()
    wb.save(buf)

    result = anonymize_upload("hr_with_title.xlsx", buf.getvalue())

    output = load_workbook(BytesIO(result["anonymized_xlsx"]))
    assert output.active["A3"].value.startswith("PDA_")
    assert "张三" in result["mapping_json"]


def test_anonymize_upload_xlsx_explicit_header_row_2():
    wb = Workbook()
    ws = wb.active
    ws["A1"] = "2024年度员工信息统计表"
    ws["A2"] = "员工姓名"
    ws["B2"] = "部门"
    ws["A3"] = "张三"
    ws["B3"] = "销售一部"
    buf = BytesIO()
    wb.save(buf)

    result = anonymize_upload("hr_with_title.xlsx", buf.getvalue(), header_row=2)

    output = load_workbook(BytesIO(result["anonymized_xlsx"]))
    assert output.active["A3"].value.startswith("PDA_")
    assert output.active["A2"].value == "员工姓名"
    assert "张三" in result["mapping_json"]
