from privacy_data_agent.models import EntityType, MappingEntry, MappingFile
from privacy_data_agent.restorer import restore_report


def test_restores_tokens_in_report():
    mapping = MappingFile(
        entries=[
            MappingEntry(entity_type=EntityType.EMPLOYEE, original="张三", token="EMP_0001"),
            MappingEntry(entity_type=EntityType.DEPARTMENT, original="华东销售一部", token="DEPT_0001"),
            MappingEntry(entity_type=EntityType.CUSTOMER, original="上海春雷科技有限公司", token="CUSTOMER_0001"),
        ]
    )
    report = "EMP_0001 在 DEPT_0001 负责 CUSTOMER_0001，建议提高资源投入。"

    restored = restore_report(report, mapping)

    assert restored == "张三 在 华东销售一部 负责 上海春雷科技有限公司，建议提高资源投入。"
