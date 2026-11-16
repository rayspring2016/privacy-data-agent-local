from io import BytesIO
from openpyxl import Workbook,load_workbook
from openpyxl.workbook.external_link.external import ExternalBook,ExternalCell,ExternalLink,ExternalRow,ExternalSheetData,ExternalSheetDataSet,ExternalSheetNames
from openpyxl.packaging.relationship import Relationship
import pytest
from test_lookup_identifiers import with_cache
from privacy_data_agent.workbook_anonymizer import anonymize_xlsx_bytes


def external_book(missing=False, stale=False, group="销售一组", field="组别", formula=None):
    book=Workbook();sheet=book.active;sheet.title='Commission';sheet.append(['工号',field]);sheet.append(['0012',formula or "=VLOOKUP(A2,'[1]Private Staff'!$D:$W,19,FALSE)"])
    cells=[ExternalCell(r='D2',t='str',v='0012'),ExternalCell(r='G2',t='str',v='张三'),ExternalCell(r='H2',t='str',v='6222000012345678901')]
    if not missing:cells.append(ExternalCell(r='V2',t='str' if isinstance(group,str) else None,v=('另一个组' if isinstance(group,str) else str(group+1)) if stale else str(group)))
    rows=[ExternalRow(r=2,cell=cells),ExternalRow(r=3,cell=[ExternalCell(r='D3',t='str',v='PRIVATE_UNUSED_ID'),ExternalCell(r='V3',t='str',v='未使用组')])]
    link=ExternalLink(externalBook=ExternalBook(id='rId1',sheetNames=ExternalSheetNames(sheetName=['Private Staff']),sheetDataSet=ExternalSheetDataSet(sheetData=[ExternalSheetData(sheetId=0,row=rows)])))
    link.file_link=Relationship(Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/externalLinkPath',Target='file:///private/person/source.xlsx',TargetMode='External');book._external_links.append(link)
    return with_cache(book,{'xl/worksheets/sheet1.xml':{'B2':group}})


@pytest.mark.parametrize('preserve',[False,True])
@pytest.mark.parametrize('mask_department',[False,True])
def test_external_attribute_becomes_saved_value_without_private_cache_leaks(preserve,mask_department):
    result=anonymize_xlsx_bytes(external_book(),preserve_calculations=preserve,anonymize_department=mask_department)
    book=load_workbook(BytesIO(result.workbook_bytes));assert not book._external_links
    assert len(book.worksheets)==1 and book.active['B2'].data_type!='f'
    assert book.active['B2'].value.startswith('PDA_') if mask_department else book.active['B2'].value=='销售一组'
    from zipfile import ZipFile
    payload=b'\n'.join(ZipFile(BytesIO(result.workbook_bytes)).read(n) for n in ZipFile(BytesIO(result.workbook_bytes)).namelist())
    assert all(v not in payload for v in [b'/private/person',b'Private Staff',b'PRIVATE_UNUSED_ID',b'6222000012345678901','张三'.encode()])
    assert result.external_value_count==1 and result.localized_external_formula_count==0 and result.external_link_count==0


@pytest.mark.parametrize('missing,stale',[(True,False),(False,True)])
def test_attribute_uses_saved_cell_result_without_needing_external_source_cache(missing,stale):
    result=anonymize_xlsx_bytes(external_book(missing,stale),preserve_calculations=True)
    book=load_workbook(BytesIO(result.workbook_bytes))
    assert len(book.worksheets)==1 and book.active['B2'].data_type!='f'
    assert result.external_value_count==1 and result.external_link_count==0


@pytest.mark.parametrize('preserve',[False,True])
@pytest.mark.parametrize('count',[1,2])
def test_web_external_snapshot_reports_localization(tmp_path,monkeypatch,preserve,count):
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    from privacy_data_agent import identity_store
    monkeypatch.setattr(identity_store,'identity_mapping_path',lambda:tmp_path/'identity.json')
    app=AppTest.from_file(str(Path(__file__).parents[1]/'src/privacy_data_agent/web_app.py')).run()
    uploads=[]
    for i in range(count):
        file=BytesIO(external_book());file.name=f'external{i}.xlsx';uploads.append(file)
    app.session_state['preserve_calculations']=preserve;app.session_state['anonymize_files']=uploads;app.session_state['processing']=True;app.run()
    assert not app.exception and not app.error
    result=app.session_state.anonymize_result if count==1 else app.session_state.anonymize_batch_result
    assert result['external_value_count']==count and result['external_link_count']==0
    assert any('外部属性' in item.value for item in app.caption)


def test_cli_records_external_snapshot_count(tmp_path,monkeypatch):
    import json
    from typer.testing import CliRunner
    from privacy_data_agent.cli import app
    from privacy_data_agent import identity_store
    monkeypatch.setattr(identity_store,'identity_mapping_path',lambda:tmp_path/'identity.json')
    source=tmp_path/'commission.xlsx';source.write_bytes(external_book());output=tmp_path/'out'
    result=CliRunner().invoke(app,['anonymize',str(source),'--preserve-calculations','-o',str(output)])
    assert result.exit_code==0,result.output
    report=json.loads((output/'local_manifest.json').read_text())
    assert report['external_value_count']==1 and report['external_link_count']==0


def test_external_cached_text_is_never_imported_as_an_executable_formula():
    result=anonymize_xlsx_bytes(external_book(group="=1+1"))
    book=load_workbook(BytesIO(result.workbook_bytes))
    assert book.active['B2'].data_type!='f'
    assert book.active['B2'].value.startswith('PDA_')


@pytest.mark.parametrize('preserve',[False,True])
def test_external_numeric_business_formula_keeps_verified_local_lookup(preserve):
    result=anonymize_xlsx_bytes(external_book(group=1200.5,field='提成金额'),preserve_calculations=preserve,anonymize_salary=False)
    book=load_workbook(BytesIO(result.workbook_bytes))
    assert len(book.worksheets)==2 and book.active['B2'].data_type=='f' and '[1]' not in book.active['B2'].value
    assert result.external_value_count==0 and result.localized_external_formula_count==1
    assert book.worksheets[1]['D2'].value==book.active['A2'].value and book.worksheets[1]['V2'].value==1200.5


@pytest.mark.parametrize('missing,stale',[(True,False),(False,True)])
def test_external_numeric_business_formula_requires_verified_source_cache(missing,stale):
    result=anonymize_xlsx_bytes(external_book(missing,stale,1200.5,field='提成金额'),preserve_calculations=True)
    book=load_workbook(BytesIO(result.workbook_bytes))
    assert len(book.worksheets)==1 and '[1]' in book.active['B2'].value
    assert result.external_value_count==result.localized_external_formula_count==0 and result.external_link_count==1
