# Privacy Data Agent — Design System

## Project Overview

**Privacy Data Agent** (本地数据脱敏工具) is a local-first data anonymization tool built for HR and sales/business teams in Chinese enterprises. It replaces sensitive fields (names, ID numbers, departments, customers, phones, emails) in spreadsheets with opaque random tokens before data leaves the machine — then restores original values after AI analysis returns.

**Product:** A Streamlit-based local web app + Python CLI package (`privacy-data-agent`). There is one product surface: a minimal two-tab web UI running at `127.0.0.1`.

**Source Repository:** `github.com/rayspring2016/data-desensitization` (private)  
Full repo available to those with access; key files include `src/privacy_data_agent/web_app.py` (UI), `web_helpers.py`, `anonymizer.py`, `detectors.py`, `models.py`.

---

## Products / Surfaces

| Surface | Description |
|---|---|
| **Web UI** (Streamlit) | Two-tab local page: "数据脱敏" (anonymize) and "报告反脱敏" (restore). Runs at 127.0.0.1. |
| **CLI** | `privacy-data-agent anonymize` / `restore` commands for power users and scripts. |

---

## CONTENT FUNDAMENTALS

### Language & Tone
- **Primary language:** Simplified Chinese (中文) for all user-facing copy. Technical strings (file names, tokens, code) remain in English/ASCII.
- **Voice:** Matter-of-fact, functional, reassuring. No marketing language. No exclamation points for hype.
- **Perspective:** 同事-to-同事 (colleague-to-colleague). The product speaks as a helpful technical colleague, not a brand.
- **Casing:** Sentence case in Chinese naturally. English labels use title case sparingly (e.g. "ZIP 包"). File names are always lowercase with hyphens or underscores.
- **Emoji usage:** Minimal and purposeful — only `⬇️` on the primary download button as a visual affordance. Not decorative.
- **Numbers:** Uses Chinese numerals in prose (一键, 两个功能); uses Arabic numerals for counts/data (120000, 1.0.0).
- **Tone examples from source:**
  - "文件只在本机处理，不会上传到服务器，也不会调用大模型。" — direct privacy reassurance upfront
  - "匹配文件和匹配表包含原始敏感信息，只能保存在本地。" — clear warning, no drama
  - "同一批次追加文件" — clear functional label, no fluff
  - "脱敏完成：X 行，生成 Y 个匹配项。" — concise success state with counts
- **Warnings vs errors:** Warnings use `st.warning()` (amber), errors use `st.error()` (red). Success uses `st.success()` (green). Info/empty states use `st.info()` (blue).
- **No slogans, no taglines.** Product is purely functional.

---

## VISUAL FOUNDATIONS

### Colors
The app uses **Streamlit's default theme** — no custom color overrides in `config.toml` beyond disabling usage stats and toolbar. This means:

- **Background:** White (`#ffffff`) for main content; light gray (`#f0f2f6`) for sidebar/secondary areas
- **Primary accent:** Streamlit red-orange (`#ff4b4b`) — used on primary buttons, focus rings
- **Text primary:** Dark gray-black (`#1f1f1f` / `#262730`)
- **Text secondary / captions:** Medium gray (`#6b6b6b` / `#808495`)
- **Success:** Muted green (`#21c354` / `#d4edda` background)
- **Warning:** Amber (`#ffa421` / `#fff3cd` background)
- **Error:** Red (`#ff4b4b` / `#fde8e8` background)
- **Info:** Blue (`#1c83e1` / `#e8f0fe` background)
- **Border / dividers:** Light gray (`#e6e9ef`)
- **Code/token text:** Monospace on light gray (`#f8f9fa`)

There is **no custom brand color palette** — the product intentionally adopts Streamlit defaults for zero-friction local tool aesthetics.

### Typography
- **Primary font:** Streamlit default — Source Sans Pro (web), falls back to system sans-serif
- **Chinese text rendering:** System default CJK fonts (`PingFang SC`, `Microsoft YaHei`, `Noto Sans CJK SC`)
- **Display/heading:** `font-size: 2.25rem` (mobile override for `h1`), normal weight title style
- **Body:** ~16px, 1.5 line height
- **Captions:** ~13-14px, muted gray
- **Monospace (tokens):** `font-family: monospace` for code blocks, token values like `PDA_A1B2C3D4E5F60708`
- **No custom web fonts.** Uses CDN-loaded Streamlit fonts.

