from privacy_data_agent.web_helpers import anonymize_upload, restore_report_upload


def test_anonymize_upload_returns_downloadable_files():
    content = open("tests/fixtures/hr_sample.csv", "rb").read()

    result = anonymize_upload("hr_sample.csv", content)

    assert result["row_count"] == 3
    assert result["entity_count"] > 0
    assert b"EMP_0001" in result["anonymized_csv"]
    assert "张三" in result["mapping_json"]
    assert result["anonymized_xlsx"]
    assert result["mapping_table_csv"]


def test_restore_report_upload_with_json_mapping():
    content = open("tests/fixtures/hr_sample.csv", "rb").read()
    anonymized = anonymize_upload("hr_sample.csv", content)

    restored = restore_report_upload(
        report_content="EMP_0001 负责 CUSTOMER_0001。".encode("utf-8"),
        mapping_filename="mapping.local.json",
        mapping_content=str(anonymized["mapping_json"]).encode("utf-8"),
    )

    assert "张三" in restored
    assert "上海春雷科技有限公司" in restored
