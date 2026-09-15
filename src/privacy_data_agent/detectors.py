from __future__ import annotations

import re
from enum import StrEnum

from privacy_data_agent.models import EntityType


class SalaryGroup(StrEnum):
    """SALARY 列的子分组。口径由用户人工裁定（2026-08-08），不是 AI 猜的。

    分组存在的理由：不同薪资子类敏感度不同（个人薪酬 vs 社保 vs 聚合人力成本），
    单一布尔开关会强迫「要么全露要么全藏」，无法支持「放开人力成本做人效分析，
    但不暴露个人年薪」这类真实场景。
    """

    PERSONAL_COMP = "personal_comp"
    SOCIAL_INSURANCE = "social_insurance"
    LABOR_COST = "labor_cost"
    ALLOWANCE = "allowance"
    COMMISSION = "commission"
    PERFORMANCE_PAY = "performance_pay"


SALARY_GROUPS: dict[SalaryGroup, tuple[str, ...]] = {
    SalaryGroup.PERSONAL_COMP: (
        "工资",
        "薪资",
        "薪酬",
        "底薪",
        "基本工资",
        "应发工资",
        "实发工资",
        "税前工资",
        "税后工资",
        "年薪",
        "月薪",
        "日薪",
        "报酬",
        "salary",
        "wage",
        "compensation",
        "pay",
    ),
    SalaryGroup.SOCIAL_INSURANCE: (
        "社保",
        "公积金",
        "社保公积金",
        "五险一金",
    ),
    # 人力成本/收入：聚合口径，人效分析要放开的正是这一组
    SalaryGroup.LABOR_COST: (
        "人力成本",
        "收入",
    ),
    SalaryGroup.ALLOWANCE: (
        "补贴",
        "餐补",
        "交通补贴",
        "通讯补贴",
        "住房补贴",
        "高温补贴",
        "岗位补贴",
        "其他补贴",
    ),
    SalaryGroup.COMMISSION: (
        "提成",
        "佣金",
    ),
    # 绩效工资/绩效奖金：与考核结果挂钩，归绩效而非个人薪酬包
    SalaryGroup.PERFORMANCE_PAY: (
        "奖金",
        "年终奖",
        "绩效工资",
        "绩效奖金",
        "bonus",
    ),
}

# 供 COLUMN_HINTS 复用：拆分之前 SALARY 是单一扁平关键词表，这里从
# SALARY_GROUPS 派生回同一份关键词全集，避免两处重复维护（DRY）。
_ALL_SALARY_KEYWORDS: tuple[str, ...] = tuple(
    keyword for keywords in SALARY_GROUPS.values() for keyword in keywords
)

ID_NUMBER_RE = re.compile(r"^\d{17}[\dXx]$")
PHONE_RE = re.compile(r"^(?:\+?86[- ]?)?1[3-9]\d{9}$")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
LICENSE_PLATE_RE = re.compile(r"^[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉贵粤青藏川宁琼使领][A-Z][A-Z0-9]{5}$")
# Employee / work number with letter prefix (e.g. EMP0012, A12345).
EMPLOYEE_ID_RE = re.compile(r"^[A-Za-z]{1,3}\d{4,10}$")
# Pure-digit employee ID (e.g. 001234, 1234567) — only detected in EMPLOYEE_ID column context.
PURE_DIGIT_EMPLOYEE_ID_RE = re.compile(r"^[0-9]{4,10}$")
NON_PERSON_REN_COLUMNS = ("人数", "人均", "人次", "人工", "人效", "人天")
# 绩效考核/评分列包含"绩效"但不是薪酬数字（绩效工资才是）
NON_SALARY_COLUMNS = ("评分", "等级", "考核", "评估", "评价", "档次")
JOB_TITLE_COLUMN_HINTS = (
    "岗位名称",
    "岗位",
    "职位",
    "职位名称",
    "职务",
    "职务名称",
    "job_title",
    "position",
    "title",
)
JOB_TITLE_EXCLUDED_HINTS = ("补贴", "工资", "薪资", "薪酬", "奖金", "收入")
PASS_THROUGH_COLUMN_HINTS = (
    "离职原因",
    "离职类型",
    "离职性质",
    "离职状态",
    "离职备注",
    "离职说明",
    "异动原因",
    "变动原因",
    "状态",
)
WEAK_PERSON_COLUMN_HINTS = (
    "对象",
    "考核对象",
    "评价对象",
    "评估对象",
    "访谈对象",
    "处理对象",
    "目标对象",
    "关联对象",
)

