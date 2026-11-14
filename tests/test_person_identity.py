from io import BytesIO

import pytest
from openpyxl import Workbook, load_workbook

from privacy_data_agent import identity_store
from privacy_data_agent.detectors import SalaryGroup
from privacy_data_agent.web_helpers import anonymize_upload


@pytest.fixture
def registry(tmp_path, monkeypatch):
    path = tmp_path / "identity/mapping.local.json"
    monkeypatch.setattr(identity_store, "identity_mapping_path", lambda: path)
    return path


def run(rows):
    data = ("姓名,工号,邮箱,部门\n" + "\n".join(rows) + "\n").encode()
    result = anonymize_upload("employees.csv", data, consistent_ids=True)
    return list(load_workbook(BytesIO(result["anonymized_xlsx"])).active.values)[1:]


def test_same_name_different_ids_never_gets_the_same_person_token(registry):
    first = run(["张三,000123,one@example.com,销售部", "张三,000124,two@example.com,研发部"])
    assert first[0][0] != first[1][0]
    later = run(["张三,000124,two@example.com,销售部", "张三,000123,one@example.com,研发部"])
    assert first[0][0] == later[1][0]
    assert first[1][0] == later[0][0]


def test_employee_master_links_id_only_and_email_only_tables(registry):
    master = run(["张三,000123,one@example.com,销售部"])
    by_id = run(["张三,000123,,研发部"])
    by_email = run(["张三,,ONE@EXAMPLE.COM,研发部"])
    assert master[0][0] == by_id[0][0] == by_email[0][0]
    assert master[0][2] == by_email[0][2]


def test_same_employee_id_can_update_name_and_add_new_email(registry):
    first = run(["张三,000123,old@example.com,销售部"])
    renamed = run(["张小三,000123,new@example.com,研发部"])
    email_only = run(["张小三,,new@example.com,研发部"])
    assert first[0][0] == renamed[0][0] == email_only[0][0]


def test_email_claimed_by_two_ids_is_rejected_without_updating_registry(registry):
    run(["张三,000123,one@example.com,销售部"])
    before = registry.read_bytes()
    with pytest.raises(ValueError, match="待核验"):
        run(["李四,000124,one@example.com,销售部"])
    assert registry.read_bytes() == before


def test_missing_id_and_email_is_not_joined_by_name(registry):
    with pytest.raises(ValueError, match="待核验"):
        run(["张三,,,销售部"])
    assert not registry.exists()


def test_unlinked_email_is_not_merged_with_an_employee_by_name(registry):
    run(["张三,000123,,销售部"])
    before = registry.read_bytes()
    second = run(["张三,,one@example.com,销售部"])
    assert second[0][0].startswith("PDA_")
    # An unlinked email is its own identity until a verified ID/email bridge is supplied.
    assert registry.read_bytes() != before


def workbook(detail_rows):
    book = Workbook()
    detail = book.active
    detail.title = "薪资明细"
    detail.append(["姓名", "部门", "月薪"])
    for row in detail_rows:
        detail.append(row)
    roster = book.create_sheet("员工基准")
    roster.append(["员工姓名", "员工编号", "邮箱", "部门"])
    roster.append(["张三", "000123", "one@example.com", "销售部"])
    roster.append(["张三", "000124", "two@example.com", "研发部"])
    stream = BytesIO()
    book.save(stream)
    return stream.getvalue()


def test_later_sheet_builds_basis_and_name_department_resolves_duplicates(registry):
    result = anonymize_upload("monthly.xlsx", workbook([["张三", "研发部", 15000], ["张三", "销售部", 16000]]), consistent_ids=True)
    book = load_workbook(BytesIO(result["anonymized_xlsx"]))
    assert book["薪资明细"]["A2"].value == book["员工基准"]["A3"].value
    assert book["薪资明细"]["A3"].value == book["员工基准"]["A2"].value
    assert book["薪资明细"]["A2"].value != book["薪资明细"]["A3"].value


