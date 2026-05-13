from __future__ import annotations
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import re

import pandas as pd
from docx import Document

from privacy_data_agent.anonymizer import AnonymizerState
from privacy_data_agent.detectors import detect_cell_entity_type, SURNAME_SET, _looks_like_chinese_name
from privacy_data_agent.models import EntityType, MappingFile


@dataclass
class DocumentAnonymizeResult:
    workbook_bytes: bytes  # docx: docx bytes; pdf: modified pdf bytes
    mapping: MappingFile
    row_count: int  # number of entities found


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


def _register_entities_in_text(text: str, state: AnonymizerState) -> None:
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


def _replace_entities_in_text(text: str, state: AnonymizerState) -> tuple[str, bool]:
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


def _extract_page_text_multi(page) -> str:
    """Try every available method to extract text from a PDF page."""
    results: list[str] = []

    # Method 1: standard text extraction
    text = page.get_text("text") or ""
    if text.strip():
        results.append(text)

    # Method 2: raw dict — iterate all chars to reconstruct text
    try:
        raw = page.get_text("rawdict")
        chars: list[str] = []
        for block in raw.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    for char in span.get("chars", []):
                        c = char.get("c", "")
                        if c:
                            chars.append(c)
                chars.append("\n")
        raw_text = "".join(chars).strip()
        if raw_text:
            results.append(raw_text)
    except Exception:
        pass

    # Method 3: text as XML and extract text nodes
    try:
        xml = page.get_text("xml")
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml)
        xml_parts: list[str] = []
        for elem in root.iter():
            if elem.text and elem.text.strip():
                xml_parts.append(elem.text.strip())
        xml_text = "\n".join(xml_parts)
        if xml_text and xml_text not in results:
            results.append(xml_text)
    except Exception:
        pass

    return "\n".join(results)


def _find_entity_in_span(span_text: str, token_by_original: dict[str, str]) -> str | None:
    """Check if span_text (or a cleaned variant) matches a known entity."""
    if span_text in token_by_original:
        return span_text
    # Also try LABELED_CHINESE_NAME_RE to extract name from "姓名：张三"
    for match in LABELED_CHINESE_NAME_RE.finditer(span_text):
        name = match.group(1)
        if name in token_by_original:
            return name
    return None


def _locate_entity_chars(
    span_chars: list[tuple[str, object]],
    span_text: str,
    original: str,
) -> list[tuple[str, object]]:
    """Find the character subset in span_chars that corresponds to original text."""
    pos = span_text.find(original)
    if pos < 0:
        return []
    return span_chars[pos : pos + len(original)]


