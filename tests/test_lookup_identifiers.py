from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
from xml.etree import ElementTree as ET
from openpyxl import Workbook, load_workbook
import pandas as pd
import pytest
from privacy_data_agent.anonymizer import anonymize_dataframe
from privacy_data_agent.workbook_anonymizer import anonymize_xlsx_bytes


def with_cache(book, caches):
    memory = BytesIO(); book.save(memory); output = BytesIO()
    ns = {'x': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with ZipFile(memory) as source, ZipFile(output, 'w', ZIP_DEFLATED) as target:
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename in caches:
                root = ET.fromstring(data)
                for address, value in caches[item.filename].items():
                    cell = root.find(f'.//x:c[@r="{address}"]', ns)
                    cell.find('x:v', ns).text = str(value)
                    if isinstance(value, str): cell.set('t', 'str')
                data = ET.tostring(root)
            target.writestr(item, data)
    return output.getvalue()


@pytest.mark.parametrize('value', ['6222000012345678901', 6222000012345678])
@pytest.mark.parametrize('header', ['工资卡号', '银行账号', '银行卡号', '收款帐号'])
def test_bank_accounts_masked_even_when_salary_is_kept(header, value):
    result = anonymize_dataframe(pd.DataFrame({header: [value], '工资': [10000]}), anonymize_salary=False, preserve_calculations=True)
    assert str(result.dataframe.iloc[0, 0]).startswith('PDA_')
    assert result.dataframe.iloc[0, 1] == 10000
    assert result.mapping.entries[0].entity_type.value == 'bank_account'


def test_exact_lookup_source_with_unrecognized_header_uses_same_id_token():
    book = Workbook(); sheet = book.active; sheet.title = 'Payroll'
    sheet.append(['工号', '姓名', '工资', '工资卡号']); sheet.append(['E001', '张三', '=VLOOKUP(A2,Staff!$A:$D,4,FALSE)', '6222000012345678901'])
    staff = book.create_sheet('Staff'); staff.append(['系统登录标识', '工号', '姓名', '工资']); staff.append(['E001', 'E001', '张三', 10000]); staff.append(['E002', 'E002', '李四', 12000])
    refs = book.create_sheet('Transfer'); refs.append(['账号', '金额']); refs.append(['=Payroll!D2', 10000])
    data = with_cache(book, {'xl/worksheets/sheet1.xml': {'C2': 10000}, 'xl/worksheets/sheet3.xml': {'A2': '6222000012345678901'}})
    result = anonymize_xlsx_bytes(data, preserve_calculations=True)
    masked = load_workbook(BytesIO(result.workbook_bytes), data_only=True)
    formulas = load_workbook(BytesIO(result.workbook_bytes))
    assert masked['Payroll']['A2'].value == masked['Staff']['A2'].value == masked['Staff']['B2'].value
    assert masked['Staff']['A3'].value == masked['Staff']['B3'].value
    assert masked['Transfer']['A2'].value == masked['Payroll']['D2'].value
    assert masked['Payroll']['C2'].value == 10000
    assert formulas['Payroll']['C2'].value == '=VLOOKUP(A2,Staff!$A:$D,4,FALSE)'
    assert masked['Staff']['D2'].value == 10000

@pytest.mark.parametrize('title_rows', [1, 2])
def test_group_titles_do_not_hide_employee_id_header(title_rows):
    book = Workbook(); sheet = book.active
    for _ in range(title_rows): sheet.append(['公司', '个人信息', '部门', '工资'])
    sheet.append(['序号', '姓名', '工号', '提成']); sheet.append([1, '张三', '0012', 1200])
    memory = BytesIO(); book.save(memory)
    result = anonymize_xlsx_bytes(memory.getvalue(), preserve_calculations=True)
    assert any(e.entity_type.value == "employee_id" and e.original == "0012" for e in result.mapping.entries)
    masked = load_workbook(BytesIO(result.workbook_bytes), data_only=True).active
    assert masked.cell(title_rows+2, 3).value.startswith('PDA_')
    assert masked.cell(title_rows+2, 4).value == 1200


def test_custom_id_header_requires_same_row_employee_identity_not_numeric_collision():
    book = Workbook(); sheet = book.active
    sheet.append(['工号', '姓名', '提成']); sheet.append(['0012', '张三', 12])
    custom = book.create_sheet('Other'); custom.append(['姓名', '系统标记', '提成', '所属期间']); custom.append(['张三', '0012', 12, '0012'])
    memory = BytesIO(); book.save(memory)
    result = anonymize_xlsx_bytes(memory.getvalue(), require_unique_people=True, preserve_calculations=True)
    masked = load_workbook(BytesIO(result.workbook_bytes), data_only=True)
    assert masked['Other']['B2'].value == masked.active['A2'].value
    assert masked['Other']['C2'].value == 12
    assert masked['Other']['D2'].value == '0012'


def test_lookup_returning_identifier_sanitizes_cached_result_with_same_token():
    book = Workbook(); sheet = book.active; sheet.title = 'Staff'
    sheet.append(['工号', '姓名', '工资卡号']); sheet.append(['0012', '张三', '6222000012345678901'])
    view = book.create_sheet('View'); view.append(['工号', '核对结果', '转账结果']); view.append(['0012', '=VLOOKUP(A2,Staff!A:C,1,FALSE)', '=VLOOKUP(A2,Staff!A:C,3,FALSE)'])
    data = with_cache(book, {'xl/worksheets/sheet2.xml': {'B2': '0012', 'C2': '6222000012345678901'}})
    masked = load_workbook(BytesIO(anonymize_xlsx_bytes(data, preserve_calculations=True).workbook_bytes), data_only=True)
    assert masked['View']['B2'].value == masked['Staff']['A2'].value
    assert masked['View']['C2'].value == masked['Staff']['C2'].value


def test_single_reference_does_not_turn_entire_mixed_column_into_identifiers():
    book = Workbook(); sheet = book.active; sheet.title = 'Payroll'
    sheet.append(['工号', '工资卡号']); sheet.append(['0012', '6222000012345678901'])
    mixed = book.create_sheet('Mixed'); mixed.append(['说明', '结果']); mixed.append(['账号', '=Payroll!B2']); mixed.append(['合计', 12345])
    data = with_cache(book, {'xl/worksheets/sheet2.xml': {'B2': '6222000012345678901'}})
    masked = load_workbook(BytesIO(anonymize_xlsx_bytes(data, preserve_calculations=True).workbook_bytes), data_only=True)
    assert masked['Mixed']['B2'].value == masked['Payroll']['B2'].value
    assert masked['Mixed']['B3'].value == 12345


@pytest.mark.parametrize('mask_department', [True, False])
def test_department_lookup_keys_follow_department_option(mask_department):
    book = Workbook(); sheet = book.active; sheet.title = 'Payroll'
    sheet.append(['部门', '系数']); sheet.append(['销售部', '=VLOOKUP(A2,Rates!A:B,2,FALSE)'])
    rates = book.create_sheet('Rates'); rates.append(['匹配项', '系数']); rates.append(['销售部', 1.2])
    data = with_cache(book, {'xl/worksheets/sheet1.xml': {'B2': 1.2}})
    masked = load_workbook(BytesIO(anonymize_xlsx_bytes(data, preserve_calculations=True, anonymize_department=mask_department).workbook_bytes), data_only=True)
    assert masked['Payroll']['A2'].value == masked['Rates']['A2'].value
    assert masked['Rates']['B2'].value == 1.2
    if not mask_department:
        assert masked['Payroll']['A2'].value == '销售部'


@pytest.mark.parametrize('count', [1, 2])
def test_web_single_and_batch_mask_bank_and_preserve_lookup_match(tmp_path, monkeypatch, count):
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    from privacy_data_agent import identity_store
    monkeypatch.setattr(identity_store, 'identity_mapping_path', lambda: tmp_path / 'mapping.local.json')
    book = Workbook(); book.active.title = 'Payroll'; book.active.append(['工号', '姓名', '工资卡号', '工资']); book.active.append(['0012', '张三', '6222000012345678901', '=VLOOKUP(A2,Staff!A:D,4,FALSE)'])
    staff = book.create_sheet('Staff'); staff.append(['系统标记', '工号', '姓名', '工资']); staff.append(['0012', '0012', '张三', 10000])
    data = with_cache(book, {'xl/worksheets/sheet1.xml': {'D2': 10000}})
    uploads = []
    for index in range(count):
        file = BytesIO(data); file.name = f'payroll{index}.xlsx'; uploads.append(file)
    app = AppTest.from_file(str(Path(__file__).parents[1] / 'src/privacy_data_agent/web_app.py')).run()
    app.session_state['preserve_calculations'] = True
    app.session_state['anonymize_files'] = uploads; app.session_state['processing'] = True; app.run()
    assert not app.exception and not app.error
    results = ([app.session_state.anonymize_result] if count == 1 else app.session_state.anonymize_batch_result['results'])
    for result in results:
        output = result.get('anonymized_xlsx') or result['anonymized_bytes']
        masked = load_workbook(BytesIO(output), data_only=True)
        assert masked['Payroll']['A2'].value == masked['Staff']['A2'].value == masked['Staff']['B2'].value
        assert masked['Payroll']['C2'].value.startswith('PDA_')
        assert masked['Payroll']['D2'].value == 10000


def test_inferred_categorical_lookup_return_does_not_mask_numeric_business_result():
    book = Workbook(); sheet = book.active; sheet.title = 'Payroll'; sheet.append(['工号', '核对']); sheet.append(['0012', '=VLOOKUP(A2,Source!A:B,2,FALSE)'])
    source = book.create_sheet('Source'); source.append(['工号', '公司支出']); source.append(['0012', 10000])
    data = with_cache(book, {'xl/worksheets/sheet1.xml': {'B2': 10000}})
    masked = load_workbook(BytesIO(anonymize_xlsx_bytes(data, preserve_calculations=True).workbook_bytes), data_only=True)
    assert masked['Payroll']['B2'].value == masked['Source']['B2'].value == 10000
