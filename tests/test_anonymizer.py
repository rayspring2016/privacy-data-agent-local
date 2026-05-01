from pathlib import Path

import pandas as pd

from privacy_data_agent.anonymizer import anonymize_dataframe
from privacy_data_agent.models import EntityType


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

    assert "EMP_0001" in csv_text
    assert "ID_0001" in csv_text
    assert "DEPT_0001" in csv_text
    assert "CUSTOMER_0001" in csv_text
    assert "PHONE_0001" in csv_text
    assert "EMAIL_0001" in csv_text
    assert result.mapping.entries[0].entity_type == EntityType.EMPLOYEE
    assert result.mapping.entries[0].original == "张三"
    assert result.mapping.entries[0].token == "EMP_0001"


def test_reuses_same_token_for_repeated_value():
    df = pd.DataFrame({"部门": ["华东销售一部", "华东销售一部"]})

    result = anonymize_dataframe(df)

    assert result.dataframe["部门"].tolist() == ["DEPT_0001", "DEPT_0001"]
    assert len(result.mapping.entries) == 1
