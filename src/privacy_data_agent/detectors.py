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
            "company",
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
        if any(hint.lower() in normalized for hint in hints):
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


def detect_cell_entity_type(value: object) -> EntityType | None:
    text = "" if value is None else str(value).strip()
    if not text:
        return None
    if ID_NUMBER_RE.match(text):
        return EntityType.ID_NUMBER
    if PHONE_RE.match(text):
        return EntityType.PHONE
    if EMAIL_RE.match(text):
        return EntityType.EMAIL
    if LICENSE_PLATE_RE.match(text):
        return EntityType.LICENSE_PLATE
    if EMPLOYEE_ID_RE.match(text):
        return EntityType.EMPLOYEE_ID
    return None
