from __future__ import annotations

from collections import defaultdict

import pandas as pd
from pydantic import BaseModel, ConfigDict

from privacy_data_agent.detectors import detect_cell_entity_type, detect_column_entity_type
from privacy_data_agent.models import EntityType, MappingEntry, MappingFile, TOKEN_PREFIX


class AnonymizeResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    dataframe: pd.DataFrame
    mapping: MappingFile


def anonymize_dataframe(df: pd.DataFrame) -> AnonymizeResult:
    output = df.copy().astype("object")
    counters: dict[EntityType, int] = defaultdict(int)
    token_by_key: dict[tuple[EntityType, str], str] = {}
    entries: list[MappingEntry] = []

    for column in output.columns:
        column_type = detect_column_entity_type(str(column))
        for row_index, value in output[column].items():
            text = "" if pd.isna(value) else str(value).strip()
            if not text:
                continue
            entity_type = column_type or detect_cell_entity_type(text)
            if entity_type is None:
                continue
            key = (entity_type, text)
            if key not in token_by_key:
                counters[entity_type] += 1
                token = f"{TOKEN_PREFIX[entity_type]}_{counters[entity_type]:04d}"
                token_by_key[key] = token
                entries.append(MappingEntry(entity_type=entity_type, original=text, token=token))
            output.at[row_index, column] = token_by_key[key]

    return AnonymizeResult(dataframe=output, mapping=MappingFile(entries=entries))
