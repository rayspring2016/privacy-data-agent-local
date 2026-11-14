import json

import pandas as pd
from openpyxl import Workbook, load_workbook
from typer.testing import CliRunner

from privacy_data_agent.cli import app
from privacy_data_agent.mapping_store import load_local_mapping


def make_month(path, name="张三"):
    rows = [["姓名", "客户名称", "部门", "月薪", "提成", "回款日期"],
            [name, "上海春雷科技有限公司", "华东销售一部", 15000, 1250.5, "2026-07-15"]]
    if path.suffix.lower() == ".xlsx":
        book = Workbook()
        for row in rows:
            book.active.append(row)
        book.save(path)
    else:
        pd.DataFrame(rows[1:], columns=rows[0]).to_csv(path, index=False)


def test_directory_reuses_tokens_and_preserves_only_selected_fields(tmp_path):
    source = tmp_path / "months"
    source.mkdir()
    make_month(source / "07.xlsx")
    make_month(source / "08.CSV")
    (source / "notes.txt").write_text("ignored", encoding="utf-8")
    (source / "~$07.xlsx").write_bytes(b"Excel lock")
    originals = {p.name: p.read_bytes() for p in source.iterdir()}
    out = tmp_path / "out"
    result = CliRunner().invoke(app, ["anonymize", str(source), "-o", str(out),
                                    "--keep-salary-group", "commission",
                                    "--no-anonymize-department"])
    assert result.exit_code == 0, result.output
    report = json.loads((out / "batch_manifest.json").read_text())
    assert report["success_count"] == 2
    assert report["failure_count"] == 0
    assert report["flags"]["kept_salary_groups"] == ["commission"]
    assert report["flags"]["anonymize_department"] is False
    frames = []
    for item in report["files"]:
        assert item["status"] == "success"
        path = out / item["output"]
        frames.append(pd.read_excel(path) if path.suffix == ".xlsx" else pd.read_csv(path))
    assert frames[0].iloc[0]["姓名"] == frames[1].iloc[0]["姓名"]
    assert frames[0].iloc[0]["客户名称"] == frames[1].iloc[0]["客户名称"]
    for frame in frames:
        row = frame.iloc[0]
        assert row["姓名"].startswith("PDA_")
        assert row["客户名称"].startswith("PDA_")
        assert row["月薪"].startswith("PDA_")
        assert row["部门"] == "华东销售一部"
        assert row["提成"] == 1250.5
        assert row["回款日期"] == "2026-07-15"
    assert {p.name: p.read_bytes() for p in source.iterdir()} == originals
    mapping = load_local_mapping(out / "mapping.local.json")
    assert any(entry.original == "张三" for entry in mapping.entries)
    assert not any(entry.original == "1250.5" for entry in mapping.entries)


def test_mapping_can_seed_single_file_then_another_batch(tmp_path):
    first = tmp_path / "first.xlsx"
    make_month(first)
    runner = CliRunner()
    initial = tmp_path / "initial"
    assert runner.invoke(app, ["anonymize", str(first), "-o", str(initial)]).exit_code == 0
    seed = initial / "mapping.local.json"
    source = tmp_path / "later"
    source.mkdir()
    make_month(source / "08.csv")
    make_month(source / "09.xlsx", name="李四")
    out = tmp_path / "out"
    seed_bytes = seed.read_bytes()
    result = runner.invoke(app, ["anonymize", str(source), "-o", str(out), "--mapping", str(seed)])
    assert result.exit_code == 0, result.output
    original = load_workbook(initial / "anonymized.xlsx").active["A2"].value
    report = json.loads((out / "batch_manifest.json").read_text())
    assert pd.read_csv(out / report["files"][0]["output"]).iloc[0]["姓名"] == original
    combined = load_local_mapping(out / "mapping.local.json")
    assert {"张三", "李四"} <= {entry.original for entry in combined.entries}
    assert seed.read_bytes() == seed_bytes
    final = tmp_path / "single"
    result = runner.invoke(app, ["anonymize", str(first), "-o", str(final),
                                 "--mapping", str(out / "mapping.local.json")])
    assert result.exit_code == 0, result.output
    assert load_workbook(final / "anonymized.xlsx").active["A2"].value == original


def test_bad_file_is_reported_and_remaining_files_are_processed(tmp_path):
    source = tmp_path / "months"
    source.mkdir()
    (source / "01.xlsx").write_bytes(b"broken workbook with private text")
    make_month(source / "02.csv")
    out = tmp_path / "out"
    result = CliRunner().invoke(app, ["anonymize", str(source), "-o", str(out)])
    assert result.exit_code == 1
    report = json.loads((out / "batch_manifest.json").read_text())
    assert report["success_count"] == 1
    assert report["failure_count"] == 1
    assert [item["status"] for item in report["files"]] == ["failed", "success"]
    assert report["files"][0]["error_type"] == "BadZipFile"
    assert "broken workbook with private text" not in (out / "batch_manifest.json").read_text()
    assert len(load_local_mapping(out / "mapping.local.json").entries) > 0


def test_batch_refuses_nonempty_output_without_overwriting(tmp_path):
    source = tmp_path / "months"
    source.mkdir()
    make_month(source / "07.csv")
    out = tmp_path / "out"
    out.mkdir()
    sentinel = out / "mapping.local.json"
    sentinel.write_text("keep existing mapping", encoding="utf-8")
    result = CliRunner().invoke(app, ["anonymize", str(source), "-o", str(out)])
    assert result.exit_code == 1
    assert "空目录" in result.output
    assert sentinel.read_text() == "keep existing mapping"
    assert list(out.iterdir()) == [sentinel]


def test_no_matching_files_produces_clear_error_without_output(tmp_path):
    source = tmp_path / "months"
    source.mkdir()
    nested = source / "nested"
    nested.mkdir()
    make_month(nested / "07.csv")
    out = tmp_path / "out"
    result = CliRunner().invoke(app, ["anonymize", str(source), "-o", str(out)])
    assert result.exit_code == 1
    assert "XLSX/CSV" in result.output
    assert not out.exists()


def test_invalid_mapping_fails_before_any_output(tmp_path):
    source = tmp_path / "months"
    source.mkdir()
    make_month(source / "07.csv")
    seed = tmp_path / "mapping.local.json"
    seed.write_text("invalid private mapping content", encoding="utf-8")
    out = tmp_path / "out"
    result = CliRunner().invoke(app, ["anonymize", str(source), "-o", str(out), "--mapping", str(seed)])
    assert result.exit_code == 1
    assert "映射文件" in result.output
    assert "invalid private mapping content" not in result.output
    assert not out.exists()
