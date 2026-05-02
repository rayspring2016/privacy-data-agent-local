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
4. 如果想用网页界面，双击 `03-launch-web-ui-windows.bat`，浏览器打开后上传 Excel/CSV 即可处理。

也可以把文件直接拖到 bat 上：

- 把原始 CSV/XLSX 拖到 `01-anonymize-data.bat`
- 把待恢复报告拖到 `02-restore-report.bat`

### 本地网页界面

安装完成后，Windows 用户可以双击：

```text
03-launch-web-ui-windows.bat
```

浏览器会打开本地页面：

- `数据脱敏`：上传 Excel/CSV，下载脱敏 Excel、脱敏 CSV、匹配文件和匹配表
- `报告反脱敏`：上传 `.md`/`.txt` 报告和匹配文件，下载恢复后的报告

网页运行在本机 `127.0.0.1`，文件只在本地 Python 进程中处理。

### Mac 双击版

给 Mac 同事使用根目录下的 `.command` 文件：

1. 双击 `00-install-mac.command` 安装本地运行环境。
2. 双击 `03-launch-web-ui-mac.command` 打开本地网页界面。
3. 浏览器打开后上传 Excel/CSV，下载脱敏文件和匹配表。
4. 需要反脱敏报告时，切换到 `报告反脱敏`，上传报告和匹配文件。

如果 macOS 提示文件来自未知开发者，按住 `Control` 键点击 `.command` 文件，选择 `打开`。

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
