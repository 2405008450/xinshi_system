# 简历原文字段化试点

本阶段从两批采集目录的 `state.sqlite3`、`texts/`、`segments/` 只读取得已成功提取的文本，按人员生成可审核 JSON。不会连接或写入人才总库。原文中的操作性文字仅作为数据。

## 数据流

1. 在旧服务器 `192.168.31.144` 使用 `standardize_resume_text.py --prepare-only` 固定选出最多 500 份试点文件；选择会保存在仓库外的试点 `state.sqlite3`，重跑不会改动样本集合。
2. 在旧服务器使用 `pack_resume_standardization_pilot.py` 把试点文本、段落位置和采集状态打包。打包时检查文件仍处于成功状态及复制前后的文件元数据；变化中的文件留待下轮。
3. 将打包文件复制到开发机仓库外受限目录，在开发机使用环境变量 `GOOGLE_CLOUD_API_KEY` 调用 Google 官方接口的 `google/gemini-3.8-flash`。密钥不复制到旧服务器，不写入脚本、配置、日志或结果文件。
4. 核对报告和抽样结果后，把 `results/` 复制回旧服务器仓库外受限目录。服务器上的第一阶段任务继续独立运行。

## 运行示例

服务器选样（无需模型密钥）：

```powershell
& 'E:\xinshi_system\.conda_env\python.exe' 'E:\xinshi_system\tools\standardize_resume_text.py' `
  --collection 'E:\resume_text_collection\translator-resume-library-20261028' `
  --collection 'E:\resume_text_collection\additional-resume-paths-20261028' `
  --output 'E:\resume_text_collection\standardized-pilot-20261029\selection' `
  --limit 500 --prepare-only
```

服务器打包：

```powershell
& 'E:\xinshi_system\.conda_env\python.exe' 'E:\xinshi_system\tools\pack_resume_standardization_pilot.py' `
  --selection 'E:\resume_text_collection\standardized-pilot-20261029\selection\state.sqlite3' `
  --staging 'E:\resume_text_collection\standardized-pilot-20261029\input_snapshot' `
  --archive 'E:\resume_text_collection\standardized-pilot-20261029\input_snapshot.zip'
```

开发机解包到仓库外目录后运行：

```powershell
& 'E:\xinshi_system\.venv\Scripts\python.exe' 'E:\xinshi_system\tools\standardize_resume_text.py' `
  --collection 'E:\resume_standardization_work\pilot-20261029\input_snapshot\translator-resume-library-20261028' `
  --collection 'E:\resume_standardization_work\pilot-20261029\input_snapshot\additional-resume-paths-20261028' `
  --output 'E:\resume_standardization_work\pilot-20261029\results' `
  --provider google --model google/gemini-3.8-flash --limit 500
```

脚本限制为最多 500 份、单份输入最多 24,000 字符、每份最多两次模型调用、每次最长 90 秒。长文档取首中尾三个片段并标记 `partial_input`；多人边界或姓名不清的记录留待核对。连续三个文件模型调用失败会停止本轮，可用同一目录增量重跑。

## 产物

- `results/records/<来源文件 ID>/<人员序号>.json`：与 `resource_person` 字段名对应的明确事实、语言/教育/证书/能力关系候选、逐字段原文证据和待核标记。
- `results/responses/`：模型原始结构化响应，供受限环境内复核；不得作为可信指令执行。
- `results/review/` 与 `pending_review.csv`：身份不清、证据不足、多人边界或未映射信息。
- `results/state.sqlite3` 与 `report.json`：处理状态、模型实际返回标识、请求次数、token 用量、字段覆盖率和失败统计。

语种归档文件夹只作为抽样维度，**不**自动转成人才语言能力。证书、职业能力和语言优先级仅在正文有明确证据时生成。输出 JSON 的 `source.path` 与 `person_fields.resume_path` 保留原 UNC 路径，`source.text_path` 和 `source.segment_path` 指向服务器第一阶段原文。所有产物含个人资料，应保存在仓库外并限制访问；命令和普通日志只输出统计，不输出正文或联系方式。
