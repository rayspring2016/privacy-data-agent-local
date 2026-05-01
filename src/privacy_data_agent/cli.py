from __future__ import annotations

import os
from pathlib import Path

import typer

from privacy_data_agent.llm_client import FakeModelProvider, OpenAIModelProvider
from privacy_data_agent.pipeline import run_analysis

app = typer.Typer(no_args_is_help=True)


@app.command("_noop", hidden=True)
def _noop() -> None:
    """Keep Typer in multi-command mode so `analyze` remains a subcommand."""


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
