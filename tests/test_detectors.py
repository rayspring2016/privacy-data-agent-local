from privacy_data_agent.detectors import (
    _looks_like_chinese_name,
    detect_cell_entity_type,
    detect_column_entity_type,
    detect_header_row,
    detect_high_confidence_cell_entity_type,
    detect_label_value_layout,
    detect_optional_column_entity_type,
    detect_weak_person_column,
    is_pass_through_column,
    looks_like_short_chinese_person_name,
    resolve_entity_from_label,
    _phone_format_suspicious,
    _email_format_suspicious,
    EntityType,
    JOB_TITLE_FULL_BLACKLIST,
    JOB_TITLE_TERM_BLACKLIST,
)
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
    assert detect_column_entity_type("所属主体") == EntityType.CUSTOMER
    assert detect_column_entity_type("法人主体") == EntityType.CUSTOMER
    assert detect_column_entity_type("用工主体") == EntityType.CUSTOMER
    assert detect_column_entity_type("销售负责人") == EntityType.EMPLOYEE
    assert detect_column_entity_type("客户经理") == EntityType.EMPLOYEE
    assert detect_column_entity_type("责任人") == EntityType.EMPLOYEE
    assert detect_column_entity_type("审批人") == EntityType.EMPLOYEE
    assert detect_column_entity_type("跟进人") == EntityType.EMPLOYEE
    assert detect_column_entity_type("人数") is None
    assert detect_column_entity_type("中心") == EntityType.DEPARTMENT
    assert detect_column_entity_type("组别") == EntityType.DEPARTMENT
    assert detect_column_entity_type("事业部") == EntityType.DEPARTMENT
    assert detect_column_entity_type("成员") == EntityType.EMPLOYEE
    assert detect_column_entity_type("成员所属部门") == EntityType.DEPARTMENT
    assert detect_column_entity_type("所属部门") == EntityType.DEPARTMENT


def test_detects_cell_patterns_without_column_hint():
    assert detect_cell_entity_type("11010119900307001X") == EntityType.ID_NUMBER
    assert detect_cell_entity_type("13800138000") == EntityType.PHONE
    assert detect_cell_entity_type("zhangsan@example.com") == EntityType.EMAIL
    assert detect_cell_entity_type("120000") is None


def test_detects_hierarchical_department_values():
    assert detect_cell_entity_type("产品中心-设计部") == EntityType.DEPARTMENT
    assert detect_cell_entity_type("产品中心/设计部") == EntityType.DEPARTMENT
    assert detect_cell_entity_type("产品中心／设计部") == EntityType.DEPARTMENT


def test_weak_person_column_and_short_name_fallback():
    assert detect_column_entity_type("对象") is None
    assert detect_weak_person_column("对象") is True
    assert detect_weak_person_column("考核对象") is True
    assert looks_like_short_chinese_person_name("张三") is True
    assert looks_like_short_chinese_person_name("欧阳婷婷") is True
    assert looks_like_short_chinese_person_name("诸葛小明明") is True
    assert looks_like_short_chinese_person_name("技术部") is False
    assert looks_like_short_chinese_person_name("张主管") is False


def test_high_confidence_cell_detection_excludes_names_and_departments():
    assert detect_high_confidence_cell_entity_type("11010119900307001X") == EntityType.ID_NUMBER
    assert detect_high_confidence_cell_entity_type("13800138000") == EntityType.PHONE
    assert detect_high_confidence_cell_entity_type("zhangsan@example.com") == EntityType.EMAIL
    assert detect_high_confidence_cell_entity_type("EMP00123") == EntityType.EMPLOYEE_ID
    assert detect_high_confidence_cell_entity_type("张三") is None
    assert detect_high_confidence_cell_entity_type("技术部") is None


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


# ── v1.12.0: D5 surname expansion + D6 blacklist ────────────────────────────

def test_surname_set_expansion():
    """Surname set should have grown significantly (~600+ entries)."""
    from privacy_data_agent.detectors import SURNAME_SET
    assert len(SURNAME_SET) >= 580, f"SURNAME_SET too small: {len(SURNAME_SET)}"
    # Verify we have both singles and compounds
    singles = {s for s in SURNAME_SET if len(s) == 1}
    compounds = SURNAME_SET - singles
    assert len(singles) >= 500, f"Too few single surnames: {len(singles)}"
    assert len(compounds) >= 80, f"Too few compound surnames: {len(compounds)}"


