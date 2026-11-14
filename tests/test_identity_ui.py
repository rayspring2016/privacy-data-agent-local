from pathlib import Path
from io import BytesIO

import pytest
from streamlit.testing.v1 import AppTest
from privacy_data_agent import identity_store


def test_numbering_mode_is_visible_and_can_be_switched():
    script = Path(__file__).parents[1] / "src/privacy_data_agent/web_app.py"
    app = AppTest.from_file(str(script)).run()
    assert not app.exception
    mode = next(item for item in app.radio if item.label == "编号方式")
    assert mode.value == "统一编号（跨月份、跨项目）"
    mode.set_value("每次生成新编号").run()
    assert not app.exception
    assert app.session_state.identity_mode == "每次生成新编号"


@pytest.mark.parametrize("mode,uses_registry", [
    ("统一编号（跨月份、跨项目）", True), ("每次生成新编号", False),
])
def test_processing_uses_the_selected_numbering_mode(tmp_path, monkeypatch, mode, uses_registry):
    registry = tmp_path / "private/mapping.local.json"
    monkeypatch.setattr(identity_store, "identity_mapping_path", lambda: registry)
    script = Path(__file__).parents[1] / "src/privacy_data_agent/web_app.py"
    app = AppTest.from_file(str(script)).run()
    file = BytesIO("姓名,工号,部门\n张三,000123,销售部\n".encode())
    file.name = "employees.csv"
    app.session_state["anonymize_files"] = [file]
    app.session_state["identity_mode"] = mode
    app.session_state["processing"] = True
    app.run()
    assert not app.exception
    assert app.session_state.anonymize_result is not None
    assert registry.exists() is uses_registry


def test_batch_page_continues_after_unresolved_employee(tmp_path, monkeypatch):
    import zipfile

    registry = tmp_path / "private/mapping.local.json"
    monkeypatch.setattr(identity_store, "identity_mapping_path", lambda: registry)
    script = Path(__file__).parents[1] / "src/privacy_data_agent/web_app.py"
    app = AppTest.from_file(str(script)).run()
    app.session_state["allow_unverified_people"] = False

    def upload(name, data):
        file = BytesIO(data.encode())
        file.name = name
        return file

    good = "姓名,工号,部门\n张三,000123,销售部\n"
    app.session_state["anonymize_files"] = [
        upload("01.csv", good),
        upload("02.csv", "姓名,部门\n李四,销售部\n"),
        upload("03.csv", good),
    ]
    app.session_state["processing"] = True
    app.run()
    assert not app.exception
    batch = app.session_state.anonymize_batch_result
    assert batch is not None
    assert batch["files_processed"] == 2
    assert batch["failures"][0]["name"] == "02.csv"
    assert "李四" not in str(batch["failures"])
    assert registry.exists()
    assert any("待核验" in warning.value for warning in app.warning)
    with zipfile.ZipFile(BytesIO(batch["consolidated_zip"])) as archive:
        assert "03_anonymized.xlsx" in archive.namelist()
        assert "02_anonymized.xlsx" not in archive.namelist()
