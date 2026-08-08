import pandas as pd
import pytest

from privacy_data_agent.aggregator import aggregate_dataframe, aggregate_file
from privacy_data_agent.detectors import SalaryGroup


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "姓名": ["张伟", "李娜", "王芳", "赵磊"],
            "部门": ["技术部", "技术部", "技术部", "销售部"],
            "人力成本": [31000, 22500, 27500, 20000],
        }
    )


def test_aggregate_suppresses_group_below_min_size():
    """技术部3人（达标），销售部1人（不足）——只有销售部被拒绝输出数字。"""
    df = _sample_df()
    result = aggregate_dataframe(df, group_by=["部门"], salary_groups=[SalaryGroup.LABOR_COST], min_group_size=3)

    rows = result.dataframe.set_index("部门")
    assert rows.loc["技术部", "人力成本_总额"] == 81000
    assert rows.loc["技术部", "人力成本_均值"] == pytest.approx(27000.0)
    assert "样本不足" in str(rows.loc["销售部", "人力成本_总额"])
    assert "样本不足" in str(rows.loc["销售部", "人力成本_均值"])
    # 人数本身不受阈值限制，照常显示
    assert rows.loc["销售部", "样本人数"] == 1
    assert result.suppressed_group_count == 1


def test_aggregate_never_produces_individual_rows():
    """输出行数应等于分组数，不等于个人数——个人数据不落盘。"""
    df = _sample_df()
    result = aggregate_dataframe(df, group_by=["部门"], salary_groups=[SalaryGroup.LABOR_COST], min_group_size=1)

    assert len(result.dataframe) == 2  # 两个部门，不是四个人
    assert "姓名" not in result.dataframe.columns
    assert "张伟" not in result.dataframe.to_string()


def test_aggregate_multiple_group_by_columns():
    df = _sample_df()
    df["岗位"] = ["工程师", "工程师", "经理", "销售"]
    result = aggregate_dataframe(
        df, group_by=["部门", "岗位"], salary_groups=[SalaryGroup.LABOR_COST], min_group_size=1
    )
    assert len(result.dataframe) == 3  # (技术部,工程师) (技术部,经理) (销售部,销售)


def test_aggregate_multiple_salary_groups():
    df = _sample_df()
    df["餐补"] = [500, 500, 500, 500]
    result = aggregate_dataframe(
        df,
        group_by=["部门"],
        salary_groups=[SalaryGroup.LABOR_COST, SalaryGroup.ALLOWANCE],
        min_group_size=1,
    )
    assert "人力成本_总额" in result.dataframe.columns
    assert "餐补_总额" in result.dataframe.columns


def test_aggregate_rejects_unknown_group_by_column():
    df = _sample_df()
    with pytest.raises(ValueError, match="不存在于源文件"):
        aggregate_dataframe(df, group_by=["不存在的列"], salary_groups=[SalaryGroup.LABOR_COST])


def test_aggregate_rejects_when_no_matching_salary_columns():
    df = pd.DataFrame({"部门": ["技术部"], "备注": ["无薪资列"]})
    with pytest.raises(ValueError, match="没有找到"):
        aggregate_dataframe(df, group_by=["部门"], salary_groups=[SalaryGroup.LABOR_COST])


def test_aggregate_file_rejects_non_tabular_format(tmp_path):
    docx_path = tmp_path / "input.docx"
    docx_path.write_bytes(b"not a real docx")
    with pytest.raises(ValueError, match="只支持 xlsx/csv"):
        aggregate_file(
            docx_path,
            tmp_path / "out.csv",
            group_by=["部门"],
            salary_groups=[SalaryGroup.LABOR_COST],
        )


def test_aggregate_file_writes_csv_output(tmp_path):
    input_path = tmp_path / "input.csv"
    _sample_df().to_csv(input_path, index=False)
    output_path = tmp_path / "out" / "aggregate.csv"

    result = aggregate_file(
        input_path,
        output_path,
        group_by=["部门"],
        salary_groups=[SalaryGroup.LABOR_COST],
        min_group_size=1,
    )

    assert output_path.exists()
    written = pd.read_csv(output_path)
    assert len(written) == len(result.dataframe)
