from __future__ import annotations

from pathlib import Path
from typing import Protocol

from privacy_data_agent.models import AnalysisResult


class ModelProvider(Protocol):
    def analyze(self, anonymized_csv: str, instruction: str) -> AnalysisResult:
        raise NotImplementedError


class FakeModelProvider:
    def __init__(self, captured_prompt_path: Path | None = None) -> None:
        self.captured_prompt_path = captured_prompt_path

    def analyze(self, anonymized_csv: str, instruction: str) -> AnalysisResult:
        prompt = f"{instruction}\n\n```csv\n{anonymized_csv}\n```"
        if self.captured_prompt_path is not None:
            self.captured_prompt_path.parent.mkdir(parents=True, exist_ok=True)
            self.captured_prompt_path.write_text(prompt, encoding="utf-8")
        return AnalysisResult(
            anonymized_report=(
                "# 数据分析报告\n\n"
                "EMP_0001 在 DEPT_0001 的 CUSTOMER_0001 相关业绩表现突出。\n\n"
                "建议复盘 CUSTOMER_0001 的成交过程，并让 EMP_0001 输出方法论。"
            )
        )