def test_ambiguous_name_without_department_is_not_guessed(registry):
    with pytest.raises(ValueError, match="待核验"):
        anonymize_upload("monthly.xlsx", workbook([["张三", None, 15000]]), consistent_ids=True)
    assert not registry.exists()


def test_email_only_sheet_can_precede_id_email_master(registry):
    book = Workbook()
    book.active.append(["姓名", "邮箱"])
    book.active.append(["张三", "one@example.com"])
    master = book.create_sheet("基准")
    master.append(["姓名", "工号", "邮箱"])
    master.append(["张三", "000123", "one@example.com"])
    stream = BytesIO()
    book.save(stream)
    result = anonymize_upload("master.xlsx", stream.getvalue(), consistent_ids=True)
    out = load_workbook(BytesIO(result["anonymized_xlsx"]))
    assert out.worksheets[0]["A2"].value == out.worksheets[1]["A2"].value


def test_name_only_sheet_matches_a_unique_registered_person(registry):
    book = Workbook()
    book.active.append(["姓名", "提成"])
    book.active.append(["张三", 100])
    master = book.create_sheet("基准")
    master.append(["姓名", "工号", "部门"])
    master.append(["张三", "000123", "销售部"])
    stream = BytesIO()
    book.save(stream)
    result = anonymize_upload("unique.xlsx", stream.getvalue(), consistent_ids=True)
    out = load_workbook(BytesIO(result["anonymized_xlsx"]))
    assert out.worksheets[0]["A2"].value == out.worksheets[1]["A2"].value


def test_duplicate_name_and_department_still_requires_review(registry):
    run(["张三,000123,one@example.com,销售部", "张三,000124,two@example.com,销售部"])
    before = registry.read_bytes()
    with pytest.raises(ValueError, match="待核验"):
        run(["张三,,,销售部"])
    assert registry.read_bytes() == before


def test_manager_column_does_not_inherit_report_employee_id(registry):
    manager = run(["李四,000124,two@example.com,销售部"])[0][0]
    employee = run(["张三,000123,one@example.com,销售部"])[0][0]
    result = anonymize_upload(
        "report.csv", "工号,直线经理,部门\n000123,李四,销售部\n".encode(),
        consistent_ids=True,
    )
    token = load_workbook(BytesIO(result["anonymized_xlsx"])).active["B2"].value
    assert token == manager
    assert token != employee


def test_duplicate_primary_columns_and_business_ids_work_across_sheets(registry):
    book = Workbook()
    book.active.append(["姓名", "部门", "提成"])
    book.active.append(["张三", "销售部", 100])
    master = book.create_sheet("人员")
    master.append(["姓名", "员工姓名", "工号", "员工编号", "合同编号", "客户邮箱", "员工邮箱", "部门"])
    master.append(["张三", "张三", "000123", "000123", "HT-1", "customer@example.com", "one@example.com", "销售部"])
    master.append([None, "李四", "000124", None, "HT-2", "customer@example.com", "two@example.com", "研发部"])
    stream = BytesIO()
    book.save(stream)
    result = anonymize_upload("payroll.xlsx", stream.getvalue(), consistent_ids=True)
    out = load_workbook(BytesIO(result["anonymized_xlsx"]))
    roster = out.worksheets[1]
    assert out.worksheets[0]["A2"].value == roster["A2"].value == roster["B2"].value
    assert roster["B3"].value.startswith("PDA_")
    email_only = run(["张三,,ONE@EXAMPLE.COM,销售部"])
    assert email_only[0][0] == roster["A2"].value
    assert "customer@example.com" not in roster["F2"].value


@pytest.mark.parametrize(("columns", "values", "reason", "positions"), [
    (["姓名", "员工姓名", "工号"], ["张三", "李四", "000123"], "主姓名不一致", "A、B"),
    (["姓名", "工号", "员工编号"], ["张三", "000123", "000124"], "员工工号不一致", "B、C"),
])
def test_conflicting_identity_fields_report_workbook_location(registry, columns, values, reason, positions):
    book = Workbook()
    book.active.title = "主数据"
    book.active.append(columns)
    book.active.append(values)
    stream = BytesIO()
    book.save(stream)
    with pytest.raises(ValueError) as exc:
        anonymize_upload("payroll.xlsx", stream.getvalue(), consistent_ids=True)
    message = str(exc.value)
    assert "第 1 张工作表" in message
    assert "第 2 行" in message
    assert reason in message
    assert positions in message
    assert not any(value in message for value in values)
    assert not registry.exists()


