"""Cross-feature release checks using synthetic HR workbooks only."""
from io import BytesIO
from itertools import product
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest
from openpyxl import Workbook, load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import Font, PatternFill

from privacy_data_agent.restorer import restore_bytes
from privacy_data_agent.web_helpers import anonymize_batch, anonymize_upload
from privacy_data_agent.workbook_anonymizer import anonymize_xlsx_bytes


def workbook_bytes(book):
    stream = BytesIO()
    book.save(stream)
    return stream.getvalue()


def text_payload(content):
    parts = []
    with ZipFile(BytesIO(content)) as archive:
        for name in archive.namelist():
            if name.endswith('.xml'):
                parts.extend(ET.fromstring(archive.read(name)).itertext())
    return '\n'.join(parts)


@pytest.fixture
def registry(tmp_path, monkeypatch):
    from privacy_data_agent import identity_store
    path = tmp_path / 'identities.json'
    monkeypatch.setattr(identity_store, 'identity_mapping_path', lambda: path)
    return path


@pytest.mark.parametrize('layout,unified,preserve,department,salary', list(product(
    ['table', 'title', 'label_value', 'hidden'], [False, True], [False, True], [False, True], [False, True],
)))
def test_release_option_layout_matrix(registry, layout, unified, preserve, department, salary):
    book = Workbook()
    sheet = book.active
    if layout == 'title':
        sheet.append(['员工信息'])
        sheet.merge_cells('A1:E1')
    headers = ['姓名', '工号', '部门', '月薪', '岗位']
    values = ['张三', '000123', '产品中心/设计部', 17001.25, '设计师']
    if layout == 'label_value':
        sheet.append(['字段', '值'])
        for label, value in zip(headers, values):
            sheet.append([label, value])
    else:
        sheet.append(headers)
        sheet.append(values)
    if layout == 'hidden':
        sheet.sheet_state = 'veryHidden'
        book.create_sheet('说明')['A1'] = '处理说明'
    result = anonymize_upload(
        'matrix.xlsx', workbook_bytes(book), consistent_ids=unified,
        preserve_calculations=preserve, anonymize_department=department, anonymize_salary=salary,
    )
    output = load_workbook(BytesIO(result['anonymized_xlsx']))
    row = ([output.worksheets[0].cell(i + 2, 2).value for i in range(5)]
           if layout == 'label_value' else list(output.worksheets[0].values)[-1])
    assert all(str(value).startswith('PDA_') for value in row[:2])
    assert row[2].startswith('PDA_') if department else row[2] == values[2]
    assert row[3].startswith('PDA_') if salary and not preserve else row[3] == values[3]
    assert row[4] == values[4]
    assert output.worksheets[0].sheet_state == sheet.sheet_state
    if layout == 'title':
        assert 'A1:E1' in output.active.merged_cells


@pytest.mark.parametrize('preserve', [False, True])
@pytest.mark.parametrize('surface', ['remark', 'comment', 'page_header', 'properties', 'formula'])
def test_known_identity_is_not_left_in_secondary_text(preserve, surface):
    book = Workbook()
    sheet = book.active
    sheet.append(['姓名', '工号', '说明'])
    sheet.append(['张三', '000123', '正常'])
    if surface == 'remark':
        sheet['C2'] = '联系人：张三'
    elif surface == 'comment':
        sheet['C2'].comment = Comment('员工张三，工号000123', '张三')
    elif surface == 'page_header':
        sheet.oddHeader.center.text = '制表人：张三'
        sheet.evenFooter.right.text = '制表人：张三'
    elif surface == 'properties':
        book.properties.creator = '张三'
        book.properties.lastModifiedBy = '张三'
    else:
        sheet['C2'] = '=COUNTIF(A2:A2,"张三")'
    content = workbook_bytes(book)
    if surface == 'formula' and preserve:
        from test_lookup_identifiers import with_cache
        content = with_cache(book, {'xl/worksheets/sheet1.xml': {'C2': 1}})
    result = anonymize_xlsx_bytes(content, preserve_calculations=preserve)
    assert '张三' not in text_payload(result.workbook_bytes)
    if surface == 'comment':
        assert '000123' not in text_payload(result.workbook_bytes)
    if surface == 'formula':
        formula = load_workbook(BytesIO(result.workbook_bytes)).active['C2'].value
        assert formula.startswith('=COUNTIF(') and 'PDA_' in formula
    restored = restore_bytes(result.workbook_bytes, 'restored.xlsx', result.mapping)
    assert 'PDA_' not in text_payload(restored)


