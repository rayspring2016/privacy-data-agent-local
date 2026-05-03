from __future__ import annotations

import streamlit as st

from privacy_data_agent.web_helpers import anonymize_upload, restore_report_upload

_DARK_THEME_CSS = """<style>
:root {
    --pda-primary: #cb7b7b;
    --pda-primary-hover: #d48888;
    --pda-primary-active: #b86e6e;
    --pda-primary-subtle: rgba(203,123,123,0.06);
    --pda-text: #e4e4e7;
    --pda-text-secondary: #7e7e86;
    --pda-text-muted: #545459;
    --pda-border: rgba(255,255,255,0.06);
    --pda-border-strong: rgba(255,255,255,0.08);
    --pda-bg: #181b24;
    --pda-bg-secondary: #151820;
    --pda-bg-tertiary: #13151e;
    --pda-success: #3dd68c;
    --pda-success-bg: rgba(61,214,140,0.06);
    --pda-success-border: rgba(61,214,140,0.12);
    --pda-success-text: #5fe09e;
    --pda-warning: #f59e0b;
    --pda-warning-bg: rgba(245,158,11,0.06);
    --pda-warning-border: rgba(245,158,11,0.12);
    --pda-warning-text: #fbbf24;
    --pda-error-bg: rgba(203,123,123,0.06);
    --pda-error-border: rgba(203,123,123,0.12);
    --pda-error-text: #e07878;
    --pda-info-bg: rgba(96,165,250,0.06);
    --pda-info-border: rgba(96,165,250,0.12);
    --pda-info-text: #93c5fd;
    --pda-font: "Inter", "PingFang SC", "Microsoft YaHei", sans-serif;
    --pda-mono: "JetBrains Mono", "SFMono-Regular", "Consolas", monospace;
}
[data-testid="stAppViewContainer"] {
    background:
        radial-gradient(ellipse 800px 300px at 50% 0%, rgba(195,105,105,0.025) 0%, transparent 60%),
        #111318 !important;
}
code { background: #13151e !important; }
.stButton > button:not([kind="primary"]):hover,
.stDownloadButton > button:not([kind="primary"]):hover { background: #1c1f2a !important; }
</style>"""

