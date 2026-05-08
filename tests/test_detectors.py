from privacy_data_agent.detectors import detect_cell_entity_type, detect_column_entity_type, detect_header_row
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


def test_detect_header_row_standard_table():
    rows = [["员工姓名", "部门", "客户名称"], ["张三", "销售一部", "上海科技"]]
    assert detect_header_row(rows) == 1


def test_detect_header_row_title_first_row():
    rows = [["2024年度员工信息表"], ["员工姓名", "部门", "客户名称"], ["张三", "销售一部", "上海科技"]]
    assert detect_header_row(rows) == 2


def test_detect_header_row_fewer_than_two_rows():
    assert detect_header_row([["员工姓名"]]) == 1


def test_n_level_org_and_dept_detected_as_department():
    """'一级组织' / '二级部门' etc. must map to EntityType.DEPARTMENT."""
    cases = [
        "一级组织", "二级组织", "三级组织", "四级组织",
        "一级部门", "二级部门", "三级部门", "四级部门",
    ]
    for col in cases:
        result = detect_column_entity_type(col)
        assert result == EntityType.DEPARTMENT, f"{col!r} → {result}, expected DEPARTMENT"


def test_new_surnames_in_surname_set():
    """v1.9.0: ~80 new entries spot-checked."""
    from privacy_data_agent.detectors import SURNAME_SET
    new_singles = [
        "卜", "刁", "华", "阳", "农", "鲍", "奉", "昌", "干", "牟",
        "岑", "芮", "荣", "闻", "阮", "敖", "衡", "宓", "匡", "米",
        "吉", "印", "禹", "仰", "薄", "沐", "晁", "桂", "沃", "展",
        "勾", "佟", "伏", "伊", "权", "隆", "扈", "籍", "诸", "茅",
        "栗", "咸", "辜", "满", "花", "靖", "相", "帅", "平", "班",
        "邴", "嵇", "边", "辛", "濮", "浦", "庄", "郗", "祁",
        "公", "富", "竺", "终", "邰", "戎", "殳", "哈", "麻", "尚",
        "甄", "冼", "危", "宿", "折", "喜", "别",
        "阙", "晋", "强", "居", "养", "逄", "隗", "菅", "国", "雍",
    ]
    new_compound = ["东方", "南宫", "西门", "百里", "端木", "夏侯", "鲜于", "司徒", "司空", "万俟"]
    missing = [s for s in new_singles + new_compound if s not in SURNAME_SET]
    assert missing == [], f"Missing from SURNAME_SET: {missing}"


def test_new_surnames_detected_as_chinese_names():
    """_looks_like_chinese_name accepts names with new surnames."""
    from privacy_data_agent.detectors import _looks_like_chinese_name
    assert _looks_like_chinese_name("卜文") is True
    assert _looks_like_chinese_name("芮嘉") is True
    assert _looks_like_chinese_name("阮华") is True
    assert _looks_like_chinese_name("甄磊") is True
    assert _looks_like_chinese_name("雍辉") is True
    assert _looks_like_chinese_name("奉子文") is True
    assert _looks_like_chinese_name("东方彤") is True
    assert _looks_like_chinese_name("夏侯涛") is True


def test_surname_set_no_regression():
    """Original surnames unchanged after expansion."""
    from privacy_data_agent.detectors import SURNAME_SET
    for s in ["王", "李", "张", "欧阳", "司马", "陈杨", "童", "仲", "左"]:
        assert s in SURNAME_SET, f"Regression: {s!r} removed"


# ── v1.10.0: SALARY entity type ──────────────────────────────────────────────

def test_salary_column_types():
    """Salary-related column names should detect as SALARY."""
    cases = [
        "工资", "薪资", "薪酬", "底薪", "基本工资", "应发工资", "实发工资",
        "税前工资", "税后工资", "奖金", "年终奖", "绩效工资", "绩效奖金",
        "提成", "佣金", "补贴", "餐补", "交通补贴", "通讯补贴", "住房补贴",
        "高温补贴", "岗位补贴", "其他补贴", "五险一金", "社保", "公积金",
        "社保公积金", "人力成本", "年薪", "月薪", "日薪", "报酬", "收入",
        "salary", "wage", "bonus", "compensation", "pay",
    ]
    for col in cases:
        result = detect_column_entity_type(col)
        assert result == EntityType.SALARY, f"{col!r} → {result}, expected SALARY"


def test_salary_column_non_salary_filtered():
    """Non-salary columns should NOT detect as SALARY."""
    non_salary = [
        "销售总额", "订单金额", "预算金额",  # 这些是金额但不是个人薪酬
        "绩效评分", "绩效等级",  # 绩效等级/评分是考核结果，不是金额
        "绩效考核", "绩效评估", "考核评分", "考核等级",
    ]
    for col in non_salary:
        result = detect_column_entity_type(col)
        # 只要不是SALARY就行（可能是CUSTOMER/DEPARTMENT/EMPLOYEE/None）
        assert result != EntityType.SALARY, f"{col!r} should NOT be SALARY, got {result}"


def test_pure_digit_employee_id_requires_column_context():
    """Pure-digit IDs (e.g. 001234) must be in an EMPLOYEE_ID column to be detected."""
    from privacy_data_agent.detectors import detect_cell_entity_type
    from privacy_data_agent.models import EntityType

    # Without column context: too ambiguous, should NOT detect
    assert detect_cell_entity_type("001234") is None
    assert detect_cell_entity_type("1234567") is None
    assert detect_cell_entity_type("000001") is None

    # In EMPLOYEE_ID column: should detect
    assert detect_cell_entity_type("001234", column_type=EntityType.EMPLOYEE_ID) == EntityType.EMPLOYEE_ID
    assert detect_cell_entity_type("1234567", column_type=EntityType.EMPLOYEE_ID) == EntityType.EMPLOYEE_ID
    assert detect_cell_entity_type("000001", column_type=EntityType.EMPLOYEE_ID) == EntityType.EMPLOYEE_ID

    # In non-EMPLOYEE_ID column: should NOT detect (avoids false positives like years/codes)
    assert detect_cell_entity_type("001234", column_type=EntityType.CUSTOMER) is None
    assert detect_cell_entity_type("001234", column_type=EntityType.DEPARTMENT) is None
    assert detect_cell_entity_type("001234", column_type=EntityType.SALARY) is None

    # Too short (<4 digits): ambiguous, should NOT detect even in EMPLOYEE_ID column
    assert detect_cell_entity_type("123", column_type=EntityType.EMPLOYEE_ID) is None
    assert detect_cell_entity_type("1234", column_type=EntityType.EMPLOYEE_ID) == EntityType.EMPLOYEE_ID

    # Too long (>10 digits): probably not an employee ID
    assert detect_cell_entity_type("12345678901", column_type=EntityType.EMPLOYEE_ID) is None