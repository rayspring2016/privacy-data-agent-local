"""Golden regression baseline for SALARY column anonymization.

Anonymization tokens are random per run (secrets.token_hex), so this cannot
snapshot literal output values. Instead it pins the invariant that must
survive the SALARY-into-groups split (T4): under DEFAULT config (no
--keep-salary-group passed), every salary-related column continues to be
fully anonymized, exactly like today's single ungrouped SALARY type.

If this test goes red after T4/T5, the split changed default-safe behavior —
that is exactly the silent drift this fixture exists to catch.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from privacy_data_agent.workbook_anonymizer import anonymize_xlsx_file

FIXTURE = Path(__file__).parent / "fixtures" / "golden_sample.xlsx"

# Original values from the fixture, keyed by column. Under default config,
# none of these should appear anywhere in the anonymized output.
ORIGINAL_VALUES = {
    "姓名": ["张伟", "李娜", "王芳"],
    "工号": ["EMP0001", "EMP0002", "EMP0003"],
    "部门": ["技术部", "人力资源部", "销售部"],
    "手机号": ["13800138000", "13900139000", "13700137000"],
    "月薪": ["25000", "18000", "22000"],
    "社保公积金": ["6000", "4500", "5500"],
    "人力成本": ["31000", "22500", "27500"],
    "餐补": ["500", "500", "500"],
    "提成": ["3000", "0", "8000"],
    "绩效奖金": ["5000", "3000", "6000"],
}

SALARY_COLUMNS = ("月薪", "社保公积金", "人力成本", "餐补", "提成", "绩效奖金")


def test_default_config_anonymizes_all_salary_columns(tmp_path):
    out = tmp_path / "anonymized.xlsx"
    anonymize_xlsx_file(FIXTURE, out)
    result = pd.read_excel(out)

    for column in SALARY_COLUMNS:
        for original in ORIGINAL_VALUES[column]:
            assert str(original) not in result[column].astype(str).values, (
                f"{column!r} leaked original value {original!r} under default config "
                "— salary grouping must not weaken the default (no flags) behavior"
            )


def test_default_config_anonymizes_person_and_department_columns(tmp_path):
    """Non-salary columns are outside this plan's scope; pin them so an
    unrelated regression elsewhere doesn't slip in unnoticed alongside T4."""
    out = tmp_path / "anonymized.xlsx"
    anonymize_xlsx_file(FIXTURE, out)
    result = pd.read_excel(out)

    for column in ("姓名", "工号", "部门", "手机号"):
        for original in ORIGINAL_VALUES[column]:
            assert str(original) not in result[column].astype(str).values, (
                f"{column!r} leaked original value {original!r} — unrelated to this "
                "plan's scope but the golden baseline pins it anyway"
            )


def test_tokens_are_consistent_within_a_run(tmp_path):
    """Same original value in the same entity role must map to the same
    token within a single run (e.g. 餐补=500 appears identically for all
    three rows). If the split breaks this, mapping tables become unusable."""
    out = tmp_path / "anonymized.xlsx"
    anonymize_xlsx_file(FIXTURE, out)
    result = pd.read_excel(out)

    # 餐补 is 500 for all three rows in the fixture — must anonymize to the
    # same token every time.
    tokens = result["餐补"].astype(str).tolist()
    assert len(set(tokens)) == 1, f"same original value produced different tokens: {tokens}"
