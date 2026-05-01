from __future__ import annotations

from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from privacy_data_agent.models import MappingFile


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
