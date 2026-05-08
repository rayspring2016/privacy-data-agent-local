# Privacy Data Agent - 项目文档

> 本文档供 AI 代理阅读，了解项目背景、功能、技术决策和使用方式。

---

## 项目概述

**Privacy Data Agent**（隐私数据脱敏工具）是一款本地优先的 HR 和业务数据匿名化、模型分析和还原管道。

- **定位**：脱敏 HR 数据（姓名/身份证/工号/部门等），安全发送给大模型（LLM）
- **核心能力**：自动检测 10 种实体类型 → Token 替换 → 生成 mapping 文件 → 支持逆向还原
- **适用场景**：薪酬表/花名册/月报等含敏感信息的数据，发给 LLM 分析前脱敏

---

## 实体类型（EntityType）

| 类型 | 说明 | 示例 |
|------|------|------|
| `EMPLOYEE` | 人名 | 张三、欧阳婷 |
| `ID_NUMBER` | 身份证号 | 11010119900307001X |
| `EMPLOYEE_ID` | 工号 | EMP00123 / 001234（需列上下文） |
| `DEPARTMENT` | 部门 | 销售部、北京中心 |
| `CUSTOMER` | 客户名 | 上海科技 |
| `PHONE` | 手机号 | 13800138000 |
| `EMAIL` | 邮箱 | zhangsan@example.com |
| `LICENSE_PLATE` | 车牌 | 京A12345 |
| `SALARY` | 薪酬字段 | 工资、奖金、补贴等金额 |
| *(自动生成 Token)* | `PDA_` + 16位HEX | `PDA_A3F2B1C4D5E6F7G8` |

---

## 版本历史

### v1.12.0（当前版本）

**发布日期**：2026-05-08

**新增功能**：

| 编号 | 功能 | 说明 |
|------|------|------|
| D1 | 纯数字工号检测 | 仅在工号列内，4-10位数字检测为 EMPLOYEE_ID，避免误报年份/手机号 |
| D8 | 脱敏前预览 | 显示列名/实体类型/示例值，最多扫描 5 行 |
| D5 | 百家姓扩增 | 单姓 507 条 + 复姓 87 条 = 594 条（之前 326 条） |
| D6 | 人名误报黑名单 | 249 条：AI工具名/常用词/地名/成语，避免"文心""北京"被误判为人名 |
| D9 | WPS/Numbers 支持 | `.numbers`（Apple Numbers）读取，`.et`（WPS）读取，输出统一为 XLSX |

**技术细节**：

```python
# D1：纯数字工号检测逻辑
PURE_DIGIT_EMPLOYEE_ID_RE = re.compile(r"^[0-9]{4,10}$")

def detect_cell_entity_type(value, column_type=None):
    # 必须有列上下文（EMPLOYEE_ID 列）才检测，避免误报
    if column_type == EntityType.EMPLOYEE_ID and PURE_DIGIT_EMPLOYEE_ID_RE.match(text):
        return EntityType.EMPLOYEE_ID
```

```python
# D6：黑名单分类（249条）
NON_NAME_BLACKLIST = AI_TOOL_BLACKLIST | COMMON_WORD_PAIR_BLACKLIST | PLACE_INSTITUTION_BLACKLIST | IDIOM_BLACKLIST

# _looks_like_chinese_name() 在姓氏匹配前先检查黑名单
if text in NON_NAME_BLACKLIST:
    return False
```

**D9 文件格式支持**：

| 格式 | 扩展名 | 读 | 写 |
|------|--------|----|----|
| Excel | `.xlsx` | ✅ openpyxl | ✅ |
| CSV | `.csv` | ✅ pandas | ✅ |
| Word | `.docx` | ✅ python-docx | ✅ |
| PDF | `.pdf` | ✅ PyMuPDF | ✅ |
| Numbers | `.numbers` | ✅ ZIP→XML 解析 | → XLSX |
| WPS | `.et` | ✅ openpyxl 优先，回退 xlrd | → XLSX |

---

### v1.11.0

**日期**：2026-05-02

**新增功能**：

| 功能 | 说明 |
|------|------|
| 批量多文件处理 | 多文件拖拽，自动累积 mapping（按 original 去重） |
| 映射文件加密 | Fernet 对称加密 ZIP 包，含加密 mapping.local.json |
| 加密密钥生成 | 界面一键生成 Fernet 密钥（43字符 URL-safe base64） |

**关键代码**：

