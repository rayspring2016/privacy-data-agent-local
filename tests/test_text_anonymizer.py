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


# ── 2026-08-09 jarvis 网关+codex 记忆管道联调发现：内嵌人名扫描器对
# AI 生成的自然语言长句系统性误报——不是"历史数据"一个孤例。用真实
# 抓到的原文（从 gateway_capture.py/codex_capture.py 联调时的映射表
# 反解还原）做回归用例，每个锚点字符出现在了当时的产出笔记里，
# 已验证是常见虚词/动词/名词，不该被当成姓氏用。
_KNOWN_FALSE_POSITIVE_SENTENCES = [
    "让我搜索一下相关的知识库信息",
    "我需要了解一下相关的内容背景",
    "让我查一下相关数据源",
    "这是基于公司既有的相关分析",
    "这部分单一源软件需要单独保留",
    "整个流程体验和过程与管理有关",
    "涉及公司的公积金与采购流程",
    "费用之类的费用需要单独核算",
    "确认终端的唯一标识符",
    "根据董秘办的要求处理会议纪要",
    "文件已经打印在法务的柜子里",
    "书与阅读相关的包与资料清单",
    "把内容平铺展开来看",
]


def test_anonymize_text_does_not_mangle_known_false_positive_sentences():
    for sentence in _KNOWN_FALSE_POSITIVE_SENTENCES:
        result = anonymize_text(sentence)
        assert result.replaced is False, f"误判触发: {sentence!r} -> {result.text!r}"
        assert result.text == sentence


def test_anonymize_text_matches_shortest_valid_name_not_greedy_longest():
    # 已知 bug：贪婪的"最长优先(4→3→2)"策略会把正确的短匹配"张三"
    # 继续往右吃，吃成错误的"张三加薪"（"加薪"两字被误吞）。
    # 改成"最短优先"后，"张三"一旦通过校验就应该立刻采用，不再尝试更长候选。
    result = anonymize_text("张三加薪到25000，帮我分析一下")
    token = next(e.token for e in result.mapping.entries)
    original = next(e.original for e in result.mapping.entries)
    assert original == "张三"
    assert "加薪到25000" in result.text
    assert result.text == f"{token}加薪到25000，帮我分析一下"
