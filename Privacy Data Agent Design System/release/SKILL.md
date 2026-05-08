# SKILL.md — Privacy Data Agent Design System

## How to use this design system

This file helps an AI agent (Claude or similar) produce designs consistent with the **Privacy Data Agent** product.

---

## Product in one line

A local-first data-anonymization web app (Streamlit + Python CLI) for Chinese enterprise HR/sales teams. It replaces sensitive spreadsheet data with opaque tokens before sending to AI, then restores original values after.

---

## Design rules (do these)

1. **Follow Streamlit's visual language.** The product intentionally uses Streamlit defaults — no custom brand palette. Use the token values in `colors_and_type.css`.

2. **Chinese-first copy.** All user-facing labels, button text, captions, and alerts are in Simplified Chinese. Technical strings (file names, token format `PDA_XXXX…`, CLI flags) stay in ASCII.

3. **Centered single column.** Max width 730px. `padding-top: 64px`. No sidebars, no multi-column layouts outside the 2-col download grid.

4. **Status through alerts.** Use the 4 semantic alert types:
   - `success` — green: operation complete + counts
   - `warning` — amber: security reminders about sensitive data
   - `error` — red: processing failure with `{exc}` details
   - `info` — blue: empty/waiting states

5. **One primary CTA per screen.** Full-width red-orange `#ff4b4b` button for the key download action. All other downloads are secondary (gray).

6. **Progressive disclosure via expanders.** Optional inputs (seed mapping file) and secondary downloads (individual files) go inside `st.expander`. Keep the main path clear.

7. **Privacy reassurance upfront.** Always show the caption "文件只在本机处理，不会上传到服务器，也不会调用大模型。" near the top.

8. **Token format.** Anonymized tokens look like `PDA_A1B2C3D4E5F60708` — 16 uppercase hex chars after the `PDA_` prefix. Render in monospace (`Source Code Pro` or system mono).

9. **Minimal iconography.** Only `⬇️` on the primary download button. No icon libraries. No decorative icons.

10. **No custom animations.** Streamlit re-renders on interaction. Only use a CSS spinner for processing states in custom UI.

---

## Design rules (avoid these)

- ❌ No sidebars, hero sections, or navigation bars
- ❌ No gradient backgrounds or decorative imagery
- ❌ No emoji beyond `⬇️` (page icon `🔒` is set by Streamlit)
- ❌ No pill-shaped or extra-rounded buttons (use `border-radius: 6px`)
- ❌ No color palette outside the token system in `colors_and_type.css`
- ❌ No text smaller than 12px (captions minimum 13px)
- ❌ No marketing copy or taglines — purely functional tone
- ❌ Don't use Inter, Roboto, or system-ui as primary font — use Source Sans Pro
- ❌ Don't show raw sensitive values (`张三`, phone numbers, ID numbers) in UI demos — use tokens or dummy data only

---

## Key UI strings (copy verbatim)

```
Page title:        本地数据脱敏工具
Page caption:      文件只在本机处理，不会上传到服务器，也不会调用大模型。
Tab 1:             数据脱敏
Tab 2:             报告反脱敏
Subheader 1:       上传 Excel 或 CSV
Subheader 2:       上传报告和匹配文件
Primary CTA:       ⬇️ 一键打包下载（推荐）
Restore CTA:       下载反脱敏报告
ZIP caption:       ZIP 包含脱敏 Excel + 匹配文件 + 使用说明，反脱敏时只需上传其中的 mapping.local.json。
Security warning:  匹配文件和匹配表包含原始敏感信息，只能保存在本地。
Empty state:       请同时上传报告文件和匹配文件。
Success (anon):    脱敏完成：{N} 行，生成 {M} 个匹配项。
Success (restore): 报告恢复完成。
Expander (seed):   同一批次追加文件？上传已有匹配文件（可选）
Expander (files):  单独下载各文件
Expander (preview):预览恢复结果
```

---

## Token color quick-reference

| Role | Value |
|---|---|
| Primary accent | `#ff4b4b` |
| Primary hover | `#e03e3e` |
| Text primary | `#1f1f1f` |
| Text secondary | `#6b6b6b` |
| Text muted | `#808495` |
| Border | `#e6e9ef` |
| Background | `#ffffff` |
| Background secondary | `#f0f2f6` |
| Success | `#21c354` bg `#e6f9ed` text `#0d6b2c` |
| Warning | `#ffa421` bg `#fff8e8` text `#7a4f00` |
| Error | `#ff4b4b` bg `#fde8e8` text `#8b1a1a` |
| Info | `#1c83e1` bg `#e8f2fd` text `#0a4a85` |

---

## File structure

```
README.md                    Design system overview
SKILL.md                     This file
colors_and_type.css          All CSS custom properties / tokens
preview/
  colors-base.html           Neutral + primary palette swatches
  colors-semantic.html       Status colors + token monospace
  type-scale.html            Typography scale specimen
  type-chinese.html          Chinese text rendering
  spacing-tokens.html        Spacing, radius, shadows, layout
  component-buttons.html     Button states
  component-upload.html      File upload zone variants
  component-alerts.html      4× alert types
  component-tabs.html        Tab/radio switcher
  component-expander.html    Expander variants
  component-download.html    Download CTA patterns
ui_kits/web_app/
  index.html                 ← Interactive prototype (main deliverable)
```

---

## Sensitive data in demos

Never use real sensitive values in demos. Use:
- Names: 张三, 李四, 王五 (these are the fixture names from `tests/fixtures/hr_sample.csv` — acceptable as fictional placeholders)
- Tokens: `PDA_A1B2C3D4E5F60708`
- Files: `hr_data_2025q1.xlsx`, `mapping.local.json`, `report.restored.md`

---

## Supported file types

| Operation | Input formats |
|---|---|
| Anonymize | `.csv`, `.xlsx` |
| Seed mapping | `.json`, `.csv` (mapping.local.json or mapping_table.csv) |
| Restore report | `.md`, `.txt`, `.html`, `.htm`, `.docx`, `.pptx` |

---

## Entity types detected

| Type | `entity_type` value | Example column hints |
|---|---|---|
| Person name | `employee` | 姓名, 员工, 负责人, 联系人 |
| Chinese ID | `id_number` | 身份证, 证件 |
| Employee ID | `employee_id` | 工号, 员工编号 |
| Department | `department` | 部门, 组织, 中心, 团队 |
| Customer/company | `customer` | 客户, 公司, 企业, 供应商 |
| Phone | `phone` | 手机号, 电话 |
| Email | `email` | 邮箱, email |
