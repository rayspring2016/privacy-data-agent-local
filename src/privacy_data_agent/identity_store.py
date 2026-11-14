from __future__ import annotations

import os
import tempfile
from pathlib import Path

from privacy_data_agent.mapping_store import load_local_mapping
from privacy_data_agent.models import MappingFile


def identity_mapping_path() -> Path:
    return Path.home() / ".privacy-data-agent" / "identities" / "mapping.local.json"


def merge_identity_mappings(base: MappingFile, incoming: MappingFile) -> MappingFile:
    entries = {}
    keys_by_token = {}
    tokens_by_key = {}
    for entry in [*base.entries, *incoming.entries]:
        original_key = entry.original.casefold() if entry.entity_type.value == "email" else entry.original
        key = (entry.entity_type, entry.identity_key or original_key)
        entry_key = (entry.entity_type, entry.original, entry.identity_key)
        if key in tokens_by_key and tokens_by_key[key] != entry.token:
            raise ValueError("编号冲突：同一对象已有不同编号，请选择一份历史映射作为基准。")
        if entry.token in keys_by_token and keys_by_token[entry.token] != key:
            raise ValueError("编号冲突：不同对象使用了同一编号，请核对历史映射。")
        entries[entry_key] = entry
        keys_by_token[entry.token] = key
        tokens_by_key[key] = entry.token
    people = {}
    for person in [*base.people, *incoming.people]:
        if person.key not in people:
            people[person.key] = person.model_copy(deep=True)
        else:
            previous = people[person.key]
            if previous.employee_id and person.employee_id and previous.employee_id != person.employee_id:
                raise ValueError("待核验：同一人员编号关联不同工号。")
            previous.employee_id = previous.employee_id or person.employee_id
            previous.id_numbers = list(dict.fromkeys([*previous.id_numbers, *person.id_numbers]))
            previous.emails = list(dict.fromkeys([*previous.emails, *person.emails]))
            previous.aliases = list(dict.fromkeys([*previous.aliases, *person.aliases]))
    from privacy_data_agent.person_identity import EmployeeIdentityResolver

    EmployeeIdentityResolver(list(people.values()))
    return MappingFile(entries=list(entries.values()), people=list(people.values()))


class UnifiedIdentityStore:
    """跨月份、跨项目共用的本地映射；处理期间独占，保存时原子替换。"""

    def __init__(self, seed_mapping: MappingFile | None = None) -> None:
        self.path = identity_mapping_path()
        self.lock_path = self.path.with_suffix(".lock")
        self.seed_mapping = seed_mapping or MappingFile()
        self.mapping = MappingFile()

    def __enter__(self) -> UnifiedIdentityStore:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            raise ValueError("统一编号库正在使用，请等待其他脱敏任务完成后重试。") from None
        os.close(fd)
        try:
            try:
                stored = load_local_mapping(self.path) if self.path.exists() else MappingFile()
            except (ValueError, OSError, KeyError):
                raise ValueError("统一编号库无法读取，请保留原文件并修复；程序不会自动重建编号。") from None
            self.mapping = merge_identity_mappings(stored, self.seed_mapping)
        except BaseException:
            self.lock_path.unlink(missing_ok=True)
            raise
        return self

    def save(self, mapping: MappingFile) -> None:
        merged = merge_identity_mappings(self.mapping, mapping)
        merged.entries = [entry for entry in merged.entries if not (entry.identity_key or "").startswith("unverified:")
                          and not entry.token.startswith("PDA_REVIEW_")]
        fd, name = tempfile.mkstemp(prefix=".mapping-", suffix=".tmp", dir=self.path.parent)
        temp_path = Path(name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(merged.model_dump_json(indent=2))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, self.path)
            self.mapping = merged
        finally:
            temp_path.unlink(missing_ok=True)

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.lock_path.unlink(missing_ok=True)
