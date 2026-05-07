from __future__ import annotations

import re

from privacy_data_agent.models import EntityType

ID_NUMBER_RE = re.compile(r"^\d{17}[\dXx]$")
PHONE_RE = re.compile(r"^(?:\+?86[- ]?)?1[3-9]\d{9}$")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
LICENSE_PLATE_RE = re.compile(r"^[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉贵粤青藏川宁琼使领][A-Z][A-Z0-9]{5}$")
# Employee / work number with letter prefix (e.g. EMP0012, A12345).
# Pure-digit IDs (e.g. 001234) are too ambiguous without column context; use column hints instead.
EMPLOYEE_ID_RE = re.compile(r"^[A-Za-z]{1,3}\d{4,10}$")
NON_PERSON_REN_COLUMNS = ("人数", "人均", "人次", "人工", "人效", "人天")

COLUMN_HINTS: tuple[tuple[EntityType, tuple[str, ...]], ...] = (
    (
        EntityType.EMPLOYEE,
        (
            "姓名",
            "员工",
            "人员",
            "负责人",
            "联系人",
            "对接人",
            "销售负责人",
            "客户经理",
            "顾问",
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
            "团队",
            "事业部",
            "大区",
            "区域",
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
    (EntityType.LICENSE_PLATE, ("车牌", "车牌号", "车牌号码", "license_plate", "plate", "car_plate", "vehicle_plate")),
)


def detect_column_entity_type(column_name: str) -> EntityType | None:
    normalized = column_name.strip().lower()
    if _looks_like_person_column(normalized):
        return EntityType.EMPLOYEE
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
# 单姓 + 常见复姓 + 双姓组合（父母姓氏合并）
SURNAME_SET: set[str] = {
    # Top 100 单姓
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
    # 复姓
    "欧阳", "司马", "上官", "诸葛", "慕容", "令狐", "公孙", "拓跋",
    "宇文", "呼延", "赫连", "澹台", "长孙", "尉迟", "皇甫", "仲孙",
    # 双姓组合（父母姓氏合并，如陈杨、张李）
    "陈杨", "张李", "刘王", "王李", "李王", "陈李", "张王", "杨李",
    "刘陈", "王陈", "杨陈", "李张", "王张", "陈张", "刘李", "王刘",
}

# AI 工具黑名单（看起来像姓名但实际是工具名的）
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
}


def _looks_like_chinese_name(text: str) -> bool:
    """检查是否像中文姓名（基于百家姓白名单，排除 AI 工具名）"""
    if len(text) < 2 or len(text) > 4:
        return False
    # AI 工具黑名单优先排除
    if text in AI_TOOL_BLACKLIST:
        return False
    # 复姓/双姓优先（2字符）
    if text[:2] in SURNAME_SET:
        return True
    # 单姓（1字符）
    if text[:1] in SURNAME_SET:
        return True
    return False


CHINESE_NAME_RE = re.compile(r"^[一-龥]{2,4}$")
# Matches department names like "技术部", "AI 数据部", "SMB 苏州 1 组", "产品研发中心", "业务线".
# - Allows spaces and numbers in department name (e.g. "苏州 1 组", "SMB 苏州 1 组")
# - Long patterns (事业部, 业务线, 小组) must come BEFORE short chars in the alternation
# - English prefix + space is allowed (e.g. "SMB ")
DEPARTMENT_RE = re.compile(
    r"^(?:[A-Za-z]{1,4}[ \t]?)?[一-龥 0-9]{1,25}(?:事业部|业务线|中心|小组|[部组处科室]|大区|区域)$"
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


def detect_cell_entity_type(value: object) -> EntityType | None:
    text = "" if value is None else str(value).strip()
    if not text:
        return None
    for pattern, entity_type in DETECTORS_BY_RE:
        if pattern.match(text):
            # CHINESE_NAME_RE 用百家姓白名单二次验证
            if entity_type == EntityType.EMPLOYEE and pattern == CHINESE_NAME_RE:
                if not _looks_like_chinese_name(text):
                    continue
            return entity_type
    return None
