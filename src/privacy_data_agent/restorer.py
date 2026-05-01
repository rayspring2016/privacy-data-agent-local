from __future__ import annotations

from privacy_data_agent.models import MappingFile


def restore_report(report: str, mapping: MappingFile) -> str:
    restored = report
    for entry in sorted(mapping.entries, key=lambda item: len(item.token), reverse=True):
        restored = restored.replace(entry.token, entry.original)
    return restored
