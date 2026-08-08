"""本地聚合：成本/人效分析专用。

跟 anonymizer.py 系列完全不同的安全模型——那边是"个人数据留在文件里，
但换成代号"；这边是"个人数据从不产出，只产出聚合后的数字"。整个函数
只读原始文件，从不调用 anonymize_dataframe，输出里没有任何一行个人数据，
只有分组标签 + 求和/均值/计数。

k-匿名保护：分组人数低于 min_group_size 时，该分组的 sum/mean 一律拒绝
输出（哪怕只差一步），因为小分组的汇总数约等于个人工资，聚合形同虚设。
count 本身不受阈值限制——部门人数通常不算敏感信息，且是判断"数据可信吗"
的必要上下文。
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from pydantic import BaseModel, ConfigDict

from privacy_data_agent.detectors import SalaryGroup, resolve_salary_group
from privacy_data_agent.pipeline import read_input_table

SUPPRESSED_LABEL = "样本不足（<{min_group_size}人），已拒绝输出"


class AggregateResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    dataframe: pd.DataFrame
    suppressed_group_count: int  # 因人数不足被拒绝输出的分组数


def _salary_columns_for_groups(columns: list[str], salary_groups: list[SalaryGroup]) -> list[str]:
    wanted = set(salary_groups)
    matched: list[str] = []
    for column in columns:
        group = resolve_salary_group(str(column))
        if group is not None and group in wanted:
            matched.append(str(column))
    return matched


def aggregate_dataframe(
    df: pd.DataFrame,
    group_by: list[str],
    salary_groups: list[SalaryGroup],
    min_group_size: int = 3,
) -> AggregateResult:
    missing_group_by = [col for col in group_by if col not in df.columns]
    if missing_group_by:
        raise ValueError(f"--group-by 指定的列不存在于源文件: {missing_group_by}")

    salary_columns = _salary_columns_for_groups(list(df.columns), salary_groups)
    if not salary_columns:
        raise ValueError(
            f"源文件里没有找到属于 {[g.value for g in salary_groups]} 组的薪资列"
        )

    numeric = df[salary_columns].apply(pd.to_numeric, errors="coerce")
    working = pd.concat([df[group_by], numeric], axis=1)

    grouped = working.groupby(group_by, dropna=False)
    counts = grouped.size().rename("样本人数")
    sums = grouped[salary_columns].sum().add_suffix("_总额")
    means = grouped[salary_columns].mean().add_suffix("_均值")

    result = pd.concat([counts, sums, means], axis=1).reset_index()

    suppressed_mask = result["样本人数"] < min_group_size
    suppressed_group_count = int(suppressed_mask.sum())
    value_columns = [c for c in result.columns if c.endswith("_总额") or c.endswith("_均值")]
    label = SUPPRESSED_LABEL.format(min_group_size=min_group_size)
    # 聚合列原本是数字 dtype，塞入拒绝提示字符串前先转 object，否则新版 pandas
    # 会因为类型不兼容直接报 TypeError（而不是静默转换）
    result[value_columns] = result[value_columns].astype(object)
    result.loc[suppressed_mask, value_columns] = label

    return AggregateResult(dataframe=result, suppressed_group_count=suppressed_group_count)


def aggregate_file(
    input_path: str | Path,
    output_path: str | Path,
    group_by: list[str],
    salary_groups: list[SalaryGroup],
    min_group_size: int = 3,
    header_row: int | None = None,
) -> AggregateResult:
    suffix = Path(input_path).suffix.lower()
    if suffix not in (".xlsx", ".csv"):
        raise ValueError(f"aggregate 只支持 xlsx/csv（表格数据），不支持 {suffix}")

    df = read_input_table(input_path, header_row=header_row)
    result = aggregate_dataframe(df, group_by=group_by, salary_groups=salary_groups, min_group_size=min_group_size)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    result.dataframe.to_csv(output, index=False)
    return result
