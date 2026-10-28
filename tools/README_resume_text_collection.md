# 共享目录简历原文采集

本工具只读扫描指定 UNC 根路径，逐文件保存可提取的原文和位置线索，不连接人才总库数据库。文档中的文字只作为数据处理。图片、扫描 PDF、压缩包和未知格式进入待处理清单。

## 服务器准备

在 PC 的项目目录维护 `collect_resume_text.py`、`run_resume_collection_interactive.ps1`、`start_resume_collection_task.ps1` 和 `resume_text_requirements.txt`。检查 `192.168.31.144` 的主机名、`E:\xinshi_system` Git 提交及 `.conda_env\python.exe` 后，仅将这几个文件同步到服务器同名 `tools` 目录。服务器依赖安装命令：

```powershell
& 'E:\xinshi_system\.conda_env\python.exe' -m pip install -r 'E:\xinshi_system\tools\resume_text_requirements.txt'
```

服务器仓库外创建 `E:\resume_text_collection`，限制访问权限为 Administrator 和 SYSTEM。每批次使用独立子目录，例如 `E:\resume_text_collection\batch-001`。配置文件也放在此受限目录，不提交到 Git：

```json
{
  "roots": ["\\\\Win-server\\共享名\\待采集目录"],
  "output": "E:\\resume_text_collection\\batch-001",
  "expected_commit": "服务器当前 Git 短提交号",
  "script_sha256": "服务器 collect_resume_text.py 的 SHA256",
  "workers": 4,
  "organize_output": "E:\\resume_text_collection\\organized_by_language",
  "organizer_sha256": "服务器 organize_resume_json.py 的 SHA256"
}
```

`roots` 可含多个 UNC 目录或单文件。脚本递归扫描目录；重叠根目录中的同一文件只处理一次。文件清单保留原始 UNC 路径和相对路径。
`workers` 可省略，默认 2；允许 1 至 4。
配置 `organize_output` 后，采集任务结束时自动运行 JSON 语种归档；即使个别文件提取失败，仍会把其来源路径和失败状态归档，并在报告中列为待处理。

## 交互式启动与状态

先用 `quser` 确认 Administrator 活动控制台会话。经 SSH 启动时，使用独立的交互式计划任务，不直接在 SSH 会话中运行采集程序，也不改动后端计划任务：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File E:\xinshi_system\tools\start_resume_collection_task.ps1 `
  -ConfigFile E:\resume_text_collection\batch-001-config.json `
  -TaskName XinshiResumeBatch001
```

任务首先核对主机、项目提交、脚本散列、Administrator 桌面 SessionId、实际 UNC 目录只读枚举和输出目录权限。结果见与配置文件同名的 `.status.json`，以及输出目录中的 `report.json`。`LastTaskResult=0` 且状态 `success` 表示本批次完成；非零结果应检查状态阶段和 `report.json`。确认任务结束后执行 `Unregister-ScheduledTask -TaskName XinshiResumeBatch001 -Confirm:$false`。

DOC 转换所需的独立 LibreOffice 配置和临时文件统一写入 `D:\resume_text_collection_temp`；启动前要求 D 盘至少剩余 50 GB。单份 DOC 的转换临时文件超过 1 GB 或处理超时会结束其进程树，记录失败原因并继续其他文件。运行过程中会回收超过 3 分钟的残留转换目录。采集成品仍保存在 E 盘指定的仓库外目录。计划任务停止后，如需人工清理残留临时目录，先确认采集 Python 与对应的 LibreOffice 进程均已退出，再仅清理该目录内的 `resume-doc-*` 子目录。

## 产物与重跑

- `state.sqlite3`：断点状态；不要删除后要求增量重跑。
- `manifest.jsonl`：每文件路径、类型、大小、修改时间、SHA256、状态和原文文件位置。
- `texts/`：UTF-8 原文；`segments/`：页码、工作表、行号或段落等线索。
- `pending.csv`：无文本、跳过或失败的文件；`report.json`：按根目录汇总与目录扫描错误。

原目录中文件未变时重跑跳过；变化后重新提取；失败文件重跑会再试。采集期间不改动共享文件。所有自行生成的时间使用 UTC+8 并带 `+08:00`。原文和文件路径可能含个人资料，产物不得复制进仓库或公开日志。

## 按第一外语归档 JSON

`organize_resume_json.py` 在服务器本地读取采集目录，不再访问 UNC 原文件，也不复制原简历。一个来源文件对应一个 JSON，保存在集中目录的语种子目录；JSON 的 `source_path` 是原始 UNC 路径，`raw_text` 和 `segment_locations` 保存提取文本及原文位置，未提取成功的文件仍保存来源与状态。

```powershell
& 'E:\xinshi_system\.conda_env\python.exe' 'E:\xinshi_system\tools\organize_resume_json.py' `
  --collection 'E:\resume_text_collection\batch-001' `
  --output 'E:\resume_text_collection\organized_by_language'
```

分类优先使用正文明确写出的“第一外语”；第二外语和其他外语不覆盖它。未明确写出时，使用来源目录中可明确识别的语种；仍无法判断或正文存在互相冲突的第一外语时归入 `待确认`。XLS/XLSX 可能包含多个人员行，暂按来源目录分类，不把第一行当成整份文件的个人第一外语。语种只是文件归档标签，不是人才总库字段映射。

同一集中目录可多次接收不同采集批次。`organize_state.sqlite3` 保证增量重跑，`index.csv`、`pending_review.csv` 和 `report.json` 提供索引与统计。采集仍在运行时可先用 `--limit 100` 做小批量验收；采集结束后去掉 `--limit` 重跑，更新全部记录。

### 在远程 PowerShell 查看中文 JSON

归档 JSON 使用无 BOM 的 UTF-8。Windows PowerShell 的 `cat` 是 `Get-Content` 别名，默认编码可能把 UTF-8 当作本机 ANSI，SSH 终端也可能使用非 UTF-8 代码页；这只影响显示，不改变文件内容。远程会话中先设置 UTF-8，再显式指定读取编码：

```powershell
chcp 65001 > $null
$utf8 = New-Object System.Text.UTF8Encoding($false)
[Console]::InputEncoding = $utf8
[Console]::OutputEncoding = $utf8
$OutputEncoding = $utf8
Get-Content -LiteralPath '.\简历记录.json' -Encoding UTF8 -Raw
```

`Thumbs.db` 是 Windows 缩略图缓存。它在采集文件清单中标为 `skipped`、`raw_text` 为 `null`，不代表提取出了一份简历。