def _anonymize_pdf_with_pymupdf(content: bytes, seed_mapping: MappingFile | None = None) -> DocumentAnonymizeResult:
    import fitz

    state = AnonymizerState(seed_mapping=seed_mapping)
    doc = fitz.open(stream=content, filetype="pdf")

    # Pass 1: register all entities across all pages using multi-method extraction
    for page in doc:
        text = _extract_page_text_multi(page)
        if text:
            _register_entities_in_text(text, state)

    # Build lookup: token by original text
    token_by_original: dict[str, str] = {}
    for entry in state.entries:
        token_by_original[entry.original] = entry.token

    # Pass 2: position-driven redaction. Use direct text matching:
    # for each span, check if its text (exact or cleaned) matches
    # a known entity from Pass 1. Also check line-level for
    # entities that span across multiple spans.
    redactions_by_page: dict[int, list[tuple[fitz.Rect, str]]] = {}
    _redacted: set[tuple[int, float, float, float, float]] = set()

    for page_index, page in enumerate(doc):
        try:
            raw = page.get_text("rawdict")
        except Exception:
            continue

        for block in raw.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                # --- Span-level: direct text lookup ---
                for span in line.get("spans", []):
                    span_chars = []
                    for char in span.get("chars", []):
                        c = char.get("c", "")
                        bbox = char.get("bbox")
                        if c and bbox:
                            span_chars.append((c, fitz.Rect(bbox)))
                    if not span_chars:
                        continue

                    span_text = "".join(c for c, _ in span_chars)
                    original = _find_entity_in_span(span_text, token_by_original)
                    if original is None:
                        continue

                    token = token_by_original[original]
                    entity_chars = _locate_entity_chars(span_chars, span_text, original)
                    if not entity_chars:
                        continue
                    x0 = min(bbox.x0 for _, bbox in entity_chars)
                    y0 = min(bbox.y0 for _, bbox in entity_chars)
                    x1 = max(bbox.x1 for _, bbox in entity_chars)
                    y1 = max(bbox.y1 for _, bbox in entity_chars)
                    _key = (page_index, x0, y0, x1, y1)
                    if _key in _redacted:
                        continue
                    _redacted.add(_key)
                    redact_rect = fitz.Rect(x0, y0 - 1, x1, y1 + 1)
                    redactions_by_page.setdefault(page_index, []).append((redact_rect, token))
                    page.add_redact_annot(redact_rect, fill=(1, 1, 1))

                # --- Line-level: for entities spanning multiple spans ---
                line_chars = []
                for span in line.get("spans", []):
                    for char in span.get("chars", []):
                        c = char.get("c", "")
                        bbox = char.get("bbox")
                        if c and bbox:
                            line_chars.append((c, fitz.Rect(bbox)))
                if not line_chars:
                    continue

                line_text = "".join(c for c, _ in line_chars)
                for orig_text, token in token_by_original.items():
                    pos = line_text.find(orig_text)
                    if pos < 0:
                        continue
                    entity_chars = line_chars[pos:pos + len(orig_text)]
                    x0 = min(bbox.x0 for _, bbox in entity_chars)
                    y0 = min(bbox.y0 for _, bbox in entity_chars)
                    x1 = max(bbox.x1 for _, bbox in entity_chars)
                    y1 = max(bbox.y1 for _, bbox in entity_chars)
                    _key = (page_index, x0, y0, x1, y1)
                    if _key in _redacted:
                        continue
                    _redacted.add(_key)
                    redact_rect = fitz.Rect(x0, y0 - 1, x1, y1 + 1)
                    redactions_by_page.setdefault(page_index, []).append((redact_rect, token))
                    page.add_redact_annot(redact_rect, fill=(1, 1, 1))

    # Pass 3: apply redactions and insert replacement tokens
    for page_index, redactions in redactions_by_page.items():
        page = doc[page_index]
        page.apply_redactions()
        page_width = page.rect.width
        for rect, token in redactions:
            token_width = min(len(token) * 4.2 + 10, page_width - rect.x0 - 4)
            token_rect = fitz.Rect(
                rect.x0, rect.y0 - 1,
                rect.x0 + token_width, rect.y1 + 8,
            )
            page.insert_textbox(
                token_rect, token, fontsize=7, fontname="helv",
                color=(0, 0, 0), align=0,
            )

    return DocumentAnonymizeResult(
        workbook_bytes=doc.tobytes(garbage=4, deflate=True),
        mapping=state.to_mapping_file(),
        row_count=len(state.entries),
    )


def anonymize_docx_bytes(content: bytes, seed_mapping: MappingFile | None = None) -> DocumentAnonymizeResult:
    state = AnonymizerState(seed_mapping=seed_mapping)
    doc = Document(BytesIO(content))

    # Build a flat list of every paragraph-like element and its runs
    para_runs: list[list[object]] = []
    for para in doc.paragraphs:
        para_runs.append(list(para.runs))
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    para_runs.append(list(para.runs))

    # Pass 1: register entities from full paragraph text
    for runs in para_runs:
        full_text = "".join(run.text or "" for run in runs)
        if full_text.strip():
            _register_entities_in_text(full_text, state)

    # Build token lookup
    token_by_original: dict[str, str] = {}
    for entry in state.entries:
        token_by_original[entry.original] = entry.token

    # Pass 2: replace entities in individual runs
    for runs in para_runs:
        _replace_in_runs(runs, token_by_original)

    buf = BytesIO()
    doc.save(buf)
    return DocumentAnonymizeResult(
        workbook_bytes=buf.getvalue(),
        mapping=state.to_mapping_file(),
        row_count=len(state.entries),
    )