def test_parallel_employee_tables_in_sixth_sheet_share_registry(registry):
    book = Workbook()
    book.active.title = "纵向明细"
    book.active.append(["姓名", "部门", "提成"])
    book.active.append(["张三", "部门2", 2000])
    for index in range(2, 6):
        book.create_sheet(f"说明{index}")["A1"] = "说明"
    sheet = book.create_sheet("横向明细")
    starts = [1, 10, 27, 33, 56]
    for index, start in enumerate(starts, start=1):
        sheet.merge_cells(start_row=1, start_column=start, end_row=1, end_column=start + 3)
        sheet.cell(1, start, f"明细{index}")
        for offset, value in enumerate(["工号", "姓名", "部门", "提成"]):
            sheet.cell(2, start + offset, value)
        for offset, value in enumerate([f"EMP{index:04}", "张三", f"部门{index}", 1000 * index]):
            sheet.cell(3, start + offset, value)
    stream = BytesIO()
    book.save(stream)
    result = anonymize_upload(
        "parallel.xlsx", stream.getvalue(), consistent_ids=True,
        keep_salary_groups=frozenset({SalaryGroup.COMMISSION}),
    )
    output = load_workbook(BytesIO(result["anonymized_xlsx"]))
    tokens = [output.worksheets[5].cell(3, start + 1).value for start in starts]
    assert all(token.startswith("PDA_") for token in tokens)
    assert len(set(tokens)) == 5
    assert output.worksheets[0]["A2"].value == tokens[1]
    assert output.worksheets[5]["K2"].value == "姓名"
    assert output.worksheets[5]["M3"].value == 2000


def test_parallel_repeating_headers_do_not_need_title_row(registry):
    book = Workbook()
    book.active.append(["姓名", "工号", "部门", "姓名", "工号", "部门"])
    book.active.append(["张三", "000123", "销售部", "张三", "000124", "研发部"])
    stream = BytesIO()
    book.save(stream)
    result = anonymize_upload("parallel.xlsx", stream.getvalue(), consistent_ids=True)
    sheet = load_workbook(BytesIO(result["anonymized_xlsx"])).active
    assert sheet["A2"].value != sheet["D2"].value
    assert sheet["A2"].value == run(["张三,000123,,销售部"])[0][0]
    assert sheet["D2"].value == run(["张三,000124,,研发部"])[0][0]


