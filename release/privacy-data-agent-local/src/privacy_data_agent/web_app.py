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

    with st.expander("同一批次追加文件？上传已有匹配文件（可选）"):
        st.caption("上传后，本批次中出现的相同姓名/部门将沿用之前的 token，新实体继续随机生成。不同批次无需上传，保持独立安全。")
        seed_file = st.file_uploader(
            "选择已有的 mapping.local.json 或 mapping_table.csv",
            type=["json", "csv"],
            accept_multiple_files=False,
            key="seed_file",
        )

    if source_file is None:
        return

    try:
        result = anonymize_upload(
            source_file.name,
            source_file.getvalue(),
            seed_mapping_filename=seed_file.name if seed_file else None,
            seed_mapping_content=seed_file.getvalue() if seed_file else None,
        )
    except Exception as exc:
        st.error(f"处理失败：{exc}")
        return

    new_count = result["new_entity_count"]
    total_count = result["entity_count"]
    if seed_file:
        st.success(f"脱敏完成：{result['row_count']} 行，新增 {new_count} 个实体，累计 {total_count} 个匹配项。")
    else:
        st.success(f"脱敏完成：{result['row_count']} 行，生成 {total_count} 个匹配项。")

    zip_name = f"{result['stem']}_脱敏包.zip"
    st.download_button(
        "⬇️ 一键打包下载（推荐）",
        data=result["zip_bundle"],
        file_name=zip_name,
        mime="application/zip",
        use_container_width=True,
        type="primary",
    )
    st.caption("ZIP 包含脱敏 Excel + 匹配文件 + 使用说明，反脱敏时只需上传其中的 mapping.local.json。")

    with st.expander("单独下载各文件"):
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


_RESTORE_MIME = {
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".html": "text/html",
    ".htm": "text/html",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def render_restore() -> None:
    st.subheader("上传报告和匹配文件")
    report_file = st.file_uploader(
        "选择待恢复的报告文件（支持 md / txt / html / docx / pptx）",
        type=["md", "txt", "html", "htm", "docx", "pptx"],
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
        result = restore_report_upload(
            report_content=report_file.getvalue(),
            report_filename=report_file.name,
            mapping_filename=mapping_file.name,
            mapping_content=mapping_file.getvalue(),
        )
    except Exception as exc:
        st.error(f"恢复失败：{exc}")
        return

    suffix = "." + result["filename"].rsplit(".", 1)[-1]
    mime = _RESTORE_MIME.get(f".{result['filename'].rsplit('.', 1)[-1]}", "application/octet-stream")

    st.success("报告恢复完成。")
    st.download_button(
        "下载反脱敏报告",
        data=result["content"],
        file_name=result["filename"],
        mime=mime,
        use_container_width=True,
        type="primary",
    )

    is_text = suffix in {".md", ".txt", ".html", ".htm"}
    if is_text:
        with st.expander("预览恢复结果", expanded=True):
            text = result["content"].decode("utf-8")
            st.text_area("恢复后的内容", value=text, height=260)


if __name__ == "__main__":
    main()
