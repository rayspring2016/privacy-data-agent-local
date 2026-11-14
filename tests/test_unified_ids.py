import json
from io import BytesIO

import pandas as pd
from openpyxl import Workbook, load_workbook
from typer.testing import CliRunner
import pytest

from privacy_data_agent import identity_store
from privacy_data_agent.cli import app
from privacy_data_agent.web_helpers import anonymize_batch, anonymize_upload
from privacy_data_agent.detectors import detect_column_entity_type
from privacy_data_agent.models import EntityType


def content(name="张三", employee_id="000123"):
    return f"员工姓名,工号,客户名称,部门,提成,月薪\n{name},{employee_id},上海春雷科技有限公司,销售一部,1250.5,15000\n".encode()


@pytest.mark.parametrize("column", ["工号", "员工编号", "员工号", "employee_id", "employee_no", "staff_id"])
def test_employee_id_headers_share_one_entity_type(column):
    assert detect_column_entity_type(column) == EntityType.EMPLOYEE_ID


def test_cli_and_web_share_identifiers_across_months_and_projects(tmp_path, monkeypatch):
    path = tmp_path / "private/mapping.local.json"
    monkeypatch.setattr(identity_store, "identity_mapping_path", lambda: path)
    source = tmp_path / "commission.xlsx"
    book = Workbook()
    book.active.append(["姓名", "员工编号", "客户名称", "部门", "提成"])
    book.active.append(["张三", "000123", "上海春雷科技有限公司", "销售一部", 1250.5])
    book.save(source)
    result = CliRunner().invoke(app, ["anonymize", str(source), "--consistent-ids", "--keep-salary-group", "commission", "-o", str(tmp_path / "cli")])
    assert result.exit_code == 0, result.output
    cli = load_workbook(tmp_path / "cli/anonymized.xlsx").active
    first = anonymize_upload("payroll.csv", content(), consistent_ids=True)
    web = load_workbook(BytesIO(first["anonymized_xlsx"])).active
    assert cli["A2"].value == web["A2"].value
    assert cli["B2"].value == web["B2"].value
    assert cli["C2"].value == web["C2"].value
    assert cli["E2"].value == 1250.5
    assert str(web["F2"].value).startswith("PDA_")
    batch = anonymize_batch([("next.csv", content()), ("new.csv", content("李四", "000124"))], consistent_ids=True)
    repeated = load_workbook(BytesIO(batch["results"][0]["anonymized_bytes"])).active
    assert repeated["A2"].value == cli["A2"].value
    assert repeated["B2"].value == cli["B2"].value
    assert "李四" in path.read_text()


def test_cli_directory_partial_failure_keeps_successful_identifiers(tmp_path, monkeypatch):
    path = tmp_path / "private/mapping.local.json"
    monkeypatch.setattr(identity_store, "identity_mapping_path", lambda: path)
    folder = tmp_path / "input"
    folder.mkdir()
    (folder / "01.xlsx").write_bytes(b"broken")
    (folder / "02.csv").write_bytes(content())
    result = CliRunner().invoke(app, ["anonymize", str(folder), "--consistent-ids", "-o", str(tmp_path / "out")])
    assert result.exit_code == 1
    assert path.exists()
    out = pd.read_csv(tmp_path / "out/files/0002/anonymized.csv")
    again = anonymize_upload("attendance.csv", content(), consistent_ids=True)
    assert load_workbook(BytesIO(again["anonymized_xlsx"])).active["A2"].value == out.iloc[0]["员工姓名"]


def test_random_mode_does_not_access_or_change_global_registry(tmp_path, monkeypatch):
    path = tmp_path / "private/mapping.local.json"
    monkeypatch.setattr(identity_store, "identity_mapping_path", lambda: path)
    shared = anonymize_upload("first.csv", content(), consistent_ids=True)
    original = path.read_bytes()
    first = anonymize_upload("fresh1.csv", content(), consistent_ids=False)
    second = anonymize_upload("fresh2.csv", content(), consistent_ids=False)
    tokens = [load_workbook(BytesIO(r["anonymized_xlsx"])).active["A2"].value for r in (shared, first, second)]
    assert len(set(tokens)) == 3
    assert path.read_bytes() == original


def test_existing_mapping_can_initialize_registry_and_conflicts_fail(tmp_path, monkeypatch):
    path = tmp_path / "private/mapping.local.json"
    monkeypatch.setattr(identity_store, "identity_mapping_path", lambda: path)
    previous = anonymize_upload("old.csv", content())
    stable = anonymize_upload("next.csv", content(), seed_mapping_filename="mapping.local.json", seed_mapping_content=previous["mapping_json"].encode(), consistent_ids=True)
    old_ids = [entry for entry in json.loads(previous["mapping_json"])["entries"] if entry["entity_type"] == "employee_id"]
    current = json.loads(stable["mapping_json"])
    assert all(entry in current["entries"] for entry in old_ids)
    assert len(current["people"]) == 1
    conflicting = anonymize_upload("other.csv", content())
    before = path.read_bytes()
    try:
        anonymize_upload("new.csv", content(), seed_mapping_filename="mapping.local.json", seed_mapping_content=conflicting["mapping_json"].encode(), consistent_ids=True)
    except ValueError as exc:
        assert "冲突" in str(exc)
    else:
        assert False, "must reject ambiguous historical numbering"
    assert path.read_bytes() == before


def test_batch_preserves_distinct_types_when_original_text_matches(tmp_path, monkeypatch):
    path = tmp_path / "private/mapping.local.json"
    monkeypatch.setattr(identity_store, "identity_mapping_path", lambda: path)
    same = "姓名,部门,工号\n张三,张三,000123\n".encode()
    result = anonymize_batch([("one.csv", same), ("two.csv", same)], consistent_ids=True)
    mapping = json.loads(result["final_mapping_json"])
    entries = [e for e in mapping["entries"] if e["original"] == "张三"]
    assert {e["entity_type"] for e in entries} == {"employee", "department"}
    assert len({e["token"] for e in entries}) == 2


def test_unresolved_file_has_a_review_reason_without_leaking_names(tmp_path, monkeypatch):
    path = tmp_path / "private/mapping.local.json"
    monkeypatch.setattr(identity_store, "identity_mapping_path", lambda: path)
    source = tmp_path / "input"
    source.mkdir()
    (source / "unknown.csv").write_bytes("姓名,部门\n张三,销售部\n".encode())
    result = CliRunner().invoke(app, ["anonymize", str(source), "--consistent-ids", "-o", str(tmp_path / "out")])
    assert result.exit_code == 1
    manifest = json.loads((tmp_path / "out/batch_manifest.json").read_text())
    record = manifest["files"][0]
    assert record["status"] == "needs_review"
    assert "待核验" in record["reason"]
    assert "张三" not in record["reason"]