def test_pivot_ranges_separate_people_and_remove_raw_caches(registry):
    from zipfile import ZipFile

    from openpyxl.pivot.cache import CacheDefinition, CacheField, CacheSource, SharedItems, Text, WorksheetSource
    from openpyxl.pivot.table import Location, RowColField, TableDefinition

    book = Workbook()
    source = book.active
    source.title = "明细"
    source.append(["工号", "姓名", "部门", "提成"])
    source.append(["000123", "张三", "销售部", 100])
    source.append(["000124", "张三", "研发部", 200])
    sheet = book.create_sheet("透视汇总")
    cache = CacheDefinition(
        cacheSource=CacheSource(type="worksheet", worksheetSource=WorksheetSource(ref="A1:D3", sheet="明细")),
        cacheFields=[
            CacheField(name="工号", sharedItems=SharedItems(_fields=[Text(v="000123"), Text(v="000124")])),
            CacheField(name="姓名", sharedItems=SharedItems(_fields=[Text(v="张三")])),
            CacheField(name="部门"),
            CacheField(name="提成"),
        ],
    )
    for index, (ref, header_row, start, identity, dept, amount) in enumerate([
        ("A2:D3", 2, 1, "000123", "销售部", 100),
        ("E3:H4", 3, 5, "000124", "研发部", 200),
    ], start=1):
        pivot = TableDefinition(
            name=f"Pivot{index}", cacheId=1, dataCaption="数据", compact=False,
            location=Location(ref=ref, firstHeaderRow=0, firstDataRow=1, firstDataCol=3),
            rowFields=[RowColField(x=i) for i in range(3)],
        )
        pivot.cache = cache
        sheet.add_pivot(pivot)
        for offset, header in enumerate(["工号", "姓名", "部门", "提成"]):
            sheet.cell(header_row, start + offset, header)
        for offset, value in enumerate([identity, "张三", dept, amount]):
            sheet.cell(header_row + 1, start + offset, value)
    stream = BytesIO()
    book.save(stream)
    with ZipFile(stream) as archive:
        assert any("pivotCache" in name for name in archive.namelist())
    result = anonymize_upload(
        "pivot.xlsx", stream.getvalue(), consistent_ids=True,
        keep_salary_groups=frozenset({SalaryGroup.COMMISSION}),
    )
    out = load_workbook(BytesIO(result["anonymized_xlsx"]))
    assert out["透视汇总"]["B3"].value == out["明细"]["B2"].value
    assert out["透视汇总"]["F4"].value == out["明细"]["B3"].value
    assert out["透视汇总"]["B3"].value != out["透视汇总"]["F4"].value
    assert out["透视汇总"]["H4"].value == 200
    with ZipFile(BytesIO(result["anonymized_xlsx"])) as archive:
        assert not any("pivotCache" in name or "pivotTables" in name for name in archive.namelist())
        assert not any("张三".encode() in archive.read(name) or b"000123" in archive.read(name)
                       for name in archive.namelist())


@pytest.mark.parametrize(("detail_dept", "employees", "reason"), [
    (None, [], "姓名未在人员基准中登记"),
    (None, [("000123", "销售部"), ("000124", "研发部")], "有 2 个同名候选"),
    ("运营部", [("000123", "销售部")], "部门信息与已登记的候选不匹配"),
])
def test_name_review_explains_reason_and_cell_without_exposing_values(registry, detail_dept, employees, reason):
    book = Workbook()
    book.active.title = "不应出现在错误里的表名"
    book.active.append(["提成", "姓名", "部门"])
    book.active.append([100, "张三", detail_dept])
    if employees:
        master = book.create_sheet("人员基准")
        master.append(["工号", "姓名", "部门"])
        for employee_id, department in employees:
            master.append([employee_id, "张三", department])
    stream = BytesIO()
    book.save(stream)
    with pytest.raises(ValueError) as error:
        anonymize_upload("test.xlsx", stream.getvalue(), consistent_ids=True)
    message = str(error.value)
    assert "第 1 张工作表第 2 行（B 列）" in message
    assert reason in message
    assert all(value not in message for value in ("张三", "运营部", "000123", book.active.title))
    assert not registry.exists()


def test_hrbp_name_links_to_own_email_not_employee_department(registry):
    result = anonymize_upload(
        "staff.csv",
        "员工,工号,员工邮箱,部门,HRBP,HRBP邮箱,人员状态\n张三,000123,staff@example.com,销售部,李四,bp@example.com,在职\n王五,000124,other@example.com,研发部,李四,bp@example.com,在职\n".encode(),
        consistent_ids=True,
    )
    sheet = load_workbook(BytesIO(result["anonymized_xlsx"])).active
    assert sheet["E2"].value == sheet["E3"].value
    assert sheet["A2"].value != sheet["E2"].value
    assert sheet["F2"].value.startswith("PDA_")
    assert sheet["G2"].value == "在职"
    imported = run(["李四,000125,bp@example.com,人力资源部"])[0][0]
    assert imported == sheet["E2"].value


def test_multiple_email_only_people_can_be_saved_and_reused(registry):
    first = run(["张三,,one@example.com,销售部", "李四,,two@example.com,研发部"])
    second = run(["李四,,TWO@EXAMPLE.COM,研发部", "张三,,ONE@EXAMPLE.COM,销售部"])
    assert first[0][0] == second[1][0]
    assert first[1][0] == second[0][0]
    assert first[0][0] != first[1][0]