```python
# 跨批次一致性：mapping 按 original（原文）去重
def merge_mapping_jsons(mappings: list[MappingFile]) -> MappingFile:
    seen = {}
    for m in mappings:
        for entry in m.entries:
            if entry.original not in seen:  # 首次出现优先
                seen[entry.original] = entry
    return MappingFile(entries=list(seen.values()))

# 加密 bundle
def create_encrypted_zip_bundle(stem, anonymized_bytes, mapping_json, suffix, key):
    fernet = Fernet(key.encode())
    encrypted = fernet.encrypt(mapping_json.encode())
    # 写入 ZIP：脱敏文件 + mapping.local.json（加密）+ README.txt
```

---

### v1.10.0

**日期**：2026-05-03

**新增功能**：

| 功能 | 说明 |
|------|------|
| SALARY 实体类型 | 检测工资/薪资/奖金/补贴等货币字段 |
| 扩展列名匹配 | 包含 80+ 薪酬相关词汇（餐补/交通补贴/五险一金 等） |
| 排除非薪酬字段 | 绩效评分/等级/考核 等非金额字段不会被误判 |

---

### v1.9.0

**日期**：2026-05-03

**新增功能**：

| 功能 | 说明 |
|------|------|
| Word 内嵌人名检测增强 | `_INLINE_RIGHT_TRIM` 右侧裁剪，`_SEGMENT_RE` 标点列表扫描 |
| 百家姓补全 | 新增约 80 个姓氏（含复姓：万俟/上官/欧阳/司马 等） |

**Bug 修复**：

- Excel 二级组织列未处理（已修复）
- Web 版本号未更新（已修复）
- Word 文档内嵌人名未识别（已同步 document_anonymizer.py）

---

### v1.8.x（早期版本）

- CSV 基础脱敏
- Excel 读取/写入
- PDF/DOCX 支持
- Web UI 界面

---

## 核心架构

```
┌─────────────────────────────────────────────────────────┐
│                      Web UI (Streamlit)                   │
│  ├── 脱敏上传（单文件/批量）                             │
│  ├── 预览（列名/实体类型/示例值）                        │
│  ├── 加密密钥生成                                        │
│  └── 反脱敏上传                                          │
└─────────────────┬───────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────┐
│                   web_helpers.py                        │
│  ├── anonymize_upload()  — 主入口                       │
│  ├── read_uploaded_table() — 多格式读取                 │
│  ├── merge_mapping_jsons() — 批量 mapping 合并            │
│  └── create_encrypted_zip_bundle()                      │
└──────┬────────────────┬────────────────┬────────────────┘
       │                │                │
   CSV/XLSX        Word(DOCX)       PDF
   │                │                │
   ▼                ▼                ▼
   ▼                ▼                ▼
┌─────────────────────────────────────────────────────────┐
│              detectors.py（实体检测引擎）                │
│  ├── detect_column_entity_type() — 列名匹配              │
│  ├── detect_cell_entity_type()  — 内容模式检测           │
│  ├── _looks_like_chinese_name() — 百家姓 + 黑名单        │
│  └── CHINESE_NAME_RE / ID_NUMBER_RE / PHONE_RE 等        │
└─────────────────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│               anonymizer.py（核心脱敏）                   │
│  ├── AnonymizerState — 状态管理，token 生成             │
│  ├── token_for() — 生成确定性 token（基于 HMAC）         │
│  └── anonymize_dataframe()                              │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│                  mapping_store.py                        │
│  ├── save_mapping_table() — 保存 JSON/CSV               │
│  ├── load_local_mapping() — 加载 mapping（含解密）       │
│  └── MappingFile 模型                                    │
└─────────────────────────────────────────────────────────┘
```

---

## 关键技术决策

### 1. Token 生成策略

**问题**：同一姓名在不同批次是否生成相同 token？

**决策**：使用 HMAC-SHA256 生成确定性 token

```python
def token_for(self, entity_type: EntityType, original: str) -> str:
    key = f"{entity_type.value}:{original}"
    h = hmac.new(self._key.encode(), key.encode(), hashlib.sha256)
    return f"PDA_{h.hexdigest()[:16]}"
```

**优点**：相同姓名跨文件/跨批次生成相同 token，便于批量分析和反脱敏。

### 2. 百家姓扩展策略

**原则**："宽进严出"

- 姓氏库覆盖 99%+ 常见姓氏（594条）
- 黑名单兜底（249条），排除 AI工具名/常用词/地名/成语

