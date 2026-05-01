# Privacy Data Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local-first data analysis agent that anonymizes personal and business-sensitive fields before model analysis, stores a local mapping file, and restores original names, departments, customers, and identifiers into the final report after analysis.

**Architecture:** The agent is a Python CLI package with four explicit stages: scan input data locally, anonymize sensitive values and write an encrypted local mapping file, send only anonymized data to an LLM adapter for analysis, then restore tokens in the returned report using the local mapping. The model boundary receives placeholders such as `EMP_0001`, `ID_0001`, `DEPT_0001`, and `CUSTOMER_0001`; raw values never leave the local process.

**Tech Stack:** Python 3.11+, `pytest`, `pandas`, `openpyxl`, `typer`, `pydantic`, `cryptography`, optional OpenAI-compatible API client behind a provider interface.

---

## File Structure

- Create `pyproject.toml`: package metadata, dependencies, pytest configuration, CLI entrypoint.
- Create `README.md`: usage contract, privacy boundary, supported file formats, environment variables.
- Create `src/privacy_data_agent/__init__.py`: package version export.
- Create `src/privacy_data_agent/models.py`: dataclasses and enums for sensitive entity types, mapping entries, run artifacts, and analysis results.
- Create `src/privacy_data_agent/detectors.py`: local sensitive value detection for names, Chinese ID numbers, departments, customer names, phone numbers, and email addresses.
- Create `src/privacy_data_agent/mapping_store.py`: encrypted mapping file write/read logic.
- Create `src/privacy_data_agent/anonymizer.py`: dataframe anonymization and mapping generation.
- Create `src/privacy_data_agent/llm_client.py`: model provider interface plus a deterministic local fake provider for tests.
- Create `src/privacy_data_agent/restorer.py`: report token replacement using the local mapping file.
- Create `src/privacy_data_agent/pipeline.py`: orchestration from input file to anonymized data, model analysis, restored report.
- Create `src/privacy_data_agent/cli.py`: `privacy-data-agent analyze ...` command.
- Create `tests/fixtures/hr_sample.csv`: small CSV fixture with employees, departments, customer names, phone numbers, email, and Chinese ID values.
- Create `tests/test_detectors.py`: detector coverage.
- Create `tests/test_anonymizer.py`: anonymization coverage and no-raw-sensitive-data assertion.
- Create `tests/test_mapping_store.py`: encrypted mapping round-trip coverage.
- Create `tests/test_restorer.py`: token restoration coverage.
- Create `tests/test_pipeline.py`: end-to-end pipeline with fake model provider.

## Data Contract

Input files:

- `.csv`: UTF-8 with header row.
- `.xlsx`: first sheet by default.

Sensitive values to replace locally:

- Employee/person names from columns containing `姓名`, `员工`, `name`, `employee`.
- Chinese resident ID numbers matching `18` digits or `17` digits plus `X/x`.
- Department names from columns containing `部门`, `组织`, `department`, `team`.
- Customer/client names from columns containing `客户`, `客户名称`, `client`, `customer`, `company`.
- Phone numbers and email addresses by regex.

Mapping token format:

- Person names: `EMP_0001`
- ID numbers: `ID_0001`
- Departments: `DEPT_0001`
- Customers: `CUSTOMER_0001`
- Phone numbers: `PHONE_0001`
- Emails: `EMAIL_0001`

Local output files per run:

- `runs/<run_id>/anonymized.csv`
- `runs/<run_id>/mapping.enc.json`
- `runs/<run_id>/model_report.anonymized.md`
- `runs/<run_id>/model_report.restored.md`
- `runs/<run_id>/run_manifest.json`

## Security Requirements

- Raw sensitive values must only appear in the source file and encrypted mapping file.
- `anonymized.csv`, model prompt content, and `model_report.anonymized.md` must not contain source names, ID numbers, departments, customers, phones, or emails from the fixture.
- Mapping encryption key comes from `PRIVACY_AGENT_KEY`, a Fernet key string.
- If `PRIVACY_AGENT_KEY` is missing, CLI exits with a clear message and does not create a mapping file.
- The fake provider used in tests must persist the exact anonymized prompt it received so tests can prove raw data was not sent across the model boundary.