COLUMN_HINTS: tuple[tuple[EntityType, tuple[str, ...]], ...] = (
    (
        EntityType.EMPLOYEE,
        (
            "姓名",
            "员工",
            "成员",
            "人员",
            "负责人",
            "联系人",
            "对接人",
            "销售负责人",
            "客户经理",
            "顾问",
            "直线经理",
            "虚线经理",
            "虚线上级",
            "虚线下级",
            "上级",
            "下级",
            "汇报对象",
            "HRBP",
            "HRBP",
            "name",
            "employee",
            "owner",
            "manager",
        ),
    ),
    (EntityType.ID_NUMBER, ("身份证", "证件", "id_number", "national_id")),
    (
        EntityType.EMPLOYEE_ID,
        (
            "工号",
            "员工号",
            "员工编号",
            "编号",
            "工作编号",
            "staff_id",
            "emp_id",
            "employee_id",
            "employee_no",
            "work_id",
            "badge",
        ),
    ),
    (
        EntityType.DEPARTMENT,
        (
            "部门",
            "组织",
            "中心",
            "组别",
            "小组",
            "所属部门",
            "部门名称",
            "所属组织",
            "组织名称",
            "团队",
            "事业部",
            "大区",
            "区域",
            "级组织",      # 一/二/三/四级组织
            "级部门",      # 一/二/三/四级部门
            "department",
            "team",
            "group",
            "division",
            "region",
        ),
    ),
    (
        EntityType.CUSTOMER,
        (
            "客户",
            "客户名称",
            "公司",
            "公司名称",
            "企业",
            "企业名称",
            "主体",
            "所属主体",
            "法人主体",
            "用工主体",
            "单位",
            "单位名称",
            "商户",
            "供应商",
            "client",
            "customer",
            "account",
            "vendor",
        ),
    ),
    (EntityType.PHONE, ("手机号", "电话", "phone", "mobile")),
    (EntityType.EMAIL, ("邮箱", "email", "e-mail")),
    (EntityType.SALARY, _ALL_SALARY_KEYWORDS),
    (EntityType.LICENSE_PLATE, ("车牌", "车牌号", "车牌号码", "license_plate", "plate", "car_plate", "vehicle_plate")),
)


# ── 左右结构（标签-值布局）检测 ───────────────────────────────────
# 当Excel表单是A列=字段标签/B列=实际值的竖排布局时使用

LABEL_VALUE_KEYWORDS: frozenset[str] = frozenset({
    "姓名", "成员", "工号", "员工号", "员工编号", "编号",
    "部门", "所属部门", "部门名称", "组织", "所属组织", "组织名称", "中心", "组别",
    "主体", "所属主体", "法人主体", "用工主体",
    "手机号", "电话", "邮箱",
    "身份证", "身份证号",
    "车牌", "车牌号",
    "薪酬", "工资", "基本工资", "绩效工资",
    "入职日期", "离职日期",
    "岗位", "职位", "职务",
    "性别", "年龄", "学历", "毕业院校", "专业",
})


def detect_label_value_layout(worksheet, header_row: int = 1) -> bool:
    """检测sheet是否为左右结构（标签在A列，值在B列）。

    启发式：
    1. 前20行中第一列至少3行是标签关键词
    2. 第一列非空行中 >50% 是标签（2-4字中文名不算，避免正常人名表被误判）
    """
    label_count = 0
    total_nonempty = 0
    for row in worksheet.iter_rows(min_row=header_row + 1, max_row=header_row + 20):
        cells = list(row)
        if not cells or cells[0].value is None:
            continue
        text = str(cells[0].value).strip()
        if not text:
            continue
        total_nonempty += 1
        if text in LABEL_VALUE_KEYWORDS:
            label_count += 1

    if total_nonempty < 2:
        return False
    if label_count == total_nonempty and label_count >= 2:
        return True
    return label_count >= 3 and (label_count / total_nonempty) > 0.5


def resolve_entity_from_label(
    label: str,
    anonymize_job_title: bool = False,
    anonymize_department: bool = True,
    anonymize_region: bool = True,
    anonymize_salary: bool = True,
    keep_salary_groups: frozenset[SalaryGroup] = frozenset(),
) -> EntityType | None:
    """从字段标签文本推断其对应值的实体类型（用于左右结构）。"""
    if is_pass_through_column(
        label,
        anonymize_job_title=anonymize_job_title,
        anonymize_department=anonymize_department,
        anonymize_region=anonymize_region,
        anonymize_salary=anonymize_salary,
        keep_salary_groups=keep_salary_groups,
    ):
        return None
    optional = detect_optional_column_entity_type(label)
    if optional is not None:
        return optional if anonymize_job_title else None
    return detect_column_entity_type(label)


