from __future__ import annotations

from io import BytesIO
from pathlib import Path

import streamlit as st

from privacy_data_agent.web_helpers import anonymize_upload, restore_report_upload

VERSION = "1.14.1"

_DARK_THEME_CSS = """<style>
:root {
    --pda-primary: #D4887B;
    --pda-primary-hover: #DE9D93;
    --pda-primary-active: #C67A6E;
    --pda-primary-subtle: rgba(212,136,123,0.08);
    --pda-text: #F4F4F5;
    --pda-text-secondary: #A1A1AA;
    --pda-text-muted: #71717A;
    --pda-border: rgba(255,255,255,0.06);
    --pda-border-strong: rgba(255,255,255,0.10);
    --pda-bg: #0C0C0F;
    --pda-bg-secondary: #18181B;
    --pda-bg-tertiary: #1F1F23;
    --pda-success: #3DD68C;
    --pda-success-bg: rgba(61,214,140,0.08);
    --pda-success-border: rgba(61,214,140,0.14);
    --pda-success-text: #5FE09E;
    --pda-warning: #F59E0B;
    --pda-warning-bg: rgba(245,158,11,0.08);
    --pda-warning-border: rgba(245,158,11,0.14);
    --pda-warning-text: #FBBF24;
    --pda-error-bg: rgba(239,68,68,0.08);
    --pda-error-border: rgba(239,68,68,0.14);
    --pda-error-text: #F87171;
    --pda-info-bg: rgba(161,161,170,0.06);
    --pda-info-border: rgba(161,161,170,0.12);
    --pda-info-text: #D4D4D8;
    --pda-font: "Outfit", "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", system-ui, sans-serif;
    --pda-mono: "JetBrains Mono", "SFMono-Regular", "Consolas", "Liberation Mono", monospace;
}
[data-testid="stAppViewContainer"] {
    background:
        radial-gradient(ellipse 800px 300px at 50% 0%, rgba(212,136,123,0.04) 0%, transparent 60%),
        #09090B !important;
}
code { background: #18181B !important; }
.stButton > button:not([kind="primary"]):hover,
.stDownloadButton > button:not([kind="primary"]):hover,
[data-testid^="stBaseButton-"]:not([data-testid="stBaseButton-primary"]):hover { background: #27272A !important; }
</style>"""

_LIGHT_THEME_CSS = """<style>
:root {
    --pda-primary: #B55B4F;
    --pda-primary-hover: #C46E63;
    --pda-primary-active: #9E4E43;
    --pda-primary-subtle: rgba(181,91,79,0.06);
    --pda-text: #18181B;
    --pda-text-secondary: #71717A;
    --pda-text-muted: #A1A1AA;
    --pda-border: #E4E4E7;
    --pda-border-strong: #D4D4D8;
    --pda-bg: #FAFAFA;
    --pda-bg-secondary: #F4F4F5;
    --pda-bg-tertiary: #ECECEE;
    --pda-success: #2CA15B;
    --pda-success-bg: rgba(44,161,91,0.06);
    --pda-success-border: rgba(44,161,91,0.14);
    --pda-success-text: #166534;
    --pda-warning: #D97706;
    --pda-warning-bg: rgba(217,119,6,0.06);
    --pda-warning-border: rgba(217,119,6,0.14);
    --pda-warning-text: #92400E;
    --pda-error-bg: rgba(181,91,79,0.06);
    --pda-error-border: rgba(181,91,79,0.14);
    --pda-error-text: #991B1B;
    --pda-info-bg: rgba(113,113,122,0.05);
    --pda-info-border: rgba(113,113,122,0.12);
    --pda-info-text: #3F3F46;
    --pda-font: "Outfit", "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", system-ui, sans-serif;
    --pda-mono: "JetBrains Mono", "SFMono-Regular", "Consolas", "Liberation Mono", monospace;
}
[data-testid="stAppViewContainer"] {
    background:
        radial-gradient(ellipse 800px 300px at 50% 0%, rgba(181,91,79,0.03) 0%, transparent 60%),
        #FAFAFA !important;
}
code { background: #F4F4F5 !important; }
.stButton > button:not([kind="primary"]):hover,
.stDownloadButton > button:not([kind="primary"]):hover,
[data-testid^="stBaseButton-"]:not([data-testid="stBaseButton-primary"]):hover { background: #ECECEE !important; }
</style>"""


