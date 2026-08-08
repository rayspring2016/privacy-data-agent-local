from __future__ import annotations

import re

from pydantic import BaseModel

from privacy_data_agent.anonymizer import AnonymizerState
from privacy_data_agent.detectors import detect_cell_entity_type, SURNAME_SET, _looks_like_chinese_name
from privacy_data_agent.models import EntityType, MappingFile


class TextAnonymizeResult(BaseModel):
    text: str
    mapping: MappingFile
    replaced: bool


DOCUMENT_ENTITY_PATTERNS: tuple[tuple[re.Pattern[str], EntityType], ...] = (
    (re.compile(r"(?<!\d)\d{17}[\dXx](?![\dXx])"), EntityType.ID_NUMBER),
    (re.compile(r"(?<![\dA-Za-z])(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)"), EntityType.PHONE),
    (
        re.compile(r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![A-Za-z])"),
        EntityType.EMAIL,
    ),
    (
        re.compile(r"(?<![A-Z0-9一-龥])[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉贵粤青藏川宁琼使领][A-Z][A-Z0-9]{5}(?![A-Z0-9])"),
        EntityType.LICENSE_PLATE,
    ),
    (re.compile(r"(?<![A-Za-z0-9])[A-Za-z]{1,3}\d{4,10}(?![A-Za-z0-9])"), EntityType.EMPLOYEE_ID),
    (
        # Department names: pure Chinese (e.g. "技术部", "产品研发中心", "产品中心-设计部")
        re.compile(
            r"(?<![一-龥A-Za-z0-9])"
            r"[一-龥]{1,8}"
            r"(?:事业部|中心|[部组处科室]|大区|区域)"
            r"(?:[-/／\\][一-龥]{1,8}(?:事业部|中心|[部组处科室]|大区|区域))*"
            r"(?![门分署落位件队族首])",
        ),
        EntityType.DEPARTMENT,
    ),
    (
        # Department names with ASCII prefix, allowed after Chinese text (e.g. "AI 数据部", "在AI数据部")
        re.compile(
            r"(?<![A-Za-z0-9])"
            r"[A-Za-z]{1,4} ?"
            r"[一-龥]{1,8}"
            r"(?:事业部|中心|[部组处科室]|大区|区域)"
            r"(?:[-/／\\][一-龥]{1,8}(?:事业部|中心|[部组处科室]|大区|区域))*"
            r"(?![门分署落位件队族首])",
        ),
        EntityType.DEPARTMENT,
    ),
)
LABELED_CHINESE_NAME_RE = re.compile(
    r"(?:姓名|员工|成员|人员|负责人|联系人|对接人|客户经理|顾问|name|employee|owner|manager)(?:\s*[:：=]\s*|\s+)([一-龥]{2,4})",
    re.IGNORECASE,
)

# 内嵌人名扫描器：用百家姓单字作锚点，在段落正文中识别 姓+名（2-4字）
# 只用单字姓，避免复姓/双姓组合被误拆
_SINGLE_SURNAMES = sorted(
    (s for s in SURNAME_SET if len(s) == 1),
    key=lambda x: -len(x),  # 长的优先（未来兼容，当前均1字）
)

# 内嵌扫描时排除高频普通词（避免 文件/方法/高兴/严格 等被当作姓触发误匹配）
_INLINE_ANCHOR_EXCLUDE = frozenset({
    "文", "方", "明", "白", "武", "易", "常", "余", "万",
    "全", "司", "步", "习", "关", "连", "强", "石", "金",
    "高", "向", "温", "安", "路", "盛", "谷",  # 形容词/名词/介词
    "严", "纪", "党",  # 常见词：严格/纪要/党委（加入避免大量误报）
})
_INLINE_SINGLE_SURNAMES: frozenset[str] = frozenset(
    s for s in _SINGLE_SURNAMES if s not in _INLINE_ANCHOR_EXCLUDE
)

