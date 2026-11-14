from __future__ import annotations

import secrets
import re

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from privacy_data_agent.detectors import (
    SalaryGroup,
    detect_column_entity_type,
    detect_high_confidence_cell_entity_type,
    detect_optional_column_entity_type,
    detect_weak_person_column,
    is_pass_through_column,
    looks_like_short_chinese_person_name,
    preserve_analysis_number,
)
from privacy_data_agent.models import ANON_TOKEN_PREFIX, EntityType, MappingEntry, MappingFile
from privacy_data_agent.person_identity import EmployeeIdentityResolver, IdentityReviewError, is_identity_placeholder


class AnonymizeResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    dataframe: pd.DataFrame
    mapping: MappingFile
    review_items: list[dict[str, str]] = Field(default_factory=list)


class AnonymizerState:
    def __init__(self, seed_mapping: MappingFile | None = None, require_unique_people: bool = False, allow_unverified_people: bool = False) -> None:
        self.used_tokens: set[str] = set()
        self.token_by_key: dict[tuple[EntityType, str], str] = {}
        self.entries: list[MappingEntry] = list(seed_mapping.entries) if seed_mapping else []
        self.entry_keys = {(entry.entity_type, entry.original, entry.identity_key) for entry in self.entries}
        self.current_entry_keys = set()
        self.people = [person.model_copy(deep=True) for person in seed_mapping.people] if seed_mapping else []
        self.require_unique_people = require_unique_people or bool(self.people)
        self.person_resolver = EmployeeIdentityResolver(self.people, allow_unverified_people=allow_unverified_people)
        self.review_items = []
        if seed_mapping:
            for entry in seed_mapping.entries:
                original_key = entry.original.casefold() if entry.entity_type == EntityType.EMAIL else entry.original
                self.token_by_key[(entry.entity_type, entry.identity_key or original_key)] = entry.token
                self.used_tokens.add(entry.token)

    def token_for(self, entity_type: EntityType, original: str, identity_key: str | None = None) -> str:
        if is_identity_placeholder(original):
            return original
        if (self.require_unique_people and entity_type == EntityType.EMPLOYEE
                and identity_key is None and original not in {"合计", "小计", "总计"}):
            raise IdentityReviewError("待核验：姓名字段尚未建立唯一身份，请核对工号、邮箱及姓名列名。")
        original_key = original.casefold() if entity_type == EntityType.EMAIL else original
        cache_key = (entity_type, identity_key or original_key)
        if cache_key not in self.token_by_key:
            token = _new_token(self.used_tokens, review=bool(identity_key and identity_key.startswith("unverified:")))
            self.token_by_key[cache_key] = token
        entry_key = (entity_type, original, identity_key)
        self.current_entry_keys.add(entry_key)
        if entry_key not in self.entry_keys:
            self.entries.append(MappingEntry(entity_type=entity_type, original=original,
                                             token=self.token_by_key[cache_key], identity_key=identity_key))
            self.entry_keys.add(entry_key)
            if identity_key in self.person_resolver.review_items:
                self.review_items.append({**self.person_resolver.review_items[identity_key],
                                          "token": self.token_by_key[cache_key], "status": "needs_review"})
        return self.token_by_key[cache_key]

    def to_mapping_file(self) -> MappingFile:
        return MappingFile(entries=self.entries, people=self.people)


def anonymize_dataframe(
    df: pd.DataFrame,
    seed_mapping: MappingFile | None = None,
    anonymize_job_title: bool = False,
    anonymize_department: bool = True,
    anonymize_region: bool = True,
    anonymize_salary: bool = True,
    keep_salary_groups: frozenset[SalaryGroup] = frozenset(),
    require_unique_people: bool = False,
    allow_unverified_people: bool = False,
    preserve_calculations: bool = False,
) -> AnonymizeResult:
    if preserve_calculations:
        anonymize_salary = False
    state = AnonymizerState(seed_mapping=seed_mapping, require_unique_people=require_unique_people, allow_unverified_people=allow_unverified_people)
    output = df.copy().astype("object")
    person_keys = {}
    if state.require_unique_people:
        rows = [(index, [None if preserve_calculations and preserve_analysis_number(value, str(df.columns[i])) else value
                         for i, value in enumerate(row.tolist())]) for index, row in df.iterrows()]
        state.person_resolver.register(list(df.columns), rows, defer_email_only=True)
        state.person_resolver.register(list(df.columns), rows)
        person_keys = state.person_resolver.keys(list(df.columns), rows)
    for column_index, column in enumerate(output.columns):
        column_name = str(column)
        if is_pass_through_column(
            column_name,
            anonymize_job_title=anonymize_job_title,
            anonymize_department=anonymize_department,
            anonymize_region=anonymize_region,
            anonymize_salary=anonymize_salary,
            keep_salary_groups=keep_salary_groups,
        ):
            continue
        column_type = detect_column_entity_type(column_name)
        if column_type is None and anonymize_job_title:
            column_type = detect_optional_column_entity_type(column_name)
        is_weak_person_column = column_type is None and detect_weak_person_column(column_name)
        for row_index, value in output[column].items():
            if preserve_calculations and preserve_analysis_number(value, column_name):
                continue
            text = "" if pd.isna(value) else str(value).strip()
            if not text:
                continue
            # DEPARTMENT 列按可选参数过滤
            if column_type == EntityType.DEPARTMENT and not anonymize_department:
                continue
            # SALARY 列按可选参数过滤
            if column_type == EntityType.SALARY and not anonymize_salary:
                continue
            if text.lower() == column_name.strip().lower() and column_type in {
                EntityType.EMPLOYEE, EntityType.EMPLOYEE_ID, EntityType.EMAIL,
            }:
                continue
            segments = [part.strip() for part in re.split(r"[、，；,;/|]+", text) if part.strip()]
            has_segment_keys = any((row_index, column_index, i) in person_keys for i in range(len(segments)))
            entity_type = (EntityType.EMPLOYEE if (row_index, column_index) in person_keys or has_segment_keys
                           else column_type or detect_high_confidence_cell_entity_type(text))
            if entity_type is None and is_weak_person_column and looks_like_short_chinese_person_name(text):
                entity_type = EntityType.EMPLOYEE
            if entity_type is None:
                continue
            if has_segment_keys:
                masked = text
                for i, segment in enumerate(segments):
                    token = state.token_for(EntityType.EMPLOYEE, segment,
                                            identity_key=person_keys.get((row_index, column_index, i)))
                    masked = masked.replace(segment, token, 1)
                output.at[row_index, column] = masked
                continue
            identity_key = person_keys.get((row_index, column_index)) if entity_type == EntityType.EMPLOYEE else None
            output.at[row_index, column] = state.token_for(entity_type, text, identity_key=identity_key)

    return AnonymizeResult(dataframe=output, mapping=state.to_mapping_file(), review_items=state.review_items)


def _new_token(used_tokens: set[str], review: bool = False) -> str:
    while True:
        prefix = f"{ANON_TOKEN_PREFIX}_REVIEW" if review else ANON_TOKEN_PREFIX
        token = f"{prefix}_{secrets.token_hex(8).upper()}"
        if token not in used_tokens:
            used_tokens.add(token)
            return token