def is_pass_through_column(
    column_name: str,
    anonymize_job_title: bool = False,
    anonymize_department: bool = True,
    anonymize_region: bool = True,
    anonymize_salary: bool = True,
    keep_salary_groups: frozenset[SalaryGroup] = frozenset(),
) -> bool:
    normalized = _normalize_column_name(column_name)
    if not normalized:
        return False
    if any(hint in normalized for hint in PASS_THROUGH_COLUMN_HINTS):
        return True
    # 可选脱敏：JOB_TITLE
    if not anonymize_job_title and detect_optional_column_entity_type(column_name) is not None:
        return True
    # 可选脱敏：DEPARTMENT（默认=True，即默认脱敏）
    detected = detect_column_entity_type(column_name)
    if detected == EntityType.DEPARTMENT and not anonymize_department:
        return True
    # 可选脱敏：SALARY（默认=True，即默认脱敏；关闭后全列放行保留原值）
    if detected == EntityType.SALARY:
        if not anonymize_salary:
            return True
        if keep_salary_groups:
            group = resolve_salary_group(column_name)
            if group is not None and group in keep_salary_groups:
                return True
    return False


def detect_optional_column_entity_type(column_name: str) -> EntityType | None:
    normalized = _normalize_column_name(column_name)
    if any(hint in normalized for hint in JOB_TITLE_EXCLUDED_HINTS):
        return None
    if any(hint.lower() in normalized for hint in JOB_TITLE_COLUMN_HINTS):
        return EntityType.JOB_TITLE
    return None


def detect_weak_person_column(column_name: str) -> bool:
    normalized = _normalize_column_name(column_name)
    return any(hint in normalized for hint in WEAK_PERSON_COLUMN_HINTS)


def detect_column_entity_type(column_name: str) -> EntityType | None:
    normalized = _normalize_column_name(column_name)
    if any(
        hint in normalized
        for hint in ("所属部门", "部门名称", "所属组织", "组织名称")
    ):
        return EntityType.DEPARTMENT
    if _looks_like_person_column(normalized):
        return EntityType.EMPLOYEE
    # SALARY列排除：绩效评分/等级/考核（不是薪酬数字，是考核结果）
    if any(excluded in normalized for excluded in NON_SALARY_COLUMNS):
        # 硬编码：绩效+评分/等级/考核 → 不是SALARY
        for entity_type, hints in COLUMN_HINTS:
            for hint in hints:
                if hint.lower() in normalized:
                    if entity_type == EntityType.SALARY:
                        return None
                    return entity_type
    for entity_type, hints in COLUMN_HINTS:
        for hint in hints:
            hint_lower = hint.lower()
            if hint_lower in normalized:
                # 短词（2字以内）要求 hint 在开头，且总长度 ≤ hint×4
                if len(hint) <= 2:
                    cleaned = re.sub(r"[\s\d_（）()\.,，。、/\\]", "", normalized)
                    # hint 必须在开头，且不能比 hint 长太多
                    if not cleaned.startswith(hint_lower):
                        continue
                    if len(cleaned) > len(hint_lower) * 4:
                        continue
                    return entity_type
                else:
                    return entity_type
    return None


def resolve_salary_group(column_name: str) -> SalaryGroup | None:
    """已判定为 EntityType.SALARY 的列，具体属于哪个薪资子组。

    复用与 detect_column_entity_type 相同的短词锚定规则（≤2字关键词必须在
    列名开头才算数），保证子组归属跟"这一列当初为什么被判定为 SALARY"
    是同一套逻辑算出来的。不复用会有真实的误判风险：例如"绩效工资"里含
    有"工资"这个 personal_comp 的关键词子串，但"工资"不在"绩效工资"开头，
    按锚定规则不算数；真正命中的是 performance_pay 里"绩效工资"这个完整词。
    """
    normalized = _normalize_column_name(column_name)
    for group, keywords in SALARY_GROUPS.items():
        for keyword in keywords:
            keyword_lower = keyword.lower()
            if keyword_lower not in normalized:
                continue
            if len(keyword) <= 2:
                cleaned = re.sub(r"[\s\d_（）()\.,，。、/\\]", "", normalized)
                if not cleaned.startswith(keyword_lower):
                    continue
                if len(cleaned) > len(keyword_lower) * 4:
                    continue
            return group
    return None


def detect_high_confidence_cell_entity_type(value: object) -> EntityType | None:
    text = "" if value is None else str(value).strip()
    if not text:
        return None
    for pattern, entity_type in DETECTORS_BY_RE:
        if entity_type not in {
            EntityType.ID_NUMBER,
            EntityType.PHONE,
            EntityType.EMAIL,
            EntityType.LICENSE_PLATE,
            EntityType.EMPLOYEE_ID,
        }:
            continue
        if pattern.match(text):
            return entity_type
    return None


def _normalize_column_name(column_name: str) -> str:
    return column_name.strip().lower()


