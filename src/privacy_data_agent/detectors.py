from __future__ import annotations

import re

from privacy_data_agent.models import EntityType

ID_NUMBER_RE = re.compile(r"^\d{17}[\dXx]$")
PHONE_RE = re.compile(r"^(?:\+?86[- ]?)?1[3-9]\d{9}$")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

COLUMN_HINTS: tuple[tuple[EntityType, tuple[str, ...]], ...] = (
    (EntityType.EMPLOYEE, ("姓名", "员工", "name", "employee")),
    (EntityType.ID_NUMBER, ("身份证", "证件", "id_number", "national_id")),
    (EntityType.DEPARTMENT, ("部门", "组织", "department", "team")),
    (EntityType.CUSTOMER, ("客户", "client", "customer", "company")),
    (EntityType.PHONE, ("手机号", "电话", "phone", "mobile")),
    (EntityType.EMAIL, ("邮箱", "email", "e-mail")),
)


def detect_column_entity_type(column_name: str) -> EntityType | None:
    normalized = column_name.strip().lower()
    for entity_type, hints in COLUMN_HINTS:
        if any(hint.lower() in normalized for hint in hints):
            return entity_type
    return None


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
    return None
