from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
import csv
import json

import pytest
from openpyxl import Workbook, load_workbook
from streamlit.testing.v1 import AppTest
from typer.testing import CliRunner

from privacy_data_agent import identity_store
from privacy_data_agent.cli import app as cli_app
from privacy_data_agent.models import MappingFile
from privacy_data_agent.restorer import restore_bytes
from privacy_data_agent.web_helpers import anonymize_upload, anonymize_batch


@pytest.fixture
def registry(tmp_path, monkeypatch):
    path = tmp_path / "registry/mapping.local.json"
    monkeypatch.setattr(identity_store, "identity_mapping_path", lambda: path)
    return path


@pytest.mark.parametrize("encrypt", [False, True])
def test_unconfirmed_occurrences_are_distinct_and_confirmed_ids_stay_stable(registry, encrypt):
    from cryptography.fernet import Fernet
    encryption_key = Fernet.generate_key().decode() if encrypt else None
    book = Workbook()
    book.active.append(["工号", "姓名", "SDR"])
    book.active.append(["000123", "张三", "李四/李四"])
    book.active.append([None, "王五", None])
    book.active.append([None, "王五", None])
    stream = BytesIO()
    book.save(stream)
    first = anonymize_upload("people.xlsx", stream.getvalue(), consistent_ids=True, allow_unverified_people=True, encryption_key=encryption_key)
    out = load_workbook(BytesIO(first["anonymized_xlsx"]))
    pending = out.active["C2"].value.split("/") + [out.active["B3"].value, out.active["B4"].value]
    assert len(set(pending)) == 4
    assert all(token.startswith("PDA_REVIEW_") for token in pending)
    assert first["review_count"] == 4
    assert not any(name in first["review_csv"].decode("utf-8-sig") for name in ("张三", "李四", "王五"))
    rows = list(csv.DictReader(first["review_csv"].decode("utf-8-sig").splitlines()))
    assert set(row["token"] for row in rows) == set(pending)
    saved = MappingFile.model_validate_json(registry.read_bytes())
    assert len(saved.people) == 1
    assert not any(entry.token.startswith("PDA_REVIEW_") for entry in saved.entries)
    second = anonymize_upload("people.xlsx", stream.getvalue(), consistent_ids=True, allow_unverified_people=True)
    next_out = load_workbook(BytesIO(second["anonymized_xlsx"]))
    assert next_out.active["B2"].value == out.active["B2"].value
    assert next_out.active["B3"].value not in pending
    with ZipFile(BytesIO(first["zip_bundle"])) as archive:
        assert archive.read("identity_review.csv") == first["review_csv"]
    restored = load_workbook(BytesIO(restore_bytes(first["anonymized_xlsx"], "people.xlsx", MappingFile.model_validate_json(first["mapping_json"]))))
    assert restored.active["C2"].value == "李四/李四"


def test_anchor_conflicts_still_stop_when_continuing_unmatched_names(registry):
    anonymize_upload("a.csv", b"name,employee_id,email\nAlice,000123,a@example.com\n", consistent_ids=True)
    before = registry.read_bytes()
    with pytest.raises(ValueError, match="不同工号"):
        anonymize_upload("b.csv", b"name,employee_id,email\nBob,000124,a@example.com\n", consistent_ids=True, allow_unverified_people=True)
    assert registry.read_bytes() == before


def test_batch_exports_per_file_review_reports(registry):
    content = "姓名\n张三\n".encode()
    result = anonymize_batch([("a.csv", content), ("b.csv", content)], consistent_ids=True, allow_unverified_people=True)
    assert result["files_processed"] == 2 and not result["failures"]
    assert result["review_count"] == 2
    tokens = [load_workbook(BytesIO(item["anonymized_bytes"])).active["A2"].value for item in result["results"]]
    assert tokens[0] != tokens[1]
    with ZipFile(BytesIO(result["consolidated_zip"])) as archive:
        assert len([name for name in archive.namelist() if name.endswith("identity_review.csv")]) == 2


def test_cli_can_continue_with_local_review_manifest(registry, tmp_path):
    source = tmp_path / "input.csv"
    source.write_text("姓名\n张三\n张三\n")
    output = tmp_path / "output"
    result = CliRunner().invoke(cli_app, ["anonymize", str(source), "--consistent-ids", "--allow-unverified-people", "--output-dir", str(output)])
    assert result.exit_code == 0, result.output
    rows = list(csv.DictReader((output / "anonymized.csv").open()))
    assert rows[0]["姓名"] != rows[1]["姓名"]
    assert (output / "identity_review.csv").exists()
    manifest = json.loads((output / "local_manifest.json").read_text())
    assert manifest["review_count"] == 2
    assert manifest["flags"]["allow_unverified_people"] is True


def test_web_defaults_to_continuing_with_review(registry):
    app = AppTest.from_file(str(Path(__file__).parents[1] / "src/privacy_data_agent/web_app.py")).run()
    setting = next(item for item in app.checkbox if item.label == "身份不明时继续脱敏，并标记待核验")
    assert setting.value is True
    file = BytesIO("姓名\n张三\n".encode()); file.name = "people.csv"
    app.session_state["anonymize_files"] = [file]
    app.session_state["processing"] = True
    app.run()
    assert not app.exception and not app.error
    assert app.session_state.anonymize_result["review_count"] == 1
    assert any("待核验" in item.value for item in app.warning)


def test_unconfirmed_name_repeated_in_custom_column_gets_another_temporary_id(registry):
    book = Workbook(); book.active.append(["业务归口"]); book.active.append(["张三"])
    other = book.create_sheet("角色"); other.append(["SDR"]); other.append(["张三"])
    stream = BytesIO(); book.save(stream)
    result = anonymize_upload("custom.xlsx", stream.getvalue(), consistent_ids=True, allow_unverified_people=True)
    out = load_workbook(BytesIO(result["anonymized_xlsx"]))
    tokens = [sheet["A2"].value for sheet in out]
    assert all(token.startswith("PDA_REVIEW_") for token in tokens)
    assert tokens[0] != tokens[1]
    assert result["review_count"] == 2


def test_imported_temporary_token_without_identity_metadata_is_not_saved_globally(registry):
    from privacy_data_agent.identity_store import UnifiedIdentityStore
    from privacy_data_agent.models import MappingEntry, EntityType
    seed = MappingFile(entries=[MappingEntry(entity_type=EntityType.EMPLOYEE, original="张三", token="PDA_REVIEW_1234567890ABCDEF")])
    with UnifiedIdentityStore(seed) as store:
        store.save(store.mapping)
    assert MappingFile.model_validate_json(registry.read_bytes()).entries == []