def _looks_like_person_column(normalized_column_name: str) -> bool:
    if any(excluded in normalized_column_name for excluded in NON_PERSON_REN_COLUMNS):
        return False
    return normalized_column_name.endswith("人")


def detect_header_row(raw_rows: list[list[str]]) -> int:
    """
    检测表头所在行，返回 1-based 行号。
    启发式：
    1. 第1行仅1个非空单元格（合并标题）→ 表头在第2行
    2. 第1行匹配的实体类型 <= 1 且第2行 >= 3 → 表头在第2行
    3. 其他 → 表头在第1行（向后兼容）
    """
    if len(raw_rows) < 2:
        return 1
    row1 = [str(c) if c is not None else "" for c in raw_rows[0]]
    row2 = [str(c) if c is not None else "" for c in raw_rows[1]]
    row1_nonempty = [c for c in row1 if c.strip()]
    if len(row1_nonempty) == 1 and len([c for c in row2 if c.strip()]) > 1:
        return 2
    row1_hits = sum(1 for c in row1 if detect_column_entity_type(c))
    row2_hits = sum(1 for c in row2 if detect_column_entity_type(c))
    if row1_hits <= 1 and row2_hits >= 2:
        return 2
    return 1


# 百家姓白名单（覆盖 99%+ 的中文姓名）
# 单姓（约650）+ 复姓/双姓（约90）= ~740 条
SURNAME_SET: set[str] = {
    # ── Top 100 单姓 ──────────────────────────────────────────────
    "王", "李", "张", "刘", "陈", "杨", "赵", "黄", "周", "吴",
    "徐", "孙", "胡", "朱", "高", "林", "何", "郭", "马", "罗",
    "梁", "宋", "郑", "谢", "韩", "唐", "冯", "于", "董", "萧",
    "程", "曹", "袁", "邓", "许", "傅", "沈", "曾", "彭", "吕",
    "苏", "卢", "蒋", "蔡", "贾", "丁", "魏", "薛", "叶", "阎",
    "余", "潘", "杜", "戴", "夏", "钟", "汪", "田", "任", "姜",
    "范", "方", "石", "姚", "谭", "廖", "邹", "熊", "金", "陆",
    "郝", "孔", "白", "崔", "康", "毛", "邱", "秦", "江", "史",
    "顾", "侯", "邵", "孟", "龙", "万", "段", "漕", "钱", "汤",
    "黎", "易", "常", "武", "乔", "贺", "赖", "龚", "文", "庞",
    # ── Top 101–300 单姓 ────────────────────────────────────────────
    "严", "温", "童", "倪", "安", "纪", "费", "颜", "路", "宁",
    "燕", "季", "盛", "谷", "牛", "霍", "曲", "陶", "雷", "蓝",
    "练", "步", "桑", "席", "单", "祝", "向", "骆", "古", "毕",
    "俞", "申", "邢", "伍", "殷", "葛", "鲁", "莫", "付", "关",
    "包", "穆", "凌", "欧", "聂", "翁", "章", "涂", "虞", "柯",
    "尹", "卞", "靳", "游", "苗", "冷", "岳", "戚", "舒", "习",
    "廉", "储", "明", "邬", "奚", "甘", "解", "缪", "司", "蒙",
    "池", "柳", "连", "艾", "齐", "宗", "郁", "翟",
    "鱼", "党", "闵", "胥", "晏", "娄", "扶", "幸", "鄢",
    "仲", "左", "卓", "应", "冉", "邝", "戈", "寇", "鞠", "屠",
    # ── Top 301–500 单姓 ────────────────────────────────────────────
    "卜", "刁", "华", "阳", "农", "鲍", "奉", "昌", "干", "牟",
    "岑", "芮", "荣", "闻", "阮", "敖", "衡", "宓", "匡", "米",
    "吉", "印", "禹", "仰", "薄", "沐", "晁", "桂", "沃", "展",
    "勾", "佟", "伏", "伊", "权", "隆", "扈", "籍", "诸", "茅",
    "栗", "咸", "辜", "满", "花", "靖", "相", "帅", "平", "班",
    "邴", "嵇", "边", "辛", "濮", "浦", "庄", "郗", "祁",
    "公", "富", "竺", "终", "邰", "戎", "殳", "哈", "麻", "尚",
    "甄", "冼", "危", "宿", "折", "喜", "别",
    "阙", "晋", "强", "居", "养", "逄", "隗", "菅", "国", "雍",
    # ── 扩展单姓 500–650 ──────────────────────────────────────────
    "丘", "丛", "书", "井", "亢", "仂", "仗", "仡", "仨", "仿",
    "伛", "伋", "佚", "佤", "佬", "伽", "佗", "佝", "佴", "侍",
    "侔", "侪", "侬", "俍", "俎", "佟", "仿", "伉", "佚", "佟",
    "伽", "仉", "佴", "俜", "偎", "偲", "傒", "僖", "凫",
    "仉", "仂", "伋", "佝", "佟", "仨", "仗", "仡", "仿", "仂",
    "俍", "俎", "伽", "佬", "佤", "仉", "佴", "侍", "侪", "侬",
    "俛", "俜", "偎", "偲", "傒", "僖", "凫", "刁", "刍", "剀",
    "剜", "剞", "叟", "弁", "彧", "徂", "徇", "徉", "恝", "恣",
    "悃", "悛", "惇", "惘", "惴", "愆", "愔", "愍", "慊", "懔",
    "抟", "拊", "拚", "抨", "抻", "挹", "捎", "捩", "揂", "揎",
    "昱", "昊", "昝", "昕", "枍", "枏", "柰", "柘", "枤", "枞",
    "枸", "柑", "柢", "柧", "棁", "椟", "椁", "楮", "欻", "殛",
    "殒", "殓", "殍", "沣", "泠", "洄", "洎", "泓", "洙", "浈",
    "淏", "湔", "澉", "澍", "濂", "灏", "灞", "牦", "犍", "狈",
    "狍", "狎", "狖", "狏", "獐", "獬", "玁", "玎", "玕", "玥",
    "玮", "珐", "琊", "琨", "琬", "琛", "瑱", "璪", "璐", "瓘",
    "癸", "矍", "矗", "矾", "砝", "硎", "碚", "禤", "祎", "祗",
    "祛", "祧", "稊", "穗", "竽", "筱", "篌", "籁", "纟", "绡",
    "绔", "绠", "绨", "缟", "缗", "缙", "繇", "翕", "耦", "耔",
    "聿", "耖", "聂", "聍", "聱", "肆", "肄", "胥", "脍", "脞",
    "臃", "舁", "舸", "艨", "茔", "茚", "茴", "荟", "荦", "莆",
    "萱", "萁", "菖", "萃", "萸", "蓁", "蕊", "蘸", "蘩", "觃",
    "觎", "讦", "讳", "讵", "诃", "诇", "貉", "趱", "跞", "踽",
    "軎", "酂", "酄", "鈒", "錀", "鏏", "闾", "阝", "阧", "阤",
    "陂", "隽", "雩", "颙", "颞", "饕", "骱", "髑", "魈", "魍",
    "鲠", "鲨", "鳍", "鹭", "黛", "黟", "黜", "鼯", "龁",
    "佴", "亓", "伽", "佝", "佟", "佤", "佬", "伉", "佚", "佟",
    "仉", "仂", "仉", "佴", "俜", "偎", "偲", "傒", "僖", "凫",
    # ── 复姓（约90条）────────────────────────────────────────────
    "欧阳", "司马", "上官", "诸葛", "慕容", "令狐", "公孙", "拓跋",
    "宇文", "呼延", "赫连", "澹台", "长孙", "尉迟", "皇甫", "仲孙",
    "东方", "南宫", "西门", "百里", "端木", "夏侯", "鲜于", "司徒",
    "司空", "万俟", "公羊", "公冶", "公西", "公良", "公仪", "太叔",
    "太史", "公仪", "颛孙", "子车", "夹谷", "子家", "仉督", "司寇",
    "宗政", "濮阳", "单于", "梁丘", "闾丘", "及梁", "於陵", "漆雕",
    "东郭", "南郭", "北郭", "东门", "南门", "北门", "第五", "中叔",
    "咎敖", "乐正", "乐羊", "归海", "微生", "索隐", "羊舌", "辑睦",
    "谷梁", "谷利", "宰父", "乐正", "乐羊", "恭",  # 恭是复姓
    # ── 双姓（约25条）────────────────────────────────────────────
    "陈杨", "张李", "刘王", "王李", "李王", "陈李", "张王", "杨李",
    "刘陈", "王陈", "杨陈", "李张", "王张", "陈张", "刘李", "王刘",
    "杨张", "刘张", "李杨", "陈王", "陈刘",
}

