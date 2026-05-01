from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pandas as pd

from privacy_data_agent.anonymizer import anonymize_dataframe
from privacy_data_agent.llm_client import ModelProvider
from privacy_data_agent.mapping_store import save_mapping_file
from privacy_data_agent.models import RunArtifacts
from privacy_data_agent.restorer import restore_report


def read_input_table(input_path: str | Path) -> pd.DataFrame:
    path = Path(input_path)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    if path.suffix.lower() == ".xlsx":
        return pd.read_excel(path)
    raise ValueError(f"Unsupported input file type: {path.suffix}")


def build_artifacts(output_dir: Path) -> RunArtifacts:
    run_id = uuid4().hex[:12]
    return RunArtifacts(
        run_id=run_id,
        output_dir=output_dir,
        anonymized_data_path=output_dir / "anonymized.csv",
        mapping_path=output_dir / "mapping.enc.json",
        anonymized_report_path=output_dir / "model_report.anonymized.md",
        restored_report_path=output_dir / "model_report.restored.md",
        manifest_path=output_dir / "run_manifest.json",
    )


def run_analysis(
    input_path: str | Path,
    output_dir: str | Path,
    mapping_key: str,
    provider: ModelProvider,
    instruction: str,
) -> RunArtifacts:
    artifacts = build_artifacts(Path(output_dir))
    artifacts.output_dir.mkdir(parents=True, exist_ok=True)

    source_df = read_input_table(input_path)
    anonymized = anonymize_dataframe(source_df)
    anonymized.dataframe.to_csv(artifacts.anonymized_data_path, index=False)
    save_mapping_file(anonymized.mapping, artifacts.mapping_path, mapping_key)

    anonymized_csv = anonymized.dataframe.to_csv(index=False)
    analysis = provider.analyze(anonymized_csv=anonymized_csv, instruction=instruction)
    artifacts.anonymized_report_path.write_text(analysis.anonymized_report, encoding="utf-8")

    restored_report = restore_report(analysis.anonymized_report, anonymized.mapping)
    artifacts.restored_report_path.write_text(restored_report, encoding="utf-8")

    artifacts.manifest_path.write_text(
        json.dumps(
            {
                "run_id": artifacts.run_id,
                "input_path": str(input_path),
                "anonymized_data_path": str(artifacts.anonymized_data_path),
                "mapping_path": str(artifacts.mapping_path),
                "anonymized_report_path": str(artifacts.anonymized_report_path),
                "restored_report_path": str(artifacts.restored_report_path),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return artifacts
