from __future__ import annotations

import secrets

import pandas as pd
from pydantic import BaseModel, ConfigDict

from privacy_data_agent.detectors import (
    SalaryGroup,
    detect_column_entity_type,
    detect_high_confidence_cell_entity_type,
    detect_optional_column_entity_type,
    detect_weak_person_column,
    is_pass_through_column,
    looks_like_short_chinese_person_name,
)
from privacy_data_agent.models import ANON_TOKEN_PREFIX, EntityType, MappingEntry, MappingFile


class AnonymizeResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    dataframe: pd.DataFrame
    mapping: MappingFile


class AnonymizerState:
    def __init__(self, seed_mapping: MappingFile | None = None) -> None:
        self.used_tokens: set[str] = set()
        self.token_by_key: dict[tuple[EntityType, str], str] = {}
        self.entries: list[MappingEntry] = list(seed_mapping.entries) if seed_mapping else []
        if seed_mapping:
            for entry in seed_mapping.entries:
                self.token_by_key[(entry.entity_type, entry.original)] = entry.token
                self.used_tokens.add(entry.token)

    def token_for(self, entity_type: EntityType, original: str) -> str:
        cache_key = (entity_type, original)
        if cache_key not in self.token_by_key:
            token = _new_token(self.used_tokens)
            self.token_by_key[cache_key] = token
            self.entries.append(MappingEntry(entity_type=entity_type, original=original, token=token))
        return self.token_by_key[cache_key]

    def to_mapping_file(self) -> MappingFile:
        return MappingFile(entries=self.entries)


def anonymize_dataframe(
    df: pd.DataFrame,
    seed_mapping: MappingFile | None = None,
    anonymize_job_title: bool = False,
    anonymize_department: bool = True,
    anonymize_region: bool = True,
    keep_salary_groups: frozenset[SalaryGroup] = frozenset(),
) -> AnonymizeResult:
    state = AnonymizerState(seed_mapping=seed_mapping)
    output = df.copy().astype("object")
    for column in output.columns:
        column_name = str(column)
        if is_pass_through_column(
            column_name,
            anonymize_job_title=anonymize_job_title,
            anonymize_department=anonymize_department,
            anonymize_region=anonymize_region,
            keep_salary_groups=keep_salary_groups,
        ):
            continue
        column_type = detect_column_entity_type(column_name)
        if column_type is None and anonymize_job_title:
            column_type = detect_optional_column_entity_type(column_name)
        is_weak_person_column = column_type is None and detect_weak_person_column(column_name)
        for row_index, value in output[column].items():
            text = "" if pd.isna(value) else str(value).strip()
            if not text:
                continue
            # DEPARTMENT 列按可选参数过滤
            if column_type == EntityType.DEPARTMENT and not anonymize_department:
                continue
            entity_type = column_type or detect_high_confidence_cell_entity_type(text)
            if entity_type is None and is_weak_person_column and looks_like_short_chinese_person_name(text):
                entity_type = EntityType.EMPLOYEE
            if entity_type is None:
                continue
            output.at[row_index, column] = state.token_for(entity_type, text)

    return AnonymizeResult(dataframe=output, mapping=state.to_mapping_file())


def _new_token(used_tokens: set[str]) -> str:
    while True:
        token = f"{ANON_TOKEN_PREFIX}_{secrets.token_hex(8).upper()}"
        if token not in used_tokens:
            used_tokens.add(token)
            return token