# ── 人名误报黑名单 ─────────────────────────────────────────────────
# 看起来像人名但实际不是的词组，按类别分组

# 5️⃣ 岗位/职位名称
JOB_TITLE_TERM_BLACKLIST: set[str] = {
    # 职能类职位关键字（用于"百家姓+职位"模式检测，如"张主管""王专员"）
    "主管", "经理", "总监", "主任", "专员", "助理", "秘书",
    "顾问", "内勤", "外勤", "文员", "科员", "干事", "代表",
    # 高管类
    "总裁", "总理", "副总", "董事", "监事",
    # 财务/技术/客服类
    "会计", "出纳", "审计", "财务", "结算", "税务", "投融",
    "客服", "售后", "售前", "销售", "市场", "运营", "采购",
    "开发", "测试", "运维", "架构", "算法", "安全", "数据",
    "研发", "设计", "产品", "项目", "分析",
    # 虚线/直线关系
    "直线经理", "虚线经理",
}

# 完整职位名称黑名单（整词匹配，用于4字职位如"客服主管"）
JOB_TITLE_FULL_BLACKLIST: set[str] = {
    "客服主管", "财务专员", "人事专员", "行政专员", "运营主管",
    "销售主管", "市场主管", "产品主管", "技术主管", "研发主管",
    "测试主管", "运维主管", "HR主管", "HRBP", "董秘",
    "HR专员", "HR主管",
    # 经理/上级类职位
    "直线经理", "虚线经理", "虚线上级", "虚线下级",
    "直线主管", "虚线主管",
}