### Layout
- **Width:** `layout="centered"` — single centered column, max ~730px
- **Padding:** `padding-top: 4rem` on block container; `1rem` sides on mobile
- **Structure:** Title → caption → radio tabs → divider → tab content
- **Sections:** Streamlit `st.subheader`, `st.expander`, `st.columns([1,1])` for side-by-side downloads
- **No sidebar used.** All content in main column.

### Spacing
- Streamlit default 8px base unit
- Dividers (`st.divider()`) separate major sections
- Expanders group optional/secondary actions
- Columns used only for download button pairs

### Backgrounds & Imagery
- **Plain white background.** No images, no illustrations, no gradients, no textures.
- **No hero images, no brand illustrations.** Pure functional UI.
- **Color fills:** Only Streamlit alert boxes (success/warning/error/info) use colored backgrounds.

### Borders & Shadows
- Streamlit default subtle shadows on cards/expanders
- Thin `1px` borders on upload areas (dashed when empty, solid on hover)
- No heavy drop shadows; no decorative borders

### Corner Radii
- Streamlit default: `~4-8px` on buttons, `~4px` on inputs and expanders
- No pill-shaped buttons; no extreme rounding

### Animations & Transitions
- **None.** Streamlit re-renders on interaction; no custom CSS animations.
- Upload area shows spinner during processing (Streamlit built-in).

### Hover & Press States
- **Buttons:** Background darkens slightly on hover; primary button stays red-orange family
- **Links:** Standard underline on hover
- **No custom hover states** — Streamlit defaults only

### Iconography approach
- Minimal: only the `🔒` lock emoji as page icon (set via `page_icon="lock"` in `set_page_config`)
- `⬇️` on primary download button
- No icon library; no SVG icons; no icon font
- Streamlit's built-in alert icons (✓ success, ⚠ warning, ✕ error, ℹ info) via component rendering

### Cards
- Streamlit `st.expander` acts as a collapsible card
- Light gray background, subtle shadow, 4px rounded corners
- No custom card components

### Color vibe of imagery
- N/A — no imagery used

### Transparency & blur
- None

---

## ICONOGRAPHY

The product uses **no custom icon system**. Icon usage is minimal:

- **Page icon:** `🔒` lock (set as `page_icon="lock"` — Streamlit renders a lock emoji favicon)
- **Download button:** `⬇️` emoji inline in button label (`"⬇️ 一键打包下载（推荐）"`)
- **Alert icons:** Streamlit renders built-in icons for `st.success`, `st.warning`, `st.error`, `st.info`
- **No SVG icons, no icon font, no PNG icons, no CDN icon library**

There are no logos, brand illustrations, or visual assets in the repository. The tool is positioned as a local utility — brand identity is minimal by design.

**Assets directory:** `assets/` — currently empty (no logos or brand assets exist in source).

---

## FILE INDEX

```
README.md                    — This file; design system overview
SKILL.md                     — Agent skill definition for Claude Code
colors_and_type.css          — CSS variables for colors and typography
assets/                      — Brand assets (currently none from source)
preview/                     — Design system card HTML files
  colors-base.html           — Base color palette swatches
  colors-semantic.html       — Semantic / status colors
  type-scale.html            — Typography scale specimen
  type-chinese.html          — Chinese text rendering specimen
  spacing-tokens.html        — Spacing and layout tokens
  component-buttons.html     — Button states
  component-upload.html      — File upload area component
  component-alerts.html      — Alert / status message components
  component-tabs.html        — Tab navigation component
  component-expander.html    — Expander/accordion component
  component-download.html    — Download button patterns
ui_kits/
  web_app/
    README.md                — Web app UI kit notes
    index.html               — Interactive prototype (main app)
    AppShell.jsx             — Top-level layout + nav
    AnonymizeTab.jsx         — 数据脱敏 tab
    RestoreTab.jsx           — 报告反脱敏 tab
    Components.jsx           — Shared UI primitives
```

---

## FONT NOTES

No custom fonts are used in the source. The Streamlit default (Source Sans Pro via CDN) is referenced in the UI kit via Google Fonts. **No font substitution needed.**
