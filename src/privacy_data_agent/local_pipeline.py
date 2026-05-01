from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel

from privacy_data_agent.anonymizer import anonymize_dataframe
from privacy_data_agent.mapping_store import load_local_mapping, save_mapping_table, save_plain_mapping_file
from privacy_data_agent.pipeline import read_input_table
from privacy_data_agent.restorer import restore_report


class LocalAnonymizeArtifacts(BaseModel):
    run_id: str
    output_dir: Path
    anonymized_data_path: Path
    mapping_json_path: Path
    mapping_table_path: Path
    manifest_path: Path


class LocalRestoreArtifacts(BaseModel):
    restored_report_path: Path


def anonymize_file(input_path: str | Path, output_dir: str | Path) -> LocalAnonymizeArtifacts:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    run_id = uuid4().hex[:12]
    artifacts = LocalAnonymizeArtifacts(
        run_id=run_id,
        output_dir=output_path,
        anonymized_data_path=output_path / "anonymized.csv",
        mapping_json_path=output_path / "mapping.local.json",
        mapping_table_path=output_path / "mapping_table.csv",
        manifest_path=output_path / "local_manifest.json",
    )

    source_df = read_input_table(input_path)
    anonymized = anonymize_dataframe(source_df)
    anonymized.dataframe.to_csv(artifacts.anonymized_data_path, index=False)
    save_plain_mapping_file(anonymized.mapping, artifacts.mapping_json_path)
    save_mapping_table(anonymized.mapping, artifacts.mapping_table_path)

    artifacts.manifest_path.write_text(
        json.dumps(
            {
                "run_id": artifacts.run_id,
                "mode": "local_anonymize",
                "input_path": str(input_path),
                "anonymized_data_path": str(artifacts.anonymized_data_path),
                "mapping_json_path": str(artifacts.mapping_json_path),
                "mapping_table_path": str(artifacts.mapping_table_path),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return artifacts


def restore_report_file(
    report_path: str | Path,
    mapping_path: str | Path,
    output_path: str | Path,
) -> LocalRestoreArtifacts:
    mapping = load_local_mapping(Path(mapping_path))
    report = Path(report_path).read_text(encoding="utf-8")
    restored = restore_report(report, mapping)
    restored_path = Path(output_path)
    restored_path.parent.mkdir(parents=True, exist_ok=True)
    restored_path.write_text(restored, encoding="utf-8")
    return LocalRestoreArtifacts(restored_report_path=restored_path)
