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

给不熟悉命令行的同事，可以直接使用 `windows/` 文件夹下的 `.bat` 文件：

1. 双击 `windows/00-install-windows.bat` 安装本地运行环境。
2. 双击 `windows/01-anonymize-data.bat`，按提示拖入或输入 CSV/XLSX 文件路径，生成脱敏文件和匹配表。
3. 双击 `windows/02-restore-report.bat`，按提示拖入或输入报告文件路径，再选择匹配文件，生成反脱敏报告。
4. 如果想用网页界面，双击 `windows/03-launch-web-ui-windows.bat`，浏览器打开后上传 Excel/CSV 即可处理。

也可以把文件直接拖到 bat 上：

- 把原始 CSV/XLSX 拖到 `windows/01-anonymize-data.bat`
- 把待恢复报告拖到 `windows/02-restore-report.bat`

### Mac 双击版

给 Mac 同事使用 `mac/` 文件夹下的 `.command` 文件：

1. 双击 `mac/00-install-mac.command` 安装本地运行环境。
2. 双击 `mac/03-launch-web-ui-mac.command` 打开本地网页界面。
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
Windows: windows/03-launch-web-ui-windows.bat
Mac:     mac/03-launch-web-ui-mac.command
```

浏览器打开本地页面，提供两个功能：

### 数据脱敏

上传 Excel 或 CSV，处理完成后点击 **「⬇️ 一键打包下载」** 获取 ZIP 包，内含：

| 文件 | 说明 |
|------|------|
| `anonymized.xlsx` | 脱敏后的数据，可安全发送给大模型或外部；XLSX 会保留原有格式、多 sheet、隐藏 sheet、隐藏行列 |
| `mapping.local.json` | 匹配文件，含原始敏感信息，**仅限本地保存** |
| `README.txt` | 中文使用说明 |

**同一批次追加文件**：如果同一个分析项目需要对多个文件脱敏，展开「同一批次追加文件」区域，上传上一个文件生成的 `mapping.local.json`，系统会复用已有 token，新实体继续随机生成，最终输出包含全批次的完整匹配文件。

**岗位字段**：`岗位名称` / `职位` / `职务` 默认保留，便于分析岗位结构；如岗位本身也需要隐藏，可在「字段脱敏范围」中开启岗位脱敏。`离职原因` / `离职类型` / `状态` 等业务判断列默认保留。

**部门与薪资字段**：同一区域可选择是否脱敏部门和薪资。薪资默认全部脱敏，也可以只放开提成、绩效奖金、社保公积金、补贴、人力成本或个人薪酬中的指定类别。例如核验提成时，只放开「提成」，其他薪资类别继续脱敏。

### 报告反脱敏

支持格式：`.md` / `.txt` / `.html` / `.docx` / `.pptx`

上传报告文件和对应批次的 `mapping.local.json`，下载还原后的文件，文件名自动加 `.restored` 后缀（如 `report.restored.docx`）。`.md`/`.txt`/`.html` 类型会同时显示预览。

网页运行在本机 `127.0.0.1`，文件只在本地 Python 进程中处理，不上传服务器，不调用大模型。

## 命令行用法

### 脱敏

```bash
privacy-data-agent anonymize input.csv --output-dir runs/local
```

如需同时脱敏岗位字段：

```bash
privacy-data-agent anonymize input.csv --output-dir runs/local --anonymize-job-title
```

输出：

- `runs/local/anonymized.csv`：脱敏后的数据文件
- `runs/local/mapping.local.json`：程序使用的匹配文件
- `runs/local/mapping_table.csv`：方便人工查看的匹配表
- `runs/local/local_manifest.json`：本次处理的文件清单

### 无界面批量处理与跨月追加

以下命令在项目虚拟环境激活后运行，无需打开网页。Mac 可先进入项目目录，再执行 `source .venv/bin/activate`。

传入文件夹即可按文件名顺序处理其第一层的 XLSX/CSV；不递归子文件夹，忽略 Excel 的 `~$` 临时文件。所有成功文件共用累计映射，相同类型、相同原始文本沿用同一编号。不同写法、别名和同名人员仍需业务核对，程序不推断身份。

```bash
# 批量核验提成：只保留提成金额，姓名、客户、部门及其他薪资继续脱敏
privacy-data-agent anonymize "/路径/各月提成表" \
  --keep-salary-group commission \
  --output-dir "/路径/第一批脱敏结果"

# 下个月追加：导入上一批的完整映射，输出到新的目录
privacy-data-agent anonymize "/路径/新增月份" \
  --mapping "/路径/第一批脱敏结果/mapping.local.json" \
  --keep-salary-group commission \
  --output-dir "/路径/第二批脱敏结果"
```

`--mapping` 也适用于单文件，接受本工具生成的明文 `mapping.local.json` 或 `mapping_table.csv`，不会修改输入映射。网页启用加密后生成的映射暂不支持通过此参数导入。追加月份时应沿用相同的字段选项；映射用于沿用编号，不会自动恢复上次的字段设置。

| 参数 | 效果 |
|------|------|
| `--no-anonymize-department` | 保留部门名称；默认脱敏 |
| `--anonymize-job-title` | 脱敏岗位；默认保留 |
| `--no-anonymize-salary` | 保留全部薪资金额；默认脱敏 |
| `--keep-salary-group commission` | 仅放开提成 / 佣金 |
| `--keep-salary-group performance_pay` | 放开绩效工资 / 奖金 |
| `--keep-salary-group personal_comp` | 放开个人工资 / 薪酬 |
| `--keep-salary-group social_insurance` | 放开社保 / 公积金 |
| `--keep-salary-group allowance` | 放开补贴 |
| `--keep-salary-group labor_cost` | 放开人力成本 / 收入 |
| `--header-row 2` | 指定所有输入表的第2行为表头；默认自动识别 |

`--keep-salary-group` 可重复传入以保留多个类别。分类依据列名；使用前核对自定义表头的识别结果。这些字段开关用于表格，DOCX/PDF 不支持同样的列级选择。

批量输出目录必须是新的或空目录，防止覆盖已有结果。输出结构：

```text
第一批脱敏结果/
  mapping.local.json         # 全批次完整映射，下个月继续使用这一份
  mapping_table.csv          # 同一映射的人工核对表
  batch_manifest.json        # 逐文件状态、原始路径、输出位置和本次字段设置
  files/
    0001/
      anonymized.xlsx        # 第一个文件的脱敏数据
      mapping.local.json     # 截至这个文件的累计映射
      mapping_table.csv
      local_manifest.json
    0002/
      anonymized.csv
      ...
```

有单个文件失败时会继续其余文件，终端显示成功/失败数量。`batch_manifest.json` 记录失败的异常类型，不记录可能包含原始单元格值的异常文本。全部成功时退出码为0，存在失败或输入错误时为1，便于脚本判断。只处理成功且有记录的输出；失败文件目录可能留有不完整产物。

只分享需要的 `anonymized.xlsx` / `anonymized.csv`。映射和处理记录（包含原始文件路径）仅限本地保存，勿将整个结果文件夹直接外发。未识别字段、批注、工作表名等内容仍需检查，本次增强不改变既有识别范围。

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
