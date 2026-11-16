from io import BytesIO
from zipfile import ZipFile,ZIP_DEFLATED
from xml.etree import ElementTree as ET
import pytest
from openpyxl import load_workbook
from privacy_data_agent.workbook_anonymizer import anonymize_xlsx_bytes
from privacy_data_agent.web_helpers import anonymize_upload,anonymize_batch
from test_external_snapshots import external_book


@pytest.mark.parametrize('preserve',[False,True])
@pytest.mark.parametrize('field,value', [('组别','销售一组'),('部门','销售部'),('姓名','张三'),('员工编号','0012'),('邮箱','employee@example.com'),('工资卡号','6222000012345678901')])
def test_external_attributes_become_values_then_follow_normal_masking(field,value,preserve):
    result=anonymize_xlsx_bytes(external_book(field=field,group=value,missing=True),preserve_calculations=preserve,require_unique_people=True)
    book=load_workbook(BytesIO(result.workbook_bytes));assert len(book.worksheets)==1 and not book._external_links
    assert book.active['B2'].data_type!='f' and book.active['B2'].value.startswith('PDA_')
    assert result.external_value_count==1 and result.localized_external_formula_count==0
    if field=='员工编号':
        assert book.active['A2'].value==book.active['B2'].value
        assert any(e.original=='0012' and e.entity_type.value=='employee_id' for e in result.mapping.entries)
        assert not any(e.original=='12' and e.entity_type.value=='employee_id' for e in result.mapping.entries)


@pytest.mark.parametrize('formula',["='[1]Private Staff'!V2",'=IFERROR(VLOOKUP(A2,\'[1]Private Staff\'!D:W,19,FALSE),"")'])
def test_external_attribute_does_not_depend_on_lookup_function_shape(formula):
    result=anonymize_xlsx_bytes(external_book(formula=formula,stale=True))
    book=load_workbook(BytesIO(result.workbook_bytes));assert book.active['B2'].data_type!='f' and not book._external_links
    assert result.external_value_count==1


def patched_cache(data,kind,value):
    out=BytesIO();ns={'x':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with ZipFile(BytesIO(data)) as source,ZipFile(out,'w',ZIP_DEFLATED) as target:
        for item in source.infolist():
            payload=source.read(item.filename)
            if item.filename=='xl/worksheets/sheet1.xml':
                root=ET.fromstring(payload);cell=root.find('.//x:c[@r="B2"]',ns);cell.set('t',kind);cell.find('x:v',ns).text=value;payload=ET.tostring(root)
            target.writestr(item,payload)
    return out.getvalue()


@pytest.mark.parametrize('preserve',[False,True])
@pytest.mark.parametrize('kind,value,reason',[('n',None,'缺少'),('e','#N/A','报错')])
def test_missing_or_error_attribute_cache_stops_without_updating_registry(tmp_path,monkeypatch,preserve,kind,value,reason):
    from privacy_data_agent import identity_store
    registry=tmp_path/'identity.json';monkeypatch.setattr(identity_store,'identity_mapping_path',lambda:registry)
    with pytest.raises(ValueError,match=f'第 1 张工作表 B2.*{reason}') as error:
        anonymize_upload('source.xlsx',patched_cache(external_book(),kind,value),consistent_ids=True,preserve_calculations=preserve)
    assert not registry.exists() and '/private/person' not in str(error.value) and '销售一组' not in str(error.value)


def test_saved_empty_attribute_result_is_a_valid_blank_not_missing():
    result=anonymize_xlsx_bytes(patched_cache(external_book(),'str',None))
    cell=load_workbook(BytesIO(result.workbook_bytes)).active['B2'];assert cell.value is None and cell.data_type!='f'
    assert result.external_value_count==1


def test_department_setting_still_applies_to_external_attribute_value():
    result=anonymize_xlsx_bytes(external_book(),anonymize_department=False)
    book=load_workbook(BytesIO(result.workbook_bytes));assert book.active['B2'].value=='销售一组' and book.active['B2'].data_type!='f'


def test_batch_reports_external_cache_location_and_continues(tmp_path,monkeypatch):
    from privacy_data_agent import identity_store
    monkeypatch.setattr(identity_store,'identity_mapping_path',lambda:tmp_path/'mapping.json')
    result=anonymize_batch([('bad.xlsx',patched_cache(external_book(),'e','#N/A')),('good.xlsx',external_book())],consistent_ids=True)
    assert result['files_processed']==1 and result['external_value_count']==1
    assert '第 1 张工作表 B2' in result['failures'][0]['reason']


def test_internal_commission_formula_remains_and_saved_result_is_preserved():
    from openpyxl import Workbook
    from test_lookup_identifiers import with_cache
    book=Workbook();book.active.title='Commission';book.active.append(['工号','组别','提成','金额']);book.active.append(['0012',"='[1]Private Staff'!V2",'=D2*0.1',1000])
    data=external_book();link=load_workbook(BytesIO(data))._external_links[0];book._external_links.append(link)
    data=with_cache(book,{'xl/worksheets/sheet1.xml':{'B2':'销售一组','C2':100}})
    result=anonymize_xlsx_bytes(data,preserve_calculations=True)
    formulas=load_workbook(BytesIO(result.workbook_bytes));values=load_workbook(BytesIO(result.workbook_bytes),data_only=True)
    assert formulas.active['C2'].value=='=D2*0.1' and values.active['C2'].value==100
    assert values.active['D2'].value==1000 and formulas.active['B2'].data_type!='f'
    assert result.formula_count==1 and result.external_value_count==1


def test_cli_batch_reports_missing_external_attribute_and_continues(tmp_path,monkeypatch):
    import json
    from typer.testing import CliRunner
    from privacy_data_agent.cli import app
    from privacy_data_agent import identity_store
    monkeypatch.setattr(identity_store,'identity_mapping_path',lambda:tmp_path/'registry.json')
    source=tmp_path/'inputs';source.mkdir();(source/'01.xlsx').write_bytes(patched_cache(external_book(),'e','#N/A'));(source/'02.xlsx').write_bytes(external_book())
    output=tmp_path/'out';result=CliRunner().invoke(app,['anonymize',str(source),'-o',str(output)])
    assert result.exit_code==1 and '外部属性' in result.output
    manifest=json.loads((output/'batch_manifest.json').read_text());assert manifest['success_count']==manifest['failure_count']==1
    assert manifest['files'][0]['status']=='needs_review' and '第 1 张工作表 B2' in manifest['files'][0]['reason']
    assert manifest['files'][1]['external_value_count']==1


@pytest.mark.parametrize('mask_title',[False,True])
def test_external_job_title_value_respects_existing_optional_masking(mask_title):
    result=anonymize_xlsx_bytes(external_book(field='岗位',group='销售专员'),anonymize_job_title=mask_title)
    cell=load_workbook(BytesIO(result.workbook_bytes)).active['B2']
    assert cell.data_type!='f'
    assert cell.value.startswith('PDA_') if mask_title else cell.value=='销售专员'
