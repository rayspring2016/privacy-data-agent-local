from cryptography.fernet import Fernet
from typer.testing import CliRunner

from privacy_data_agent.cli import app


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
