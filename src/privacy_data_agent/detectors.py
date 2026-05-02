from __future__ import annotations

import re

from privacy_data_agent.models import EntityType

ID_NUMBER_RE = re.compile(r"^\d{17}[\dXx]$")
PHONE_RE = re.compile(r"^(?:\+?86[- ]?)?1[3-9]\d{9}$")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
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
    if EMPLOYEE_ID_RE.match(text):
        return EntityType.EMPLOYEE_ID
    return None
