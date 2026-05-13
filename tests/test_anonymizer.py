from pathlib import Path
import re

import pandas as pd

from privacy_data_agent.anonymizer import anonymize_dataframe
from privacy_data_agent.models import EntityType

TOKEN_RE = re.compile(r"PDA_[A-F0-9]{16}")


def test_anonymizes_sensitive_columns_and_builds_mapping():
    df = pd.read_csv(Path("tests/fixtures/hr_sample.csv"))

    result = anonymize_dataframe(df)

    csv_text = result.dataframe.to_csv(index=False)
    for raw in [
        "张三",
        "李四",
        "王五",
        "11010119900307001X",
        "华东销售一部",
        "上海春雷科技有限公司",
        "13800138000",
        "zhangsan@example.com",
    ]:
        assert raw not in csv_text

    assert len(TOKEN_RE.findall(csv_text)) >= 6
    for type_revealing_prefix in ["EMP_", "ID_", "DEPT_", "CUSTOMER_", "PHONE_", "EMAIL_"]:
        assert type_revealing_prefix not in csv_text
    assert result.mapping.entries[0].entity_type == EntityType.EMPLOYEE
    assert result.mapping.entries[0].original == "张三"
    assert TOKEN_RE.fullmatch(result.mapping.entries[0].token)


def test_license_plate_detection():
    """Blue license plates (新能源 excluded for simplicity) are detected and anonymized."""
    df = pd.DataFrame({
        "车牌号": ["苏E8V329", "苏E12345", "京A12345"],
    })

    result = anonymize_dataframe(df)

    csv_text = result.dataframe.to_csv(index=False)
    for raw in ["苏E8V329", "苏E12345", "京A12345"]:
        assert raw not in csv_text
    assert TOKEN_RE.findall(csv_text)
    plate_entries = [e for e in result.mapping.entries if e.entity_type == EntityType.LICENSE_PLATE]
    assert len(plate_entries) == 3
    for entry in plate_entries:
        assert TOKEN_RE.fullmatch(entry.token)


def test_reuses_same_token_for_repeated_value():
    df = pd.DataFrame({"部门": ["华东销售一部", "华东销售一部"]})

    result = anonymize_dataframe(df)

    tokens = result.dataframe["部门"].tolist()
    assert tokens[0] == tokens[1]
    assert TOKEN_RE.fullmatch(tokens[0])
    assert len(result.mapping.entries) == 1


def test_member_and_member_department_columns_anonymized():
    df = pd.DataFrame({
        "成员": ["张三", "李四"],
        "成员所属部门": ["产品中心-设计部", "产品中心/研发部"],
    })

    result = anonymize_dataframe(df)

    csv_text = result.dataframe.to_csv(index=False)
    for raw in ["张三", "李四", "产品中心-设计部", "产品中心/研发部"]:
        assert raw not in csv_text
    originals = {e.original: e.entity_type for e in result.mapping.entries}
    assert originals["张三"] == EntityType.EMPLOYEE
    assert originals["产品中心-设计部"] == EntityType.DEPARTMENT


def test_weak_person_object_column_uses_short_name_fallback():
    df = pd.DataFrame({
        "对象": ["张三", "欧阳婷婷", "诸葛小明明", "技术部", "张主管"],
        "备注": ["李四", "王五", "赵六", "陈七", "孙八"],
    })

    result = anonymize_dataframe(df)

    csv_text = result.dataframe.to_csv(index=False)
    for raw in ["张三", "欧阳婷婷", "诸葛小明明"]:
        assert raw not in csv_text
    for raw in ["技术部", "张主管", "李四", "王五", "赵六", "陈七", "孙八"]:
        assert raw in csv_text
    originals = {e.original: e.entity_type for e in result.mapping.entries}
    assert originals["张三"] == EntityType.EMPLOYEE
    assert originals["诸葛小明明"] == EntityType.EMPLOYEE


def test_subject_columns_are_anonymized_as_customer():
    df = pd.DataFrame({
        "所属主体": ["上海春雷科技有限公司", "北京星河管理咨询有限公司"],
        "法人主体": ["深圳远山科技有限公司", "杭州云舟信息技术有限公司"],
    })

    result = anonymize_dataframe(df)

    csv_text = result.dataframe.to_csv(index=False)
    for raw in [
        "上海春雷科技有限公司",
        "北京星河管理咨询有限公司",
        "深圳远山科技有限公司",
        "杭州云舟信息技术有限公司",
    ]:
        assert raw not in csv_text
    originals = {e.original: e.entity_type for e in result.mapping.entries}
    assert originals["上海春雷科技有限公司"] == EntityType.CUSTOMER
    assert originals["深圳远山科技有限公司"] == EntityType.CUSTOMER


def test_independent_batches_produce_different_tokens():
    """Without a seed, the same value in two separate batches should get different tokens."""
    df = pd.DataFrame({"姓名": ["张三"]})

    r1 = anonymize_dataframe(df)
    r2 = anonymize_dataframe(df)

    assert r1.dataframe.iloc[0]["姓名"] != r2.dataframe.iloc[0]["姓名"], "独立批次应产生不同 token"


def test_seed_mapping_reuses_tokens_for_known_entities():
    """When a seed mapping is provided, known entities reuse their tokens; new entities get fresh ones."""
    df1 = pd.DataFrame({"姓名": ["张三"], "部门": ["华东销售一部"]})
    r1 = anonymize_dataframe(df1)
    token_zhangsan = r1.dataframe.iloc[0]["姓名"]
    token_dept = r1.dataframe.iloc[0]["部门"]

    df2 = pd.DataFrame({"姓名": ["张三", "李四"], "部门": ["华东销售一部", "产品研发部"]})
    r2 = anonymize_dataframe(df2, seed_mapping=r1.mapping)

    assert r2.dataframe.iloc[0]["姓名"] == token_zhangsan, "seed 中已有实体应复用 token"
    assert r2.dataframe.iloc[0]["部门"] == token_dept, "seed 中已有部门应复用 token"
    assert r2.dataframe.iloc[1]["姓名"] != token_zhangsan, "新实体应生成新 token"
    # Merged mapping contains all 4 entries
    assert len(r2.mapping.entries) == 4
