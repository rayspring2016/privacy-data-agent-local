from cryptography.fernet import Fernet
from openpyxl import Workbook, load_workbook
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


def test_cli_keep_salary_group_preserves_only_named_group(tmp_path, monkeypatch):
    monkeypatch.delenv("PRIVACY_AGENT_KEY", raising=False)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "anonymize",
            "tests/fixtures/golden_sample.xlsx",
            "--output-dir",
            str(tmp_path),
            "--keep-salary-group",
            "labor_cost",
        ],
    )

    assert result.exit_code == 0
    import pandas as pd

    output = pd.read_excel(tmp_path / "anonymized.xlsx")
    assert output["人力成本"].astype(str).tolist() == ["31000", "22500", "27500"]
    assert not output["月薪"].astype(str).str.startswith("2").any()  # anonymized, not "25000" etc


def test_cli_keep_salary_group_accepts_repeated_flag(tmp_path, monkeypatch):
    monkeypatch.delenv("PRIVACY_AGENT_KEY", raising=False)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "anonymize",
            "tests/fixtures/golden_sample.xlsx",
            "--output-dir",
            str(tmp_path),
            "--keep-salary-group",
            "labor_cost",
            "--keep-salary-group",
            "allowance",
        ],
    )

    assert result.exit_code == 0
    import pandas as pd

    output = pd.read_excel(tmp_path / "anonymized.xlsx")
    assert output["人力成本"].astype(str).tolist() == ["31000", "22500", "27500"]
    assert output["餐补"].astype(str).tolist() == ["500", "500", "500"]


def test_cli_keep_salary_group_rejects_unknown_group(tmp_path, monkeypatch):
    """拼错组名必须报错退出，不能静默无效（Eng Review 发现2/3）。"""
    monkeypatch.delenv("PRIVACY_AGENT_KEY", raising=False)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "anonymize",
            "tests/fixtures/golden_sample.xlsx",
            "--output-dir",
            str(tmp_path),
            "--keep-salary-group",
            "labor_cast",  # typo
        ],
    )

    assert result.exit_code != 0
    assert not (tmp_path / "anonymized.xlsx").exists()


def test_cli_anonymize_xlsx_outputs_preserved_workbook(tmp_path, monkeypatch):
    monkeypatch.delenv("PRIVACY_AGENT_KEY", raising=False)
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "员工"
    worksheet["A1"] = "姓名"
    worksheet["A2"] = "张三"
    hidden = workbook.create_sheet("隐藏")
    hidden.sheet_state = "hidden"
    hidden["A1"] = "客户名称"
    hidden["A2"] = "上海春雷科技有限公司"
    input_path = tmp_path / "input.xlsx"
    workbook.save(input_path)

    runner = CliRunner()
    result = runner.invoke(app, ["anonymize", str(input_path), "--output-dir", str(tmp_path / "out")])

    assert result.exit_code == 0
    output_path = tmp_path / "out" / "anonymized.xlsx"
    assert output_path.exists()
    output = load_workbook(output_path)
    assert output["员工"]["A2"].value.startswith("PDA_")
    assert output["隐藏"]["A2"].value.startswith("PDA_")
    assert output["隐藏"].sheet_state == "hidden"
