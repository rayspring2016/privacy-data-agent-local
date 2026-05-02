from __future__ import annotations

import secrets

import pandas as pd
from pydantic import BaseModel, ConfigDict

from privacy_data_agent.detectors import detect_cell_entity_type, detect_column_entity_type
from privacy_data_agent.models import ANON_TOKEN_PREFIX, EntityType, MappingEntry, MappingFile


class AnonymizeResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    dataframe: pd.DataFrame
    mapping: MappingFile


def anonymize_dataframe(
    df: pd.DataFrame,
    seed_mapping: MappingFile | None = None,
) -> AnonymizeResult:
    used_tokens: set[str] = set()
    # Pre-populate from seed so existing entities reuse their tokens within the same batch
    token_by_key: dict[tuple[EntityType, str], str] = {}
    if seed_mapping:
        for entry in seed_mapping.entries:
            token_by_key[(entry.entity_type, entry.original)] = entry.token
            used_tokens.add(entry.token)

    output = df.copy().astype("object")
    entries: list[MappingEntry] = list(seed_mapping.entries) if seed_mapping else []
    seen_in_seed: set[tuple[EntityType, str]] = set(token_by_key)

    for column in output.columns:
        column_type = detect_column_entity_type(str(column))
        for row_index, value in output[column].items():
            text = "" if pd.isna(value) else str(value).strip()
            if not text:
                continue
            entity_type = column_type or detect_cell_entity_type(text)
            if entity_type is None:
                continue
            cache_key = (entity_type, text)
            if cache_key not in token_by_key:
                token = _new_token(used_tokens)
                token_by_key[cache_key] = token
                entries.append(MappingEntry(entity_type=entity_type, original=text, token=token))
            output.at[row_index, column] = token_by_key[cache_key]

    return AnonymizeResult(dataframe=output, mapping=MappingFile(entries=entries))


def _new_token(used_tokens: set[str]) -> str:
    while True:
        token = f"{ANON_TOKEN_PREFIX}_{secrets.token_hex(8).upper()}"
        if token not in used_tokens:
            used_tokens.add(token)
            return token
