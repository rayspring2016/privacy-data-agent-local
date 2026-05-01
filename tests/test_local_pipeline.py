from privacy_data_agent.local_pipeline import anonymize_file, restore_report_file


def test_local_anonymize_and_restore_without_model_or_key(tmp_path, monkeypatch):
    monkeypatch.delenv("PRIVACY_AGENT_KEY", raising=False)
    output_dir = tmp_path / "local"

    anonymize_artifacts = anonymize_file(
        input_path="tests/fixtures/hr_sample.csv",
        output_dir=output_dir,
    )

    anonymized_text = anonymize_artifacts.anonymized_data_path.read_text(encoding="utf-8")
    mapping_text = anonymize_artifacts.mapping_json_path.read_text(encoding="utf-8")
    assert "张三" not in anonymized_text
    assert "上海春雷科技有限公司" not in anonymized_text
    assert "EMP_0001" in anonymized_text
    assert "张三" in mapping_text
    assert anonymize_artifacts.mapping_table_path.exists()

    anonymized_report = output_dir / "report.anonymized.md"
    anonymized_report.write_text(
        "EMP_0001 负责 CUSTOMER_0001，所在部门是 DEPT_0001。",
        encoding="utf-8",
    )

    restore_artifacts = restore_report_file(
        report_path=anonymized_report,
        mapping_path=anonymize_artifacts.mapping_json_path,
        output_path=output_dir / "report.restored.md",
    )

    restored_text = restore_artifacts.restored_report_path.read_text(encoding="utf-8")
    assert "张三" in restored_text
    assert "上海春雷科技有限公司" in restored_text
    assert "华东销售一部" in restored_text


def test_local_restore_can_use_mapping_table_csv(tmp_path):
    output_dir = tmp_path / "local"
    anonymize_artifacts = anonymize_file(
        input_path="tests/fixtures/hr_sample.csv",
        output_dir=output_dir,
    )
    anonymized_report = output_dir / "report.anonymized.md"
    anonymized_report.write_text("EMP_0001 服务 CUSTOMER_0001。", encoding="utf-8")

    restore_artifacts = restore_report_file(
        report_path=anonymized_report,
        mapping_path=anonymize_artifacts.mapping_table_path,
        output_path=output_dir / "report.from_csv.restored.md",
    )

    restored_text = restore_artifacts.restored_report_path.read_text(encoding="utf-8")
    assert "张三" in restored_text
    assert "上海春雷科技有限公司" in restored_text
