from cryptography.fernet import Fernet

from privacy_data_agent.llm_client import FakeModelProvider
from privacy_data_agent.mapping_store import load_mapping_file
from privacy_data_agent.pipeline import run_analysis


def test_pipeline_never_sends_raw_sensitive_values_to_model(tmp_path):
    key = Fernet.generate_key().decode()
    captured_prompt = tmp_path / "captured_prompt.md"
    provider = FakeModelProvider(captured_prompt_path=captured_prompt)

    artifacts = run_analysis(
        input_path="tests/fixtures/hr_sample.csv",
        output_dir=tmp_path / "run",
        mapping_key=key,
        provider=provider,
        instruction="请分析销售额和客户跟进风险。",
    )

    prompt_text = captured_prompt.read_text(encoding="utf-8")
    anonymized_text = artifacts.anonymized_data_path.read_text(encoding="utf-8")
    anonymized_report = artifacts.anonymized_report_path.read_text(encoding="utf-8")
    restored_report = artifacts.restored_report_path.read_text(encoding="utf-8")

    for raw in [
        "张三",
        "李四",
        "王五",
        "11010119900307001X",
        "华东销售一部",
        "上海春雷科技有限公司",
        "13800138000",
        "zhangsan@example.com",
    ]:
        assert raw not in prompt_text
        assert raw not in anonymized_text
        assert raw not in anonymized_report

    assert "PDA_" in prompt_text
    assert "PDA_" in anonymized_report
    for type_revealing_prefix in ["EMP_", "ID_", "DEPT_", "CUSTOMER_", "PHONE_", "EMAIL_"]:
        assert type_revealing_prefix not in prompt_text
        assert type_revealing_prefix not in anonymized_report
    assert "张三" in restored_report
    assert "上海春雷科技有限公司" in restored_report
    assert load_mapping_file(artifacts.mapping_path, key).entries