---

### Task 1: Project Skeleton and Fixture

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `src/privacy_data_agent/__init__.py`
- Create: `tests/fixtures/hr_sample.csv`

- [ ] **Step 1: Create package metadata**

Add this exact content to `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "privacy-data-agent"
version = "0.1.0"
description = "Local-first anonymization, model analysis, and restoration pipeline for sensitive HR and business data."
requires-python = ">=3.11"
dependencies = [
  "cryptography>=42.0.0",
  "openpyxl>=3.1.2",
  "pandas>=2.2.0",
  "pydantic>=2.7.0",
  "typer>=0.12.3"
]

[project.optional-dependencies]
dev = ["pytest>=8.2.0"]

[project.scripts]
privacy-data-agent = "privacy_data_agent.cli:app"

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

- [ ] **Step 2: Create package init**

Add this exact content to `src/privacy_data_agent/__init__.py`:

```python
__version__ = "0.1.0"
```

- [ ] **Step 3: Create README**

Add this exact content to `README.md`:

```markdown
# Privacy Data Agent

Local-first pipeline for sensitive HR and business data:

1. Read CSV or XLSX locally.
2. Replace sensitive names, ID numbers, departments, customer names, phones, and emails with stable tokens.
3. Store the original-to-token mapping in an encrypted local file.
4. Send only anonymized data to a model provider for analysis.
5. Restore original values into the final report locally.

## Privacy Boundary

Raw sensitive values never cross the model boundary. The model receives tokens such as `EMP_0001`, `DEPT_0001`, and `CUSTOMER_0001`.

## Required Environment

```bash
export PRIVACY_AGENT_KEY="$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
```

## CLI

```bash
privacy-data-agent analyze tests/fixtures/hr_sample.csv --output-dir runs/manual
```
```

- [ ] **Step 4: Create CSV fixture**

Add this exact content to `tests/fixtures/hr_sample.csv`:

```csv
员工姓名,身份证号,部门,客户名称,手机号,邮箱,销售额,备注
张三,11010119900307001X,华东销售一部,上海春雷科技有限公司,13800138000,zhangsan@example.com,120000,客户续费稳定
李四,310101198812120011,华南客户成功部,深圳星海贸易有限公司,13900139000,lisi@example.com,98000,需要主管跟进
王五,440101199506150032,华东销售一部,上海春雷科技有限公司,13700137000,wangwu@example.com,156000,跨部门协作完成
```

- [ ] **Step 5: Install dependencies**

Run:

```bash
python -m pip install -e ".[dev]"
```

Expected: command exits with status `0`.

- [ ] **Step 6: Run baseline tests**

Run:

```bash
pytest -q
```

Expected: pytest reports no tests collected or passes existing tests.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml README.md src/privacy_data_agent/__init__.py tests/fixtures/hr_sample.csv
git commit -m "chore: initialize privacy data agent project"
```

---

### Task 2: Sensitive Entity Models and Detectors

**Files:**
- Create: `src/privacy_data_agent/models.py`
- Create: `src/privacy_data_agent/detectors.py`
- Create: `tests/test_detectors.py`

- [ ] **Step 1: Write detector tests**

Add this exact content to `tests/test_detectors.py`:

```python
from privacy_data_agent.detectors import detect_cell_entity_type, detect_column_entity_type
from privacy_data_agent.models import EntityType


def test_detects_column_semantics():
    assert detect_column_entity_type("员工姓名") == EntityType.EMPLOYEE
    assert detect_column_entity_type("身份证号") == EntityType.ID_NUMBER
    assert detect_column_entity_type("部门") == EntityType.DEPARTMENT
    assert detect_column_entity_type("客户名称") == EntityType.CUSTOMER
    assert detect_column_entity_type("手机号") == EntityType.PHONE
    assert detect_column_entity_type("邮箱") == EntityType.EMAIL
    assert detect_column_entity_type("销售额") is None


def test_detects_cell_patterns_without_column_hint():
    assert detect_cell_entity_type("11010119900307001X") == EntityType.ID_NUMBER
    assert detect_cell_entity_type("13800138000") == EntityType.PHONE
    assert detect_cell_entity_type("zhangsan@example.com") == EntityType.EMAIL
    assert detect_cell_entity_type("120000") is None
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_detectors.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `privacy_data_agent.detectors`.

- [ ] **Step 3: Implement models**

Add this exact content to `src/privacy_data_agent/models.py`:

```python
from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field


class EntityType(StrEnum):
    EMPLOYEE = "employee"
    ID_NUMBER = "id_number"
    DEPARTMENT = "department"
    CUSTOMER = "customer"
    PHONE = "phone"
    EMAIL = "email"


TOKEN_PREFIX: dict[EntityType, str] = {
    EntityType.EMPLOYEE: "EMP",
    EntityType.ID_NUMBER: "ID",
    EntityType.DEPARTMENT: "DEPT",
    EntityType.CUSTOMER: "CUSTOMER",
    EntityType.PHONE: "PHONE",
    EntityType.EMAIL: "EMAIL",
}


class MappingEntry(BaseModel):
    entity_type: EntityType
    original: str
    token: str


class MappingFile(BaseModel):
    version: int = 1
    entries: list[MappingEntry] = Field(default_factory=list)


class RunArtifacts(BaseModel):
    run_id: str
    output_dir: Path
    anonymized_data_path: Path
    mapping_path: Path
    anonymized_report_path: Path
    restored_report_path: Path
    manifest_path: Path


class AnalysisResult(BaseModel):
    anonymized_report: str
```

- [ ] **Step 4: Implement detectors**

Add this exact content to `src/privacy_data_agent/detectors.py`:

```python
from __future__ import annotations

import re

from privacy_data_agent.models import EntityType

ID_NUMBER_RE = re.compile(r"^\d{17}[\dXx]$")
PHONE_RE = re.compile(r"^(?:\+?86[- ]?)?1[3-9]\d{9}$")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

COLUMN_HINTS: tuple[tuple[EntityType, tuple[str, ...]], ...] = (
    (EntityType.EMPLOYEE, ("姓名", "员工", "name", "employee")),
    (EntityType.ID_NUMBER, ("身份证", "证件", "id_number", "national_id")),
    (EntityType.DEPARTMENT, ("部门", "组织", "department", "team")),
    (EntityType.CUSTOMER, ("客户", "client", "customer", "company")),
    (EntityType.PHONE, ("手机号", "电话", "phone", "mobile")),
    (EntityType.EMAIL, ("邮箱", "email", "e-mail")),
)


def detect_column_entity_type(column_name: str) -> EntityType | None:
    normalized = column_name.strip().lower()
    for entity_type, hints in COLUMN_HINTS:
        if any(hint.lower() in normalized for hint in hints):
            return entity_type
    return None


def detect_cell_entity_type(value: object) -> EntityType | None:
    text = "" if value is None else str(value).strip()
    if not text:
        return None
    if ID_NUMBER_RE.match(text):
        return EntityType.ID_NUMBER
    if PHONE_RE.match(text):
        return EntityType.PHONE
    if EMAIL_RE.match(text):
        return EntityType.EMAIL
    return None
```

- [ ] **Step 5: Run detector tests**

Run:

```bash
pytest tests/test_detectors.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/privacy_data_agent/models.py src/privacy_data_agent/detectors.py tests/test_detectors.py
git commit -m "feat: detect sensitive data entities"
```

---

### Task 3: Dataframe Anonymizer

**Files:**
- Create: `src/privacy_data_agent/anonymizer.py`
- Create: `tests/test_anonymizer.py`

- [ ] **Step 1: Write anonymizer tests**

Add this exact content to `tests/test_anonymizer.py`:

```python
from pathlib import Path