def test_known_name_in_sheet_title_requires_review():
    book = Workbook()
    book.active.title = '张三的记录'
    book.active.append(['姓名', '工号'])
    book.active.append(['张三', '000123'])
    with pytest.raises(ValueError, match='工作表名称'):
        anonymize_xlsx_bytes(workbook_bytes(book))


@pytest.mark.parametrize('preserve', [False, True])
def test_label_value_row_count_is_not_zero(preserve):
    book = Workbook()
    book.active.append(['字段', '值'])
    for pair in [('姓名', '张三'), ('工号', '000123'), ('部门', '研发部')]:
        book.active.append(pair)
    result = anonymize_xlsx_bytes(workbook_bytes(book), preserve_calculations=preserve)
    assert result.row_count == 3


def test_style_and_original_values_round_trip():
    book = Workbook()
    sheet = book.active
    sheet.append(['姓名', '工号', '部门', '月薪'])
    sheet.append(['张三', '000123', '研发部', 17001.25])
    sheet['A2'].font = Font(bold=True, color='FF0000')
    sheet['A2'].fill = PatternFill('solid', fgColor='00FF00')
    sheet.column_dimensions['A'].width = 24
    sheet.row_dimensions[2].hidden = True
    sheet.freeze_panes = 'C2'
    result = anonymize_xlsx_bytes(workbook_bytes(book))
    restored = load_workbook(BytesIO(restore_bytes(result.workbook_bytes, 'output.xlsx', result.mapping)))
    assert list(restored.active.values)[1] == ('张三', '000123', '研发部', '17001.25')
    assert restored.active['A2'].font.bold and restored.active['A2'].fill.fgColor.rgb == '0000FF00'
    assert restored.active.row_dimensions[2].hidden and restored.active.freeze_panes == 'C2'
    assert restored.active.column_dimensions['A'].width == 24


def test_mixed_batch_failure_does_not_pollute_registry(registry):
    good = '姓名,工号,邮箱\n张三,000123,qa@example.com\n'.encode()
    conflict = '姓名,工号,邮箱\n李四,000124,qa@example.com\n'.encode()
    result = anonymize_batch([('same.csv', good), ('bad.xlsx', b'not an Excel file'),
                              ('conflict.csv', conflict), ('same.csv', good)], consistent_ids=True)
    assert result['files_processed'] == 2 and len(result['failures']) == 2
    assert all('张三' not in item['reason'] and '李四' not in item['reason'] for item in result['failures'])
    with ZipFile(BytesIO(result['consolidated_zip'])) as archive:
        names = archive.namelist()
        assert len(names) == len(set(names))
    assert '000124' not in registry.read_text()


def test_bad_preview_cannot_block_the_whole_batch(registry, monkeypatch):
    from pathlib import Path
    import streamlit as st
    from streamlit.testing.v1 import AppTest

    good = BytesIO('姓名,工号\n张三,000123\n'.encode())
    good.name, good.size = 'good.csv', len(good.getvalue())
    bad = BytesIO(b'not an Excel file')
    bad.name, bad.size = 'bad.xlsx', len(bad.getvalue())
    original = st.file_uploader

    def upload(*args, **kwargs):
        if kwargs.get('key') == 'multi_file_uploader':
            return [good, bad]
        return original(*args, **kwargs)

    monkeypatch.setattr(st, 'file_uploader', upload)
    app = AppTest.from_file(str(Path(__file__).parents[1] / 'src/privacy_data_agent/web_app.py')).run()
    assert not app.exception
    assert any(button.label == '开始处理' for button in app.button)
    next(button for button in app.button if button.label == '开始处理').click().run()
    assert not app.exception and not app.error
    result = app.session_state.anonymize_batch_result
    assert result['files_processed'] == 1 and len(result['failures']) == 1


@pytest.mark.parametrize('preserve', [False, True])
def test_chart_cached_names_are_masked_and_restore(preserve):
    from openpyxl.chart import BarChart, Reference
    from openpyxl.chart.data_source import AxDataSource, StrData, StrRef, StrVal

    book = Workbook()
    sheet = book.active
    sheet.append(['姓名', '回款'])
    sheet.append(['张三', 100])
    sheet.append(['李四', 200])
    chart = BarChart()
    chart.title = '张三和李四的回款'
    chart.add_data(Reference(sheet, min_col=2, min_row=1, max_row=3), titles_from_data=True)
    chart.series[0].cat = AxDataSource(strRef=StrRef(
        f="'Sheet'!$A$2:$A$3", strCache=StrData(ptCount=2, pt=[StrVal(idx=0, v='张三'), StrVal(idx=1, v='李四')]),
    ))
    sheet.add_chart(chart, 'D2')
    result = anonymize_xlsx_bytes(workbook_bytes(book), preserve_calculations=preserve)
    assert '张三' not in text_payload(result.workbook_bytes)
    assert '李四' not in text_payload(result.workbook_bytes)
    assert len(load_workbook(BytesIO(result.workbook_bytes)).active._charts) == 1
    restored = restore_bytes(result.workbook_bytes, 'restored.xlsx', result.mapping)
    assert 'PDA_' not in text_payload(restored)


