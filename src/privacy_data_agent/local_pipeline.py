from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel

from privacy_data_agent.anonymizer import anonymize_dataframe
from privacy_data_agent.detectors import SalaryGroup
from privacy_data_agent.mapping_store import load_local_mapping, save_mapping_table, save_plain_mapping_file
from privacy_data_agent.models import MappingFile
from privacy_data_agent.pipeline import read_input_table
from privacy_data_agent.restorer import restore_report
from privacy_data_agent.workbook_anonymizer import anonymize_xlsx_file


class LocalAnonymizeArtifacts(BaseModel):
    run_id: str
    output_dir: Path
    anonymized_data_path: Path
    mapping_json_path: Path
    mapping_table_path: Path
    manifest_path: Path


class LocalRestoreArtifacts(BaseModel):
    restored_report_path: Path


class LocalBatchAnonymizeArtifacts(BaseModel):
    manifest_path: Path
    mapping_json_path: Path
    success_count: int
    failure_count: int


def anonymize_file(
    input_path: str | Path,
    output_dir: str | Path,
    header_row: int | None = None,
    anonymize_job_title: bool = False,
    anonymize_department: bool = True,
    anonymize_region: bool = True,
    anonymize_salary: bool = True,
    keep_salary_groups: frozenset[SalaryGroup] = frozenset(),
    seed_mapping: MappingFile | None = None,
) -> LocalAnonymizeArtifacts:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    run_id = uuid4().hex[:12]
    input_file = Path(input_path)
    anonymized_path = output_path / ("anonymized.xlsx" if input_file.suffix.lower() == ".xlsx" else "anonymized.csv")
    artifacts = LocalAnonymizeArtifacts(
        run_id=run_id,
        output_dir=output_path,
        anonymized_data_path=anonymized_path,
        mapping_json_path=output_path / "mapping.local.json",
        mapping_table_path=output_path / "mapping_table.csv",
        manifest_path=output_path / "local_manifest.json",
    )

    if input_file.suffix.lower() == ".xlsx":
        anonymized_workbook = anonymize_xlsx_file(
            input_file,
            artifacts.anonymized_data_path,
            seed_mapping=seed_mapping,
            header_row=header_row,
            anonymize_job_title=anonymize_job_title,
            anonymize_department=anonymize_department,
            anonymize_region=anonymize_region,
            anonymize_salary=anonymize_salary,
            keep_salary_groups=keep_salary_groups,
        )
        mapping = anonymized_workbook.mapping
    else:
        source_df = read_input_table(input_file, header_row=header_row)
        anonymized = anonymize_dataframe(
            source_df,
            seed_mapping=seed_mapping,
            anonymize_job_title=anonymize_job_title,
            anonymize_department=anonymize_department,
            anonymize_region=anonymize_region,
            anonymize_salary=anonymize_salary,
            keep_salary_groups=keep_salary_groups,
        )
        anonymized.dataframe.to_csv(artifacts.anonymized_data_path, index=False)
        mapping = anonymized.mapping
    save_plain_mapping_file(mapping, artifacts.mapping_json_path)
    save_mapping_table(mapping, artifacts.mapping_table_path)

    artifacts.manifest_path.write_text(
        json.dumps(
            {
                "run_id": artifacts.run_id,
                "mode": "local_anonymize",
                "input_path": str(input_path),
                "anonymized_data_path": str(artifacts.anonymized_data_path),
                "mapping_json_path": str(artifacts.mapping_json_path),
                "mapping_table_path": str(artifacts.mapping_table_path),
                # 主动降低脱敏强度的动作最该留痕：半年后拿到这份 anonymized
                # 文件，得能查出当初到底放开了哪些。region 不记，因为它从未
                # 真正生效（详见 detectors.py 里的相关说明）。
                "flags": {
                    "anonymize_job_title": anonymize_job_title,
                    "anonymize_department": anonymize_department,
                    "anonymize_salary": anonymize_salary,
                    "kept_salary_groups": sorted(g.value for g in keep_salary_groups),
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return artifacts


def anonymize_directory(
    input_path: str | Path,
    output_dir: str | Path,
    header_row: int | None = None,
    anonymize_job_title: bool = False,
    anonymize_department: bool = True,
    anonymize_salary: bool = True,
    keep_salary_groups: frozenset[SalaryGroup] = frozenset(),
    seed_mapping: MappingFile | None = None,
) -> LocalBatchAnonymizeArtifacts:
    source = Path(input_path)
    files = sorted(
        (path for path in source.iterdir()
         if path.is_file() and path.suffix.lower() in {".csv", ".xlsx"}
         and not path.name.startswith("~$")),
        key=lambda path: path.name,
    )
    if not files:
        raise ValueError("文件夹第一层没有可处理的 XLSX/CSV 文件（不递归子文件夹）。")
    output_path = Path(output_dir)
    if output_path.exists() and (not output_path.is_dir() or any(output_path.iterdir())):
        raise ValueError("批量输出必须使用新的或空目录，以免覆盖已有文件。")
    output_path.mkdir(parents=True, exist_ok=True)
    mapping = seed_mapping or MappingFile()
    records = []
    for index, path in enumerate(files, start=1):
        record = {"input_path": str(path), "status": "failed"}
        try:
            artifacts = anonymize_file(
                input_path=path,
                output_dir=output_path / "files" / f"{index:04d}",
                header_row=header_row,
                anonymize_job_title=anonymize_job_title,
                anonymize_department=anonymize_department,
                anonymize_salary=anonymize_salary,
                keep_salary_groups=keep_salary_groups,
                seed_mapping=mapping,
            )
            updated_mapping = load_local_mapping(artifacts.mapping_json_path)
        except Exception as exc:
            # 文件级失败不能中断整批；异常文本可能含原始数据，只记录类型。
            record["error_type"] = type(exc).__name__
        else:
            mapping = updated_mapping
            record.update(
                status="success",
                output=str(artifacts.anonymized_data_path.relative_to(output_path)),
            )
        records.append(record)

    mapping_path = output_path / "mapping.local.json"
    save_plain_mapping_file(mapping, mapping_path)
    save_mapping_table(mapping, output_path / "mapping_table.csv")
    success_count = sum(record["status"] == "success" for record in records)
    manifest_path = output_path / "batch_manifest.json"
    manifest_path.write_text(
        json.dumps({
            "mode": "local_batch_anonymize",
            "input_path": str(source),
            "mapping_json_path": str(mapping_path),
            "header_row": header_row,
            "flags": {
                "anonymize_job_title": anonymize_job_title,
                "anonymize_department": anonymize_department,
                "anonymize_salary": anonymize_salary,
                "kept_salary_groups": sorted(group.value for group in keep_salary_groups),
            },
            "success_count": success_count,
            "failure_count": len(records) - success_count,
            "files": records,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return LocalBatchAnonymizeArtifacts(
        manifest_path=manifest_path,
        mapping_json_path=mapping_path,
        success_count=success_count,
        failure_count=len(records) - success_count,
    )


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
