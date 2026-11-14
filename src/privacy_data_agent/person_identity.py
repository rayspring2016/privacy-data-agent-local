from __future__ import annotations

import re
import hashlib
import json
from collections.abc import Callable
from uuid import uuid4

import pandas as pd
from openpyxl.utils.cell import get_column_letter

from privacy_data_agent.detectors import EMPLOYEE_EMAIL_HEADERS, EMPLOYEE_ID_HEADERS, ID_NUMBER_RE, detect_column_entity_type, is_pass_through_column, looks_like_short_chinese_person_name
from privacy_data_agent.models import EmployeeIdentity, EntityType


PRIMARY_NAME_HEADERS = frozenset({
    "姓名", "员工姓名", "人员姓名", "销售姓名", "销售人员姓名", "employee_name", "name", "员工", "销售",
})


class IdentityReviewError(ValueError):
    pass


def is_identity_placeholder(value) -> bool:
    return str(value).strip() in {"", "/", "-", "--", "—", "无", "(空白)", "（空白）", "合计", "小计", "总计"}


def _text(value) -> str:
    if value is None or pd.isna(value) or is_identity_placeholder(value):
        return ""
    return str(value).strip()


class EmployeeIdentityResolver:
    """工号/邮箱建基准，姓名及部门仅在基准唯一匹配时关联。"""

    def __init__(self, people: list[EmployeeIdentity], allow_unverified_people: bool = False) -> None:
        self.people = people
        self.allow_unverified_people = allow_unverified_people
        self.review_items = {}
        self.observed_names = set()
        self.by_id = {}
        self.by_email = {}
        self.by_number = {}
        for person in people:
            if person.employee_id:
                if person.employee_id in self.by_id:
                    raise IdentityReviewError("待核验：人员基准中存在重复工号。")
                self.by_id[person.employee_id] = person
            for number in person.id_numbers:
                if number in self.by_number and self.by_number[number].key != person.key:
                    raise IdentityReviewError("待核验：同一证件号关联不同人员。")
                self.by_number[number] = person
            for email in person.emails:
                normalized = email.casefold()
                if normalized in self.by_email and self.by_email[normalized].key != person.key:
                    raise IdentityReviewError("待核验：同一邮箱关联了不同员工。")
                self.by_email[normalized] = person

    def _columns(self, headers):
        types = [detect_column_entity_type(str(header)) for header in headers]
        names = [i for i, kind in enumerate(types) if kind == EntityType.EMPLOYEE]
        primary = [i for i in names if str(headers[i]).strip().lower() in PRIMARY_NAME_HEADERS]
        if not primary:
            ids, _ = self._identity_columns(headers)
            primary = [i for i in names if i - 1 in ids and (
                "归属" in str(headers[i]) or str(headers[i]).strip().lower() == "leader"
            )]
        return types, names, primary

    @staticmethod
    def _is_header_row(values, primary, ids, emails):
        return (any(_text(values[i]).lower() in EMPLOYEE_ID_HEADERS for i in ids)
                or any(_text(values[i]).lower() in EMPLOYEE_EMAIL_HEADERS for i in emails)
                or any(_text(values[i]).lower() in PRIMARY_NAME_HEADERS for i in primary))

    def _identity_columns(self, headers):
        normalized = [str(header).strip().lower() for header in headers]
        return (
            [i for i, header in enumerate(normalized) if header in EMPLOYEE_ID_HEADERS],
            [i for i, header in enumerate(normalized) if header in EMPLOYEE_EMAIL_HEADERS],
        )

    def _role_contacts(self, headers):
        def normalize(value):
            return re.sub(r"[\s_（）()：:]", "", str(value).lower())
        pairs = []
        for column, header in enumerate(headers):
            if detect_column_entity_type(str(header)) != EntityType.EMAIL:
                continue
            label = normalize(header)
            for suffix in ("电子邮件", "邮箱", "e-mail", "email"):
                if label.endswith(suffix):
                    role = label[:-len(suffix)]
                    break
            else:
                continue
            if not role or any(term in role for term in ("客户联系人", "客户姓名", "联系人")) or str(header).strip().lower() in EMPLOYEE_EMAIL_HEADERS:
                continue
            matching = [i for i, name in enumerate(headers)
                        if normalize(name).removesuffix("姓名") == role
                        and detect_column_entity_type(str(name)) == EntityType.EMPLOYEE]
            if len(matching) == 1:
                pairs.append((matching[0], column))
        return pairs

    @staticmethod
    def _location(row_index, columns, location):
        if location is not None:
            return location(row_index, columns)
        letters = "、".join(get_column_letter(i + 1) for i in columns)
        return f"第 {row_index + 1} 条数据（{letters} 列）"

    def register(
        self, headers, rows, defer_email_only: bool = False,
        location: Callable[[int, list[int]], str] | None = None,
    ) -> None:
        types, names, primary = self._columns(headers)
        id_columns, email_columns = self._identity_columns(headers)
        dept_columns = [i for i, kind in enumerate(types) if kind == EntityType.DEPARTMENT]
        number_columns = [i for i, kind in enumerate(types) if kind == EntityType.ID_NUMBER]
        if not names and not id_columns:
            return
        role_contacts = self._role_contacts(headers)
        if role_contacts and not defer_email_only:
            for name_column, email_column in role_contacts:
                role_rows = [(index, [values[name_column], values[email_column]])
                             for index, values in rows if _text(values[email_column])]
                role_location = None
                if location:
                    def role_location(index, columns, name_column=name_column, email_column=email_column):
                        original = [name_column, email_column]
                        return location(index, [original[i] for i in columns])
                self.register(["姓名", "邮箱"], role_rows, location=role_location)
        for row_index, values in rows:
            if self._is_header_row(values, primary, id_columns, email_columns):
                continue
            if self.allow_unverified_people:
                for column in names:
                    if any(term in str(headers[column]) for term in ("客户联系人", "客户姓名", "联系人")):
                        continue
                    self.observed_names.update(part.strip() for part in re.split(r"[、，；,;/|]+", _text(values[column]))
                                               if looks_like_short_chinese_person_name(part.strip()))
            ids = {i: _text(values[i]) for i in id_columns if _text(values[i])}
            emails = {i: _text(values[i]).casefold() for i in email_columns if _text(values[i])}
            numbers = {i: _text(values[i]).upper() for i in number_columns if ID_NUMBER_RE.fullmatch(_text(values[i]).upper())}
            if (not ids and not emails and not numbers) or (defer_email_only and not ids):
                continue
            name_values = {i: _text(values[i]) for i in primary if _text(values[i])}
            for candidates, field in ((ids, "员工工号"), (emails, "员工邮箱"), (numbers, "证件号"), (name_values, "主姓名")):
                if len(set(candidates.values())) > 1:
                    position = self._location(row_index, list(candidates), location)
                    raise IdentityReviewError(f"待核验：{position}的{field}不一致，请核对这些字段。")
            employee_id = next(iter(ids.values()), "")
            email = next(iter(emails.values()), "")
            number = next(iter(numbers.values()), "")
            by_id = self.by_id.get(employee_id)
            by_email = self.by_email.get(email)
            by_number = self.by_number.get(number)
            anchors = {p.key for p in (by_id, by_email, by_number) if p is not None}
            if len(anchors) > 1:
                raise IdentityReviewError("待核验：工号和邮箱指向不同员工，禁止自动合并。")
            person = by_id or by_email or by_number
            if person is not None and employee_id and person.employee_id and person.employee_id != employee_id:
                raise IdentityReviewError("待核验：同一邮箱对应不同工号，禁止自动合并。")
            if person is None:
                person = EmployeeIdentity(key=uuid4().hex, employee_id=employee_id)
                self.people.append(person)
            if employee_id:
                person.employee_id = employee_id
                self.by_id[employee_id] = person
            if number and number not in person.id_numbers:
                person.id_numbers.append(number)
                self.by_number[number] = person
            if email and email not in person.emails:
                person.emails.append(email)
                self.by_email[email] = person
            if name_values:
                name = next(iter(name_values.values()))
                if re.search(r"[、，；,;/|]", name):
                    raise IdentityReviewError("待核验：单元格包含多个姓名，无法与单一工号关联。")
                departments = {_text(values[i]) for i in dept_columns} - {""}
                for department in departments or {""}:
                    alias = (name, department)
                    if name and alias not in person.aliases:
                        person.aliases.append(alias)

    def keys(
        self, headers, rows, location: Callable[[int, list[int]], str] | None = None,
    ) -> dict:
        types, names, primary = self._columns(headers)
        id_columns, email_columns = self._identity_columns(headers)
        dept_columns = [i for i, kind in enumerate(types) if kind == EntityType.DEPARTMENT]
        number_columns = [i for i, kind in enumerate(types) if kind == EntityType.ID_NUMBER]
        name_keys = {}
        department_keys = {}
        for person in self.people:
            for name, department in person.aliases:
                name_keys.setdefault(name, set()).add(person.key)
                department_keys.setdefault((name, department), set()).add(person.key)
        role_emails = dict(self._role_contacts(headers))
        custom_columns = [i for i, kind in enumerate(types)
                          if kind is None and not is_pass_through_column(str(headers[i]))]
        result = {}
        for row_index, values in rows:
            if self._is_header_row(values, primary, id_columns, email_columns):
                continue
            ids = {_text(values[i]) for i in id_columns} - {""}
            emails = {_text(values[i]).casefold() for i in email_columns} - {""}
            direct = next((self.by_id[value] for value in ids if value in self.by_id), None)
            direct = direct or next((self.by_email[value] for value in emails if value in self.by_email), None)
            direct = direct or next((self.by_number[_text(values[i]).upper()] for i in number_columns
                                     if _text(values[i]).upper() in self.by_number), None)
            departments = {_text(values[i]) for i in dept_columns} - {""}
            known_columns = [i for i in custom_columns if _text(values[i]) in name_keys or _text(values[i]) in self.observed_names]
            for column in [*names, *known_columns]:
                name = _text(values[column])
                if not name or name in {"合计", "小计", "总计"}:
                    continue
                label = str(headers[column])
                if name.lower() == label.strip().lower():
                    continue
                if any(term in label for term in ("客户联系人", "客户姓名", "联系人")):
                    anchors = [
                        (_text(values[i]), str(headers[i])) for i, kind in enumerate(types)
                        if kind == EntityType.CUSTOMER and _text(values[i])
                    ]
                    if anchors:
                        payload = json.dumps([label, name, anchors], ensure_ascii=False)
                        result[row_index, column] = "contact:" + hashlib.sha256(payload.encode()).hexdigest()
                        continue
                segments = [part.strip() for part in re.split(r"[、，；,;/|]+", name) if part.strip()]
                if len(segments) > 1:
                    for segment_index, segment in enumerate(segments):
                        if is_identity_placeholder(segment):
                            continue
                        segment_values = [None] * len(values)
                        segment_values[column] = segment
                        if column in primary:
                            for i in dept_columns:
                                segment_values[i] = values[i]
                        keys = self.keys(headers, [(row_index, segment_values)], location)
                        if (row_index, column) not in keys:
                            position = self._location(row_index, [column], location)
                            raise IdentityReviewError(f"待核验：{position}的多人名单包含非姓名项，请核对姓名列。")
                        result[row_index, column, segment_index] = keys[row_index, column]
                    continue
                if column in primary and direct is not None:
                    result[row_index, column] = direct.key
                    continue

                if "系统" in name:
                    payload = json.dumps([label, name], ensure_ascii=False)
                    result[row_index, column] = "account:" + hashlib.sha256(payload.encode()).hexdigest()
                    continue
                if column in role_emails:
                    contact = self.by_email.get(_text(values[role_emails[column]]).casefold())
                    if contact is not None:
                        result[row_index, column] = contact.key
                        continue
                by_name = name_keys.get(name, set())
                candidates = by_name.copy()
                department_matches = [
                    department_keys.get((name, department), set()) for department in departments
                ] if column in primary else []
                if department_matches:
                    known_matches = [match for match in department_matches if match]
                    if not known_matches:
                        candidates.clear()
                    for match in known_matches:
                        candidates.intersection_update(match)
                if len(candidates) == 1:
                    result[row_index, column] = next(iter(candidates))
                    continue

                position = self._location(row_index, [column], location)
                if not by_name:
                    reason = "姓名未在人员基准中登记。请在人员基准中补充姓名及工号，或核对姓名列。"
                elif not candidates:
                    reason = f"部门信息与已登记的候选不匹配（按姓名找到 {len(by_name)} 人）。请核对部门或补充工号、已关联邮箱。"
                else:
                    reason = f"有 {len(candidates)} 个同名候选。请补充员工工号、已关联邮箱，或与人员基准一致的部门。"
                if self.allow_unverified_people:
                    key = "unverified:" + uuid4().hex
                    self.review_items[key] = {"location": position, "reason": reason}
                    result[row_index, column] = key
                    continue
                raise IdentityReviewError(f"待核验：{position}，{reason}")
        return result