```python
# _looks_like_chinese_name() 优先级
1. 长度检查（2-4字符）
2. 黑名单排除（AI工具/常用词/地名/成语）
3. 复姓优先匹配（2字符）
4. 单姓匹配（1字符）
```

### 3. 工号检测依赖列上下文

**问题**：纯数字可能是工号，也可能是年份/电话/序号

**决策**：4-10位纯数字只在 EMPLOYEE_ID 列内才检测

```python
if column_type == EntityType.EMPLOYEE_ID and PURE_DIGIT_EMPLOYEE_ID_RE.match(text):
    return EntityType.EMPLOYEE_ID  # 仅在工号列生效
# 其他列：年份/电话等不会被误判
```

### 4. 批量处理 mapping 合并

**策略**：按 original（原文）去重，保留首次出现的 token

```python
# 合并逻辑
seen = {}  # original → MappingEntry
for m in mappings:
    for entry in m.entries:
        if entry.original not in seen:  # 首次优先
            seen[entry.original] = entry
```

**原因**：跨文件同一姓名应生成相同 token，合并 mapping 确保一致性。

---

## 使用方式

### Web UI（本地运行）

```bash
cd /Users/caochunlei/Documents/HR\ Things/数据清洗
./.venv/bin/streamlit run src/privacy_data_agent/web_app.py --server.port 8501
```

### CLI（命令行）

```bash
# 脱敏
privacy-data-agent anonymize input.xlsx -o output/

# 批量脱敏
privacy-data-agent batch input1.xlsx input2.csv --seed mapping.json

# 反脱敏
privacy-data-agent restore report.docx --mapping mapping.json -o restored/
```

### Python API

```python
from privacy_data_agent.web_helpers import anonymize_upload

result = anonymize_upload(
    filename="employee_data.xlsx",
    content=file_content,
    seed_mapping_content=existing_mapping,
    header_row=2,
    encryption_key="你的密钥",
)
# result["zip_bundle"] — 可下载的 ZIP 包
# result["mapping_json"] — 匹配文件 JSON
```

---

## 文件结构

```
数据清洗/
├── src/privacy_data_agent/
│   ├── web_app.py           # Streamlit Web UI
│   ├── web_helpers.py       # 文件处理辅助函数
│   ├── anonymizer.py         # 核心脱敏逻辑
│   ├── detectors.py          # 实体检测引擎
│   ├── workbook_anonymizer.py # Excel 处理
│   ├── document_anonymizer.py # Word/PDF 处理
│   ├── restorer.py           # 反脱敏逻辑
│   ├── mapping_store.py      # mapping 存储
│   ├── models.py             # Pydantic 模型
│   └── pipeline.py          # 管道入口
├── tests/                   # 测试套件（62个测试）
│   ├── test_detectors.py     # 实体检测测试
│   ├── test_workbook_anonymizer.py
│   └── test_document_anonymizer.py
├── tools/
│   └── build_app.sh         # 构建脚本
├── release/
│   └── privacy-data-agent-local-v1.12.0.zip  # 发行包
└── pyproject.toml
```

---

## 测试覆盖

| 测试文件 | 测试数 | 覆盖内容 |
|----------|--------|---------|
| test_detectors.py | 19 | 实体检测、百家姓、黑名单 |
| test_workbook_anonymizer.py | 10 | Excel 脱敏、分割检测 |
| test_anonymizer.py | 9 | Token 生成、mapping 合并 |
| test_document_anonymizer.py | 17 | Word/PDF 脱敏 |
| test_numbers_support.py | 3 | Numbers/WPS 格式支持 |
| test_mapping_store.py | 4 | mapping 存储加密 |

**总测试数**：62 个（全部通过）

---

## 已知限制

1. **WPS 输出**：WPS 格式（.et）读取后输出为 XLSX，不保留原格式
2. **Numbers 输出**：Numbers 格式读取后输出为 XLSX，不保留原格式
3. **加密依赖**：mapping 文件加密使用 Fernet（对称加密），密钥必须妥善保存
4. **跨文件一致性**：依赖首次出现的 token，需确保文件处理顺序一致

---

## 未来规划（未实现）

- D5 百家姓扩至 ~800 条（当前 594，可继续扩展）
- D6 人名误报黑名单扩展（更多 AI 工具名）
- Web 端 LLM 分析集成（直接发送脱敏数据给 LLM）
- 增量脱敏模式（只处理新增行）

---

*文档生成时间：2026-05-08 | 版本：v1.12.0*