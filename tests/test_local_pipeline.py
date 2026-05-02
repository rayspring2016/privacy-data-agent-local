from privacy_data_agent.local_pipeline import anonymize_file, restore_report_file
from privacy_data_agent.mapping_store import load_local_mapping


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
    assert "PDA_" in anonymized_text
    assert "EMP_" not in anonymized_text
    assert "DEPT_" not in anonymized_text
    assert "CUSTOMER_" not in anonymized_text
    assert "张三" in mapping_text
    assert anonymize_artifacts.mapping_table_path.exists()

    mapping = load_local_mapping(anonymize_artifacts.mapping_json_path)
    employee_token = next(entry.token for entry in mapping.entries if entry.original == "张三")
    customer_token = next(entry.token for entry in mapping.entries if entry.original == "上海春雷科技有限公司")
    department_token = next(entry.token for entry in mapping.entries if entry.original == "华东销售一部")
    anonymized_report = output_dir / "report.anonymized.md"
    anonymized_report.write_text(
        f"{employee_token} 负责 {customer_token}，所在部门是 {department_token}。",
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
    mapping = load_local_mapping(anonymize_artifacts.mapping_json_path)
    employee_token = next(entry.token for entry in mapping.entries if entry.original == "张三")
    customer_token = next(entry.token for entry in mapping.entries if entry.original == "上海春雷科技有限公司")
    anonymized_report = output_dir / "report.anonymized.md"
    anonymized_report.write_text(f"{employee_token} 服务 {customer_token}。", encoding="utf-8")

    restore_artifacts = restore_report_file(
        report_path=anonymized_report,
        mapping_path=anonymize_artifacts.mapping_table_path,
        output_path=output_dir / "report.from_csv.restored.md",
    )

    restored_text = restore_artifacts.restored_report_path.read_text(encoding="utf-8")
    assert "张三" in restored_text
    assert "上海春雷科技有限公司" in restored_text
