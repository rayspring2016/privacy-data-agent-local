from privacy_data_agent.llm_client import build_analysis_prompt


def test_build_analysis_prompt_contains_only_anonymized_csv():
    prompt = build_analysis_prompt(
        anonymized_csv="员工姓名,部门\nPDA_AAAAAAAAAAAAAAAA,PDA_BBBBBBBBBBBBBBBB\n",
        instruction="请分析风险。",
    )

    assert "请分析风险。" in prompt
    assert "PDA_AAAAAAAAAAAAAAAA" in prompt
    assert "PDA_BBBBBBBBBBBBBBBB" in prompt
    assert "张三" not in prompt
