from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from xml.etree import ElementTree as ET
import json

from openpyxl import Workbook, load_workbook
from streamlit.testing.v1 import AppTest
from typer.testing import CliRunner
import pytest

from privacy_data_agent import identity_store
from privacy_data_agent.cli import app as cli
from privacy_data_agent.web_helpers import anonymize_upload, anonymize_batch


def cached_workbook(cached_value="123.45", cached_type=None, extra_formula=None, extra_value="1", extra_type=None, external_link=False):
    book = Workbook()
    book.active.append(["工号", "姓名", "客户名称", "回款金额", "提成比例", "提成", "公司总支出", "部门", "电话", "提成系数"])
    book.active.append([123456, "张三", "示例公司", 1234.5, 0.1, "=D2*E2", 1234.5, "销售部", 13800138000, "1.25"])
    book.active["K1"] = "提成说明"
    book.active["K2"] = "张三按标准核算"
    if extra_formula:
        book.active["L1"] = "人数核对"
        book.active["L2"] = extra_formula
    if external_link:
        from openpyxl.workbook.external_link.external import ExternalBook, ExternalCell, ExternalLink, ExternalRow, ExternalSheetData, ExternalSheetDataSet, ExternalSheetNames
        from openpyxl.packaging.relationship import Relationship
        link = ExternalLink(externalBook=ExternalBook(id="rId1", sheetNames=ExternalSheetNames(sheetName=["Data"]), sheetDataSet=ExternalSheetDataSet(sheetData=[ExternalSheetData(sheetId=0, row=[ExternalRow(r=1, cell=[ExternalCell(r="A1", t="str", v="张三")])])])))
        link.file_link = Relationship(Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/externalLinkPath", Target="file:///private/source.xlsx", TargetMode="External")
        book._external_links.append(link)
    book.active["E2"].number_format = "0.00%"
    book.active["F2"].number_format = "0.00"
    memory = BytesIO(); book.save(memory)
    out = BytesIO()
    with ZipFile(memory) as source, ZipFile(out, "w", ZIP_DEFLATED) as target:
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename == "xl/worksheets/sheet1.xml":
                root = ET.fromstring(data); ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                cell = root.find(".//x:c[@r='F2']", ns)
                cell.find("x:v", ns).text = cached_value
                if cached_type:
                    cell.set("t", cached_type)
                if extra_formula:
                    extra = root.find(".//x:c[@r='L2']", ns)
                    extra.find("x:v", ns).text = extra_value
                    if extra_type:
                        extra.set("t", extra_type)
                data = ET.tostring(root, encoding="utf-8")
            target.writestr(item, data)
    return out.getvalue()


@pytest.fixture
def registry(tmp_path, monkeypatch):
    path = tmp_path / "identity/mapping.local.json"
    monkeypatch.setattr(identity_store, "identity_mapping_path", lambda: path)
    return path


def test_analysis_keeps_numbers_and_cached_result_but_masks_identifiers(registry):
    result = anonymize_upload("commission.xlsx", cached_workbook(), consistent_ids=True, allow_unverified_people=True, preserve_calculations=True)
    book = load_workbook(BytesIO(result["anonymized_xlsx"]))
    sheet = load_workbook(BytesIO(result["anonymized_xlsx"]), data_only=True).active
    assert [sheet[f"{col}2"].value for col in ["D", "E", "F", "G", "J"]] == [1234.5, 0.1, 123.45, 1234.5, "1.25"]
    assert book.active["F2"].value == "=D2*E2" and sheet["E2"].number_format == "0.00%"
    assert book.calculation.calcMode == "manual"
    assert all(sheet[f"{col}2"].value.startswith("PDA_") for col in ["A", "B", "C", "H", "I"])
    assert result["formula_count"] == 1
    assert sheet["K2"].value == sheet["B2"].value + "按标准核算"


def test_missing_formula_cache_stops_without_updating_registry(registry):
    book = Workbook(); book.active.append(["工号", "姓名", "提成"]); book.active.append([123456, "张三", "=100*0.1"])
    memory = BytesIO(); book.save(memory)
    with pytest.raises(ValueError, match="C2.*计算结果") as error:
        anonymize_upload("missing.xlsx", memory.getvalue(), consistent_ids=True, preserve_calculations=True)
    assert "张三" not in str(error.value) and not registry.exists()


def test_saved_empty_string_formula_result_is_supported(registry):
    result = anonymize_upload("empty.xlsx", cached_workbook(None, "str"), consistent_ids=True, preserve_calculations=True)
    assert result["formula_count"] == 1
    assert load_workbook(BytesIO(result["anonymized_xlsx"]), data_only=True).active["F2"].value is None


def test_formula_identity_text_changes_but_numbers_references_and_cache_are_preserved(registry):
    result = anonymize_upload("literal.xlsx", cached_workbook(extra_formula='=COUNTIF(B2:B2,"张三")'), consistent_ids=True, preserve_calculations=True)
    book = load_workbook(BytesIO(result["anonymized_xlsx"]))
    token = book.active["B2"].value
    assert book.active["L2"].value == f'=COUNTIF(B2:B2,"{token}")'
    assert load_workbook(BytesIO(result["anonymized_xlsx"]), data_only=True).active["L2"].value == 1


def test_numeric_formula_constants_do_not_become_identifier_tokens(registry):
    formula = '=IF(D2>0,"123456","0")'
    data = cached_workbook(extra_formula=formula, extra_value="123456", extra_type="str")
    result = anonymize_upload("constants.xlsx", data, consistent_ids=True, preserve_calculations=True)
    assert load_workbook(BytesIO(result["anonymized_xlsx"])).active["L2"].value == formula


def test_restoring_a_calculation_workbook_preserves_its_cached_numbers(registry):
    from privacy_data_agent.models import MappingFile
    from privacy_data_agent.restorer import restore_bytes
    result = anonymize_upload("restore.xlsx", cached_workbook(), consistent_ids=True, preserve_calculations=True)
    restored = restore_bytes(result["anonymized_xlsx"], "restore.xlsx", MappingFile.model_validate_json(result["mapping_json"]))
    assert load_workbook(BytesIO(restored), data_only=True).active["F2"].value == 123.45
    assert load_workbook(BytesIO(restored)).active["F2"].value == "=D2*E2"


@pytest.mark.parametrize("preserve", [False, True])
def test_external_reference_structure_remains_but_private_cache_is_removed(registry, preserve):
    result = anonymize_upload("external.xlsx", cached_workbook(external_link=True), consistent_ids=True, preserve_calculations=preserve)
    book = load_workbook(BytesIO(result["anonymized_xlsx"]))
    assert len(book._external_links) == 1
    assert book._external_links[0].externalBook.sheetDataSet is None
    assert book._external_links[0].file_link.Target == "external-source-01.xlsx"
    assert book.active["F2"].value == "=D2*E2"


def test_batch_and_cli_apply_analysis_mode(registry, tmp_path):
    data = cached_workbook()
    result = anonymize_batch([("a.xlsx", data), ("b.xlsx", data)], consistent_ids=True, preserve_calculations=True)
    assert result["files_processed"] == 2 and result["formula_count"] == 2
    assert load_workbook(BytesIO(result["results"][1]["anonymized_bytes"]), data_only=True).active["F2"].value == 123.45
    source = tmp_path / "source.xlsx"; source.write_bytes(data); out = tmp_path / "out"
    command = CliRunner().invoke(cli, ["anonymize", str(source), "--consistent-ids", "--preserve-calculations", "-o", str(out)])
    assert command.exit_code == 0, command.output
    manifest = json.loads((out / "local_manifest.json").read_text())
    assert manifest["flags"]["preserve_calculations"] is True and manifest["formula_count"] == 1


def test_web_can_choose_preserve_calculations(registry):
    app = AppTest.from_file(str(Path(__file__).parents[1] / "src/privacy_data_agent/web_app.py")).run()
    setting = next(c for c in app.checkbox if c.label == "核验模式（保留数值和原公式）")
    setting.check().run()
    file = BytesIO(cached_workbook()); file.name = "commission.xlsx"
    app.session_state["anonymize_files"] = [file]; app.session_state["processing"] = True; app.run()
    assert not app.exception and not app.error
    result = app.session_state.anonymize_result
    assert result["formula_count"] == 1
    assert load_workbook(BytesIO(result["anonymized_xlsx"]), data_only=True).active["F2"].value == 123.45
