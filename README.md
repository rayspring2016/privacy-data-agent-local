# Privacy Data Agent

纯本地的数据脱敏和报告反脱敏小工具，适合把表格发给模型或外部人员前先替换敏感信息；模型分析不在这个本地流程里发生。

## Local Flow

1. 同事把 CSV 或 XLSX 放到本机。
2. 本地运行 `anonymize`，生成脱敏后的 `anonymized.csv`。
3. 同时生成匹配表 `mapping.local.json` 和 `mapping_table.csv`。
4. 同事把脱敏文件拿去分析，得到带 token 的报告。
5. 本地运行 `restore`，按匹配表把报告里的 token 还原成原始姓名、部门、客户等。

## Sensitive Data Covered

- Employee/person names from name-like columns
- Chinese resident ID numbers
- Departments and organizations
- Customer/client/company names
- Phone numbers
- Email addresses

## Install

### Windows 双击版

给不熟悉命令行的同事，可以直接使用根目录下的 `.bat` 文件：

1. 双击 `00-install-windows.bat` 安装本地运行环境。
2. 双击 `01-anonymize-data.bat`，按提示拖入或输入 CSV/XLSX 文件路径，生成脱敏文件和匹配表。
3. 双击 `02-restore-report.bat`，按提示拖入或输入报告文件路径，再选择匹配文件，生成反脱敏报告。

也可以把文件直接拖到 bat 上：

- 把原始 CSV/XLSX 拖到 `01-anonymize-data.bat`
- 把待恢复报告拖到 `02-restore-report.bat`

### 命令行安装

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Windows PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
```

## Anonymize a File

```bash
privacy-data-agent anonymize input.csv --output-dir runs/local
```

Outputs:

- `runs/local/anonymized.csv`: 脱敏后的数据文件
- `runs/local/mapping.local.json`: 程序使用的匹配文件
- `runs/local/mapping_table.csv`: 方便人工查看的匹配表
- `runs/local/local_manifest.json`: 本次处理的文件清单

`mapping.local.json` 和 `mapping_table.csv` 包含原始敏感值，只应保存在本地。

## Restore a Report

如果报告里仍是 `EMP_0001`、`DEPT_0001`、`CUSTOMER_0001` 这样的 token：

```bash
privacy-data-agent restore report.anonymized.md \
  --mapping runs/local/mapping.local.json \
  --output runs/local/report.restored.md
```

也可以使用 CSV 匹配表：

```bash
privacy-data-agent restore report.anonymized.md \
  --mapping runs/local/mapping_table.csv \
  --output runs/local/report.restored.md
```

## Optional Model Analysis

默认安装不需要 OpenAI 依赖。本地脱敏和本地恢复不调用大模型。

如果以后要重新启用模型分析扩展：

```bash
pip install -e ".[model]"
```

## Privacy Check

Run:

```bash
pytest -q
```

The test suite verifies raw fixture values do not appear in anonymized data, captured prompts, or anonymized reports.