@pytest.mark.parametrize('preserve', [False, True])
def test_salary_chart_cache_follows_masking_settings(preserve):
    from openpyxl.chart import BarChart, Reference
    from openpyxl.chart.data_source import NumData, NumVal

    book = Workbook()
    sheet = book.active
    sheet.append(['月薪'])
    sheet.append([17001.25])
    chart = BarChart()
    chart.add_data(Reference(sheet, min_col=1, min_row=1, max_row=2), titles_from_data=True)
    chart.series[0].val.numRef.numCache = NumData(ptCount=1, pt=[NumVal(idx=0, v=17001.25)])
    sheet.add_chart(chart, 'C2')
    result = anonymize_xlsx_bytes(workbook_bytes(book), preserve_calculations=preserve)
    with ZipFile(BytesIO(result.workbook_bytes)) as archive:
        payload = ''.join(ET.fromstring(archive.read('xl/charts/chart1.xml')).itertext())
    assert ('17001.25' in payload) is preserve


def test_preview_respects_department_and_salary_settings(registry, monkeypatch):
    from pathlib import Path
    import streamlit as st
    from streamlit.testing.v1 import AppTest

    file = BytesIO('姓名,工号,部门,月薪\n张三,000123,研发部,17001.25\n'.encode())
    file.name, file.size = 'preview.csv', len(file.getvalue())
    original = st.file_uploader
    monkeypatch.setattr(st, 'file_uploader', lambda *args, **kwargs:
                        [file] if kwargs.get('key') == 'multi_file_uploader' else original(*args, **kwargs))
    app = AppTest.from_file(str(Path(__file__).parents[1] / 'src/privacy_data_agent/web_app.py')).run()
    app.session_state['anonymize_department'] = False
    app.session_state['preserve_calculations'] = True
    app.run()
    preview = app.dataframe[0].value.set_index('列名')
    assert preview.loc['部门', '处理方式'] == '保留'
    assert preview.loc['月薪', '处理方式'] == '保留'


def test_removing_seed_upload_clears_historical_mapping(registry, monkeypatch):
    from pathlib import Path
    import streamlit as st
    from streamlit.testing.v1 import AppTest

    file = BytesIO('姓名,工号\n张三,000123\n'.encode())
    file.name, file.size = 'preview.csv', len(file.getvalue())
    original = st.file_uploader
    monkeypatch.setattr(st, 'file_uploader', lambda *args, **kwargs:
                        [file] if kwargs.get('key') == 'multi_file_uploader' else original(*args, **kwargs))
    app = AppTest.from_file(str(Path(__file__).parents[1] / 'src/privacy_data_agent/web_app.py')).run()
    previous = BytesIO(b'{"version":1,"entries":[]}')
    previous.name = 'old-mapping.json'
    app.session_state['seed_file'] = previous
    app.run()
    assert app.session_state.seed_file is None


@pytest.mark.parametrize('filename', ['report.xlsx', 'report.md'])
def test_encrypted_mapping_restores_downloaded_outputs(filename):
    import json
    from cryptography.fernet import Fernet
    from privacy_data_agent.web_helpers import restore_report_upload

    key = Fernet.generate_key().decode()
    result = anonymize_upload('source.csv', '姓名,工号\n张三,000123\n'.encode(), encryption_key=key)
    with ZipFile(BytesIO(result['zip_bundle'])) as archive:
        mapping = archive.read('mapping.local.json')
        assert '张三'.encode() not in mapping and b'000123' not in mapping
    token = json.loads(result['mapping_json'])['entries'][0]['token']
    content = result['anonymized_xlsx'] if filename.endswith('.xlsx') else token.encode()
    restored = restore_report_upload(content, filename, 'mapping.local.json', mapping, decryption_key=key)
    text = text_payload(restored['content']) if filename.endswith('.xlsx') else restored['content'].decode()
    assert '张三' in text and 'PDA_' not in text
