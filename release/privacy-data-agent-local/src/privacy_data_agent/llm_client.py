from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

from privacy_data_agent.models import AnalysisResult


class ModelProvider(Protocol):
    def analyze(self, anonymized_csv: str, instruction: str) -> AnalysisResult:
        raise NotImplementedError


def build_analysis_prompt(anonymized_csv: str, instruction: str) -> str:
    return (
        f"{instruction}\n\n"
        "你只能基于下方脱敏 CSV 进行分析。报告中保留 token，不要猜测真实姓名、部门、客户或证件信息。\n\n"
        f"```csv\n{anonymized_csv}\n```"
    )


class FakeModelProvider:
    def __init__(self, captured_prompt_path: Path | None = None) -> None:
        self.captured_prompt_path = captured_prompt_path

    def analyze(self, anonymized_csv: str, instruction: str) -> AnalysisResult:
        prompt = build_analysis_prompt(anonymized_csv, instruction)
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


class OpenAIModelProvider:
    def __init__(self, model: str, base_url: str | None = None, api_key: str | None = None) -> None:
        from openai import OpenAI

        self.model = model
        self.client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"), base_url=base_url)

    def analyze(self, anonymized_csv: str, instruction: str) -> AnalysisResult:
        prompt = build_analysis_prompt(anonymized_csv, instruction)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是严谨的数据分析助手。输出 Markdown 报告。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        content = response.choices[0].message.content or ""
        return AnalysisResult(anonymized_report=content)