def test_verified_national_id_connects_missing_employee_id_sheet(registry):
    book = Workbook()
    book.active.append(["姓名", "身份证号", "部门"])
    book.active.append(["张三", "110101199001011237", "另一部门"])
    master = book.create_sheet("基准")
    master.append(["工号", "姓名", "证件类型", "证件号码", "部门"])
    master.append(["000123", "张三", "身份证", "110101199001011237", "销售部"])
    buffer = BytesIO()
    book.save(buffer)
    result = anonymize_upload("national.xlsx", buffer.getvalue(), consistent_ids=True)
    out = load_workbook(BytesIO(result["anonymized_xlsx"]))
    assert out.worksheets[0]["A2"].value == out.worksheets[1]["B2"].value
    assert out.worksheets[0]["B2"].value.startswith("PDA_")
    again = run(["张三,000123,,销售部"])[0][0]
    assert again == out.worksheets[0]["A2"].value


def test_missing_name_slash_placeholder_is_kept_without_identity(registry):
    result = anonymize_upload(
        "placeholders.csv", "姓名,工号\n/,000123\n".encode(), consistent_ids=True,
    )
    assert load_workbook(BytesIO(result["anonymized_xlsx"])).active["A2"].value == "/"


def test_formula_in_name_column_is_not_registered_as_a_name(registry):
    book = Workbook()
    book.active.append(["工号", "姓名"])
    book.active.append(["000123", "张三"])
    report = book.create_sheet("计算表")
    report.append(["工号", "姓名"])
    report.append(["000123", '=IFERROR(VLOOKUP(A2,人员!A:B,2,0),"/")'])
    buffer = BytesIO()
    book.save(buffer)
    result = anonymize_upload("formula.xlsx", buffer.getvalue(), consistent_ids=True)
    out = load_workbook(BytesIO(result["anonymized_xlsx"]))
    assert out["计算表"]["B2"].data_type == "f"
    assert out["计算表"]["A2"].value == out.worksheets[0]["A2"].value


def test_matching_known_department_level_allows_other_level_labels(registry):
    run(["张三,000123,,销售部"])
    result = anonymize_upload(
        "levels.csv",
        "姓名,一级部门,二级部门\n张三,公司全名下的销售体系,销售部\n".encode(),
        consistent_ids=True,
    )
    token = load_workbook(BytesIO(result["anonymized_xlsx"])).active["A2"].value
    assert token == run(["张三,000123,,销售部"])[0][0]


def test_customer_contacts_use_customer_context_not_employee_name(registry):
    result = anonymize_upload(
        "customers.csv",
        "工号,姓名,客户编号,客户联系人\n000123,张三,C001,张三\n000123,张三,C002,张三\n000123,张三,C001,张三\n".encode(),
        consistent_ids=True,
    )
    sheet = load_workbook(BytesIO(result["anonymized_xlsx"])).active
    assert sheet["D2"].value != sheet["B2"].value
    assert sheet["D2"].value != sheet["D3"].value
    assert sheet["D2"].value == sheet["D4"].value


def test_customer_owner_can_link_to_registered_employee(registry):
    token = run(["张三,000123,,销售部"])[0][0]
    result = anonymize_upload(
        "owner.csv", "客户编号,客户负责人\nC001,张三\n".encode(), consistent_ids=True,
    )
    sheet = load_workbook(BytesIO(result["anonymized_xlsx"])).active
    assert sheet["B2"].value == token


@pytest.mark.parametrize("anonymize_department", [True, False])
def test_customer_owner_team_is_department_not_employee(registry, anonymize_department):
    result = anonymize_upload(
        "team.csv", "客户负责人团队\n区域销售一组\n".encode(),
        consistent_ids=True, anonymize_department=anonymize_department,
    )
    cell = load_workbook(BytesIO(result["anonymized_xlsx"])).active["A2"].value
    assert cell.startswith("PDA_") if anonymize_department else cell == "区域销售一组"