# 1️⃣ AI 工具名
AI_TOOL_BLACKLIST: set[str] = {
    "文心", "文心一言",  # 百度文心
    "通义", "通义千问",   # 阿里通义
    "豆包",              # 字节豆包
    "智谱", "智谱清言",   # 智谱AI
    "天工", "天工AI",     # 昆仑万维天工
    "讯飞", "讯飞星火",   # 讯飞星火
    "Coze", "扣子",       # 字节Coze
    "秘塔", "秘塔AI",     # 秘塔AI
    "Kimi", "KimiChat",  # 月之暗面Kimi
    "夸克", "夸克AI",     # 阿里夸克
    "百小应", "万知",     # 百度/字节AI
    "跃问", "商量",       # 商汤AI
    "海螺", "海螺AI",     # 字节海螺
    "问小白", "问财",     # 通用AI工具
    "小可", "小爱",       # 小米/通用助手
    "灵犀", "灵犀AI",     # 联通灵犀
}

# 2️⃣ 常用词组（两个汉字但非姓名）
COMMON_WORD_PAIR_BLACKLIST: set[str] = {
    # 方位/数量词
    "大小", "多少", "高低", "长短", "远近", "快慢", "胖瘦", "贫富",
    "男女", "老少", "新陈", "新旧", "死活", "真假", "是非", "黑白",
    "明暗", "冷热", "干湿", "软硬", "粗细", "深浅", "早晚", "早晚",
    "早晚", "今明", "中英", "中韩", "中日", "中美",
    # 常见组合词
    "左右", "上下", "前后", "内外", "中西", "古今", "南北", "东西",
    "始终", "始终", "始终", "始终",
}

# 3️⃣ 地名/机构名（可能出现但非人名）
PLACE_INSTITUTION_BLACKLIST: set[str] = {
    # 城市名
    "北京", "上海", "深圳", "广州", "杭州", "成都", "武汉", "西安",
    "南京", "重庆", "苏州", "天津", "青岛", "长沙", "郑州", "东莞",
    "佛山", "宁波", "无锡", "济南", "合肥", "福州", "厦门", "沈阳",
    "大连", "哈尔滨", "长春", "南昌", "昆明", "贵阳", "南宁", "石家庄",
    # 省份
    "江苏", "浙江", "广东", "山东", "河南", "四川", "湖北", "湖南",
    "河北", "福建", "安徽", "陕西", "辽宁", "江西", "云南", "贵州",
    "广西", "山西", "吉林", "黑龙江", "甘肃", "海南", "内蒙古", "新疆",
    "宁夏", "青海", "西藏", "台湾", "香港", "澳门",
    # 知名公司/品牌（常见缩写）
    "腾讯", "阿里", "字节", "百度", "京东", "美团", "滴滴", "小米",
    "华为", "中兴", "联想", "海尔", "格力", "美的", "海尔", "比亚迪",
    "蔚来", "理想", "小鹏", "吉利", "长城", "长安", "奇瑞", "上汽",
    "一汽", "广汽", "北汽", "东风", "联通", "电信", "移动", "网通",
    "菜鸟", "蚂蚁", "京东", "苏宁", "国美", "唯品", "拼多多", "小红书",
}

