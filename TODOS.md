# TODOS

## [P3] cli anonymize 处理 .pdf 时裸崩

**What:** `cli anonymize x.pdf` 无论传不传任何开关都会抛未捕获的 `ValueError: Unsupported input file type: .pdf`，而不是友好提示。

**Why:** `pipeline.py:17-26` 的 `read_input_table` 只处理 `.csv`/`.xlsx`/`.docx` 三种后缀，`.pdf` 落到兜底的 `raise ValueError(...)`。但 `document_anonymizer.py` 里确实有 `anonymize_pdf_bytes`，只是这条路径只接在 Streamlit UI（`web_helpers.py`），CLI 从未调用它。

**Pros:** 修好后 CLI 与 Streamlit UI 的格式支持能力对齐；用户不再看到裸 traceback。

**Cons:** 需要先决定修复方向——是把 `anonymize_pdf_bytes` 接进 CLI（涉及坐标级替换逻辑，回归面较大），还是仅仅把这个 `ValueError` 包装成更友好的 `typer.Exit(1)` 提示（"CLI 暂不支持 PDF，请用 Web UI"）。两种方案设计取舍不同。

**Context:** 2026-08-08 `/plan-eng-review` 审查「PDA 薪资分组开关」计划（Phase 1）时，独立 subagent 交叉验证 T6 的立论依据时顺带发现。与薪资分组这个计划的目标完全无关，纯属旁支发现。发现路径：`pipeline.py:17-26` 无 `.pdf` 分支。

**Effort:** S(human) → S(CC)

**Priority:** P3

**Depends on / blocked by:** 无
