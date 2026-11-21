from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from openpyxl import Workbook, load_workbook
from openpyxl.descriptors.nested import NestedInteger
from openpyxl.pivot.cache import CacheDefinition, CacheField, CacheSource, FieldGroup, WorksheetSource
from openpyxl.pivot.table import Location, RowColField, TableDefinition

from privacy_data_agent.workbook_anonymizer import anonymize_xlsx_bytes


def grouped_pivot_bytes():
    book = Workbook()
    source = book.active
    source.title = "Detail"
    source.append(["姓名", "提成"])
    source.append(["张三", 100])
    source.append(["李四", 200])
    sheet = book.create_sheet("Summary")
    sheet.append(["姓名", "提成"])
    sheet.append(["张三", 100])
    sheet.append(["李四", 200])
    pivot = TableDefinition(
        name="GroupedPivot", cacheId=1, dataCaption="Data", compact=False,
        location=Location(ref="A1:B3", firstHeaderRow=0, firstDataRow=1, firstDataCol=1),
        rowFields=[RowColField(x=0)],
    )
    pivot.cache = CacheDefinition(
        cacheSource=CacheSource(type="worksheet", worksheetSource=WorksheetSource(ref="A1:B3", sheet="Detail")),
        cacheFields=[CacheField(name="姓名"), CacheField(name="提成")],
    )
    sheet.add_pivot(pivot)
    original = BytesIO()
    book.save(original)
    output = BytesIO()
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    # Inject Excel's grouping XML because the upstream descriptor cannot create it.
    with ZipFile(original) as archive, ZipFile(output, "w", ZIP_DEFLATED) as target:
        for item in archive.infolist():
            content = archive.read(item.filename)
            if item.filename.startswith("xl/pivotCache/pivotCacheDefinition"):
                root = ET.fromstring(content)
                field = root.find(ns + "cacheFields")[0]
                group = ET.SubElement(field, ns + "fieldGroup", {"base": "0"})
                indices = ET.SubElement(group, ns + "discretePr", {"count": "2"})
                for value in (0, 1):
                    ET.SubElement(indices, ns + "x", {"v": str(value)})
                content = ET.tostring(root, encoding="utf-8")
            target.writestr(item, content)
    return output.getvalue()


@pytest.mark.parametrize("preserve", [False, True])
def test_grouped_pivot_loads_and_anonymizes_without_raw_cache(monkeypatch, preserve):
    content = grouped_pivot_bytes()
    monkeypatch.setattr(FieldGroup.discretePr, "expected_type", NestedInteger)
    result = anonymize_xlsx_bytes(content, preserve_calculations=preserve)
    book = load_workbook(BytesIO(result.workbook_bytes))
    for sheet in book:
        assert sheet["A2"].value.startswith("PDA_")
        assert sheet["A3"].value.startswith("PDA_")
    with ZipFile(BytesIO(result.workbook_bytes)) as archive:
        assert not any("pivotCache" in name or "pivotTables" in name for name in archive.namelist())
        payload = b"\n".join(archive.read(name) for name in archive.namelist())
        assert "张三".encode() not in payload and "李四".encode() not in payload
    # The corrected reader must retain both indices when loading the original.
    group = load_workbook(BytesIO(content))["Summary"]._pivots[0].cache.cacheFields[0].fieldGroup
    assert [index.v for index in group.discretePr] == [0, 1]
    loaded = load_workbook(BytesIO(content))
    saved = BytesIO()
    loaded.save(saved)
    reloaded = load_workbook(BytesIO(saved.getvalue()))
    assert [index.v for index in reloaded["Summary"]._pivots[0].cache.cacheFields[0].fieldGroup.discretePr] == [0, 1]


def test_web_processes_grouped_pivot(tmp_path, monkeypatch):
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    from privacy_data_agent import identity_store

    monkeypatch.setattr(identity_store, "identity_mapping_path", lambda: tmp_path / "identity.json")
    monkeypatch.setattr(FieldGroup.discretePr, "expected_type", NestedInteger)
    app = AppTest.from_file(str(Path(__file__).parents[1] / "src/privacy_data_agent/web_app.py")).run()
    upload = BytesIO(grouped_pivot_bytes())
    upload.name = "grouped.xlsx"
    app.session_state["anonymize_files"] = [upload]
    app.session_state["processing"] = True
    app.run()
    assert not app.exception and not app.error
    assert app.session_state.anonymize_result["anonymized_xlsx"]
