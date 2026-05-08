# Changelog

所有重要版本更新记录，按时间倒序排列。

---

## [v1.12.0] - 2026-05-08

### 新增功能

| 编号 | 功能 | 描述 |
|------|------|------|
| D1 | 纯数字工号检测 | 仅在工号列内检测 4-10 位纯数字，避免误报年份/手机号 |
| D8 | 脱敏前预览 | 显示列名/实体类型/示例值，帮助用户确认处理范围 |
| D5 | 百家姓扩增 | 从 326 条扩展至 594 条（单姓 507 + 复姓 87） |
| D6 | 人名误报黑名单 | 新增 249 条黑名单：AI工具名(文心/通义/Kimi等)、常用词(大小/多少)、地名(北京/上海)、成语(春夏秋冬) |
| D9 | WPS/Numbers 支持 | Apple Numbers (`.numbers`) 和 WPS (`.et`) 格式读取支持 |

### 技术细节

- `detectors.py`：新增 `NON_NAME_BLACKLIST`、`PURE_DIGIT_EMPLOYEE_ID_RE`
- `web_helpers.py`：新增 `_read_uploaded_numbers()` 函数，`anonymize_upload()` 增加 `.numbers` / `.et` 分支
- `web_app.py`：文件选择器支持 `.numbers` / `.et`，预览区域显示格式名称
- 测试：新增 6 个 D5/D6 测试用例，3 个 D9 测试用例

---

## [v1.11.0] - 2026-05-02

### 新增功能

| 功能 | 描述 |
|------|------|
| 批量多文件处理 | 多文件拖拽上传，自动累积 mapping，按 original 去重 |
| 映射文件加密 | Fernet 对称加密 mapping.local.json，密钥自主生成 |
| ZIP 捆绑包 | 脱敏文件 + mapping + README 一键下载 |
| build 优化 | 删除 .venv 目录，ZIP 从 158MB 降至 52KB |

### 技术细节

- `mapping_store.py`：新增 `load_local_mapping()` 支持加密 JSON 加载
- `web_helpers.py`：`merge_mapping_jsons()` 按 original 去重，`create_encrypted_zip_bundle()` 创建加密包
- `anonymizer.py`：HMAC-SHA256 确定性 token 生成

---

## [v1.10.0] - 2026-05-01

### 新增功能

| 功能 | 描述 |
|------|------|
| SALARY 实体类型 | 检测工资/薪资/奖金/补贴等货币字段 |
| 扩展列名匹配 | 80+ 薪酬相关词汇（餐补/交通补贴/五险一金/月薪/年终奖 等） |
| 排除非薪酬字段 | 绩效评分/等级/考核 等非金额字段不误判 |

### 技术细节

- `detectors.py`：`NON_SALARY_COLUMNS` 排除规则（评分/等级/考核）
- `COLUMN_HINTS` 新增 SALARY 相关列名

---

## [v1.9.0] - 2026-05-03

### 新增功能

| 功能 | 描述 |
|------|------|
| Word 内嵌人名检测增强 | `_INLINE_RIGHT_TRIM` 右侧裁剪，`_SEGMENT_RE` 标点列表扫描 |
| 百家姓补全 | 新增约 80 个姓氏（含复姓：万俟/上官/欧阳/司马 等） |

### Bug 修复

- Excel 二级组织列未处理
- Web 版本号未更新
- Word 文档内嵌人名未识别（release 同步问题）

---

## [v1.8.x] - 早期版本

- CSV 基础脱敏
- Excel 读取/写入（openpyxl）
- Word (DOCX) 支持（python-docx）
- PDF 支持（PyMuPDF）
- Streamlit Web UI 基础功能

---

*格式说明：新增功能使用 `[功能名]` 标记，Bug 修复使用 `[fix]` 标记*