import pandas as pd

from privacy_data_agent.anonymizer import anonymize_dataframe
from privacy_data_agent.models import EntityType


def test_anonymizes_sensitive_columns_and_builds_mapping():
    df = pd.read_csv(Path("tests/fixtures/hr_sample.csv"))

    result = anonymize_dataframe(df)

    csv_text = result.dataframe.to_csv(index=False)
    for raw in [
        "张三",
        "李四",
        "王五",
        "11010119900307001X",
        "华东销售一部",
        "上海春雷科技有限公司",
        "13800138000",
        "zhangsan@example.com",
    ]:
        assert raw not in csv_text

    assert "EMP_0001" in csv_text
    assert "ID_0001" in csv_text
    assert "DEPT_0001" in csv_text
    assert "CUSTOMER_0001" in csv_text
    assert "PHONE_0001" in csv_text
    assert "EMAIL_0001" in csv_text
    assert result.mapping.entries[0].entity_type == EntityType.EMPLOYEE
    assert result.mapping.entries[0].original == "张三"
    assert result.mapping.entries[0].token == "EMP_0001"


def test_reuses_same_token_for_repeated_value():
    df = pd.DataFrame({"部门": ["华东销售一部", "华东销售一部"]})

    result = anonymize_dataframe(df)

    assert result.dataframe["部门"].tolist() == ["DEPT_0001", "DEPT_0001"]
    assert len(result.mapping.entries) == 1
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_anonymizer.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `privacy_data_agent.anonymizer`.

- [ ] **Step 3: Implement anonymizer**

Add this exact content to `src/privacy_data_agent/anonymizer.py`:

```python
from __future__ import annotations

from collections import defaultdict

import pandas as pd
from pydantic import BaseModel

from privacy_data_agent.detectors import detect_cell_entity_type, detect_column_entity_type
from privacy_data_agent.models import EntityType, MappingEntry, MappingFile, TOKEN_PREFIX


class AnonymizeResult(BaseModel):
    dataframe: pd.DataFrame
    mapping: MappingFile

    class Config:
        arbitrary_types_allowed = True


def anonymize_dataframe(df: pd.DataFrame) -> AnonymizeResult:
    output = df.copy()
    counters: dict[EntityType, int] = defaultdict(int)
    token_by_key: dict[tuple[EntityType, str], str] = {}
    entries: list[MappingEntry] = []

    for column in output.columns:
        column_type = detect_column_entity_type(str(column))
        for row_index, value in output[column].items():
            text = "" if pd.isna(value) else str(value).strip()
            if not text:
                continue
            entity_type = column_type or detect_cell_entity_type(text)
            if entity_type is None:
                continue
            key = (entity_type, text)
            if key not in token_by_key:
                counters[entity_type] += 1
                token = f"{TOKEN_PREFIX[entity_type]}_{counters[entity_type]:04d}"
                token_by_key[key] = token
                entries.append(MappingEntry(entity_type=entity_type, original=text, token=token))
            output.at[row_index, column] = token_by_key[key]

    return AnonymizeResult(dataframe=output, mapping=MappingFile(entries=entries))
```

- [ ] **Step 4: Run anonymizer tests**

Run:

```bash
pytest tests/test_anonymizer.py -q
```

Expected: PASS.

- [ ] **Step 5: Run detector and anonymizer tests together**

Run:

```bash
pytest tests/test_detectors.py tests/test_anonymizer.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/privacy_data_agent/anonymizer.py tests/test_anonymizer.py
git commit -m "feat: anonymize sensitive dataframe values"
```

---

### Task 4: Encrypted Mapping Store

**Files:**
- Create: `src/privacy_data_agent/mapping_store.py`
- Create: `tests/test_mapping_store.py`

- [ ] **Step 1: Write mapping store tests**

Add this exact content to `tests/test_mapping_store.py`:

```python
from cryptography.fernet import Fernet

from privacy_data_agent.mapping_store import load_mapping_file, save_mapping_file
from privacy_data_agent.models import EntityType, MappingEntry, MappingFile


def test_mapping_store_encrypts_raw_values(tmp_path):
    key = Fernet.generate_key().decode()
    mapping = MappingFile(
        entries=[
            MappingEntry(entity_type=EntityType.EMPLOYEE, original="张三", token="EMP_0001"),
            MappingEntry(entity_type=EntityType.CUSTOMER, original="上海春雷科技有限公司", token="CUSTOMER_0001"),
        ]
    )
    path = tmp_path / "mapping.enc.json"

    save_mapping_file(mapping, path, key)

    encrypted_text = path.read_text(encoding="utf-8")
    assert "张三" not in encrypted_text
    assert "上海春雷科技有限公司" not in encrypted_text
    assert load_mapping_file(path, key) == mapping
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_mapping_store.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `privacy_data_agent.mapping_store`.

- [ ] **Step 3: Implement mapping store**

Add this exact content to `src/privacy_data_agent/mapping_store.py`:

```python
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
```

- [ ] **Step 4: Run mapping store tests**

Run:

```bash
pytest tests/test_mapping_store.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/privacy_data_agent/mapping_store.py tests/test_mapping_store.py
git commit -m "feat: encrypt local sensitive mapping"
```

---

### Task 5: Model Provider Interface and Report Restorer

**Files:**
- Create: `src/privacy_data_agent/llm_client.py`
- Create: `src/privacy_data_agent/restorer.py`
- Create: `tests/test_restorer.py`

- [ ] **Step 1: Write restorer tests**

Add this exact content to `tests/test_restorer.py`:

```python
from privacy_data_agent.models import EntityType, MappingEntry, MappingFile
from privacy_data_agent.restorer import restore_report


def test_restores_tokens_in_report():
    mapping = MappingFile(
        entries=[
            MappingEntry(entity_type=EntityType.EMPLOYEE, original="张三", token="EMP_0001"),
            MappingEntry(entity_type=EntityType.DEPARTMENT, original="华东销售一部", token="DEPT_0001"),
            MappingEntry(entity_type=EntityType.CUSTOMER, original="上海春雷科技有限公司", token="CUSTOMER_0001"),
        ]
    )
    report = "EMP_0001 在 DEPT_0001 负责 CUSTOMER_0001，建议提高资源投入。"

    restored = restore_report(report, mapping)

    assert restored == "张三 在 华东销售一部 负责 上海春雷科技有限公司，建议提高资源投入。"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_restorer.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `privacy_data_agent.restorer`.

- [ ] **Step 3: Implement model provider interface**

Add this exact content to `src/privacy_data_agent/llm_client.py`:

```python
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
```

- [ ] **Step 4: Implement restorer**

Add this exact content to `src/privacy_data_agent/restorer.py`:

```python
from __future__ import annotations

from privacy_data_agent.models import MappingFile


def restore_report(report: str, mapping: MappingFile) -> str:
    restored = report
    for entry in sorted(mapping.entries, key=lambda item: len(item.token), reverse=True):
        restored = restored.replace(entry.token, entry.original)
    return restored
```

- [ ] **Step 5: Run restorer tests**

Run:

```bash
pytest tests/test_restorer.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/privacy_data_agent/llm_client.py src/privacy_data_agent/restorer.py tests/test_restorer.py
git commit -m "feat: restore anonymized model reports"
```

---

### Task 6: End-to-End Pipeline

**Files:**
- Create: `src/privacy_data_agent/pipeline.py`
- Create: `tests/test_pipeline.py`

- [ ] **Step 1: Write pipeline tests**

Add this exact content to `tests/test_pipeline.py`:

```python
from cryptography.fernet import Fernet

from privacy_data_agent.llm_client import FakeModelProvider
from privacy_data_agent.mapping_store import load_mapping_file
from privacy_data_agent.pipeline import run_analysis


def test_pipeline_never_sends_raw_sensitive_values_to_model(tmp_path):
    key = Fernet.generate_key().decode()
    captured_prompt = tmp_path / "captured_prompt.md"
    provider = FakeModelProvider(captured_prompt_path=captured_prompt)

    artifacts = run_analysis(
        input_path="tests/fixtures/hr_sample.csv",
        output_dir=tmp_path / "run",
        mapping_key=key,
        provider=provider,
        instruction="请分析销售额和客户跟进风险。",
    )

    prompt_text = captured_prompt.read_text(encoding="utf-8")
    anonymized_text = artifacts.anonymized_data_path.read_text(encoding="utf-8")
    anonymized_report = artifacts.anonymized_report_path.read_text(encoding="utf-8")
    restored_report = artifacts.restored_report_path.read_text(encoding="utf-8")

    for raw in [
        "张三",
        "李四",
        "王五",
        "11010119900307001X",
        "华东销售一部",
        "上海春雷科技有限公司",
        "13800138000",
        "zhangsan@example.com",
    ]:
        assert raw not in prompt_text
        assert raw not in anonymized_text
        assert raw not in anonymized_report

    assert "EMP_0001" in prompt_text
    assert "CUSTOMER_0001" in anonymized_report
    assert "张三" in restored_report
    assert "上海春雷科技有限公司" in restored_report
    assert load_mapping_file(artifacts.mapping_path, key).entries
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_pipeline.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `privacy_data_agent.pipeline`.

- [ ] **Step 3: Implement pipeline**

Add this exact content to `src/privacy_data_agent/pipeline.py`:

```python
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
```

- [ ] **Step 4: Run pipeline tests**

Run:

```bash
pytest tests/test_pipeline.py -q
```

Expected: PASS.

- [ ] **Step 5: Run all current tests**

Run:

```bash
pytest -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/privacy_data_agent/pipeline.py tests/test_pipeline.py
git commit -m "feat: run local anonymize analyze restore pipeline"
```

---

### Task 7: CLI Command

**Files:**
- Create: `src/privacy_data_agent/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write CLI tests**

Add this exact content to `tests/test_cli.py`:

```python
from cryptography.fernet import Fernet
from typer.testing import CliRunner

from privacy_data_agent.cli import app


def test_cli_requires_mapping_key(tmp_path, monkeypatch):
    monkeypatch.delenv("PRIVACY_AGENT_KEY", raising=False)
    runner = CliRunner()

    result = runner.invoke(app, ["analyze", "tests/fixtures/hr_sample.csv", "--output-dir", str(tmp_path)])

    assert result.exit_code == 1
    assert "PRIVACY_AGENT_KEY is required" in result.output


def test_cli_runs_with_fake_provider(tmp_path, monkeypatch):
    monkeypatch.setenv("PRIVACY_AGENT_KEY", Fernet.generate_key().decode())
    runner = CliRunner()

    result = runner.invoke(app, ["analyze", "tests/fixtures/hr_sample.csv", "--output-dir", str(tmp_path)])

    assert result.exit_code == 0
    assert "Restored report:" in result.output
    assert (tmp_path / "model_report.restored.md").exists()
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_cli.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `privacy_data_agent.cli`.

- [ ] **Step 3: Implement CLI**

Add this exact content to `src/privacy_data_agent/cli.py`:

```python
from __future__ import annotations

import os
from pathlib import Path

import typer

from privacy_data_agent.llm_client import FakeModelProvider
from privacy_data_agent.pipeline import run_analysis

app = typer.Typer(no_args_is_help=True)


@app.command()
def analyze(
    input_path: Path = typer.Argument(..., exists=True, readable=True),
    output_dir: Path = typer.Option(Path("runs/latest"), "--output-dir", "-o"),
    instruction: str = typer.Option("请基于脱敏数据生成结构化数据分析报告。", "--instruction", "-i"),
) -> None:
    mapping_key = os.environ.get("PRIVACY_AGENT_KEY")
    if not mapping_key:
        typer.echo("PRIVACY_AGENT_KEY is required. Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'")
        raise typer.Exit(code=1)

    provider = FakeModelProvider(captured_prompt_path=output_dir / "model_prompt.anonymized.md")
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
```

- [ ] **Step 4: Run CLI tests**

Run:

```bash
pytest tests/test_cli.py -q
```

Expected: PASS.

- [ ] **Step 5: Run all tests**

Run:

```bash
pytest -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/privacy_data_agent/cli.py tests/test_cli.py
git commit -m "feat: add privacy data agent cli"
```

---

### Task 8: Real Model Provider Adapter

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/privacy_data_agent/llm_client.py`
- Modify: `src/privacy_data_agent/cli.py`
- Create: `tests/test_llm_client.py`