def _replace_in_runs(runs: list[object], token_by_original: dict[str, str]) -> None:
    """Replace known entity text with tokens across a paragraph's runs.

    Works on the paragraph-level full text first (so entities split across
    runs like "AI" + "数据部" are caught), then writes the result back
    into the first run, preserving the paragraph content.
    """
    if not runs or not token_by_original:
        return

    full_text = "".join(run.text or "" for run in runs)
    for orig_text, token in token_by_original.items():
        full_text = full_text.replace(orig_text, token)

    runs[0].text = full_text
    for run in runs[1:]:
        run.text = ""


def anonymize_pdf_bytes(content: bytes, seed_mapping: MappingFile | None = None) -> DocumentAnonymizeResult:
    try:
        return _anonymize_pdf_with_pymupdf(content, seed_mapping=seed_mapping)
    except ImportError:
        pass

    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import ArrayObject, ByteStringObject, ContentStream, TextStringObject

    state = AnonymizerState(seed_mapping=seed_mapping)
    reader = PdfReader(BytesIO(content))
    writer = PdfWriter()

    # First pass: extract text properly and detect entities
    all_lines: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            all_lines.extend(text.split("\n"))
        else:
            # Fallback: raw stream for text-based PDFs where extract_text fails
            try:
                if "/Contents" in page:
                    from pypdf.generic import ArrayObject

                    contents = page["/Contents"]
                    if isinstance(contents, ArrayObject):
                        for item in contents:
                            obj = item.get_object() if hasattr(item, "get_object") else item
                            raw = obj.get_data()
                            # Try utf-8-sig first (common for Chinese PDFs)
                            decoded = raw.decode("utf-8-sig", errors="")
                            if decoded.strip():
                                all_lines.extend(decoded.split("\n"))
                            else:
                                decoded = raw.decode("latin-1", errors="")
                                if decoded.strip():
                                    all_lines.extend(decoded.split("\n"))
            except Exception:
                pass

    for line in all_lines:
        _register_entities_in_text(line, state)

    def _replace_pdf_text_operand(operand):
        if isinstance(operand, TextStringObject):
            replaced, changed = _replace_entities_in_text(str(operand), state)
            return TextStringObject(replaced), changed
        if isinstance(operand, ByteStringObject):
            try:
                text = bytes(operand).decode("latin-1")
            except Exception:
                return operand, False
            replaced, changed = _replace_entities_in_text(text, state)
            return TextStringObject(replaced), changed
        return operand, False

    def _replace_page_text(page) -> None:
        contents = page.get_contents()
        if contents is None:
            return
        content_stream = ContentStream(contents, reader)
        changed = False
        for operands, operator in content_stream.operations:
            if operator in (b"Tj", b"'") and operands:
                operands[0], operand_changed = _replace_pdf_text_operand(operands[0])
                changed = changed or operand_changed
            elif operator == b'"' and operands:
                operands[-1], operand_changed = _replace_pdf_text_operand(operands[-1])
                changed = changed or operand_changed
            elif operator == b"TJ" and operands and isinstance(operands[0], ArrayObject):
                for index, item in enumerate(operands[0]):
                    operands[0][index], operand_changed = _replace_pdf_text_operand(item)
                    changed = changed or operand_changed
        if changed:
            page.replace_contents(content_stream)

    # Second pass: copy pages and replace text in parseable PDF content streams.
    for page in reader.pages:
        writer.add_page(page)
        _replace_page_text(writer.pages[-1])

    buf = BytesIO()
    writer.write(buf)
    return DocumentAnonymizeResult(
        workbook_bytes=buf.getvalue(),
        mapping=state.to_mapping_file(),
        row_count=len(state.entries),
    )