def main() -> None:
    st.set_page_config(
        page_title="本地数据脱敏工具",
        page_icon="lock",
        layout="centered",
    )
    if "dark_mode" not in st.session_state:
        st.session_state.dark_mode = False
    st.markdown(
        _DARK_THEME_CSS if st.session_state.dark_mode else _LIGHT_THEME_CSS,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

        header, footer, #MainMenu, [data-testid="stToolbar"], [data-testid="stDecoration"],
        [data-testid="stStatusWidget"], .stDeployButton {
            display: none !important;
            visibility: hidden !important;
            height: 0 !important;
        }

        html, body, [class*="css"] {
            font-family: var(--pda-font) !important;
        }

        [data-testid="stAppViewContainer"] {
            color: var(--pda-text) !important;
            min-height: 100vh;
        }

        .block-container {
            padding-top: 4rem;
            padding-left: 1rem;
            padding-right: 1rem;
            padding-bottom: 4rem;
            max-width: 730px;
        }

        .stMarkdown h1 {
            color: var(--pda-text) !important;
            font-size: 2.25rem !important;
            font-weight: 700 !important;
            line-height: 1.15 !important;
            margin-bottom: 0.4rem !important;
            margin-top: 0 !important;
            letter-spacing: -0.01em;
        }

        .stMarkdown h2 {
            color: var(--pda-text) !important;
            font-size: 1.5rem !important;
            font-weight: 600 !important;
            line-height: 1.3 !important;
            margin-top: 1.5rem !important;
            margin-bottom: 0.75rem !important;
        }

        .stMarkdown h3 {
            color: var(--pda-text) !important;
            font-size: 1.25rem !important;
            font-weight: 600 !important;
            line-height: 1.3 !important;
            margin-top: 1.25rem !important;
            margin-bottom: 0.65rem !important;
        }

        .stMarkdown p, .stCaption, label, [data-testid="stMarkdownContainer"] {
            color: var(--pda-text-secondary) !important;
            line-height: 1.5 !important;
        }

        code {
            font-family: var(--pda-mono) !important;
            background: var(--pda-bg-secondary) !important;
            color: var(--pda-text) !important;
            border-radius: 3px !important;
            padding: 0.1em 0.35em !important;
        }

        .stDivider {
            border-color: var(--pda-border) !important;
            margin: 1.25rem 0 !important;
        }

        [data-baseweb="tab-list"] {
            gap: 1.75rem !important;
            border-bottom: 1px solid var(--pda-border) !important;
            margin-top: 1rem !important;
        }

        [data-baseweb="tab"] {
            color: var(--pda-text-muted) !important;
            font-weight: 600 !important;
            padding: 0.85rem 0 !important;
            background: transparent !important;
        }

        [data-baseweb="tab"][aria-selected="true"] {
            color: var(--pda-text) !important;
        }

        [data-baseweb="tab-highlight"] {
            background-color: var(--pda-primary) !important;
            height: 2px !important;
        }

        [data-baseweb="tab-border"] {
            display: none !important;
        }

        [role="radiogroup"] {
            display: flex !important;
            gap: 0 !important;
            margin-bottom: 1rem !important;
            margin-top: 1rem !important;
            border-bottom: 1px solid var(--pda-border) !important;
        }

        [role="radio"] {
            flex: 0 0 auto !important;
            padding: 0.85rem 0 !important;
            margin-right: 1.75rem !important;
            border-radius: 0 !important;
            background: transparent !important;
            border: 0 !important;
            border-bottom: 2px solid transparent !important;
            cursor: pointer !important;
            transition: color 0.15s, border-color 0.15s !important;
        }

        [role="radio"] > div:first-child {
            display: none !important;
        }

        [role="radio"] svg,
        [role="radio"] input,
        label[data-baseweb="radio"] > div:first-child,
        label[data-baseweb="radio"] [aria-hidden="true"] {
            display: none !important;
        }

        label[data-baseweb="radio"] {
            gap: 0 !important;
        }

        [role="radio"]:hover {
            border-bottom-color: var(--pda-border-strong) !important;
        }

        [role="radio"][aria-checked="true"] {
            border-bottom-color: var(--pda-primary) !important;
        }

        [role="radio"] > label {
            cursor: pointer !important;
            font-weight: 600 !important;
            font-size: 0.95rem !important;
            color: var(--pda-text-muted) !important;
            margin: 0 !important;
            line-height: 1.4 !important;
        }

        [role="radio"][aria-checked="true"] > label {
            color: var(--pda-text) !important;
        }

        .uploadedFile {
            background: var(--pda-success-bg) !important;
            border: 1px solid var(--pda-success-border) !important;
            border-radius: 6px !important;
            padding: 0.8rem !important;
            margin: 0.6rem 0 !important;
        }

        [data-testid="stFileUploader"] {
            background: var(--pda-bg-tertiary) !important;
            border: 1.5px dashed var(--pda-border-strong) !important;
            border-radius: 8px !important;
            padding: 1.5rem !important;
            transition: border-color 0.15s, background 0.15s !important;
            margin: 0.6rem 0 !important;
        }

        [data-testid="stFileUploader"]:hover {
            border-color: var(--pda-primary) !important;
            background: var(--pda-primary-subtle) !important;
        }

        .stButton > button {
            width: 100%;
            padding: 0.75rem 1rem !important;
            font-size: 0.9375rem !important;
            font-weight: 600 !important;
            border-radius: 7px !important;
            letter-spacing: 0;
            cursor: pointer !important;
            transition: background 0.15s ease, transform 0.1s ease, box-shadow 0.15s ease !important;
        }

        .stButton > button[kind="primary"]:active,
        .stDownloadButton > button[kind="primary"]:active,
        [data-testid="stBaseButton-primary"]:active {
            transform: scale(0.985) !important;
        }

        .stButton > button[kind="primary"],
        .stDownloadButton > button[kind="primary"],
        [data-testid="stBaseButton-primary"] {
            background: var(--pda-primary) !important;
            color: #ffffff !important;
            border: 1px solid var(--pda-primary) !important;
            border-radius: 7px !important;
            box-shadow: 0 1px 3px rgba(181,91,79,0.15), 0 4px 12px rgba(181,91,79,0.08) !important;
            font-weight: 600 !important;
        }

        .stButton > button[kind="primary"] p,
        .stDownloadButton > button[kind="primary"] p,
        [data-testid="stBaseButton-primary"] p {
            color: #ffffff !important;
        }

        .stButton > button[kind="primary"]:hover,
        .stDownloadButton > button[kind="primary"]:hover,
        [data-testid="stBaseButton-primary"]:hover {
            background: var(--pda-primary-hover) !important;
            border-color: var(--pda-primary-hover) !important;
            color: #ffffff !important;
            box-shadow: 0 2px 6px rgba(181,91,79,0.2), 0 6px 16px rgba(181,91,79,0.1) !important;
        }

        .stButton > button[kind="primary"]:hover p,
        .stDownloadButton > button[kind="primary"]:hover p,
        [data-testid="stBaseButton-primary"]:hover p {
            color: #ffffff !important;
        }

        .stButton > button:not([kind="primary"]),
        .stDownloadButton > button:not([kind="primary"]),
        [data-testid^="stBaseButton-"]:not([data-testid="stBaseButton-primary"]) {
            background: var(--pda-bg-secondary) !important;
            color: var(--pda-text) !important;
            border: 1px solid var(--pda-border-strong) !important;
            border-radius: 7px !important;
            font-weight: 600 !important;
        }

        .stButton > button:not([kind="primary"]) p,
        .stDownloadButton > button:not([kind="primary"]) p,
        [data-testid^="stBaseButton-"]:not([data-testid="stBaseButton-primary"]) p {
            color: var(--pda-text) !important;
        }

        .stButton > button:not([kind="primary"]):hover,
        .stDownloadButton > button:not([kind="primary"]):hover,
        [data-testid^="stBaseButton-"]:not([data-testid="stBaseButton-primary"]):hover {
            border-color: var(--pda-text-muted) !important;
        }

        .stCaption {
            color: var(--pda-text-secondary) !important;
            font-size: 0.8125rem !important;
            margin-top: 0.5rem !important;
        }

        [data-testid="stAlert"] {
            border-radius: 6px !important;
            border: 1px solid !important;
            padding: 0.8rem !important;
            margin: 0.6rem 0 !important;
        }

        [data-testid="stAlert"][kind="info"] {
            background: var(--pda-info-bg) !important;
            border-color: var(--pda-info-border) !important;
            color: var(--pda-info-text) !important;
        }

        [data-testid="stAlert"][kind="success"] {
            background: var(--pda-success-bg) !important;
            border-color: var(--pda-success-border) !important;
            color: var(--pda-success-text) !important;
        }

        [data-testid="stAlert"][kind="error"] {
            background: var(--pda-error-bg) !important;
            border-color: var(--pda-error-border) !important;
            color: var(--pda-error-text) !important;
        }

        [data-testid="stAlert"][kind="warning"] {
            background: var(--pda-warning-bg) !important;
            border-color: var(--pda-warning-border) !important;
            color: var(--pda-warning-text) !important;
        }

        [data-testid="stExpander"] {
            background: var(--pda-bg) !important;
            border: 1px solid var(--pda-border) !important;
            border-radius: 6px !important;
            margin: 0.6rem 0 !important;
        }

        [data-testid="stExpander"] summary {
            color: var(--pda-text) !important;
            font-weight: 600 !important;
            padding: 0.8rem !important;
        }

        [data-testid="stExpander"] summary:hover {
            background: var(--pda-bg-tertiary) !important;
        }

        input, textarea, select {
            background: var(--pda-bg) !important;
            border: 1px solid var(--pda-border-strong) !important;
            color: var(--pda-text) !important;
            border-radius: 6px !important;
        }

        input:focus, textarea:focus, select:focus {
            border-color: var(--pda-primary) !important;
            box-shadow: 0 0 0 1px var(--pda-primary) !important;
        }

        .pda-caption {
            color: var(--pda-text-secondary);
            font-size: 0.95rem;
            margin: 0.25rem 0 1.5rem;
        }

        .pda-selected-file {
            background: var(--pda-success-bg);
            border: 1px solid var(--pda-success-border);
            border-radius: 6px;
            padding: 1rem;
            margin: 1rem 0;
        }

        .pda-selected-file p:first-child {
            margin: 0;
            color: var(--pda-success-text);
            font-weight: 600;
        }

        .pda-selected-file p:last-child {
            margin: 0.35rem 0 0;
            color: var(--pda-success-text);
            font-size: 0.9rem;
            font-family: var(--pda-mono);
        }

        .pda-stats {
            background: var(--pda-info-bg);
            border: 1px solid var(--pda-info-border);
            border-radius: 6px;
            padding: 1.25rem;
            margin: 1.25rem 0;
        }

        .pda-stats-title {
            margin: 0;
            color: var(--pda-info-text);
            font-weight: 600;
        }

        .pda-stats-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 1rem;
            margin-top: 1rem;
        }

        .pda-stat {
            text-align: center;
        }

        .pda-stat-num {
            margin: 0;
            color: var(--pda-info-text);
            font-size: 1.5rem;
            font-weight: 700;
            font-family: var(--pda-mono);
        }

        .pda-stat-label {
            margin: 0.35rem 0 0;
            color: var(--pda-text-secondary);
            font-size: 0.85rem;
        }

        .pda-download-caption {
            color: var(--pda-text-secondary);
            font-size: 0.85rem;
            margin-top: 1rem;
        }

        .stage-container {
            display: flex;
            justify-content: space-between;
            margin: 1.5rem 0;
            gap: 0.5rem;
        }

        .stage {
            flex: 1;
            text-align: center;
            padding: 0.9rem 0.65rem;
            background: var(--pda-bg-tertiary);
            border-radius: 6px;
            border: 1px solid var(--pda-border);
        }

        .stage.active {
            background: var(--pda-primary-subtle);
            border-color: var(--pda-primary);
        }

        .stage.completed {
            background: var(--pda-success-bg);
            border-color: var(--pda-success-border);
        }

        .stage-dot {
            width: 28px;
            height: 28px;
            border-radius: 999px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 0.45rem;
            font-weight: 600;
            background: var(--pda-bg-secondary);
            color: var(--pda-text-secondary);
            border: 1px solid var(--pda-border-strong);
        }

        .stage.active .stage-dot {
            background: var(--pda-primary);
            border-color: var(--pda-primary);
            color: #ffffff;
        }

        .stage.completed .stage-dot {
            background: var(--pda-success);
            border-color: var(--pda-success);
            color: #ffffff;
        }

        .stage-label {
            font-size: 0.8125rem;
            color: var(--pda-text-secondary);
            font-weight: 600;
        }

        .stage.active .stage-label {
            color: var(--pda-primary);
        }

        .stage.completed .stage-label {
            color: var(--pda-success-text);
        }

        @media (max-width: 480px) {
            .block-container {
                padding-left: 1rem;
                padding-right: 1rem;
                padding-top: 2.5rem;
            }
            .stMarkdown h1 {
                font-size: 2.25rem !important;
                word-break: keep-all;
            }
            .stMarkdown h2 {
                font-size: 1.35rem !important;
            }
            [role="radiogroup"] {
                overflow-x: auto !important;
            }
            .stage-container,
            .pda-stats-grid {
                grid-template-columns: 1fr;
            }
            .stage-container {
                flex-direction: column;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    _title_col, _version_col, _toggle_col = st.columns([7, 1, 1])
    with _title_col:
        st.markdown("# 本地数据脱敏工具")
        st.markdown(
            '<p class="pda-caption">文件只在本机处理，不会上传到服务器，也不会调用大模型。</p>',
            unsafe_allow_html=True,
        )
    with _version_col:
        st.markdown("<div style='padding-top:1.4rem'></div>", unsafe_allow_html=True)
        st.markdown(
            f'<span style="background:var(--pda-bg-tertiary);color:var(--pda-text-secondary);'
            f'padding:2px 10px;border-radius:10px;font-size:0.75rem;font-weight:500">v{VERSION}</span>',
            unsafe_allow_html=True,
        )
    with _toggle_col:
        st.markdown("<div style='padding-top:1.4rem'></div>", unsafe_allow_html=True)
        st.toggle("🌙", key="dark_mode")

    anonymize_tab, restore_tab = st.tabs(["数据脱敏", "报告反脱敏"])

    with anonymize_tab:
        render_anonymize()

    with restore_tab:
        render_restore()


def _stage_html(s1: str, s2: str, s3: str, s4: str, label3: str = "处理中") -> str:
    return f"""
    <div class="stage-container">
        <div class="stage {s1}">
            <div class="stage-dot">1</div>
            <div class="stage-label">上传文件</div>
        </div>
        <div class="stage {s2}">
            <div class="stage-dot">2</div>
            <div class="stage-label">配置选项</div>
        </div>
        <div class="stage {s3}">
            <div class="stage-dot">3</div>
            <div class="stage-label">{label3}</div>
        </div>
        <div class="stage {s4}">
            <div class="stage-dot">✓</div>
            <div class="stage-label">完成</div>
        </div>
    </div>
    """


def render_anonymize() -> None:
    for key, default in [
        ("anonymize_file", None),
        ("anonymize_files", []),       # v1.11.0: multi-file batch list
        ("seed_file", None),
        ("header_mode", "自动检测"),
        ("custom_header_row", 1),
        ("anonymize_job_title", False),
        ("anonymize_department", True),
        ("anonymize_region", True),
        ("processing", False),
        ("anonymize_result", None),
        ("anonymize_batch_result", None),  # v1.11.0: batch results
        ("encryption_key", None),  # v1.10.0: Fernet key for mapping encryption
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    has_single = st.session_state.anonymize_file is not None
    has_multi = bool(st.session_state.anonymize_files)
    has_file = has_single or has_multi
    proc = st.session_state.processing
    has_single_result = st.session_state.anonymize_result is not None
    has_batch_result = st.session_state.anonymize_batch_result is not None
    has_result = has_single_result or has_batch_result

    # Stage indicator — driven by result presence, not processing flag
    s1 = "completed" if (has_file or proc or has_result) else "active"
    s2 = "completed" if (proc or has_result) else ("active" if has_file else "")
    s3 = "completed" if has_result else ("active" if proc else "")
    s4 = "completed" if has_result else ""
    st.markdown(_stage_html(s1, s2, s3, s4), unsafe_allow_html=True)
    st.divider()

    # ── Processing phase ─────────────────────────────────────────────────────
    if proc and has_file:
        try:
            with st.spinner("正在处理，请稍候..."):
                _header_mode = st.session_state.get("header_mode", "自动检测")
                if _header_mode == "自动检测":
                    _header_row = None
                elif _header_mode == "第一行":
                    _header_row = 1
                elif _header_mode == "第二行":
                    _header_row = 2
                else:
                    _header_row = st.session_state.get("custom_header_row", 1)

                if has_multi:
                    from privacy_data_agent.web_helpers import anonymize_batch

                    files = [(f.name, f.getvalue()) for f in st.session_state.anonymize_files]
                    batch_result = anonymize_batch(
                        files,
                        first_seed_filename=st.session_state.seed_file.name if st.session_state.seed_file else None,
                        first_seed_content=st.session_state.seed_file.getvalue() if st.session_state.seed_file else None,
                        header_row=_header_row,
                        encryption_key=st.session_state.encryption_key,
                        anonymize_job_title=st.session_state.anonymize_job_title,
                        anonymize_department=st.session_state.anonymize_department,
                        anonymize_region=st.session_state.anonymize_region,
                    )
                    st.session_state.anonymize_batch_result = batch_result
                    st.session_state.processing = False
                    st.rerun()
                else:
                    result = anonymize_upload(
                        st.session_state.anonymize_file.name,
                        st.session_state.anonymize_file.getvalue(),
                        seed_mapping_filename=st.session_state.seed_file.name if st.session_state.seed_file else None,
                        seed_mapping_content=st.session_state.seed_file.getvalue() if st.session_state.seed_file else None,
                        header_row=_header_row,
                        encryption_key=st.session_state.encryption_key,
                        anonymize_job_title=st.session_state.anonymize_job_title,
                        anonymize_department=st.session_state.anonymize_department,
                        anonymize_region=st.session_state.anonymize_region,
                    )
                    st.session_state.anonymize_result = result
                    st.session_state.processing = False
                    st.rerun()
        except Exception as exc:
            st.session_state.processing = False
            st.error(f"处理失败：{str(exc)}")
            if st.button("重新尝试", use_container_width=True):
                st.rerun()
        return

    # ── Result phase ──────────────────────────────────────────────────────────
    if has_result:
        # v1.11.0: batch result display
        if has_batch_result:
            batch = st.session_state.anonymize_batch_result
            st.success(
                f"批量脱敏完成：处理 {batch['files_processed']} 个文件，"
                f"共 {batch['total_rows']} 行，新增 {batch['total_new_entities']} 个实体。"
            )
            st.markdown(
                f"""
                <div class="pda-stats">
                    <p class="pda-stats-title">批量处理统计</p>
                    <div class="pda-stats-grid">
                        <div class="pda-stat">
                            <p class="pda-stat-num">{batch['files_processed']}</p>
                            <p class="pda-stat-label">处理文件</p>
                        </div>
                        <div class="pda-stat">
                            <p class="pda-stat-num">{batch['total_rows']}</p>
                            <p class="pda-stat-label">数据行数</p>
                        </div>
                        <div class="pda-stat">
                            <p class="pda-stat-num">{batch['total_new_entities']}</p>
                            <p class="pda-stat-label">新增实体</p>
                        </div>
                        <div class="pda-stat">
                            <p class="pda-stat-num">{batch['total_entities']}</p>
                            <p class="pda-stat-label">累计实体</p>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.divider()
            st.markdown("### 下载结果")
            col1, col2 = st.columns([2, 1])
            with col1:
                st.download_button(
                    "⬇️ 下载全部（打包ZIP）",
                    data=batch["consolidated_zip"],
                    file_name="批量脱敏数据包.zip",
                    mime="application/zip",
                    use_container_width=True,
                    type="primary",
                    key="download_batch_zip",
                )
            with col2:
                st.button(
                    "继续添加文件",
                    use_container_width=True,
                    on_click=lambda: st.session_state.update({
                        "processing": False,
                        "anonymize_file": None,
                        "anonymize_files": [],
                        "seed_file": None,
                        "header_mode": "自动检测",
                        "custom_header_row": 1,
                        "anonymize_job_title": False,
                        "anonymize_department": True,
                        "anonymize_region": True,
                        "anonymize_batch_result": None,
                        "anonymize_result": None,
                    }),
                    key="batch_continue",
                )
            with st.expander("展开查看各文件结果", expanded=False):
                for i, r in enumerate(batch["results"]):
                    suffix = r.get("suffix", ".xlsx")
                    with st.container():
                        st.markdown(f"**文件 {i+1}: {r['stem']}{suffix}**")
                        cols = st.columns(3)
                        cols[0].metric("数据行数", r["row_count"])
                        cols[1].metric("新增实体", r["new_entity_count"])
                        cols[2].metric("累计实体", r["entity_count"])
                        st.download_button(
                            f"下载 {r['stem']}{suffix}",
                            data=r["anonymized_bytes"],
                            file_name=f"{r['stem']}_anonymized{suffix}",
                            mime="application/octet-stream",
                            use_container_width=True,
                            key=f"download_batch_file_{i}",
                        )
                        st.divider()
        else:
            # Single-file result (existing code)
            result = st.session_state.anonymize_result
            new_count = result["new_entity_count"]
            total_count = result["entity_count"]

            suffix = result.get("file_suffix", ".xlsx")
            if suffix in (".docx", ".pdf"):
                unit = "个"
                row_label = "检出实体"
                format_name = "Word 文档" if suffix == ".docx" else "PDF 文档"
            elif suffix == ".numbers":
                unit = "行"
                row_label = "数据行数"
                format_name = "Numbers 数据文件"
            elif suffix == ".et":
                unit = "行"
                row_label = "数据行数"
                format_name = "WPS 电子表格"
            else:
                unit = "行"
                row_label = "数据行数"
                format_name = "Excel 数据文件"

            st.success(f"脱敏完成：{result['row_count']} {unit}，生成 {new_count} 个匹配项。")
            st.markdown(
                f"""
                <div class="pda-stats">
                    <p class="pda-stats-title">处理统计</p>
                    <div class="pda-stats-grid">
                        <div class="pda-stat">
                            <p class="pda-stat-num">{result['row_count']}</p>
                            <p class="pda-stat-label">{row_label}</p>
                        </div>
                        <div class="pda-stat">
                            <p class="pda-stat-num">{new_count}</p>
                            <p class="pda-stat-label">新增实体</p>
                        </div>
                        <div class="pda-stat">
                            <p class="pda-stat-num">{total_count}</p>
                            <p class="pda-stat-label">总计实体</p>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.divider()
            st.markdown("### 下载结果")

            zip_name = f"{result['stem']}_脱敏包.zip"
            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    "⬇️ 一键打包下载（推荐）",
                    data=result["zip_bundle"],
                    file_name=zip_name,
                    mime="application/zip",
                    use_container_width=True,
                    type="primary",
                    key="download_zip",
                )
            with col2:
                st.button(
                    "处理其他文件",
                    use_container_width=True,
                    on_click=lambda: st.session_state.update({
                        "processing": False,
                        "anonymize_file": None,
                        "seed_file": None,
                        "header_mode": "自动检测",
                        "custom_header_row": 1,
                        "anonymize_job_title": False,
                        "anonymize_result": None,
                    }),
                    key="process_another",
                )
            st.markdown(
                f"""
                <p class="pda-download-caption">
                    ZIP 包含脱敏 {format_name} + 匹配文件 + 使用说明，反脱敏时只需上传其中的 mapping.local.json。
                </p>
                """,
                unsafe_allow_html=True,
            )
            with st.expander("单独下载各文件", expanded=False):
                suffix = result.get("file_suffix", ".xlsx")
                mime_map = {
                    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    ".numbers": "application/x-iwork-numbers-sffnumbers",
                    ".et": "application/vnd.ms-excel",
                    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    ".pdf": "application/pdf",
                }
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button(
                        f"脱敏文件（{suffix}）",
                        data=result["anonymized_xlsx"],
                        file_name=f"{result['stem']}_anonymized{suffix}",
                        mime=mime_map.get(suffix, "application/octet-stream"),
                        use_container_width=True,
                        key="download_xlsx",
                    )
                    st.download_button(
                        "匹配文件 JSON（加密）" if st.session_state.encryption_key else "匹配文件 JSON",
                        data=(
                            result["encrypted_mapping_json"]
                            if result.get("encrypted_mapping_json") is not None
                            else str(result["mapping_json"]).encode("utf-8")
                        ),
                        file_name="mapping.local.json",
                        mime="application/json",
                        use_container_width=True,
                        key="download_json",
                    )
                with col2:
                    st.download_button(
                        "CSV 脱敏数据",
                        data=result["anonymized_csv"],
                        file_name=f"{result['stem']}_anonymized.csv",
                        mime="text/csv",
                        use_container_width=True,
                        key="download_csv",
                    )
                st.download_button(
                    "匹配表 CSV",
                    data=result["mapping_table_csv"],
                    file_name="mapping_table.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key="download_mapping_csv",
                )
        st.warning(
                "匹配文件和匹配表包含原始敏感信息，只能保存在本地。"
                + (" 匹配文件 JSON 已加密。" if st.session_state.encryption_key else "")
            )
        return

    # ── Upload & config phase ─────────────────────────────────────────────────
    st.markdown("### 第一步：选择需要脱敏的文件")
    st.caption("支持单文件或多文件批量处理，多文件将自动累积匹配结果。")

    # v1.11.0: multi-file batch uploader
    multi_files = st.file_uploader(
        "拖拽或点击上传多个文件（Excel、CSV、Numbers、WPS、DOCX、PDF）",
        type=["csv", "xlsx", "numbers", "et", "docx", "pdf"],
        accept_multiple_files=True,
        key="multi_file_uploader",
        label_visibility="collapsed",
    )
    st.session_state.anonymize_files = list(multi_files or [])
    has_multi = bool(st.session_state.anonymize_files)
    if multi_files:
        st.success(f"已选择 {len(multi_files)} 个文件：")
        for f in multi_files:
            st.write(f"  • {f.name} ({f.size / 1024:.1f} KB)")

    source_file = st.file_uploader(
        "或选择单个文件（Excel、CSV、Numbers、WPS、DOCX 或 PDF 文件）",
        type=["csv", "xlsx", "numbers", "et", "docx", "pdf"],
        accept_multiple_files=False,
        key="source_file_uploader",
        label_visibility="collapsed",
    )

    st.session_state.anonymize_file = source_file
    has_single = st.session_state.anonymize_file is not None
    has_file = has_single or has_multi

    if source_file is not None:
        st.markdown(
            f"""
            <div class="pda-selected-file">
                <p>文件已选择</p>
                <p>{source_file.name} ({source_file.size / 1024:.1f} KB)</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if has_file:
        st.markdown("### 第二步：处理前预览（可选）")

        # v1.12.0: D8 — Pre-anonymization preview stats
        with st.expander("📊 预览数据概览与实体分布", expanded=False):
            from privacy_data_agent.detectors import (
                detect_column_entity_type,
                detect_header_row,
                detect_optional_column_entity_type,
                is_pass_through_column,
            )
            from privacy_data_agent.models import EntityType
            import pandas as pd

            def _preview_single_file(uploaded_file) -> pd.DataFrame:
                suffix = Path(uploaded_file.name).suffix.lower()
                buffer = BytesIO(uploaded_file.getvalue())
                if suffix == ".csv":
                    lines = []
                    for _ in range(3):
                        line = buffer.readline()
                        if line:
                            lines.append(line.decode("utf-8-sig").strip())
                    buffer.seek(0)
                    header_row = detect_header_row([line.split(",") for line in lines]) if lines else 1
                    df = pd.read_csv(buffer, nrows=5, encoding="utf-8-sig", header=max(0, header_row - 1))
                elif suffix == ".xlsx":
                    raw = pd.read_excel(buffer, nrows=3, header=None, engine="openpyxl")
                    buffer.seek(0)
                    raw_rows = [
                        [str(c) if pd.notna(c) else "" for c in raw.iloc[i].tolist()]
                        for i in range(min(3, len(raw)))
                    ]
                    header_row = detect_header_row(raw_rows)
                    df = pd.read_excel(buffer, nrows=5, header=max(0, header_row - 1), engine="openpyxl")
                else:
                    return pd.DataFrame()
                col_info = []
                for col in df.columns:
                    col_name = str(col) if not isinstance(col, int) else f"列{col+1}"
                    if is_pass_through_column(
                        col_name,
                        anonymize_job_title=st.session_state.anonymize_job_title,
                    ):
                        entity = None
                        action = "保留"
                    else:
                        entity = detect_column_entity_type(col_name)
                        if entity is None and st.session_state.anonymize_job_title:
                            entity = detect_optional_column_entity_type(col_name)
                        action = "脱敏" if entity else "仅高置信扫描"
                    col_info.append({
                        "列名": col_name,
                        "实体类型": entity.value if entity else "—",
                        "处理方式": action,
                        "示例值": str(df[col].dropna().iloc[0])[:20] if len(df[col].dropna()) > 0 else "—",
                    })
                return pd.DataFrame(col_info)

            if has_multi:
                for f in st.session_state.anonymize_files:
                    preview_df = _preview_single_file(f)
                    st.markdown(f"**📄 {f.name}**")
                    if not preview_df.empty:
                        st.dataframe(preview_df, use_container_width=True, hide_index=True)
                    else:
                        st.caption("（DOCX/PDF 格式暂不支持预览）")
                    st.divider()
            else:
                preview_df = _preview_single_file(source_file)
                if not preview_df.empty:
                    st.dataframe(preview_df, use_container_width=True, hide_index=True)
                else:
                    st.caption("（该文件格式暂不支持预览）")

        st.markdown("### 第三步：配置处理选项（可选）")

        with st.expander("同一批次追加文件？上传已有匹配文件（可选）", expanded=False):
            st.markdown(
                "<p>如需在同一批次追加处理相同数据，上传已有的匹配文件。这样新出现的相同实体将沿用之前的匹配结果，保持一致性。</p>",
                unsafe_allow_html=True,
            )
            seed_file = st.file_uploader(
                "选择已有的 mapping.local.json 或 mapping_table.csv",
                type=["json", "csv"],
                accept_multiple_files=False,
                key="seed_file_uploader",
                label_visibility="collapsed",
            )
            if seed_file is not None:
                st.session_state.seed_file = seed_file

        # ── v1.10.0: 映射文件加密配置 ────────────────────────────────────────
        with st.expander("🔐 加密匹配文件（可选）", expanded=False):
            st.markdown(
                "<p>如需对匹配文件进行加密，请开启此选项。加密后下载的 mapping.local.json 将包含加密后的敏感信息，且在反脱敏时需要输入相同密钥才能解密。</p>",
                unsafe_allow_html=True,
            )
            col_gen, col_key = st.columns([1, 2])
            with col_gen:
                if st.button("生成加密密钥", use_container_width=True, key="generate_key_btn"):
                    from cryptography.fernet import Fernet

                    st.session_state.encryption_key = Fernet.generate_key().decode("utf-8")
                    st.rerun()
            with col_key:
                if st.session_state.encryption_key:
                    st.text_input(
                        "当前加密密钥（请妥善保存）",
                        value=st.session_state.encryption_key,
                        disabled=True,
                        key="key_display",
                    )
                    st.caption("密钥会在当前会话中保持。关闭页面后将丢失，请务必下载后妥善保管。")

        with st.expander("字段脱敏范围（可选）", expanded=False):
            st.checkbox(
                "脱敏岗位名称 / 职位 / 职务",
                value=st.session_state.anonymize_job_title,
                key="anonymize_job_title",
                help="默认保留岗位，便于分析岗位结构。开启后，岗位名称列会进入匹配文件并替换为 token。",
            )
            st.checkbox(
                "脱敏部门名称",
                value=st.session_state.anonymize_department,
                key="anonymize_department",
                help="默认脱敏。关闭后，部门名称列将保留原值，不替换为 token。",
            )
            st.caption("离职原因、离职类型、状态等业务判断列默认保留，不参与姓名/部门类弱规则扫描。")

        source_suffix = Path(source_file.name).suffix.lower() if source_file else ""
        has_table_file = has_multi or source_suffix in (".xlsx", ".csv", ".numbers", ".et")
        if has_table_file:
            with st.expander("表格格式配置（可选）", expanded=False):
                st.markdown(
                    '<p>如果表格首行是标题文字（如"2024年度员工统计表"），而非列名表头，请在此调整。</p>',
                    unsafe_allow_html=True,
                )
                header_mode = st.radio(
                    "表头所在行",
                    ["自动检测", "第一行", "第二行", "自定义行号"],
                    index=["自动检测", "第一行", "第二行", "自定义行号"].index(st.session_state.header_mode),
                    horizontal=True,
                    key="header_mode_radio",
                )
                st.session_state.header_mode = header_mode
                if header_mode == "自定义行号":
                    custom_row = st.number_input(
                        "表头行号",
                        min_value=1,
                        value=st.session_state.custom_header_row,
                        step=1,
                        key="custom_header_row_input",
                    )
                    st.session_state.custom_header_row = custom_row

        st.divider()

        col1, col2 = st.columns([2, 1])
        with col1:
            start_btn = st.button(
                "开始处理",
                use_container_width=True,
                type="primary",
                key="start_anonymize_btn",
            )
        with col2:
            reset_btn = st.button(
                "重新选择",
                use_container_width=True,
                key="reset_anonymize_btn",
            )

        if reset_btn:
            st.session_state.update({
                "anonymize_file": None,
                "anonymize_files": [],
                "seed_file": None,
                "header_mode": "自动检测",
                "custom_header_row": 1,
                "anonymize_job_title": False,
                "anonymize_department": True,
                "anonymize_region": True,
                "anonymize_result": None,
                "anonymize_batch_result": None,
            })
            st.rerun()

        if start_btn:
            st.session_state.processing = True
            st.rerun()


_RESTORE_MIME = {
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".html": "text/html",
    ".htm": "text/html",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def render_restore() -> None:
    for key, default in [
        ("restore_report", None),
        ("restore_mapping", None),
        ("restore_processing", False),
        ("restore_result", None),
        ("restore_decryption_key", ""),  # v1.10.0: key for encrypted mapping files
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    has_report = st.session_state.restore_report is not None
    has_mapping = st.session_state.restore_mapping is not None
    both = has_report and has_mapping
    proc = st.session_state.restore_processing
    has_result = st.session_state.restore_result is not None

    s1 = "completed" if (both or proc or has_result) else "active"
    s2 = "completed" if (proc or has_result) else ("active" if both else "")
    s3 = "completed" if has_result else ("active" if proc else "")
    s4 = "completed" if has_result else ""
    st.markdown(_stage_html(s1, s2, s3, s4, label3="恢复中"), unsafe_allow_html=True)
    st.divider()

    # ── Processing phase ──────────────────────────────────────────────────────
    if proc and both:
        try:
            with st.spinner("正在恢复，请稍候..."):
                result = restore_report_upload(
                    report_content=st.session_state.restore_report.getvalue(),
                    report_filename=st.session_state.restore_report.name,
                    mapping_filename=st.session_state.restore_mapping.name,
                    mapping_content=st.session_state.restore_mapping.getvalue(),
                    decryption_key=st.session_state.get("restore_decryption_key") or None,
                )
            st.session_state.restore_result = result
            st.session_state.restore_processing = False
            st.rerun()
        except Exception as exc:
            st.session_state.restore_processing = False
            st.error(f"恢复失败：{str(exc)}")
            if st.button("重新尝试", use_container_width=True):
                st.rerun()
        return

    # ── Result phase ──────────────────────────────────────────────────────────
    if has_result:
        result = st.session_state.restore_result
        suffix = "." + result["filename"].rsplit(".", 1)[-1]
        mime = _RESTORE_MIME.get(suffix, "application/octet-stream")

        st.success("报告恢复完成。")
        st.divider()
        st.markdown("### 下载恢复结果")

        col1, col2 = st.columns([2, 1])
        with col1:
            st.download_button(
                "下载反脱敏报告",
                data=result["content"],
                file_name=result["filename"],
                mime=mime,
                use_container_width=True,
                type="primary",
                key="download_restored",
            )
        with col2:
            st.button(
                "恢复其他文件",
                use_container_width=True,
                on_click=lambda: st.session_state.update({
                    "restore_processing": False,
                    "restore_report": None,
                    "restore_mapping": None,
                    "restore_result": None,
                }),
                key="restore_another",
            )

        if suffix in {".md", ".txt", ".html", ".htm"}:
            with st.expander("预览恢复结果", expanded=True):
                st.markdown(result["content"].decode("utf-8"))
        return

    # ── Upload phase ──────────────────────────────────────────────────────────
    st.markdown("### 第一步：选择待恢复的报告文件")
    report_file = st.file_uploader(
        "支持 md / txt / html / docx / pptx 等格式",
        type=["md", "txt", "html", "htm", "docx", "pptx"],
        accept_multiple_files=False,
        key="report_file_uploader",
        label_visibility="collapsed",
    )

    if report_file is not None:
        st.session_state.restore_report = report_file
        st.markdown(
            f"""
            <div class="pda-selected-file">
                <p>报告文件已选择</p>
                <p>{report_file.name}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("### 第二步：选择匹配文件")
    mapping_file = st.file_uploader(
        "选择 mapping.local.json 或 mapping_table.csv",
        type=["json", "csv"],
        accept_multiple_files=False,
        key="mapping_file_uploader",
        label_visibility="collapsed",
    )

    if mapping_file is not None:
        st.session_state.restore_mapping = mapping_file
        st.markdown(
            f"""
            <div class="pda-selected-file">
                <p>匹配文件已选择</p>
                <p>{mapping_file.name}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # v1.10.0: 解密密钥输入（加密匹配文件需要）
    restore_key_input = st.text_input(
        "如匹配文件已加密，请输入解密密钥（明文 JSON/CSV 文件无需输入）",
        value=st.session_state.get("restore_decryption_key", ""),
        placeholder="输入 Fernet 加密密钥...",
        key="restore_decryption_key_input",
    )
    st.session_state.restore_decryption_key = restore_key_input

    st.divider()

    if report_file is not None and mapping_file is not None:
        col1, col2 = st.columns([2, 1])
        with col1:
            start_restore_btn = st.button(
                "开始恢复",
                use_container_width=True,
                type="primary",
                key="start_restore_btn",
            )
        with col2:
            reset_restore_btn = st.button(
                "重新选择",
                use_container_width=True,
                key="reset_restore_btn",
            )

        if reset_restore_btn:
            st.session_state.update({
                "restore_report": None,
                "restore_mapping": None,
                "restore_result": None,
            })
            st.rerun()

        if start_restore_btn:
            st.session_state.restore_processing = True
            st.rerun()
    elif report_file or mapping_file:
        st.info("请同时上传报告文件和匹配文件。")


if __name__ == "__main__":
    main()