- [ ] **Step 1: Add OpenAI-compatible dependency**

Modify `pyproject.toml` dependencies to include:

```toml
  "openai>=1.30.0",
```

The dependencies block should become:

```toml
dependencies = [
  "cryptography>=42.0.0",
  "openai>=1.30.0",
  "openpyxl>=3.1.2",
  "pandas>=2.2.0",
  "pydantic>=2.7.0",
  "typer>=0.12.3"
]
```

- [ ] **Step 2: Write adapter tests**

Add this exact content to `tests/test_llm_client.py`:

```python
from privacy_data_agent.llm_client import build_analysis_prompt


def test_build_analysis_prompt_contains_only_anonymized_csv():
    prompt = build_analysis_prompt(
        anonymized_csv="员工姓名,部门\nEMP_0001,DEPT_0001\n",
        instruction="请分析风险。",
    )

    assert "请分析风险。" in prompt
    assert "EMP_0001" in prompt
    assert "DEPT_0001" in prompt
    assert "张三" not in prompt
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```bash
pytest tests/test_llm_client.py -q
```

Expected: FAIL with `ImportError` for `build_analysis_prompt`.

- [ ] **Step 4: Replace `src/privacy_data_agent/llm_client.py` with provider implementations**

Set `src/privacy_data_agent/llm_client.py` to this exact content:

```python
from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

from openai import OpenAI

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
```

- [ ] **Step 5: Modify CLI provider selection**

Replace `src/privacy_data_agent/cli.py` content with:

```python
from __future__ import annotations

import os
from pathlib import Path

import typer

from privacy_data_agent.llm_client import FakeModelProvider, OpenAIModelProvider
from privacy_data_agent.pipeline import run_analysis

app = typer.Typer(no_args_is_help=True)


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
```

- [ ] **Step 6: Run LLM client and CLI tests**

Run:

```bash
pytest tests/test_llm_client.py tests/test_cli.py -q
```

Expected: PASS.

- [ ] **Step 7: Run all tests**

Run:

```bash
pytest -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml src/privacy_data_agent/llm_client.py src/privacy_data_agent/cli.py tests/test_llm_client.py
git commit -m "feat: add openai compatible analysis provider"
```

---

### Task 9: Documentation and Manual Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace README with operational instructions**

Replace `README.md` with this exact content:

```markdown
# Privacy Data Agent

Local-first pipeline for sensitive HR and business data.

## Flow

1. Read CSV or XLSX locally.
2. Detect sensitive values from columns and patterns.
3. Replace raw values with stable tokens.
4. Save token mapping in an encrypted local file.
5. Send only anonymized CSV to the model.
6. Save the anonymized model report.
7. Restore original values into the final report locally.

## Sensitive Data Covered

- Employee/person names from name-like columns
- Chinese resident ID numbers
- Departments and organizations
- Customer/client/company names
- Phone numbers
- Email addresses

## Generate Local Mapping Key

```bash
export PRIVACY_AGENT_KEY="$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
```

Keep this key local. Without it, `mapping.enc.json` cannot be restored.

## Run with Fake Provider

```bash
privacy-data-agent analyze tests/fixtures/hr_sample.csv --output-dir runs/manual
```

The fake provider is deterministic and does not call the network. It writes `runs/manual/model_prompt.anonymized.md` so you can inspect exactly what would have been sent to the model.

## Run with OpenAI-Compatible Provider