def test_system_actor_is_masked_independently_of_employee(registry):
    result = anonymize_upload(
        "actors.csv", "姓名,工号,创建人\n张三,000123,业务系统管理员\n".encode(),
        consistent_ids=True,
    )
    sheet = load_workbook(BytesIO(result["anonymized_xlsx"])).active
    assert sheet["C2"].value.startswith("PDA_")
    assert sheet["A2"].value != sheet["C2"].value


def test_system_actor_in_primary_name_without_employee_id(registry):
    result = anonymize_upload(
        "actors.csv", "工号,归属人\n000123,张三\n,业务系统管理员\n".encode(),
        consistent_ids=True,
    )
    sheet = load_workbook(BytesIO(result["anonymized_xlsx"])).active
    assert sheet["B3"].value.startswith("PDA_")
    assert sheet["B2"].value != sheet["B3"].value


def test_contact_group_cell_keeps_its_customer_context_in_xlsx(registry):
    book = Workbook()
    book.active.append(["姓名", "工号", "客户编号", "客户联系人"])
    book.active.append(["张三", "000123", "C001", "李四/王五"])
    buffer = BytesIO()
    book.save(buffer)
    result = anonymize_upload("contacts.xlsx", buffer.getvalue(), consistent_ids=True)
    sheet = load_workbook(BytesIO(result["anonymized_xlsx"])).active
    assert sheet["D2"].value.startswith("PDA_")
    assert "李四" not in sheet["D2"].value


def test_leader_table_registers_its_own_id_and_masks_role_columns(registry):
    book = Workbook()
    book.active.append(["姓名", "提成"])
    book.active.append(["李四", 100])
    master = book.create_sheet("员工")
    master.append(["工号", "Leader"])
    master.append(["000124", "李四"])
    detail = book.create_sheet("业务")
    detail.append(["工号", "姓名", "核算商务", "最终业绩归属销售经理", "SDR"])
    detail.append(["000123", "张三", "李四", "李四", "李四"])
    stream = BytesIO()
    book.save(stream)
    result = anonymize_upload("roles.xlsx", stream.getvalue(), consistent_ids=True)
    out = load_workbook(BytesIO(result["anonymized_xlsx"]))
    token = out.worksheets[0]["A2"].value
    assert token.startswith("PDA_")
    assert out.worksheets[1]["B2"].value == token
    assert all(out.worksheets[2].cell(2, col).value == token for col in (3, 4, 5))
    assert out.worksheets[2]["B2"].value != token


@pytest.mark.parametrize("file_type", ["csv", "xlsx"])
def test_known_employee_name_in_custom_column_is_masked(registry, file_type):
    expected = run(["李四,000124,,销售部"])[0][0]
    content = "工号,姓名,业务归口\n000123,张三,李四\n".encode()
    if file_type == "xlsx":
        book = Workbook()
        book.active.append(["工号", "姓名", "业务归口"])
        book.active.append(["000123", "张三", "李四"])
        stream = BytesIO()
        book.save(stream)
        content = stream.getvalue()
    result = anonymize_upload(
        f"custom.{file_type}", content,
        consistent_ids=True,
    )
    sheet = load_workbook(BytesIO(result["anonymized_xlsx"])).active
    assert sheet["C2"].value == expected


def test_repeated_headers_are_not_registered_as_employee_names(registry):
    book = Workbook()
    book.active.append(["工号", "姓名"])
    book.active.append(["000123", "张三"])
    book.active.append(["工号", "姓名"])
    book.active.append(["000124", "李四"])
    buffer = BytesIO()
    book.save(buffer)
    result = anonymize_upload("headers.xlsx", buffer.getvalue(), consistent_ids=True)
    from privacy_data_agent.models import MappingFile
    mapping = MappingFile.model_validate_json(result["mapping_json"])
    assert len(mapping.people) == 2
    out = load_workbook(BytesIO(result["anonymized_xlsx"]))
    assert out.active["B3"].value == "姓名"


