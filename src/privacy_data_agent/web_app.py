from __future__ import annotations

import streamlit as st

from privacy_data_agent.web_helpers import anonymize_upload, restore_report_upload


def main() -> None:
    st.set_page_config(
        page_title="本地数据脱敏工具",
        page_icon="lock",
        layout="centered",
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
        .block-container {
            padding-top: 4rem;
        }
        @media (max-width: 480px) {
            .block-container {
                padding-left: 1rem;
                padding-right: 1rem;
                padding-top: 3rem;
            }
            h1 {
                font-size: 2.25rem !important;
                line-height: 1.15 !important;
                word-break: keep-all;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("本地数据脱敏工具")
    st.caption("文件只在本机处理，不会上传到服务器，也不会调用大模型。")

    mode = st.radio(
        "选择功能",
        ["数据脱敏", "报告反脱敏"],
        horizontal=True,
        label_visibility="collapsed",
    )
    st.divider()

    if mode == "数据脱敏":
        render_anonymize()
    else:
        render_restore()


def render_anonymize() -> None:
    st.subheader("上传 Excel 或 CSV")
    source_file = st.file_uploader(
        "选择需要脱敏的数据文件",
        type=["csv", "xlsx"],
        accept_multiple_files=False,
        key="source_file",
    )
    if source_file is None:
        return

    try:
        result = anonymize_upload(source_file.name, source_file.getvalue())
    except Exception as exc:
        st.error(f"处理失败：{exc}")
        return

    st.success(f"脱敏完成：{result['row_count']} 行，生成 {result['entity_count']} 个匹配项。")
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "下载脱敏 Excel",
            data=result["anonymized_xlsx"],
            file_name="anonymized.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
        st.download_button(
            "下载匹配文件 JSON",
            data=str(result["mapping_json"]).encode("utf-8"),
            file_name="mapping.local.json",
            mime="application/json",
            use_container_width=True,
        )
    with col2:
        st.download_button(
            "下载脱敏 CSV",
            data=result["anonymized_csv"],
            file_name="anonymized.csv",
            mime="text/csv",
            use_container_width=True,
        )
        st.download_button(
            "下载匹配表 CSV",
            data=result["mapping_table_csv"],
            file_name="mapping_table.csv",
            mime="text/csv",
            use_container_width=True,
        )
    st.warning("匹配文件和匹配表包含原始敏感信息，只能保存在本地。")


def render_restore() -> None:
    st.subheader("上传报告和匹配表")
    report_file = st.file_uploader(
        "选择待恢复的报告文件",
        type=["md", "txt"],
        accept_multiple_files=False,
        key="report_file",
    )
    mapping_file = st.file_uploader(
        "选择 mapping.local.json 或 mapping_table.csv",
        type=["json", "csv"],
        accept_multiple_files=False,
        key="mapping_file",
    )
    if report_file is None or mapping_file is None:
        st.info("请同时上传报告文件和匹配文件。")
        return

    try:
        restored = restore_report_upload(
            report_content=report_file.getvalue(),
            mapping_filename=mapping_file.name,
            mapping_content=mapping_file.getvalue(),
        )
    except Exception as exc:
        st.error(f"恢复失败：{exc}")
        return

    st.success("报告恢复完成。")
    st.download_button(
        "下载反脱敏报告",
        data=restored.encode("utf-8"),
        file_name="report.restored.md",
        mime="text/markdown",
        use_container_width=True,
    )
    with st.expander("预览恢复结果", expanded=True):
        st.text_area("恢复后的报告内容", value=restored, height=260)


if __name__ == "__main__":
    main()