```bash
export OPENAI_API_KEY="your_api_key"
privacy-data-agent analyze tests/fixtures/hr_sample.csv \
  --output-dir runs/openai \
  --provider openai \
  --model gpt-4.1-mini \
  --instruction "请分析销售额、客户跟进风险和可复制动作。"
```

## Output Files

- `anonymized.csv`: model-safe data with tokens.
- `mapping.enc.json`: encrypted local mapping file.
- `model_prompt.anonymized.md`: prompt captured by fake provider.
- `model_report.anonymized.md`: model output before restoration.
- `model_report.restored.md`: final local report with original values restored.
- `run_manifest.json`: file manifest for the run.

## Privacy Check

Run:

```bash
pytest -q
```

The test suite verifies raw fixture values do not appear in anonymized data, captured model prompts, or anonymized model reports.
```

- [ ] **Step 2: Run all tests**

Run:

```bash
pytest -q
```

Expected: PASS.

- [ ] **Step 3: Run manual fake-provider analysis**

Run:

```bash
export PRIVACY_AGENT_KEY="$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
privacy-data-agent analyze tests/fixtures/hr_sample.csv --output-dir runs/manual
```

Expected output includes:

```text
Anonymized data: runs/manual/anonymized.csv
Encrypted mapping: runs/manual/mapping.enc.json
Anonymized report: runs/manual/model_report.anonymized.md
Restored report: runs/manual/model_report.restored.md
```

- [ ] **Step 4: Verify no raw fixture values crossed model boundary**

Run:

```bash
python - <<'PY'
from pathlib import Path

raw_values = [
    "张三",
    "李四",
    "王五",
    "11010119900307001X",
    "华东销售一部",
    "上海春雷科技有限公司",
    "13800138000",
    "zhangsan@example.com",
]
checked_files = [
    Path("runs/manual/anonymized.csv"),
    Path("runs/manual/model_prompt.anonymized.md"),
    Path("runs/manual/model_report.anonymized.md"),
]
for file in checked_files:
    text = file.read_text(encoding="utf-8")
    leaked = [value for value in raw_values if value in text]
    if leaked:
        raise SystemExit(f"{file} leaked raw values: {leaked}")
print("privacy boundary verified")
PY
```

Expected:

```text
privacy boundary verified
```

- [ ] **Step 5: Verify restored report contains original values**

Run:

```bash
python - <<'PY'
from pathlib import Path

text = Path("runs/manual/model_report.restored.md").read_text(encoding="utf-8")
assert "张三" in text
assert "华东销售一部" in text
assert "上海春雷科技有限公司" in text
print("restored report verified")
PY
```

Expected:

```text
restored report verified
```

- [ ] **Step 6: Commit**

```bash
git add README.md
git commit -m "docs: document privacy data agent workflow"
```

---

## Self-Review

**Spec coverage:**

- Local anonymization before model call: Task 3 and Task 6.
- Personal sensitive information: Task 2 detector rules and Task 3 anonymization.
- Names, ID numbers, departments, customer names: Task 2 detector rules and Task 3 tests.
- Matching file generation: Task 4 encrypted `mapping.enc.json`.
- Send anonymized data to model for report: Task 5 provider interface and Task 6 pipeline.
- Restore customers, employee names, and departments locally after analysis: Task 5 restorer and Task 6 end-to-end assertions.
- CLI agent behavior: Task 7.
- Real model adapter: Task 8.
- Verification and documentation: Task 9.

**Placeholder scan:** The plan avoids `TBD`, empty error-handling instructions, and vague test requests. Each implementation task provides exact files, code, commands, and expected results.

**Type consistency:** `EntityType`, `MappingEntry`, `MappingFile`, `AnalysisResult`, `RunArtifacts`, `ModelProvider`, `FakeModelProvider`, `OpenAIModelProvider`, `anonymize_dataframe`, `save_mapping_file`, `load_mapping_file`, `restore_report`, and `run_analysis` are named consistently across tests and implementation steps.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-01-privacy-data-agent.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
