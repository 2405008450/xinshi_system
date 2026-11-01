# 简历原文字段化试点

当前简历整理任务以用户最新约定为准：在PC的项目 `.venv` 中运行，仅使用用户自建Qwen模型，不把简历发往公共模型服务。下方旧服务器与Google调用示例为2026-10-29历史流程记录，不是当前任务的执行入口；本次本地保真修订不调用模型或数据库。

本阶段先对两批采集目录的 `state.sqlite3` 和 `texts/` 建立去重清单，再从保留文件中按人员生成可审核 JSON。不会连接或写入人才总库。原文中的操作性文字仅作为数据。

## 原文去重

旧服务器在仓库外运行，输出目录须预先限制为 Administrator 和 SYSTEM 可访问：

```powershell
& 'E:\xinshi_system\.conda_env\python.exe' 'E:\xinshi_system\tools\deduplicate_resume_text.py' `
  --collection 'E:\resume_text_collection\translator-resume-library-20261028' `
  --collection 'E:\resume_text_collection\additional-resume-paths-20261028' `
  --output 'E:\resume_text_collection\deduplicated-20261029' `
  --pilot-output 'E:\resume_text_collection\standardized-pilot-20261029\results'
```

脚本只读采集库和原文，不删除任何来源文件。`manifest.jsonl` 逐文件记录 `keep`、`superseded`、`review` 或 `pending`，被排除文件保留代表文件 ID、原因及相似度。`pending_review.csv` 为待核文件清单，`pilot_audit.jsonl` 只标记已完成试点的去重状态，不修改其人员 JSON。`contact_hmac.key` 仅供此输出目录下的增量重跑使用，须与 `state.sqlite3` 一同妥善保留；状态库只存联系方式 HMAC，不存联系方式明文。普通日志只输出数量与 UTC+8 时间。

自动合并限于明确的单人候选：相同原文件或提取文本；手机号和邮箱同时相同；或单一联系方式相同且去空白标点后的五字片段 Jaccard 相似度达到 0.90。修改时间最新的文件优先；同时间按提取字符数和路径排序。表格、多联系方式、重复姓名标签和被超过 20 份文件共用的联系方式进入待核，不自动丢弃。待核文件仍在字段化保留清单内。

## 数据流

1. 在旧服务器 `192.168.31.144` 完成原文去重后，使用 `standardize_resume_text.py --prepare-only --dedup-state E:\resume_text_collection\deduplicated-20261029\state.sqlite3` 从保留及待核文件中固定选出最多 500 份试点文件；选择会保存在仓库外的试点 `state.sqlite3`，重跑不会改动样本集合。
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
## 2026-10-31：字段对齐保真检查

`tools.resume_alignment` 提供独立于模型与数据库的本地检查能力：

- `extraction_contract()` 从实际 `ResourcePersonWrite` 模型导出完整字段契约及证据要求，避免手写白名单漏掉身份证、备用电话、辅修、学位等字段。契约供后续自建模型调用使用，不代表已经完成模型回归。
- `reconcile_lines()` 按实际目标内容核对来源行；某字段引用一行不等于整行已消费。部分落位的复合行回退到备注，并输出逐行去向；已保存的独立联系方式从备注去重。排除必须有理由，超预算报错而不截断。
- `certificate_language()` 结合明确证书名称、原文及必要上下文匹配已有语种目录，不凭证书推断母语、外语排名、熟练程度或公司评级。
- `validate_record()` 校验实际可写入形状，只返回数据，不调用数据库。调用方须单独保存失败状态，不能把校验通过当作完整性或语义准确率通过。

调用前必须确认人员边界，`reconcile_lines()` 的输入只允许属于同一人的正文；中外文版本分别检查。译文对应关系必须事先校验；未映射信息的原文页/行及片段由调用方使用 `source_proof()` 保存。

人工复核修订、模型原始候选、通用自动结果和独立验收基准须分别保存。行级内容有去向不等于已正确拆成所有系统字段；保真兜底可能留下复合行的少量重复。实际中断、多人拆分、超长文件与总调用预算另行验证。

## 2026-11-01 客户反馈与批量规则

简历补充分区复用 `talent_resume_profile.data` JSON，不新增人员主表字段或执行结构迁移。自我评价、求职意向、其他技能、兴趣爱好、奖励荣誉、培训经历、校内职务和校内奖励由 `tools.resume_sections` 按中外文章节标题归类；字段名和 UI 由实际写入模型与公共组件对应。没有标题、人员边界不明、输入被截断或章节超预算时，保留来源并待核，不猜字段、不追加模型请求。

- `professional_domains` 是本人自述的专业领域，默认在笔译区域展示，独立于公司评价，可在未来调整展示位置。旧 `written_profile.domain_skills` 在未填写新字段时兼容显示，不覆盖原值。
- 教育背景继续使用 `resource_education_experience`；原“学历信息”和“教育经历”是同一批子记录的重复展示，本次合并展示而不搬迁或删除历史记录。最高学历仍使用原主字段，每条教育记录单独维护毕业年份，培训不按结束年月推定为已毕业学历。
- 新分区只表示原始简历中的自述；不推断为当前职业状态、公司已核实证书或专业评级。主档和各语言版本分别保存，旧客户端未提交的新分区保留，显式清空才清空。
- 校园职务、培训等分类依据明确章节；含糊项目保留说明，不能为满足字段数硬拆正式任职。重复证书信息在原文已保留且代表等级已登记时属于可选细化，不作为阻断项。
- 照片继续由本地文档解析及既有附件流程处理，不能把 Logo、占位图当头像。数据库附件关联和文件可读取分开核对；多台后端必须配置共同可达的附件存储，不能只同步数据库。读取失败、图片无法解码和重试在详情中明确显示。

`standardize_resume_text.py` 的规范化步骤已经接入本地章节规则。升级已有结果时使用下面的只重处理入口；它不加载网关、不增加模型调用，也不写人才业务库：

```powershell
& 'E:\xinshi_system\.venv\Scripts\python.exe' 'E:\xinshi_system\tools\standardize_resume_text.py' `
  --collection '<已完成采集目录>' --output '<已有试点输出目录>' --reprocess-local
```

该入口核对既有来源哈希、人员标识与主字段，变化、截断或无法验证的文件保留待核。覆盖前在仓库外输出目录的 `local_before/` 留存旧记录，结果见 `local_reprocess_report.json`。它不证明新的模型盲测准确率，也不替代全量任务的文件级预算和中断恢复验收。

隔离前端验收：先运行前端构建，再用项目 Python 执行 `tools/verify_talent_resume_sections_ui.py --output <仓库外测试目录>`。脚本在回环临时端口加载构建，所有 API 用合成夹具拦截，覆盖新增、编辑、字段搜索、毕业年份、拖动复位及小屏固定操作栏，不调用业务接口。