@pytest.mark.parametrize("file_type", ["csv", "xlsx"])
@pytest.mark.parametrize("middle", ["/", "/--/"])
def test_multiple_employees_in_role_cell_keep_individual_tokens(registry, file_type, middle):
    expected = run(["张三,000123,,销售部", "李四,000124,,销售部"])
    content = f"SDR\n张三{middle}李四\n".encode()
    if file_type == "xlsx":
        book = Workbook()
        book.active.append(["SDR"])
        book.active.append([f"张三{middle}李四"])
        buffer = BytesIO()
        book.save(buffer)
        content = buffer.getvalue()
    result = anonymize_upload(f"groups.{file_type}", content, consistent_ids=True)
    out = load_workbook(BytesIO(result["anonymized_xlsx"]))
    assert out.active["A2"].value == f"{expected[0][0]}{middle}{expected[1][0]}"


def test_customer_names_are_also_masked_in_titles_notes_and_comments(registry):
    from openpyxl.comments import Comment
    book = Workbook()
    book.active.append(["工号", "姓名", "客户名称", "备注", "客户类型", "客户拜访数-实际"])
    book.active.append(["000123", "张三", "示例科技有限公司", "与示例科技有限公司续约", "新签", 15])
    book.active["D2"].comment = Comment("示例科技有限公司的说明", "测试")
    title = book.create_sheet("说明")
    title["A1"] = "单位名称：示例科技有限公司"
    buffer = BytesIO()
    book.save(buffer)
    result = anonymize_upload("customers.xlsx", buffer.getvalue(), consistent_ids=True)
    out = load_workbook(BytesIO(result["anonymized_xlsx"]))
    token = out.active["C2"].value
    assert token.startswith("PDA_")
    assert out.active["D2"].value == f"与{token}续约"
    assert out.active["D2"].comment.text == f"{token}的说明"
    assert out.worksheets[1]["A1"].value == f"单位名称：{token}"
    assert out.active["E2"].value == "新签"
    assert out.active["F2"].value == 15


def test_short_customer_name_does_not_replace_part_of_existing_token(registry):
    import re
    book = Workbook()
    book.active.append(["客户名称", "DATE"])
    book.active.append(["DA", "2026-11-14"])
    buffer = BytesIO()
    book.save(buffer)
    result = anonymize_upload("short.xlsx", buffer.getvalue(), consistent_ids=True)
    out = load_workbook(BytesIO(result["anonymized_xlsx"]))
    value = out.active["A2"].value
    assert re.fullmatch(r"PDA_[0-9A-F]{16}", value)
    assert out.active["B1"].value == "DATE"


@pytest.mark.parametrize("location", ["formula_reference", "sheet_title"])
def test_customer_name_in_formula_or_sheet_title_requires_review(registry, location):
    book = Workbook()
    book.active.append(["客户名称", "公式"])
    book.active.append(["示例科技有限公司", None])
    if location == "formula_reference":
        book.active["B2"] = "='[示例科技有限公司.xlsx]Sheet1'!A2"
    else:
        book.active.title = "示例科技有限公司"
    buffer = BytesIO()
    book.save(buffer)
    with pytest.raises(ValueError, match="客户名称") as error:
        anonymize_upload("formulas.xlsx", buffer.getvalue(), consistent_ids=True)
    assert "示例科技有限公司" not in str(error.value)
    assert not registry.exists()


def test_customer_literal_in_formula_uses_same_token_without_changing_function(registry):
    book = Workbook()
    book.active.append(["客户名称", "公式"])
    book.active.append(["示例科技有限公司", '=COUNTIF(A:A,"示例科技有限公司")'])
    buffer = BytesIO()
    book.save(buffer)
    result = anonymize_upload("formula.xlsx", buffer.getvalue(), consistent_ids=True)
    out = load_workbook(BytesIO(result["anonymized_xlsx"]))
    token = out.active["A2"].value
    assert out.active["B2"].value == f'=COUNTIF(A:A,"{token}")'
    assert out.active["B2"].data_type == "f"