# 常见职务/头衔后缀：当一个"看起来像名字"的串以这些结尾时，跳过（如 张总监、董事长）
_NAME_TITLE_SUFFIXES: frozenset[str] = frozenset({
    "总监", "经理", "主任", "主席", "总裁", "总理", "书记", "委员",
    "处长", "科长", "队长", "组长", "班长", "部长", "局长", "院长",
    "所长", "校长", "厂长", "站长", "理事", "事长", "事会",
    "顾问", "秘书", "助理", "专员", "工程", "设计", "分析",
    "总经", "副总", "董事",
})

# 内嵌扫描右侧裁剪集：匹配到的名字若以这些字符结尾，说明贪婪吃入了后续内容
# 包含所有单字百家姓（下一个人名的姓）+ 常见连词/虚词
_INLINE_RIGHT_TRIM: frozenset[str] = frozenset(
    {s for s in SURNAME_SET if len(s) == 1}
    | set("的了和或与及而且也被从让到把如虽然虽")
)

# 名字列表分隔符（"张三、李四；王五，赵六"格式中的分隔字符）
_LIST_DELIMITERS: frozenset[str] = frozenset("、，；：。\n\r\t -–—")

# 用于名字列表段落识别的连续汉字模式（2-4字）
_SEGMENT_RE = re.compile(r"[一-龥]{2,4}")


CHINESE_NAME_RE = re.compile(r"^[一-龥]{2,4}$")
DOCUMENT_LABEL_WORDS = frozenset(
    {
        "姓名", "员工", "成员", "人员", "负责人", "联系人", "对接人",
        "客户经理", "顾问", "岗位", "部门", "总分", "人数",
        "人均", "人次", "人效", "人天", "指标", "结果",
        "月份", "限制", "影响", "说明", "项目", "来源",
        "平均", "考勤", "需求", "价值", "备注", "记录",
        "信号", "出现", "次数", "处理", "计算", "数据",
        "文件", "方法", "身份", "脱敏", "样本", "有效",
        "编号", "姓名编码", "组织", "组别", "中心",
        "区域", "大区", "事业部", "日期", "期间", "生成",
        "报告", "口径", "格式", "来源文件", "主数据表",
        "辅助表", "总分计算", "缺失处理", "需求价值",
        "样本人数", "有效人数", "平均总分", "考勤均分",
        "需求价值分", "考勤分", "中位数", "最高分",
        "最低分", "平均分", "记录数", "信号类型",
        "出现次数", "身份脱敏", "任务周期", "优化",
        "测试等待", "交付链路", "回源解读", "管理含义",
        "建议动作", "附录", "字段", "类型",
        # Department label rows that are not actual department names
        "二级部门", "一级部门", "所属部门", "部门名称",
        "二级部门（脱敏）", "部门（脱敏）",
        # Column headers
        "阅读提示", "核心结论", "数据范围", "计算方法",
        "月度趋势", "当前月", "人员名单", "高分样本",
        "低分样本", "部门观察", "岗位观察", "低分备注",
        "风险信号", "核算过程", "摘要", "字段限制",
        "限制说明", "计算公式", "数据来源", "统计口径",
    }
)


