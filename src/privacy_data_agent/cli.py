from __future__ import annotations

import os
from contextlib import nullcontext
from pathlib import Path

import typer

from privacy_data_agent.aggregator import aggregate_file
from privacy_data_agent.detectors import SalaryGroup
from privacy_data_agent.identity_store import UnifiedIdentityStore
from privacy_data_agent.llm_client import FakeModelProvider, OpenAIModelProvider
from privacy_data_agent.local_pipeline import anonymize_directory, anonymize_file, restore_report_file
from privacy_data_agent.mapping_store import load_local_mapping
from privacy_data_agent.pipeline import run_analysis

app = typer.Typer(no_args_is_help=True)


@app.command("_noop", hidden=True)
def _noop() -> None:
    """Keep Typer in multi-command mode so `analyze` remains a subcommand."""


@app.command()
def anonymize(
    input_path: Path = typer.Argument(..., exists=True, readable=True, help="单文件或文件夹；文件夹仅处理第一层 XLSX/CSV。"),
    output_dir: Path = typer.Option(Path("runs/local"), "--output-dir", "-o"),
    header_row: int | None = typer.Option(None, "--header-row", "-hr", help="1-based header row number (default: auto-detect)"),
    anonymize_job_title: bool = typer.Option(False, "--anonymize-job-title", help="Also anonymize job title columns such as 岗位名称 / 职位 / 职务."),
    anonymize_department: bool = typer.Option(True, "--anonymize-department/--no-anonymize-department", help="Anonymize department names (default: enabled)."),
    anonymize_salary: bool = typer.Option(True, "--anonymize-salary/--no-anonymize-salary", help="Anonymize salary columns (default: enabled)."),
    keep_salary_group: list[SalaryGroup] = typer.Option(
        [],
        "--keep-salary-group",
        help="Keep this salary sub-group as plaintext instead of anonymizing it. "
        "Repeatable, e.g. --keep-salary-group labor_cost --keep-salary-group allowance. "
        "Default: none kept, all salary columns anonymized.",
    ),
    mapping_path: Path | None = typer.Option(
        None, "--mapping", "-m", exists=True, readable=True, dir_okay=False,
        help="导入已有明文 JSON/CSV 匹配文件，保持跨文件、跨月份编号一致。",
    ),
    consistent_ids: bool = typer.Option(
        False, "--consistent-ids", help="使用本机统一编号库，跨月份、跨项目自动沿用编号。",
    ),
    allow_unverified_people: bool = typer.Option(
        False, "--allow-unverified-people", help="统一模式中身份不明的姓名继续脱敏，按位置生成 PDA_REVIEW_ 临时编号和核验清单；临时编号不用于跨项目合并。",
    ),
    preserve_calculations: bool = typer.Option(False, "--preserve-calculations", help="分析核验版：保留业务数值，保留 XLSX 原公式与已保存结果（手动计算）；工号、证件等标识仍脱敏。"),
) -> None:
    # docx/pdf 处理时列语义会被拍平（docx 整篇拍成单列 "text"，pdf 目前完全
    # 不支持——见 TODOS.md），这四个开关对这两种格式从不生效。与其让用户以为
    # 开关生效了、实际静默无效，不如在这里直接拒绝，把静默无效变成明确报错。
    suffix = input_path.suffix.lower()
    if consistent_ids and suffix in (".docx", ".pdf") and input_path.is_file():
        typer.echo("统一人员编号需要结构化表格，DOCX/PDF 请使用新编号模式。")
        raise typer.Exit(code=1)
    if suffix in (".docx", ".pdf") and (
        anonymize_job_title or not anonymize_department or not anonymize_salary or keep_salary_group or preserve_calculations
    ):
        typer.echo(
            f"该格式（{suffix}）不支持 --anonymize-job-title / --no-anonymize-department / "
            "--no-anonymize-salary / --keep-salary-group / --preserve-calculations 开关：docx 处理时列名语义会被拍平，pdf 暂不支持任何开关。"
            "请去掉这些开关重新运行，或改用 xlsx/csv。"
        )
        raise typer.Exit(code=1)

    seed_mapping = None
    if mapping_path is not None:
        try:
            seed_mapping = load_local_mapping(mapping_path)
        except (ValueError, OSError, KeyError):
            typer.echo("无法读取映射文件，请使用有效的明文 mapping.local.json 或 mapping_table.csv。")
            raise typer.Exit(code=1)

    options = {
        "input_path": input_path,
        "output_dir": output_dir,
        "header_row": header_row,
        "anonymize_job_title": anonymize_job_title,
        "anonymize_department": anonymize_department,
        "anonymize_salary": anonymize_salary,
        "keep_salary_groups": frozenset(keep_salary_group),
        "seed_mapping": seed_mapping,
        "allow_unverified_people": allow_unverified_people,
        "preserve_calculations": preserve_calculations,
    }
    is_directory = input_path.is_dir()
    try:
        with UnifiedIdentityStore(seed_mapping) if consistent_ids else nullcontext(None) as identities:
            if identities is not None:
                options["seed_mapping"] = identities.mapping
                options["require_unique_people"] = True
            processor = anonymize_directory if is_directory else anonymize_file
            artifacts = processor(**options)
            if identities is not None:
                identities.save(load_local_mapping(artifacts.mapping_json_path))
                typer.echo(f"统一编号库：{identities.path}")
    except (ValueError, OSError) as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc

    if is_directory:
        batch = artifacts
        if preserve_calculations:
            typer.echo(f"分析核验版：保留业务数值，{batch.formula_count} 个公式和原计算结果已保留，工作簿设为手动计算。")
        typer.echo(f"批量处理：成功 {batch.success_count}，失败 {batch.failure_count}")
        if batch.review_count:
            typer.echo(f"另有 {batch.review_count} 个人员项使用待核验临时编号，不用于跨项目合并；核验清单位于各文件输出目录。")
        typer.echo(f"处理记录：{batch.manifest_path}")
        typer.echo(f"完整映射：{batch.mapping_json_path}")
        typer.echo("映射及处理记录仅限本地保存；只分享 files 下的 anonymized 数据文件。")
        if batch.failure_count:
            raise typer.Exit(code=1)
        return

    typer.echo(f"Anonymized data: {artifacts.anonymized_data_path}")
    typer.echo(f"Mapping JSON: {artifacts.mapping_json_path}")
    typer.echo(f"Mapping table: {artifacts.mapping_table_path}")
    if preserve_calculations:
        typer.echo(f"分析核验版：保留业务数值，{artifacts.formula_count} 个公式和原计算结果已保留，工作簿设为手动计算。")
    if artifacts.review_count:
        typer.echo(f"待核验临时编号：{artifacts.review_count} 个，不用于跨项目人员合并。清单：{artifacts.review_path}")
    typer.echo("Keep mapping files local. They contain original sensitive values.")