def test_blacklist_filters_ai_tool_names():
    """AI tool names should NOT be detected as names."""
    from privacy_data_agent.detectors import _looks_like_chinese_name
    ai_tools = ["文心", "通义", "豆包", "Kimi", "智谱", "天工", "讯飞", "秘塔"]
    for name in ai_tools:
        assert _looks_like_chinese_name(name) is False, f"{name!r} should be blocked by AI_TOOL_BLACKLIST"


def test_blacklist_filters_common_word_pairs():
    """Common two-character words should NOT be detected as names."""
    from privacy_data_agent.detectors import _looks_like_chinese_name
    word_pairs = ["大小", "多少", "高低", "长短", "远近", "左右", "上下", "前后"]
    for word in word_pairs:
        assert _looks_like_chinese_name(word) is False, f"{word!r} should be blocked by COMMON_WORD_PAIR_BLACKLIST"


def test_blacklist_filters_places_and_institutions():
    """Place/institution names should NOT be detected as names."""
    from privacy_data_agent.detectors import _looks_like_chinese_name
    places = ["北京", "上海", "深圳", "腾讯", "阿里", "字节", "百度", "京东"]
    for place in places:
        assert _looks_like_chinese_name(place) is False, f"{place!r} should be blocked by PLACE_INSTITUTION_BLACKLIST"


def test_blacklist_filters_idioms():
    """Idioms (4-char) should NOT be detected as names."""
    from privacy_data_agent.detectors import _looks_like_chinese_name
    idioms = ["春夏秋冬", "东南西北", "千军万马", "三心二意"]
    for idiom in idioms:
        assert _looks_like_chinese_name(idiom) is False, f"{idiom!r} should be blocked by IDIOM_BLACKLIST"


def test_names_not_in_blacklist_still_detected():
    """Valid names not in blacklist should still be detected."""
    from privacy_data_agent.detectors import _looks_like_chinese_name
    names = ["王明", "李华", "张伟", "欧阳婷", "陈杨健", "东方彤"]
    for name in names:
        assert _looks_like_chinese_name(name) is True, f"{name!r} should be a valid name"


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


# ── v1.13.0: Label-value layout detection ──────────────────────────────────

def test_resolve_entity_from_label():
    """Labels map to correct entity types."""
    assert resolve_entity_from_label("姓名") == EntityType.EMPLOYEE
    assert resolve_entity_from_label("员工姓名") == EntityType.EMPLOYEE
    assert resolve_entity_from_label("手机号") == EntityType.PHONE
    assert resolve_entity_from_label("身份证号") == EntityType.ID_NUMBER
    assert resolve_entity_from_label("部门") == EntityType.DEPARTMENT
    assert resolve_entity_from_label("工资") == EntityType.SALARY
    assert resolve_entity_from_label("岗位名称") is None
    assert resolve_entity_from_label("岗位名称", anonymize_job_title=True) == EntityType.JOB_TITLE
    assert resolve_entity_from_label("备注") is None
    assert resolve_entity_from_label("随便写的") is None


def test_optional_and_pass_through_columns():
    assert detect_column_entity_type("岗位名称") is None
    assert detect_optional_column_entity_type("岗位名称") == EntityType.JOB_TITLE
    assert is_pass_through_column("岗位名称") is True
    assert is_pass_through_column("岗位名称", anonymize_job_title=True) is False
    assert is_pass_through_column("离职原因") is True
    assert is_pass_through_column("离职类型") is True
    assert detect_column_entity_type("岗位补贴") == EntityType.SALARY
    assert detect_optional_column_entity_type("岗位补贴") is None
    assert is_pass_through_column("岗位补贴") is False


def test_detect_label_value_layout_positive():
    """Sheet with labels in column A → detected as label-value layout."""
    import openpyxl
    from io import BytesIO

    wb = openpyxl.Workbook()
    ws = wb.active
    # Row 1: header-like row (skipped by detection)
    ws.append(["字段", "值"])
    # Rows 2-6: label-value pairs
    ws.append(["姓名", "张三"])
    ws.append(["工号", "EMP001"])
    ws.append(["部门", "技术部"])
    ws.append(["手机号", "13800138000"])
    ws.append(["邮箱", "test@example.com"])
    # Detection scans rows 2–21 (header_row+1 to header_row+20)
    assert detect_label_value_layout(ws, header_row=1) is True