_LIGHT_THEME_CSS = """<style>
:root {
    --pda-primary: #c56a6a;
    --pda-primary-hover: #d47a7a;
    --pda-primary-active: #b65a5a;
    --pda-primary-subtle: #fef5f5;
    --pda-text: #1a1a1d;
    --pda-text-secondary: #5c5c63;
    --pda-text-muted: #9999a0;
    --pda-border: #f0f0f3;
    --pda-border-strong: #e4e4e8;
    --pda-bg: #ffffff;
    --pda-bg-secondary: #fafafc;
    --pda-bg-tertiary: #f5f5f8;
    --pda-success: #3dd68c;
    --pda-success-bg: #f0fdf6;
    --pda-success-border: #bbf7d0;
    --pda-success-text: #15803d;
    --pda-warning: #f59e0b;
    --pda-warning-bg: #fffdf5;
    --pda-warning-border: #fde68a;
    --pda-warning-text: #92400e;
    --pda-error-bg: #fef5f5;
    --pda-error-border: #fccccc;
    --pda-error-text: #8b1a1a;
    --pda-info-bg: #f5f8fe;
    --pda-info-border: #bfdbfe;
    --pda-info-text: #1d4ed8;
    --pda-font: "Inter", "PingFang SC", "Microsoft YaHei", sans-serif;
    --pda-mono: "JetBrains Mono", "SFMono-Regular", "Consolas", monospace;
}
[data-testid="stAppViewContainer"] {
    background:
        radial-gradient(ellipse 900px 400px at 60% -10%, rgba(195,105,105,0.04) 0%, transparent 60%),
        radial-gradient(ellipse 600px 300px at 10% 80%, rgba(195,105,105,0.02) 0%, transparent 50%),
        #fafafc !important;
}
code { background: #f5f5f8 !important; }
.stButton > button:not([kind="primary"]):hover,
.stDownloadButton > button:not([kind="primary"]):hover { background: #f0f0f3 !important; }
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
            font-size: 0.95rem !important;
            font-weight: 600 !important;
            border-radius: 6px !important;
            transition: background 0.15s, border-color 0.15s, color 0.15s !important;
            letter-spacing: 0;
            cursor: pointer !important;
        }

        .stButton > button[kind="primary"],
        .stDownloadButton > button[kind="primary"] {
            background: var(--pda-primary) !important;
            color: #ffffff !important;
            border: 1px solid var(--pda-primary) !important;
            border-radius: 6px !important;
            box-shadow: none !important;
            font-weight: 600 !important;
        }

        .stButton > button[kind="primary"]:hover,
        .stDownloadButton > button[kind="primary"]:hover {
            background: var(--pda-primary-hover) !important;
            border-color: var(--pda-primary-hover) !important;
        }

        .stButton > button:not([kind="primary"]),
        .stDownloadButton > button:not([kind="primary"]) {
            background: var(--pda-bg-secondary) !important;
            color: var(--pda-text) !important;
            border: 1px solid var(--pda-border-strong) !important;
            border-radius: 6px !important;
            font-weight: 600 !important;
        }

        .stButton > button:not([kind="primary"]):hover,
        .stDownloadButton > button:not([kind="primary"]):hover {
            border-color: var(--pda-border-strong) !important;
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
            color: var(--pda-primary-active);
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

    _title_col, _toggle_col = st.columns([8, 1])
    with _title_col:
        st.markdown("# 本地数据脱敏工具")
        st.markdown(
            '<p class="pda-caption">文件只在本机处理，不会上传到服务器，也不会调用大模型。</p>',
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


def render_anonymize() -> None:
    # 初始化session state
    if "anonymize_file" not in st.session_state:
        st.session_state.anonymize_file = None
    if "seed_file" not in st.session_state:
        st.session_state.seed_file = None
    if "header_mode" not in st.session_state:
        st.session_state.header_mode = "自动检测"
    if "custom_header_row" not in st.session_state:
        st.session_state.custom_header_row = 1
    if "processing" not in st.session_state:
        st.session_state.processing = False
    
    # 显示进度指示器
    st.markdown(
        """
        <div class="stage-container">
            <div class="stage """ + ("active" if not st.session_state.anonymize_file and not st.session_state.processing else "") + (" completed" if st.session_state.anonymize_file or st.session_state.processing else "") + """">
                <div class="stage-dot">1</div>
                <div class="stage-label">上传文件</div>
            </div>
            <div class="stage """ + ("active" if st.session_state.anonymize_file and not st.session_state.processing else "") + (" completed" if st.session_state.processing else "") + """">
                <div class="stage-dot">2</div>
                <div class="stage-label">配置选项</div>
            </div>
            <div class="stage """ + ("active" if st.session_state.processing else "") + """">
                <div class="stage-dot">3</div>
                <div class="stage-label">处理中</div>
            </div>
            <div class="stage """ + ("completed" if st.session_state.processing else "") + """">
                <div class="stage-dot">✓</div>
                <div class="stage-label">完成</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    st.divider()
    
    # 第一步：上传文件
    st.markdown("### 第一步：选择需要脱敏的文件")
    source_file = st.file_uploader(
        "选择 Excel 或 CSV 文件",
        type=["csv", "xlsx"],
        accept_multiple_files=False,
        key="source_file_uploader",
        label_visibility="collapsed",
        disabled=st.session_state.processing,
    )
    
    if source_file is not None:
        st.session_state.anonymize_file = source_file
        st.markdown(
            f"""
            <div class="pda-selected-file">
                <p>文件已选择</p>
                <p>{source_file.name} ({source_file.size / 1024:.1f} KB)</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    # 第二步：可选配置
    if st.session_state.anonymize_file:
        st.markdown("### 第二步：配置处理选项（可选）")
        
        with st.expander("同一批次追加文件？上传已有匹配文件（可选）", expanded=False):
            st.markdown(
                """
                <p>
                    如需在同一批次追加处理相同数据，上传已有的匹配文件。这样新出现的相同实体将沿用之前的匹配结果，保持一致性。
                </p>
                """,
                unsafe_allow_html=True,
            )
            seed_file = st.file_uploader(
                "选择已有的 mapping.local.json 或 mapping_table.csv",
                type=["json", "csv"],
                accept_multiple_files=False,
                key="seed_file_uploader",
                label_visibility="collapsed",
                disabled=st.session_state.processing,
            )
            if seed_file is not None:
                st.session_state.seed_file = seed_file
        
        with st.expander("表格格式配置（可选）", expanded=False):
            st.markdown(
                """
                <p>
                    如果 Excel 或 CSV 的首行是标题文字（如"2024年度员工统计表"），而非列名表头，请在此调整。
                </p>
                """,
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
                custom_row = st.number_input("表头行号", min_value=1, value=st.session_state.custom_header_row, step=1, key="custom_header_row_input")
                st.session_state.custom_header_row = custom_row
        
        st.divider()
        
        # 开始处理按钮
        col1, col2 = st.columns([2, 1])
        with col1:
            start_btn = st.button(
                "开始处理",
                use_container_width=True,
                type="primary",
                disabled=st.session_state.processing,
                key="start_anonymize_btn",
            )
        with col2:
            reset_btn = st.button(
                "重新选择",
                use_container_width=True,
                disabled=st.session_state.processing,
                key="reset_anonymize_btn",
            )
        
        if reset_btn:
            st.session_state.anonymize_file = None
            st.session_state.seed_file = None
            st.session_state.header_mode = "自动检测"
            st.session_state.custom_header_row = 1
            st.rerun()
        
        if start_btn:
            st.session_state.processing = True
            st.rerun()
    
    # 处理流程
    if st.session_state.processing and st.session_state.anonymize_file:
        try:
            # 显示处理进度
            progress_container = st.container()
            with progress_container:
                st.markdown("### 处理进度")
                progress_bar = st.progress(0)
                
                # 模拟处理过程
                processing_steps = [
                    ("读取文件中...", 0.25),
                    ("检测敏感信息...", 0.50),
                    ("执行匿名化...", 0.75),
                    ("生成结果...", 1.0),
                ]
                
                for step_name, progress in processing_steps:
                    with st.spinner(step_name):
                        progress_bar.progress(progress)
            
            # 计算 header_row
            _header_mode = st.session_state.get("header_mode", "自动检测")
            if _header_mode == "自动检测":
                _header_row = None
            elif _header_mode == "第一行":
                _header_row = 1
            elif _header_mode == "第二行":
                _header_row = 2
            else:
                _header_row = st.session_state.get("custom_header_row", 1)
            
            # 执行处理
            result = anonymize_upload(
                st.session_state.anonymize_file.name,
                st.session_state.anonymize_file.getvalue(),
                seed_mapping_filename=st.session_state.seed_file.name if st.session_state.seed_file else None,
                seed_mapping_content=st.session_state.seed_file.getvalue() if st.session_state.seed_file else None,
                header_row=_header_row,
            )
            
            # 清空进度显示
            progress_container.empty()
            
            # 显示成功信息
            st.success(f"脱敏完成：{result['row_count']} 行，生成 {result['new_entity_count']} 个匹配项。")
            
            # 处理统计信息
            new_count = result["new_entity_count"]
            total_count = result["entity_count"]
            
            st.markdown(
                f"""
                <div class="pda-stats">
                    <p class="pda-stats-title">处理统计</p>
                    <div class="pda-stats-grid">
                        <div class="pda-stat">
                            <p class="pda-stat-num">{result['row_count']}</p>
                            <p class="pda-stat-label">数据行数</p>
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
            
            # 下载选项
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
                    on_click=lambda: st.session_state.update({"processing": False, "anonymize_file": None, "seed_file": None, "header_mode": "自动检测", "custom_header_row": 1}),
                    key="process_another",
                )
            
            st.markdown(
                """
                <p class="pda-download-caption">
                    ZIP 包含脱敏 Excel + 匹配文件 + 使用说明，反脱敏时只需上传其中的 mapping.local.json。
                </p>
                """,
                unsafe_allow_html=True,
            )
            
            # 单独下载选项
            with st.expander("单独下载各文件", expanded=False):
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button(
                        "Excel 脱敏数据",
                        data=result["anonymized_xlsx"],
                        file_name="anonymized.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        key="download_xlsx",
                    )
                    st.download_button(
                        "匹配文件 JSON",
                        data=str(result["mapping_json"]).encode("utf-8"),
                        file_name="mapping.local.json",
                        mime="application/json",
                        use_container_width=True,
                        key="download_json",
                    )
                with col2:
                    st.download_button(
                        "CSV 脱敏数据",
                        data=result["anonymized_csv"],
                        file_name="anonymized.csv",
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
            
            st.warning("匹配文件和匹配表包含原始敏感信息，只能保存在本地。")
            
        except Exception as exc:
            st.session_state.processing = False
            st.error(f"处理失败：{str(exc)}")
            if st.button("重新尝试", use_container_width=True):
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
    # 初始化session state
    if "restore_report" not in st.session_state:
        st.session_state.restore_report = None
    if "restore_mapping" not in st.session_state:
        st.session_state.restore_mapping = None
    if "restore_processing" not in st.session_state:
        st.session_state.restore_processing = False
    
    # 显示进度指示器
    st.markdown(
        """
        <div class="stage-container">
            <div class="stage """ + ("active" if not (st.session_state.restore_report and st.session_state.restore_mapping) else "") + ("" if not st.session_state.restore_processing else " completed") + """">
                <div class="stage-dot">1</div>
                <div class="stage-label">上传文件</div>
            </div>
            <div class="stage """ + ("active" if st.session_state.restore_report and st.session_state.restore_mapping and not st.session_state.restore_processing else "") + ("" if not st.session_state.restore_processing else " completed") + """">
                <div class="stage-dot">2</div>
                <div class="stage-label">确认处理</div>
            </div>
            <div class="stage """ + ("active" if st.session_state.restore_processing else "") + """">
                <div class="stage-dot">3</div>
                <div class="stage-label">恢复中</div>
            </div>
            <div class="stage """ + ("completed" if st.session_state.restore_processing else "") + """">
                <div class="stage-dot">✓</div>
                <div class="stage-label">完成</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    st.divider()
    
    # 第一步：上传报告文件
    st.markdown("### 第一步：选择待恢复的报告文件")
    report_file = st.file_uploader(
        "支持 md / txt / html / docx / pptx 等格式",
        type=["md", "txt", "html", "htm", "docx", "pptx"],
        accept_multiple_files=False,
        key="report_file_uploader",
        label_visibility="collapsed",
        disabled=st.session_state.restore_processing,
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
    
    # 第二步：上传匹配文件
    st.markdown("### 第二步：选择匹配文件")
    mapping_file = st.file_uploader(
        "选择 mapping.local.json 或 mapping_table.csv",
        type=["json", "csv"],
        accept_multiple_files=False,
        key="mapping_file_uploader",
        label_visibility="collapsed",
        disabled=st.session_state.restore_processing,
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
    
    st.divider()
    
    # 处理按钮
    if st.session_state.restore_report and st.session_state.restore_mapping:
        col1, col2 = st.columns([2, 1])
        with col1:
            start_restore_btn = st.button(
                "开始恢复",
                use_container_width=True,
                type="primary",
                disabled=st.session_state.restore_processing,
                key="start_restore_btn",
            )
        with col2:
            reset_restore_btn = st.button(
                "重新选择",
                use_container_width=True,
                disabled=st.session_state.restore_processing,
                key="reset_restore_btn",
            )
        
        if reset_restore_btn:
            st.session_state.restore_report = None
            st.session_state.restore_mapping = None
            st.rerun()
        
        if start_restore_btn:
            st.session_state.restore_processing = True
            st.rerun()
    else:
        if report_file or mapping_file:
            st.info("请同时上传报告文件和匹配文件。")
    
    # 处理流程
    if st.session_state.restore_processing and st.session_state.restore_report and st.session_state.restore_mapping:
        try:
            # 显示处理进度
            progress_container = st.container()
            with progress_container:
                st.markdown("### 处理进度")
                progress_bar = st.progress(0)
                
                # 模拟处理过程
                processing_steps = [
                    ("读取报告文件...", 0.33),
                    ("加载匹配信息...", 0.66),
                    ("执行恢复...", 1.0),
                ]
                
                for step_name, progress in processing_steps:
                    with st.spinner(step_name):
                        progress_bar.progress(progress)
            
            # 执行处理
            result = restore_report_upload(
                report_content=st.session_state.restore_report.getvalue(),
                report_filename=st.session_state.restore_report.name,
                mapping_filename=st.session_state.restore_mapping.name,
                mapping_content=st.session_state.restore_mapping.getvalue(),
            )
            
            # 清空进度显示
            progress_container.empty()
            
            # 显示成功信息
            st.success("报告恢复完成。")
            
            st.divider()
            
            # 下载选项
            st.markdown("### 下载恢复结果")
            
            suffix = "." + result["filename"].rsplit(".", 1)[-1]
            mime = _RESTORE_MIME.get(f".{result['filename'].rsplit('.', 1)[-1]}", "application/octet-stream")
            
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
                    on_click=lambda: st.session_state.update({"restore_processing": False, "restore_report": None, "restore_mapping": None}),
                    key="restore_another",
                )
            
            # 预览恢复结果
            is_text = suffix in {".md", ".txt", ".html", ".htm"}
            if is_text:
                with st.expander("预览恢复结果", expanded=True):
                    text = result["content"].decode("utf-8")
                    st.markdown(text)
            
        except Exception as exc:
            st.session_state.restore_processing = False
            st.error(f"恢复失败：{str(exc)}")
            if st.button("重新尝试", use_container_width=True):
                st.rerun()


if __name__ == "__main__":
    main()