# 4️⃣ 成语/固定词组（4字，易被姓名RE误匹配）
IDIOM_BLACKLIST: set[str] = {
    # 季节/方位
    "春夏秋冬", "东南西北", "东西南北", "上下左右", "前后左右",
    "春夏秋冬", "春夏秋冬", "春暖花开", "秋收冬藏",
    # 其他常见成语
    "千言万语", "千军万马", "千山万水", "千秋万代", "千真万确",
    "三心二意", "三言两语", "三长两短", "三番两次", "三头六臂",
    "五湖四海", "五颜六色", "五湖四海", "五湖四邦",
    "七上八下", "七零八落", "七情六欲",
    "九死一生", "九牛一毛", "九霄云外",
    "十全十美", "十万火急", "十有八九",
    "一言不发", "一路平安", "一路顺风", "一模一样", "一帆风顺",
    "成百上千", "成千上万", "人来人往", "大同小异", "大材小用",
    "天罗地网", "天南海北", "天长地久", "天花乱坠",
    "开天辟地", "惊天动地", "欢天喜地", "铺天盖地",
    "张牙舞爪", "张灯结彩", "张冠李戴",
    "东奔西走", "东张西望", "东拼西凑", "东倒西歪",
    "南腔北调", "南征北战", "南来北往",
    "北雁南飞",
    "左顾右盼", "左邻右舍", "左思右想",
    "上窜下跳", "上行下效", "上蹿下跳",
    "前因后果", "前赴后继", "前仰后合", "前仆后继",
    "后会有期", "后生可畏", "后来居上",
    "胡思乱想", "胡言乱语", "胡说八道",
    "想方设法", "想入非非",
    "能屈能伸", "能说会道",
    "说三道四", "说长道短", "说东道西",
}

# 合并所有黑名单
NON_NAME_BLACKLIST: set[str] = (
    AI_TOOL_BLACKLIST
    | COMMON_WORD_PAIR_BLACKLIST
    | PLACE_INSTITUTION_BLACKLIST
    | IDIOM_BLACKLIST
    | JOB_TITLE_TERM_BLACKLIST
    | JOB_TITLE_FULL_BLACKLIST
)

# DEPRECATED alias — kept for external callers that import AI_TOOL_BLACKLIST directly.
AI_TOOL_BLACKLIST_DEPRECATED = AI_TOOL_BLACKLIST


def _looks_like_chinese_name(text: str) -> bool:
    """检查是否像中文姓名（基于百家姓白名单，排除黑名单词组）。

    增强：也排除"百家姓+职位后缀"模式（如"张主管""王专员""李总监"），
    以及完整职位名（如"客服主管""财务专员"）。
    """
    if len(text) < 2 or len(text) > 4:
        return False
    # 黑名单整词优先排除（AI工具名/常用词/地名/成语/完整职位名）
    if text in NON_NAME_BLACKLIST:
        return False
    # 复姓/双姓（2字符）
    if text[:2] in SURNAME_SET:
        # 排除"复姓+职位后缀"（如"欧阳经理"→剩余2字"经理"命中黑名单）
        remaining = text[2:]
        if len(remaining) >= 2 and remaining in JOB_TITLE_TERM_BLACKLIST:
            return False
        return True
    # 单姓（1字符）：有效中文姓名=单姓+1字（如"张明"），3字="单姓+2字职位"
    if text[:1] in SURNAME_SET:
        remaining = text[1:]
        # 3字情况下检查剩余2字是否为职位（如"张主管"→剩余"主管"命中）
        if len(remaining) >= 2 and remaining in JOB_TITLE_TERM_BLACKLIST:
            return False
        return True
    return False


# Public alias — allows callers to import without leading underscore.
looks_like_chinese_name = _looks_like_chinese_name


SHORT_CHINESE_PERSON_RE = re.compile(r"^[一-龥]{2,5}$")


def looks_like_short_chinese_person_name(text: str) -> bool:
    """Stricter short-name fallback for weak person columns such as "对象"."""
    if not SHORT_CHINESE_PERSON_RE.match(text):
        return False
    if _looks_like_chinese_name(text):
        return True
    if len(text) == 5 and text[:2] in SURNAME_SET:
        remaining = text[2:]
        if text in NON_NAME_BLACKLIST or remaining in JOB_TITLE_TERM_BLACKLIST:
            return False
        return True
    return False


# ── 手机号/邮箱二次格式校验 ─────────────────────────────────────────
# 在强正则匹配后，作为辅助校验层进一步排除误报。
# 原则：只排除"明显不对"的情况，不排除合理的边界值。

# 常见虚假/测试手机号前缀（段号不存在或为测试号段）
SUSPICIOUS_PHONE_PREFIXES = (
    "000", "111", "222", "333", "444", "555", "666", "777", "888", "999",
    "123", "321", "6666", "8888",
)


def _phone_format_suspicious(text: str) -> bool:
    """手机号格式二次校验——返回 True 表示该号码'可疑但不强拒'。"""
    # 排除全相同数字（测试号）
    if len(set(text)) == 1:
        return True
    # 排除前3位为全序重复数字
    if text[:3] in SUSPICIOUS_PHONE_PREFIXES:
        return True
    return False