def test_detect_label_value_layout_negative_normal_table():
    """Normal data table (names in column A) → NOT detected as label-value."""
    import openpyxl
    from io import BytesIO

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["姓名", "部门", "手机号"])
    ws.append(["张三", "技术部", "13800138000"])
    ws.append(["李四", "销售部", "13900139000"])
    ws.append(["王五", "财务部", "13700137000"])
    # Column A has 张三/李四/王五 — not labels
    assert detect_label_value_layout(ws, header_row=1) is False


def test_detect_label_value_layout_negative_too_few_labels():
    """Sheet with only 2 labels → NOT detected (needs ≥3)."""
    import openpyxl
    from io import BytesIO

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["字段", "值"])
    ws.append(["姓名", "张三"])
    ws.append(["年龄", "30"])
    ws.append(["备注", "无"])
    ws.append(["地址", "苏州"])
    # Only "姓名" is a label keyword → 1/4 = 25%, < 50%
    assert detect_label_value_layout(ws, header_row=1) is False


# ── 二次校验层测试 ────────────────────────────────────────────────

def test_job_title_blacklist_has_full_terms():
    """完整职位名在黑名单中（整词匹配）"""
    assert "客服主管" in JOB_TITLE_FULL_BLACKLIST
    assert "财务专员" in JOB_TITLE_FULL_BLACKLIST
    assert "HRBP" in JOB_TITLE_FULL_BLACKLIST
    assert "董秘" in JOB_TITLE_FULL_BLACKLIST


def test_job_title_term_blacklist_has_keywords():
    """职位关键字在黑名单中（用于"百家姓+职位"模式）"""
    assert "主管" in JOB_TITLE_TERM_BLACKLIST
    assert "专员" in JOB_TITLE_TERM_BLACKLIST
    assert "总监" in JOB_TITLE_TERM_BLACKLIST
    assert "经理" in JOB_TITLE_TERM_BLACKLIST
    assert "董事" in JOB_TITLE_TERM_BLACKLIST
    assert "直线经理" in JOB_TITLE_TERM_BLACKLIST
    assert "虚线经理" in JOB_TITLE_TERM_BLACKLIST


def test_surname_plus_job_title_rejected():
    """百家姓+职位后缀被正确排除：单姓+2字职位"""
    assert _looks_like_chinese_name("张主管") is False
    assert _looks_like_chinese_name("王专员") is False
    assert _looks_like_chinese_name("李总监") is False
    assert _looks_like_chinese_name("赵经理") is False


def test_surname_plus_job_title_compound_rejected():
    """百家姓+职位后缀被正确排除：复姓+2字职位"""
    assert _looks_like_chinese_name("欧阳经理") is False
    assert _looks_like_chinese_name("司马主管") is False


def test_valid_chinese_names_still_detected():
    """正常中文姓名仍然被正确识别"""
    assert _looks_like_chinese_name("张明") is True
    assert _looks_like_chinese_name("欧阳静") is True
    assert _looks_like_chinese_name("王丽") is True


def test_job_title_full_blacklist_rejected():
    """完整职位名（黑名单整词）被正确排除"""
    assert _looks_like_chinese_name("客服主管") is False
    assert _looks_like_chinese_name("财务专员") is False
    assert _looks_like_chinese_name("董秘") is False


def test_strong_rule_employee_column_job_titles_filtered():
    """强规则 EMPLOYEE 列中，岗位值被百家姓二次校验过滤"""
    assert detect_cell_entity_type("张主管", EntityType.EMPLOYEE) is None
    assert detect_cell_entity_type("客服主管", EntityType.EMPLOYEE) is None
    assert detect_cell_entity_type("张明", EntityType.EMPLOYEE) == EntityType.EMPLOYEE
    # 无列上下文时：内容模式能检测到"张明"
    assert detect_cell_entity_type("张明", None) == EntityType.EMPLOYEE


def test_phone_format_suspicious_rejects_test_numbers():
    """手机号格式二次校验排除测试号"""
    assert _phone_format_suspicious("00000000000") is True
    assert _phone_format_suspicious("11111111111") is True
    assert _phone_format_suspicious("12345678901") is True
    assert _phone_format_suspicious("13812345678") is False  # 正常号段


def test_email_format_suspicious_rejects_test_addresses():
    """邮箱格式二次校验排除测试地址"""
    assert _email_format_suspicious("test@example.com") is True
    assert _email_format_suspicious("测试@163.com") is True
    assert _email_format_suspicious("zhangsan@163.com") is False  # 正常邮箱