def _entity_spans(text: str) -> list[tuple[int, int, EntityType, str]]:
    """Entity detection for inline text (no per-line context)."""
    if not text:
        return []

    candidates: list[tuple[int, int, EntityType, str]] = []

    # Document entity patterns first — department regex takes priority
    # over generic Chinese-name matching for terms like "技术部".
    for pattern, entity_type in DOCUMENT_ENTITY_PATTERNS:
        for match in pattern.finditer(text):
            candidates.append((match.start(), match.end(), entity_type, match.group(0)))

    stripped = text.strip()
    if stripped and stripped not in DOCUMENT_LABEL_WORDS:
        entity_type = detect_cell_entity_type(stripped)
        if entity_type:
            start = len(text) - len(text.lstrip())
            candidates.append((start, start + len(stripped), entity_type, stripped))

    for match in LABELED_CHINESE_NAME_RE.finditer(text):
        name = match.group(1)
        if name not in DOCUMENT_LABEL_WORDS:
            candidates.append((match.start(1), match.end(1), EntityType.EMPLOYEE, name))

    # ── 内嵌人名扫描（百家姓锚点，安全子集）──────────────────────────────
    # 最长优先（4→3→2）+ 右侧裁剪：遇到下一个姓或连词就缩短
    # 仅对长段落，且只用不易误报的安全姓氏子集（_INLINE_SINGLE_SURNAMES）
    if len(stripped) > 4:
        i = 0
        while i < len(text):
            if text[i] in _INLINE_SINGLE_SURNAMES:
                matched = False
                for name_len in (4, 3, 2):          # 最长优先
                    end = i + name_len
                    if end > len(text):
                        continue
                    name = text[i:end]
                    # 右侧裁剪：遇到姓氏字或连词则缩短
                    while len(name) > 2 and name[-1] in _INLINE_RIGHT_TRIM:
                        name = name[:-1]
                    if not (
                        CHINESE_NAME_RE.match(name)     # 全汉字
                        and _looks_like_chinese_name(name)
                        and name not in DOCUMENT_LABEL_WORDS
                        and not any(name.endswith(s) for s in _NAME_TITLE_SUFFIXES)
                    ):
                        continue
                    candidates.append((i, i + len(name), EntityType.EMPLOYEE, name))
                    i += len(name)
                    matched = True
                    break
                if not matched:
                    i += 1
            else:
                i += 1

    # ── 标点分隔名字列表扫描 ──────────────────────────────────────────────
    # 识别 "张三、李四；常五盛六" 这类用中文标点分隔的名字列表
    # 使用完整 SURNAME_SET（含常/盛等），前后都是分隔符时才触发
    for seg_m in _SEGMENT_RE.finditer(text):
        seg = seg_m.group(0)
        start, end = seg_m.start(), seg_m.end()
        before = text[start - 1] if start > 0 else "\n"
        after = text[end] if end < len(text) else "\n"
        if before in _LIST_DELIMITERS and after in _LIST_DELIMITERS:
            if (
                _looks_like_chinese_name(seg)
                and seg not in DOCUMENT_LABEL_WORDS
                and not any(seg.endswith(s) for s in _NAME_TITLE_SUFFIXES)
            ):
                candidates.append((start, end, EntityType.EMPLOYEE, seg))

    accepted: list[tuple[int, int, EntityType, str]] = []
    for candidate in sorted(candidates, key=lambda item: (item[0], -(item[1] - item[0]))):
        start, end, _, _ = candidate
        if any(start < accepted_end and end > accepted_start for accepted_start, accepted_end, _, _ in accepted):
            continue
        accepted.append(candidate)
    return sorted(accepted, key=lambda item: item[0])


def register_entities_in_text(text: str, state: AnonymizerState) -> None:
    for _, _, entity_type, original in _entity_spans(text):
        state.token_for(entity_type, original)

    # Additional per-line scan: PDF text extraction often places names
    # on their own line via get_text("text"), where CHINESE_NAME_RE works.
    for line in text.split("\n"):
        line_stripped = line.strip()
        if (
            CHINESE_NAME_RE.match(line_stripped)
            and line_stripped not in DOCUMENT_LABEL_WORDS
        ):
            state.token_for(EntityType.EMPLOYEE, line_stripped)


def replace_entities_in_text(text: str, state: AnonymizerState) -> tuple[str, bool]:
    spans = _entity_spans(text)
    if not spans:
        return text, False

    parts: list[str] = []
    cursor = 0
    for start, end, entity_type, original in spans:
        parts.append(text[cursor:start])
        parts.append(state.token_for(entity_type, original))
        cursor = end
    parts.append(text[cursor:])
    return "".join(parts), True


def anonymize_text(text: str, seed_mapping: MappingFile | None = None) -> TextAnonymizeResult:
    """纯文本脱敏公开入口。text 为 None 时抛 TypeError——None 是类型错误，
    不是"没有内容"的合法输入，调用方必须显式处理。"""
    if text is None:
        raise TypeError("anonymize_text() text must be str, not None")

    state = AnonymizerState(seed_mapping=seed_mapping)
    replaced_text, replaced = replace_entities_in_text(text, state)
    return TextAnonymizeResult(
        text=replaced_text,
        mapping=state.to_mapping_file(),
        replaced=replaced,
    )
