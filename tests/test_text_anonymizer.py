from privacy_data_agent.text_anonymizer import TextAnonymizeResult, anonymize_text


def test_anonymize_text_empty_string_not_replaced():
    result = anonymize_text("")
    assert isinstance(result, TextAnonymizeResult)
    assert result.text == ""
    assert result.replaced is False
    assert result.mapping.entries == []


def test_anonymize_text_detects_and_replaces_entity():
    # "姓名：X" 走 LABELED_CHINESE_NAME_RE 精确匹配，不受内嵌人名扫描器
    # 贪婪启发式（对无标签长句可能吃入相邻字符）的影响，是确定性用例。
    result = anonymize_text("姓名：张三")
    assert result.replaced is True
    assert "张三" not in result.text
    assert result.text.count("PDA_") == 1
    assert any(entry.original == "张三" for entry in result.mapping.entries)


def test_anonymize_text_seed_mapping_keeps_token_consistent():
    first = anonymize_text("姓名：张三")
    token = next(e.token for e in first.mapping.entries if e.original == "张三")

    second = anonymize_text("姓名：张三", seed_mapping=first.mapping)
    assert token in second.text
    # 同一原文在跨调用后仍只对应一个 token，不重复生成
    assert sum(1 for e in second.mapping.entries if e.original == "张三") == 1


def test_anonymize_text_none_raises_type_error():
    import pytest

    with pytest.raises(TypeError):
        anonymize_text(None)


def test_anonymize_text_does_not_mangle_lishi_shuju():
    # 已知 bug（2026-08-09 jarvis 管道联调发现）：内嵌人名扫描器把"历史数据"
    # 里的"史"当成姓氏锚点，3字候选"史数据"被 JOB_TITLE_TERM_BLACKLIST
    # （"数据"在其中）正确拒绝后，回退尝试2字候选"史数"——但2字候选缺少
    # 任何黑名单校验，被当成人名替换掉，导致"查了历史数据"变成
    # "查了历PDA_xxxx"，文字残缺。
    result = anonymize_text("查了历史数据")
    assert "历史数据" in result.text
    assert result.replaced is False
