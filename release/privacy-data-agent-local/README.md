# Privacy Data Agent

纯本地的数据脱敏和报告反脱敏小工具，适合把表格发给模型或外部人员前先替换敏感信息；模型分析不在这个本地流程里发生。

## Local Flow

1. 同事把 CSV 或 XLSX 放到本机。
2. 本地运行 `anonymize`，生成脱敏后的 `anonymized.csv`。
3. 同时生成匹配文件 `mapping.local.json`（用于程序反脱敏）和 `mapping_table.csv`（方便人工核查）。
4. 同事把脱敏文件拿去分析，得到带 token 的报告。
5. 本地运行 `restore`，按匹配文件把报告里的 token 还原成原始姓名、部门、客户等。

## Sensitive Data Covered

- 姓名（员工、联系人等姓名列）
- 身份证号
- 部门/组织名称
- 客户/公司名称
- 工号 / 员工编号（字母前缀+数字，如 `EMP001`；纯数字工号依赖列名识别）
- 手机号
- 邮箱地址

## Token 安全模型

每次脱敏独立生成随机 token，**不同批次的同一个名字会得到不同 token**。这样即使某批的匹配文件泄露，也只影响那一批数据，其他批次不受影响。

如果同一个项目需要对多个文件分批脱敏，并希望相同实体保持一致 token，可在脱敏时上传上一批的匹配文件作为"批次种子"，详见下方网页界面说明。

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

### Mac 双击版

给 Mac 同事使用根目录下的 `.command` 文件：

1. 双击 `00-install-mac.command` 安装本地运行环境。
2. 双击 `03-launch-web-ui-mac.command` 打开本地网页界面。
3. 浏览器打开后上传 Excel/CSV，下载脱敏文件和匹配表。
4. 需要反脱敏报告时，切换到「报告反脱敏」，上传报告和匹配文件。

如果 macOS 提示文件来自未知开发者，按住 `Control` 键点击 `.command` 文件，选择「打开」。

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

## 本地网页界面

安装完成后启动：

```text
Windows: 03-launch-web-ui-windows.bat
Mac:     03-launch-web-ui-mac.command
```

浏览器打开本地页面，提供两个功能：

### 数据脱敏

上传 Excel 或 CSV，处理完成后点击 **「⬇️ 一键打包下载」** 获取 ZIP 包，内含：

| 文件 | 说明 |
|------|------|
| `anonymized.xlsx` | 脱敏后的数据，可安全发送给大模型或外部 |
| `mapping.local.json` | 匹配文件，含原始敏感信息，**仅限本地保存** |
| `README.txt` | 中文使用说明 |

**同一批次追加文件**：如果同一个分析项目需要对多个文件脱敏，展开「同一批次追加文件」区域，上传上一个文件生成的 `mapping.local.json`，系统会复用已有 token，新实体继续随机生成，最终输出包含全批次的完整匹配文件。

### 报告反脱敏

支持格式：`.md` / `.txt` / `.html` / `.docx` / `.pptx`

上传报告文件和对应批次的 `mapping.local.json`，下载还原后的文件，文件名自动加 `.restored` 后缀（如 `report.restored.docx`）。`.md`/`.txt`/`.html` 类型会同时显示预览。

网页运行在本机 `127.0.0.1`，文件只在本地 Python 进程中处理，不上传服务器，不调用大模型。

## 命令行用法

### 脱敏

```bash
privacy-data-agent anonymize input.csv --output-dir runs/local
```

输出：

- `runs/local/anonymized.csv`：脱敏后的数据文件
- `runs/local/mapping.local.json`：程序使用的匹配文件
- `runs/local/mapping_table.csv`：方便人工查看的匹配表
- `runs/local/local_manifest.json`：本次处理的文件清单

### 反脱敏

```bash
privacy-data-agent restore report.md \
  --mapping runs/local/mapping.local.json \
  --output runs/local/report.restored.md
```

也可以使用 CSV 匹配表：

```bash
privacy-data-agent restore report.md \
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

```bash
pytest -q
```

测试套件验证原始 fixture 值不会出现在脱敏数据、prompt 或脱敏报告中，并覆盖 docx/pptx 格式的反脱敏、跨批次 token 独立性和批次内 token 一致性。
