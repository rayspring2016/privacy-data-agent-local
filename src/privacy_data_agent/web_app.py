from __future__ import annotations

import streamlit as st

from privacy_data_agent.web_helpers import anonymize_upload, restore_report_upload

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

        /* ── Typography ─────────────────────────────────────────── */

        .stMarkdown h1 {
            color: var(--pda-text) !important;
            font-size: 2rem !important;
            font-weight: 700 !important;
            line-height: 1.15 !important;
            margin-bottom: 0.4rem !important;
            margin-top: 0 !important;
            letter-spacing: -0.02em;
        }

        .stMarkdown h2 {
            color: var(--pda-text) !important;
            font-size: 1.375rem !important;
            font-weight: 600 !important;
            line-height: 1.25 !important;
            margin-top: 1.5rem !important;
            margin-bottom: 0.75rem !important;
            letter-spacing: -0.01em;
        }

        .stMarkdown h3 {
            color: var(--pda-text) !important;
            font-size: 1.125rem !important;
            font-weight: 600 !important;
            line-height: 1.3 !important;
            margin-top: 1.25rem !important;
            margin-bottom: 0.65rem !important;
        }

        .stMarkdown p, .stCaption, label, [data-testid="stMarkdownContainer"] {
            color: var(--pda-text-secondary) !important;
            line-height: 1.55 !important;
            font-size: 0.9375rem !important;
        }

        code {
            font-family: var(--pda-mono) !important;
            font-size: 0.8125rem !important;
            font-weight: 500 !important;
            background: var(--pda-bg-secondary) !important;
            color: var(--pda-text) !important;
            border-radius: 4px !important;
            padding: 0.1em 0.35em !important;
        }

        .stDivider {
            border-color: var(--pda-border) !important;
            margin: 1.25rem 0 !important;
        }

        /* ── Tabs ────────────────────────────────────────────────── */

        [data-baseweb="tab-list"] {
            gap: 1.5rem !important;
            border-bottom: 1px solid var(--pda-border) !important;
            margin-top: 1rem !important;
        }

        [data-baseweb="tab"] {
            color: var(--pda-text-muted) !important;
            font-weight: 500 !important;
            padding: 0.85rem 0 !important;
            background: transparent !important;
            transition: color 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
        }

        [data-baseweb="tab"][aria-selected="true"] {
            color: var(--pda-text) !important;
        }

        [data-baseweb="tab-highlight"] {
            background-color: var(--pda-primary) !important;
            height: 2px !important;
            transition: width 0.3s cubic-bezier(0.16, 1, 0.3, 1) !important;
        }

        [data-baseweb="tab-border"] {
            display: none !important;
        }

        /* ── Radio group (tab-style) ─────────────────────────────── */

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
            margin-right: 1.5rem !important;
            border-radius: 0 !important;
            background: transparent !important;
            border: 0 !important;
            border-bottom: 2px solid transparent !important;
            cursor: pointer !important;
            transition: color 0.2s cubic-bezier(0.16, 1, 0.3, 1),
                        border-color 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
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
            font-weight: 500 !important;
            font-size: 0.9375rem !important;
            color: var(--pda-text-muted) !important;
            margin: 0 !important;
            line-height: 1.4 !important;
        }

        [role="radio"][aria-checked="true"] > label {
            color: var(--pda-text) !important;
        }

        /* ── File uploader ───────────────────────────────────────── */

        .uploadedFile {
            background: var(--pda-success-bg) !important;
            border: 1px solid var(--pda-success-border) !important;
            border-radius: 7px !important;
            padding: 0.8rem !important;
            margin: 0.6rem 0 !important;
        }

        [data-testid="stFileUploader"] {
            background: var(--pda-bg) !important;
            border: 1.5px solid var(--pda-border-strong) !important;
            border-radius: 8px !important;
            padding: 1.5rem !important;
            margin: 0.6rem 0 !important;
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.6), 0 1px 3px rgba(0,0,0,0.04);
            transition: border-color 0.2s cubic-bezier(0.16, 1, 0.3, 1),
                        background 0.2s cubic-bezier(0.16, 1, 0.3, 1),
                        box-shadow 0.2s ease !important;
        }

        [data-testid="stFileUploader"]:hover {
            border-color: var(--pda-primary) !important;
            background: var(--pda-primary-subtle) !important;
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.6), 0 2px 8px rgba(181,91,79,0.06);
        }

        /* ── Buttons ─────────────────────────────────────────────── */

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

        /* ── Download button arrow icon ──────────────────────────── */

        .stDownloadButton > button[kind="primary"]::before,
        [data-testid="stBaseButton-primary"]::before {
            content: '';
            display: inline-block;
            width: 8px;
            height: 8px;
            border-right: 2px solid currentColor;
            border-bottom: 2px solid currentColor;
            transform: rotate(45deg) translateY(-1px);
            margin-right: 8px;
            opacity: 0.9;
        }

        /* ── Alerts ──────────────────────────────────────────────── */

        [data-testid="stAlert"] {
            border-radius: 7px !important;
            border: 1px solid !important;
            border-left-width: 3px !important;
            padding: 0.8rem !important;
            margin: 0.6rem 0 !important;
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.5) !important;
        }

        [data-testid="stAlert"][kind="info"] {
            background: var(--pda-info-bg) !important;
            border-color: var(--pda-info-border) !important;
            border-left-color: var(--pda-info-text) !important;
            color: var(--pda-info-text) !important;
        }

        [data-testid="stAlert"][kind="success"] {
            background: var(--pda-success-bg) !important;
            border-color: var(--pda-success-border) !important;
            border-left-color: var(--pda-success) !important;
            color: var(--pda-success-text) !important;
        }

        [data-testid="stAlert"][kind="error"] {
            background: var(--pda-error-bg) !important;
            border-color: var(--pda-error-border) !important;
            border-left-color: var(--pda-error-text) !important;
            color: var(--pda-error-text) !important;
            animation: error-shake 0.4s ease;
        }

        [data-testid="stAlert"][kind="warning"] {
            background: var(--pda-warning-bg) !important;
            border-color: var(--pda-warning-border) !important;
            border-left-color: var(--pda-warning) !important;
            color: var(--pda-warning-text) !important;
        }

        /* ── Expanders ───────────────────────────────────────────── */

        [data-testid="stExpander"] {
            background: var(--pda-bg) !important;
            border: 1px solid var(--pda-border) !important;
            border-radius: 8px !important;
            margin: 0.6rem 0 !important;
            box-shadow: 0 1px 3px rgba(0,0,0,0.03);
            transition: box-shadow 0.2s ease !important;
        }

        [data-testid="stExpander"]:hover {
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        }

        [data-testid="stExpander"] summary {
            color: var(--pda-text) !important;
            font-weight: 600 !important;
            padding: 0.8rem !important;
            transition: background 0.15s cubic-bezier(0.16, 1, 0.3, 1) !important;
        }

        [data-testid="stExpander"] summary:hover {
            background: var(--pda-bg-tertiary) !important;
        }

        /* ── Inputs ──────────────────────────────────────────────── */

        input, textarea, select {
            background: var(--pda-bg) !important;
            border: 1px solid var(--pda-border-strong) !important;
            color: var(--pda-text) !important;
            border-radius: 7px !important;
            transition: border-color 0.2s cubic-bezier(0.16, 1, 0.3, 1),
                        box-shadow 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
        }

        input:focus, textarea:focus, select:focus {
            border-color: var(--pda-primary) !important;
            box-shadow: 0 0 0 1px var(--pda-primary) !important;
            outline: none !important;
        }

        /* ── Custom: caption ─────────────────────────────────────── */

        .pda-caption {
            color: var(--pda-text-secondary);
            font-size: 0.9375rem;
            margin: 0.25rem 0 1.5rem;
        }

        /* ── Custom: selected file badge ─────────────────────────── */

        .pda-selected-file {
            background: var(--pda-success-bg);
            border: 1px solid var(--pda-success-border);
            border-left: 3px solid var(--pda-success);
            border-radius: 7px;
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
            font-size: 0.875rem;
            font-family: var(--pda-mono);
        }

        /* ── Custom: stats card (key-value rows) ─────────────────── */

        .pda-stats {
            background: var(--pda-bg-secondary);
            border: 1px solid var(--pda-border);
            border-radius: 8px;
            padding: 1.25rem;
            margin: 1.25rem 0;
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.6), 0 1px 3px rgba(0,0,0,0.03);
        }

        .pda-stats-title {
            margin: 0 0 1rem 0;
            color: var(--pda-text);
            font-weight: 600;
            font-size: 0.9375rem;
        }

        .pda-stats-rows {
            display: flex;
            flex-direction: column;
        }

        .pda-stats-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.65rem 0;
            border-bottom: 1px solid var(--pda-border);
            animation: fade-in-up 0.4s cubic-bezier(0.16, 1, 0.3, 1) both;
        }

        .pda-stats-row:nth-child(1) { animation-delay: 0.00s; }
        .pda-stats-row:nth-child(2) { animation-delay: 0.05s; }
        .pda-stats-row:nth-child(3) { animation-delay: 0.10s; }

        .pda-stats-row:last-child {
            border-bottom: none;
        }

        .pda-stat-num {
            margin: 0;
            color: var(--pda-text);
            font-size: 1.25rem;
            font-weight: 700;
            font-family: var(--pda-mono);
        }

        .pda-stat-label {
            margin: 0;
            color: var(--pda-text-secondary);
            font-size: 0.8125rem;
            font-weight: 500;
        }

        /* ── Custom: download caption ────────────────────────────── */

        .pda-download-caption {
            color: var(--pda-text-secondary);
            font-size: 0.85rem;
            margin-top: 1rem;
        }

        /* ── Custom: horizontal progress tracker ─────────────────── */

        .progress-tracker {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin: 1.25rem 0;
        }

        .progress-step {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 0.4rem;
            flex-shrink: 0;
        }

        .progress-connector {
            flex: 1;
            height: 1.5px;
            min-width: 12px;
            margin: 0 4px;
            margin-bottom: 1.35rem;
            background: var(--pda-border);
            transition: background 0.4s cubic-bezier(0.16, 1, 0.3, 1);
        }

        .progress-connector.done {
            background: var(--pda-success);
        }

        .progress-connector.active {
            background: var(--pda-primary);
        }

        .progress-dot {
            width: 26px;
            height: 26px;
            border-radius: 50%;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            font-weight: 600;
            font-size: 0.75rem;
            background: var(--pda-bg-secondary);
            color: var(--pda-text-secondary);
            border: 1.5px solid var(--pda-border-strong);
            transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
        }

        .progress-step.active .progress-dot {
            background: var(--pda-primary);
            border-color: var(--pda-primary);
            color: #ffffff;
            animation: step-pulse 1.5s ease-in-out infinite;
            box-shadow: 0 0 0 4px var(--pda-primary-subtle);
        }

        .progress-step.completed .progress-dot {
            background: var(--pda-success);
            border-color: var(--pda-success);
            color: #ffffff;
        }

        .progress-label {
            font-size: 0.75rem;
            color: var(--pda-text-secondary);
            font-weight: 500;
            white-space: nowrap;
            transition: color 0.3s cubic-bezier(0.16, 1, 0.3, 1);
        }

        .progress-step.active .progress-label {
            color: var(--pda-primary);
            font-weight: 600;
        }

        .progress-step.completed .progress-label {
            color: var(--pda-success-text);
        }

        /* ── Dark mode toggle positioning ────────────────────────── */

        .pda-header-row {
            position: relative;
        }

        [data-testid="stToggle"] {
            margin-top: 0.25rem;
        }

        /* ── Keyframes ───────────────────────────────────────────── */

        @keyframes fade-in-up {
            from {
                opacity: 0;
                transform: translateY(8px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        @keyframes shimmer {
            0% {
                background-position: -400px 0;
            }
            100% {
                background-position: 400px 0;
            }
        }

        @keyframes step-pulse {
            0%, 100% {
                box-shadow: 0 0 0 4px var(--pda-primary-subtle);
            }
            50% {
                box-shadow: 0 0 0 8px rgba(181,91,79,0.02);
            }
        }

        @keyframes error-shake {
            0%, 100% { transform: translateX(0); }
            10%, 50%, 90% { transform: translateX(-2px); }
            30%, 70% { transform: translateX(2px); }
        }

        .pda-loading-skeleton {
            background: linear-gradient(
                90deg,
                var(--pda-bg-tertiary) 25%,
                var(--pda-bg-secondary) 50%,
                var(--pda-bg-tertiary) 75%
            );
            background-size: 400px 100%;
            animation: shimmer 1.5s ease-in-out infinite;
            border-radius: 6px;
            height: 1rem;
        }

        /* ── Mobile ──────────────────────────────────────────────── */

        @media (max-width: 480px) {
            .block-container {
                padding-left: 1rem;
                padding-right: 1rem;
                padding-top: 2.5rem;
            }
            .stMarkdown h1 {
                font-size: 1.75rem !important;
            }
            .stMarkdown h2 {
                font-size: 1.25rem !important;
            }
            [role="radiogroup"] {
                overflow-x: auto !important;
                flex-wrap: nowrap !important;
            }
            .progress-tracker {
                margin: 1rem 0;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("# 本地数据脱敏工具")
    st.markdown(
        '<p class="pda-caption">文件只在本机处理，不会上传到服务器，也不会调用大模型。</p>',
        unsafe_allow_html=True,
    )
    st.toggle("深色模式", key="dark_mode")

    anonymize_tab, restore_tab = st.tabs(["数据脱敏", "报告反脱敏"])

    with anonymize_tab:
        render_anonymize()

    with restore_tab:
        render_restore()


def _stage_html(s1: str, s2: str, s3: str, s4: str, label3: str = "处理中") -> str:
    def _connector(a: str, b: str) -> str:
        if a == "completed" and b == "completed":
            return "done"
        if a == "completed" and b == "active":
            return "active"
        return ""

    c12 = _connector(s1, s2)
    c23 = _connector(s2, s3)
    c34 = _connector(s3, s4)

    return f"""
    <div class="progress-tracker">
        <div class="progress-step {s1}">
            <div class="progress-dot">{'&#10003;' if s1 == 'completed' else '1'}</div>
            <div class="progress-label">上传文件</div>
        </div>
        <div class="progress-connector {c12}"></div>
        <div class="progress-step {s2}">
            <div class="progress-dot">{'&#10003;' if s2 == 'completed' else '2'}</div>
            <div class="progress-label">配置选项</div>
        </div>
        <div class="progress-connector {c23}"></div>
        <div class="progress-step {s3}">
            <div class="progress-dot">{'&#10003;' if s3 == 'completed' else '3'}</div>
            <div class="progress-label">{label3}</div>
        </div>
        <div class="progress-connector {c34}"></div>
        <div class="progress-step {s4}">
            <div class="progress-dot">{'&#10003;' if s4 == 'completed' else '4'}</div>
            <div class="progress-label">完成</div>
        </div>
    </div>
    """


def render_anonymize() -> None:
    for key, default in [
        ("anonymize_file", None),
        ("seed_file", None),
        ("header_mode", "自动检测"),
        ("custom_header_row", 1),
        ("processing", False),
        ("anonymize_result", None),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    has_file = st.session_state.anonymize_file is not None
    proc = st.session_state.processing
    has_result = st.session_state.anonymize_result is not None

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

                result = anonymize_upload(
                    st.session_state.anonymize_file.name,
                    st.session_state.anonymize_file.getvalue(),
                    seed_mapping_filename=st.session_state.seed_file.name if st.session_state.seed_file else None,
                    seed_mapping_content=st.session_state.seed_file.getvalue() if st.session_state.seed_file else None,
                    header_row=_header_row,
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
        result = st.session_state.anonymize_result
        new_count = result["new_entity_count"]
        total_count = result["entity_count"]

        st.success(f"脱敏完成：{result['row_count']} 行，生成 {new_count} 个匹配项。")
        st.markdown(
            f"""
            <div class="pda-stats">
                <p class="pda-stats-title">处理统计</p>
                <div class="pda-stats-rows">
                    <div class="pda-stats-row">
                        <span class="pda-stat-num">{result['row_count']}</span>
                        <span class="pda-stat-label">数据行数</span>
                    </div>
                    <div class="pda-stats-row">
                        <span class="pda-stat-num">{new_count}</span>
                        <span class="pda-stat-label">新增实体</span>
                    </div>
                    <div class="pda-stats-row">
                        <span class="pda-stat-num">{total_count}</span>
                        <span class="pda-stat-label">总计实体</span>
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
                "一键打包下载（推荐）",
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
                    "anonymize_result": None,
                }),
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
        return

    # ── Upload & config phase ─────────────────────────────────────────────────
    st.markdown("### 第一步：选择需要脱敏的文件")
    source_file = st.file_uploader(
        "选择 Excel 或 CSV 文件",
        type=["csv", "xlsx"],
        accept_multiple_files=False,
        key="source_file_uploader",
        label_visibility="collapsed",
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

    if source_file is not None:
        st.markdown("### 第二步：配置处理选项（可选）")

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

        with st.expander("表格格式配置（可选）", expanded=False):
            st.markdown(
                '<p>如果 Excel 或 CSV 的首行是标题文字（如"2024年度员工统计表"），而非列名表头，请在此调整。</p>',
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
                    "表头行号", min_value=1, value=st.session_state.custom_header_row, step=1, key="custom_header_row_input"
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
                "seed_file": None,
                "header_mode": "自动检测",
                "custom_header_row": 1,
                "anonymize_result": None,
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