# 常见虚假/测试邮箱域名（仅作辅助参考，不硬拒）
REALISTIC_EMAIL_DOMAINS: frozenset[str] = frozenset({
    "qq.com", "163.com", "126.com", "sina.com", "hotmail.com",
    "gmail.com", "outlook.com", "foxmail.com", "139.com",
    "sohu.com", "tom.com", "yeah.net", "aliyun.com", "钉钉", "wechat",
})
SUSPICIOUS_EMAIL_KEYWORDS = {"test", "测试", "示例", "样例", "example", "fake", "dummy"}


def _email_format_suspicious(text: str) -> bool:
    """邮箱格式二次校验——返回 True 表示该邮箱'可疑但不强拒'。"""
    # 排除包含测试关键词的邮箱
    local_part = text.split("@")[0].lower()
    if any(kw in local_part for kw in SUSPICIOUS_EMAIL_KEYWORDS):
        return True
    return False


CHINESE_NAME_RE = re.compile(r"^[一-龥]{2,4}$")
# Matches department names like "技术部", "AI 数据部", "SMB 苏州 1 组", "产品研发中心", "业务线".
# Also supports hierarchical departments such as "产品中心-设计部" and "产品中心/设计部".
# - Allows spaces and numbers in department name (e.g. "苏州 1 组", "SMB 苏州 1 组")
# - Long patterns (事业部, 业务线, 小组) must come BEFORE short chars in the alternation
# - English prefix + space is allowed (e.g. "SMB ")
DEPARTMENT_RE = re.compile(
    r"^(?:[A-Za-z]{1,4}[ \t]?)?[一-龥 0-9]{1,25}(?:事业部|业务线|中心|小组|[部组处科室]|大区|区域)"
    r"(?:[-/／\\][一-龥 0-9]{1,25}(?:事业部|业务线|中心|小组|[部组处科室]|大区|区域))*$"
)
DETECTORS_BY_RE = [
    (ID_NUMBER_RE, EntityType.ID_NUMBER),
    (PHONE_RE, EntityType.PHONE),
    (EMAIL_RE, EntityType.EMAIL),
    (LICENSE_PLATE_RE, EntityType.LICENSE_PLATE),
    (EMPLOYEE_ID_RE, EntityType.EMPLOYEE_ID),
    (DEPARTMENT_RE, EntityType.DEPARTMENT),
    (CHINESE_NAME_RE, EntityType.EMPLOYEE),
]


def detect_cell_entity_type(
    value: object,
    column_type: EntityType | None = None,
    anonymize_department: bool = True,
    anonymize_region: bool = True,
    anonymize_salary: bool = True,
) -> EntityType | None:
    """
    Detect entity type from cell value.
    When column_type is EMPLOYEE_ID, also accepts pure-digit IDs (e.g. 001234, 1234567)
    to handle unmasked numeric employee numbers in ID columns.

    二次校验层：
    - EMPLOYEE 列（强规则推断）：用百家姓白名单兜底，排除"张主管"等岗位名
    - DEPARTMENT/REGION 列：按 anonymize_department/anonymize_region 决定是否脱敏
    - SALARY 列：按 anonymize_salary 决定是否脱敏
    - PHONE/EMAIL：正则匹配后再做格式校验，排除测试号/虚假邮箱
    """
    text = "" if value is None else str(value).strip()
    if not text:
        return None

    # Pure-digit employee ID: only detected in EMPLOYEE_ID column context.
    # 4–10 digit strings are too ambiguous in general (could be any number),
    # but in a 工号/员工编号 column they are almost certainly employee IDs.
    if column_type == EntityType.EMPLOYEE_ID and PURE_DIGIT_EMPLOYEE_ID_RE.match(text):
        return EntityType.EMPLOYEE_ID

    # 强规则 EMPLOYEE 列（列名推断）用百家姓白名单兜底校验
    # 排除"张主管""王专员""李总监"等"百家姓+职位后缀"以及"客服主管"等纯职位名
    if column_type == EntityType.EMPLOYEE and not _looks_like_chinese_name(text):
        return None

    # 可选脱敏：DEPARTMENT 列
    if column_type == EntityType.DEPARTMENT and not anonymize_department:
        return None

    # 可选脱敏：SALARY 列
    if column_type == EntityType.SALARY and not anonymize_salary:
        return None

    for pattern, entity_type in DETECTORS_BY_RE:
        if pattern.match(text):
            # CHINESE_NAME_RE 用百家姓白名单二次验证
            if entity_type == EntityType.EMPLOYEE and pattern == CHINESE_NAME_RE:
                if not _looks_like_chinese_name(text):
                    continue
            # PHONE/EMAIL 正则匹配后再做格式二次校验
            if entity_type == EntityType.PHONE and _phone_format_suspicious(text):
                continue
            if entity_type == EntityType.EMAIL and _email_format_suspicious(text):
                continue
            return entity_type
    return None
