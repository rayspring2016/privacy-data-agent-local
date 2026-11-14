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

支持两种编号方式：**统一编号（跨月份、跨项目）**与**每次生成新编号**。编号均为随机生成的不透明 token；统一模式将已生成的编号保存在本机，之后复用，不通过可猜测的姓名哈希生成。

界面默认统一编号；命令行使用 `--consistent-ids` 开启。不启用时维持原来的独立批次行为，也可显式导入旧映射。统一库包含所有已登记项目的真实映射，仅限本地保存。

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

提成、薪资或人效核验时，在网页勾选“核验模式（保留数值和原公式）”。普通脱敏默认继续应用薪资脱敏开关。该模式保留业务金额、比例和系数等数值，不应用薪资金额脱敏；身份标识继续脱敏。XLSX 保留原公式和已保存结果，使用手动计算供核验。只替换公式内的身份文本条件，保留运算符、数值常量和单元格引用；涉及待核验身份的条件需回原表确认后重算。外部引用结构保留，但外部文件路径使用匿名占位，并移除外部数据缓存。原表应先用 Excel 计算并保存。缺少公式结果时程序会提示位置，不会以空白替代。

命令行示例：`privacy-data-agent anonymize 提成.xlsx --consistent-ids --allow-unverified-people --preserve-calculations --output-dir 核验结果`。普通脱敏模式的原有薪资选项保持有效。

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

**推荐：跨月份、跨项目统一编号，无需每次导入匹配文件。**

```bash
privacy-data-agent anonymize "/路径/提成表" --consistent-ids \
  --keep-salary-group commission --output-dir "/路径/提成脱敏结果"

privacy-data-agent anonymize "/路径/薪资表" --consistent-ids \
  --no-anonymize-salary --output-dir "/路径/薪资脱敏结果"
```

两次命令自动共用 `~/.privacy-data-agent/identities/mapping.local.json`，不随安装包更新而重置。首次运行可增加 `--mapping` 导入无冲突的历史匹配文件。输入映射与统一库冲突时会报错，不会静默改号；坏库不会自动重建。库内包含人员身份关联与原始值，只在本机保存，不加入安装包或 Git。

人员识别规则：

- 工号、员工邮箱可独立建立身份；同一记录中的身份证号也可用来关联已登记人员。工号保留前导零，邮箱匹配忽略大小写。同名、不同工号的员工分别编号。
- 工作簿先扫描**全部 sheet**中的工号/邮箱，再处理仅有姓名的 sheet，不依赖工作表顺序。已登记的人员基准可跨项目继续复用。
- 没有直接标识时，按姓名和表内共有的部门信息匹配；基准中候选唯一才关联。姓名唯一且没有部门信息时也可关联；姓名、部门都相同而工号不同的情况转待核验。
- 仅有邮箱的人员可以登记，之后首次补齐工号时沿用编号。已有工号身份和邮箱身份若分别登记成两个人员，仍需核对冲突，不能仅凭相同姓名合并。HRBP 等角色通过同名角色的邮箱字段关联，避免继承该行其他员工的身份或部门。
- 多级部门中有一级精确匹配已登记别名时可关联；出现互相矛盾的已知部门候选时仍待核验。组合匹配以当前已登记基准为准，使用前须确保基准完整；程序不能证明基准之外不存在同名人员。
- 客户联系人使用客户上下文单独编号；无员工标识的系统账号单独脱敏，不作为员工基准。员工签订人、负责人等仍须匹配已登记人员，找不到工号或邮箱时须补录基准。
- Excel 中的姓名公式不作为真实姓名登记，输出保留公式；空白占位符和人员状态不作为姓名。并排小表按各自范围处理；透视表导出保留脱敏后的可见结果，移除原始缓存及透视定义，因此导出表不再支持透视刷新。
- 统一模式下，自定义未识别列中与已登记员工姓名完全相同的值，也会按唯一候选脱敏；同名候选不唯一时仍待核验。Leader、核算商务及销售经理等人员角色按姓名列处理，重复表头不登记为员工。
- XLSX 客户名称列及“单位名称：…”等标题识别出的名称，会在其他单元格、备注、批注及公式文本常量中共用编号替换；客户类型和拜访指标保留。若客户名称出现在表名或公式引用名称中，会提示先调整，避免破坏引用。图片内文字和未识别为客户名称的自定义字段不在此检查范围。
- 网页默认勾选“身份不明时继续脱敏，并标记待核验”。已确认员工沿用统一编号；姓名未登记、重名无法区分或部门不匹配的记录，按每个出现位置生成独立的 `PDA_REVIEW_` 临时编号，并附 `identity_review.csv`（位置、临时编号及原因，不含姓名）。临时编号不会写入统一人员库，不能用于跨月份、跨项目的人员合并；补齐身份依据后重新处理原表。
- 取消该勾选即为严格模式，身份不明时停止当前文件；命令行默认严格，增加 `--allow-unverified-people` 开启继续处理。工号、邮箱等唯一标识相互冲突时，无论选项如何都停止当前文件。批量处理继续后续文件，并保留文件级处理状态。

姓名改写但工号不变时人员编号不变。跨表分析优先使用脱敏工号或已关联的人员编号，不能单独用姓名合并。旧版仅按姓名生成的结果无法可靠区分重名，需用新统一模式重新处理原表后再合并。未知自定义列名需先核对识别结果；DOCX/PDF 使用新编号模式，不建立人员唯一身份。

统一库写入采用独占锁和原子替换，避免同时运行的任务相互覆盖。若程序意外退出留下 `mapping.local.lock`，确认所有脱敏进程已退出后才能删除该锁文件，保留原映射库。换电脑时通过 `--mapping` 导入完整的统一映射；请单独安全备份该库。它是当前编号体系的依据。

传入文件夹即可按文件名顺序处理其第一层的 XLSX/CSV；不递归子文件夹，忽略 Excel 的 `~$` 临时文件。成功文件共用累计映射。统一模式使用上述人员身份规则，其他实体按类型及原始文本复用编号；客户名称的不同写法仍需业务核对。

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