@app.command()
def aggregate(
    input_path: Path = typer.Argument(..., exists=True, readable=True),
    output_path: Path = typer.Option(Path("runs/local/aggregate.csv"), "--output", "-o"),
    group_by: list[str] = typer.Option(
        ...,
        "--group-by",
        help="按哪一列（或多列，组合分组）汇总，如 --group-by 部门 --group-by 岗位。"
        "必须是源文件里真实存在的列名。",
    ),
    salary_group: list[SalaryGroup] = typer.Option(
        ...,
        "--salary-group",
        help="汇总哪个薪资子组的数字（求和+均值+人数）。可重复传多个。",
    ),
    min_group_size: int = typer.Option(
        3,
        "--min-group-size",
        help="k-匿名阈值：分组人数低于此值时，拒绝输出该分组的总额/均值"
        "（只留人数，不留数字），默认3人。",
    ),
    header_row: int | None = typer.Option(None, "--header-row", "-hr"),
) -> None:
    """本地聚合成本/人效数字，不脱敏、不输出任何个人行——个人数据从不产出，
    只产出分组汇总。跟 anonymize 是完全不同的安全模型，只吃 xlsx/csv。"""
    try:
        result = aggregate_file(
            input_path=input_path,
            output_path=output_path,
            group_by=group_by,
            salary_groups=salary_group,
            min_group_size=min_group_size,
            header_row=header_row,
        )
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc
    typer.echo(f"Aggregated output: {output_path}")
    if result.suppressed_group_count:
        typer.echo(
            f"{result.suppressed_group_count} 个分组因人数少于 {min_group_size} 人被拒绝输出汇总数（k-匿名保护）。"
        )


@app.command()
def restore(
    report_path: Path = typer.Argument(..., exists=True, readable=True),
    mapping_path: Path = typer.Option(..., "--mapping", "-m", exists=True, readable=True),
    output_path: Path = typer.Option(Path("runs/local/report.restored.md"), "--output", "-o"),
) -> None:
    artifacts = restore_report_file(
        report_path=report_path,
        mapping_path=mapping_path,
        output_path=output_path,
    )
    typer.echo(f"Restored report: {artifacts.restored_report_path}")


@app.command()
def analyze(
    input_path: Path = typer.Argument(..., exists=True, readable=True),
    output_dir: Path = typer.Option(Path("runs/latest"), "--output-dir", "-o"),
    instruction: str = typer.Option("请基于脱敏数据生成结构化数据分析报告。", "--instruction", "-i"),
    provider_name: str = typer.Option("fake", "--provider"),
    model: str = typer.Option("gpt-4.1-mini", "--model"),
    base_url: str | None = typer.Option(None, "--base-url"),
) -> None:
    mapping_key = os.environ.get("PRIVACY_AGENT_KEY")
    if not mapping_key:
        typer.echo("PRIVACY_AGENT_KEY is required. Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'")
        raise typer.Exit(code=1)

    if provider_name == "fake":
        provider = FakeModelProvider(captured_prompt_path=output_dir / "model_prompt.anonymized.md")
    elif provider_name == "openai":
        provider = OpenAIModelProvider(model=model, base_url=base_url)
    else:
        typer.echo("Unsupported provider. Use --provider fake or --provider openai.")
        raise typer.Exit(code=1)

    artifacts = run_analysis(
        input_path=input_path,
        output_dir=output_dir,
        mapping_key=mapping_key,
        provider=provider,
        instruction=instruction,
    )
    typer.echo(f"Anonymized data: {artifacts.anonymized_data_path}")
    typer.echo(f"Encrypted mapping: {artifacts.mapping_path}")
    typer.echo(f"Anonymized report: {artifacts.anonymized_report_path}")
    typer.echo(f"Restored report: {artifacts.restored_report_path}")
