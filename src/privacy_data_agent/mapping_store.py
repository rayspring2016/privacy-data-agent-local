from __future__ import annotations

from pathlib import Path

import pandas as pd
from cryptography.fernet import Fernet, InvalidToken

from privacy_data_agent.models import EntityType, MappingEntry, MappingFile


def save_mapping_file(mapping: MappingFile, path: Path, key: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = mapping.model_dump_json().encode("utf-8")
    encrypted = Fernet(key.encode("utf-8")).encrypt(payload)
    path.write_bytes(encrypted)


def load_mapping_file(path: Path, key: str) -> MappingFile:
    try:
        decrypted = Fernet(key.encode("utf-8")).decrypt(path.read_bytes())
    except InvalidToken as exc:
        raise ValueError("Mapping file cannot be decrypted with PRIVACY_AGENT_KEY") from exc
    return MappingFile.model_validate_json(decrypted.decode("utf-8"))


def save_plain_mapping_file(mapping: MappingFile, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(mapping.model_dump_json(indent=2), encoding="utf-8")


def load_plain_mapping_file(path: Path) -> MappingFile:
    return MappingFile.model_validate_json(path.read_text(encoding="utf-8"))


def save_mapping_table(mapping: MappingFile, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {"entity_type": entry.entity_type.value, "token": entry.token, "original": entry.original}
        for entry in mapping.entries
    ]
    pd.DataFrame(rows, columns=["entity_type", "token", "original"]).to_csv(path, index=False)


def load_mapping_table(path: Path) -> MappingFile:
    df = pd.read_csv(path, dtype=str).fillna("")
    entries = [
        MappingEntry(
            entity_type=EntityType(row["entity_type"]),
            token=row["token"],
            original=row["original"],
        )
        for row in df.to_dict(orient="records")
    ]
    return MappingFile(entries=entries)


def load_local_mapping(path: Path) -> MappingFile:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return load_mapping_table(path)
    if suffix == ".json":
        return load_plain_mapping_file(path)
    raise ValueError("Local restore supports .json mapping files or .csv mapping tables.")
