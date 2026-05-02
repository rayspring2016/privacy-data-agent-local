from cryptography.fernet import Fernet
from typer.testing import CliRunner

from privacy_data_agent.cli import app
from privacy_data_agent.mapping_store import load_local_mapping


def test_cli_requires_mapping_key(tmp_path, monkeypatch):
    monkeypatch.delenv("PRIVACY_AGENT_KEY", raising=False)
    runner = CliRunner()

    result = runner.invoke(app, ["analyze", "tests/fixtures/hr_sample.csv", "--output-dir", str(tmp_path)])

    assert result.exit_code == 1
    assert "PRIVACY_AGENT_KEY is required" in result.output


def test_cli_runs_with_fake_provider(tmp_path, monkeypatch):
    monkeypatch.setenv("PRIVACY_AGENT_KEY", Fernet.generate_key().decode())
    runner = CliRunner()

    result = runner.invoke(app, ["analyze", "tests/fixtures/hr_sample.csv", "--output-dir", str(tmp_path)])

    assert result.exit_code == 0
    assert "Restored report:" in result.output
    assert (tmp_path / "model_report.restored.md").exists()


def test_cli_anonymize_and_restore_are_local_only(tmp_path, monkeypatch):
    monkeypatch.delenv("PRIVACY_AGENT_KEY", raising=False)
    runner = CliRunner()

    anonymize_result = runner.invoke(
        app,
        ["anonymize", "tests/fixtures/hr_sample.csv", "--output-dir", str(tmp_path)],
    )

    assert anonymize_result.exit_code == 0
    assert "Anonymized data:" in anonymize_result.output
    assert (tmp_path / "anonymized.csv").exists()
    assert (tmp_path / "mapping.local.json").exists()
    assert (tmp_path / "mapping_table.csv").exists()

    mapping = load_local_mapping(tmp_path / "mapping.local.json")
    employee_token = next(entry.token for entry in mapping.entries if entry.original == "张三")
    customer_token = next(entry.token for entry in mapping.entries if entry.original == "上海春雷科技有限公司")
    report_path = tmp_path / "report.anonymized.md"
    report_path.write_text(f"{employee_token} 负责 {customer_token}。", encoding="utf-8")
    restored_path = tmp_path / "report.restored.md"

    restore_result = runner.invoke(
        app,
        [
            "restore",
            str(report_path),
            "--mapping",
            str(tmp_path / "mapping.local.json"),
            "--output",
            str(restored_path),
        ],
    )

    assert restore_result.exit_code == 0
    assert "Restored report:" in restore_result.output
    assert "张三" in restored_path.read_text(encoding="utf-8")
