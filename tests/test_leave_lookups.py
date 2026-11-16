from io import BytesIO
from openpyxl import Workbook, load_workbook
import pytest
from test_lookup_identifiers import with_cache
from privacy_data_agent.workbook_anonymizer import anonymize_xlsx_bytes


@pytest.mark.parametrize('preserve', [False, True])
@pytest.mark.parametrize('unified', [False, True])
def test_leave_lookup_uses_actual_lookup_column_in_both_modes(preserve, unified):
    book=Workbook(); sheet=book.active; sheet.title='Payroll'
    sheet.append(['工号','事假','病假','旷工天数'])
    sheet.append(['0012','=VLOOKUP(A2,Staff!A:E,3,FALSE)','=VLOOKUP(A2,Staff!A:E,4,FALSE)','=VLOOKUP(A2,Staff!A:E,5,FALSE)'])
    staff=book.create_sheet('Staff');staff.append(['系统标记','工号','事假','病假','旷工天数']);staff.append(['0012','0012',0,0.5,1])
    data=with_cache(book,{'xl/worksheets/sheet1.xml':{'B2':0,'C2':0.5,'D2':1}})
    result=anonymize_xlsx_bytes(data, anonymize_salary=False, preserve_calculations=preserve, require_unique_people=unified)
    masked=load_workbook(BytesIO(result.workbook_bytes))
    token=masked['Payroll']['A2'].value
    assert token==masked['Staff']['A2'].value==masked['Staff']['B2'].value
    assert [masked['Staff'].cell(2,c).value for c in [3,4,5]]==[0,0.5,1]
    assert masked['Payroll']['B2'].value=='=VLOOKUP(A2,Staff!A:E,3,FALSE)'


@pytest.mark.parametrize('mode', ['统一编号（跨月份、跨项目）','每次生成新编号'])
@pytest.mark.parametrize('count', [1,2])
@pytest.mark.parametrize('preserve', [False,True])
def test_web_leave_lookup_across_modes(tmp_path, monkeypatch, mode, count, preserve):
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    from privacy_data_agent import identity_store
    monkeypatch.setattr(identity_store,'identity_mapping_path',lambda:tmp_path/'mapping.local.json')
    book=Workbook();book.active.title='Payroll';book.active.append(['工号','事假','病假','旷工天数']);book.active.append(['0012','=VLOOKUP(A2,Staff!A:E,3,FALSE)','=VLOOKUP(A2,Staff!A:E,4,FALSE)','=VLOOKUP(A2,Staff!A:E,5,FALSE)'])
    staff=book.create_sheet('Staff');staff.append(['系统标记','工号','事假','病假','旷工天数']);staff.append(['0012','0012',0,0.5,1])
    data=with_cache(book,{'xl/worksheets/sheet1.xml':{'B2':0,'C2':0.5,'D2':1}})
    files=[]
    for i in range(count):
        f=BytesIO(data);f.name=f'leave{i}.xlsx';files.append(f)
    app=AppTest.from_file(str(Path(__file__).parents[1]/'src/privacy_data_agent/web_app.py')).run()
    app.session_state['identity_mode']=mode;app.session_state['preserve_calculations']=preserve;app.session_state['anonymize_files']=files;app.session_state['processing']=True;app.run()
    assert not app.exception and not app.error
    results=[app.session_state.anonymize_result] if count==1 else app.session_state.anonymize_batch_result['results']
    for result in results:
        masked=load_workbook(BytesIO(result.get('anonymized_xlsx') or result['anonymized_bytes']))
        assert masked['Payroll']['A2'].value==masked['Staff']['A2'].value==masked['Staff']['B2'].value
        assert [masked['Staff'].cell(2,c).value for c in [3,4,5]]==[0,0.5,1]
