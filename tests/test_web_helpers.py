import zipfile
from io import BytesIO

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
