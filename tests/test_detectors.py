from privacy_data_agent.detectors import detect_cell_entity_type, detect_column_entity_type
from privacy_data_agent.models import EntityType


def test_detects_column_semantics():
    assert detect_column_entity_type("员工姓名") == EntityType.EMPLOYEE
    assert detect_column_entity_type("身份证号") == EntityType.ID_NUMBER
    assert detect_column_entity_type("部门") == EntityType.DEPARTMENT
    assert detect_column_entity_type("客户名称") == EntityType.CUSTOMER
    assert detect_column_entity_type("手机号") == EntityType.PHONE
    assert detect_column_entity_type("邮箱") == EntityType.EMAIL
    assert detect_column_entity_type("销售额") is None


def test_detects_common_business_sensitive_columns():
    assert detect_column_entity_type("公司名称") == EntityType.CUSTOMER
    assert detect_column_entity_type("销售负责人") == EntityType.EMPLOYEE
    assert detect_column_entity_type("客户经理") == EntityType.EMPLOYEE
    assert detect_column_entity_type("责任人") == EntityType.EMPLOYEE
    assert detect_column_entity_type("审批人") == EntityType.EMPLOYEE
    assert detect_column_entity_type("跟进人") == EntityType.EMPLOYEE
    assert detect_column_entity_type("人数") is None
    assert detect_column_entity_type("中心") == EntityType.DEPARTMENT
    assert detect_column_entity_type("组别") == EntityType.DEPARTMENT
    assert detect_column_entity_type("事业部") == EntityType.DEPARTMENT


def test_detects_cell_patterns_without_column_hint():
    assert detect_cell_entity_type("11010119900307001X") == EntityType.ID_NUMBER
    assert detect_cell_entity_type("13800138000") == EntityType.PHONE
    assert detect_cell_entity_type("zhangsan@example.com") == EntityType.EMAIL
    assert detect_cell_entity_type("120000") is None
