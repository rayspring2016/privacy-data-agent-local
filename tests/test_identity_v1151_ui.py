from io import BytesIO
from pathlib import Path

from openpyxl import Workbook, load_workbook
from streamlit.testing.v1 import AppTest

from privacy_data_agent import identity_store


def test_web_processes_single_workbook_with_multiple_matching_name_columns(tmp_path, monkeypatch):
    mapping_path = tmp_path / "mapping.local.json"
    monkeypatch.setattr(identity_store, "identity_mapping_path", lambda: mapping_path)
    file = BytesIO()
    file.name = "commission.xlsx"
    book = Workbook()
    book.active.append(["姓名", "部门", "提成"])
    book.active.append(["张三", "销售部", 200])
    roster = book.create_sheet("人员")
    roster.append(["员工姓名", "姓名", "工号", "合同编号", "部门"])
    roster.append(["张三", "张三", "000123", "HT-1", "销售部"])
    book.save(file)

    app = AppTest.from_file(str(Path(__file__).parents[1] / "src/privacy_data_agent/web_app.py")).run()
    app.session_state["anonymize_files"] = [file]
    app.session_state["processing"] = True
    app.run()
    assert not app.exception
    assert not app.error
    result = app.session_state.anonymize_result
    output = load_workbook(BytesIO(result["anonymized_xlsx"]))
    actual = output.worksheets[0]["A2"].value
    assert actual.startswith("PDA_")
    assert actual == output.worksheets[1]["A2"].value == output.worksheets[1]["B2"].value
    assert mapping_path.is_file()
