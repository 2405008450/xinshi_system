# 标注业务第三阶段数据库结构设计（业务确认版）

> 状态：业务口径已确认（仅数据库设计，不包含迁移脚本、接口和页面实现）  
> 需求来源：《系统开发_客户专员简单功能_Wm意见_第三阶段_260820.docx》  
> 数据库：PostgreSQL 17；主键沿用系统现有 UUID 规范。  
> 确认日期：2026-08-25；全部待决策项采用原草案推荐方案。

## 1. 设计结论

需求文档中的 5 张“表单”不机械对应为 5 张物理表。结合现有系统，确定复用已有的 `annotation_project`、`resource_person`、`annotation_project_language_item`、`annotation_project_price_item` 和 `annotation_project_assignee`，再补充项目状态履历、标注平台账号、试标记录、正式标注计价、动态字段和资源请求等子表。

主要原则：

1. 标注员编号、姓名统一取自 `resource_person`，不在账号、试标、正式标注表中重复保存。
2. 客户编号、客户简称、客户全称通过 `annotation_project -> client/sub_client` 关联获得。
3. “序号”是查询结果中的显示序号；只有确实需要人工排序的子表才保存 `sequence_no`。
4. 账号密码只在凭据表保存一次；试标表通过外键使用账号，不复制账号和密码。
5. 可拆分、可查询、需要校验的数据使用子表；仅用于描述的内容使用 `TEXT`；动态新增列使用“字段定义 + JSONB 值”。
6. 文档中的客户单价已由 `annotation_project_price_item` 覆盖，无须再次新增客户单价字段。

## 2. 需求表单与物理表映射

| 需求表单 | 物理表 | 处理方式 |
|---|---|---|
| 标注项目管理 | `annotation_project`、`annotation_project_status_history` | 扩展现表并新增状态履历 |
| 标注员账号表 | `annotation_project_platform`、`annotation_platform_member`、`annotation_platform_member_language`、`annotation_platform_credential` | 按项目平台、人员和凭据拆分 |
| 试标流程表 | `annotation_trial_record` | 新增；账号、人员通过外键关联 |
| 标注流程表 | `annotation_project_assignee`、`annotation_assignee_rate` | 扩展现有正式安排表，新增计价子表 |
| 资源需求管理表 | `resource_request`、`resource_request_item`、`resource_request_progress_log` | 新增跨业务资源请求主表、需求明细和进度履历 |
| 自由新增列 | `annotation_custom_field_definition` + 各业务记录的 `custom_values` | 新增动态字段定义，记录值存 JSONB |

## 3. 标注项目管理

### 3.1 复用并扩展 `annotation_project`

现有字段已经覆盖订单号、项目名称、项目类型、具体任务、客户、子客户/联系人、客户单号、项目状态、潜在需求量、任务派发/提交时间、客户经理和创建审计信息。

新增字段：

| 字段 | 类型 | 约束/默认值 | 说明 |
|---|---|---|---|
| `language_region` | `VARCHAR(255)` | 可空 | 文档中的“语言地区”，如“肇庆” |
| `status_effective_on` | `DATE` | 非空；默认 `CURRENT_DATE` | 当前状态实际生效日期，列表右下角显示该日期；不是系统操作时间 |
| `custom_values` | `JSONB` | 非空；默认 `{}` | 主表动态业务字段值，键使用动态字段定义 ID |

继续复用的关联：

- 语言/语言方向：`annotation_project_language_item`。
- 客户单价：`annotation_project_price_item`，已经支持项目类型、单语/语言方向、金额、币种、计价单位和备注。
- 标注人员正式安排：`annotation_project_assignee`。
- 客户简称、客户编号、客户全称：由 `client_id/sub_client_id` 关联计算，不重复落库。

数据库不负责项目名称和订单号的拼接规则，只保存最终结果并维持 `order_no` 唯一。订单号格式 `AP-YYYYMMDD-NNN` 可在业务确认历史数据兼容后再考虑增加正则 CHECK。

`annotation_project.project_status` 的新建默认值确定为 `initial_consultation`（初步咨询）。

### 3.2 项目状态值

需求文档明确要求保留以下中文状态名称，不替换成“已启动”等同义名称：

| code | 中文名称 | 状态性质 |
|---|---|---|
| `initial_consultation` | 初步咨询 | 进行中 |
| `consultation_no_result` | 初步咨询后无结果 | 终止/搁置 |
| `resource_sourcing` | 资源开拓 | 进行中 |
| `resource_sourcing_cancelled` | 取消资源开拓 | 终止 |
| `trial_preparation` | 试标准备 | 进行中 |
| `trial_in_progress` | 试标中 | 进行中 |
| `trial_passed` | 试标通过 | 阶段结果 |
| `trial_failed` | 试标未通过 | 阶段结果 |
| `trial_partially_passed` | 部分试标通过 | 阶段结果 |
| `project_in_progress` | 项目进行中 | 进行中 |
| `sent_to_client` | 已发客户 | 进行中 |
| `client_feedback` | 客户反馈 | 进行中 |
| `cancelled` | 已取消 | 终止 |
| `partially_cancelled` | 已部分取消 | 终止/部分终止 |

在 `annotation_project.project_status` 和状态履历的 `from_status/to_status` 上使用相同的 CHECK 集合。现有状态按下表一次性映射：

| 现有 code | 新 code | 中文含义 |
|---|---|---|
| `pending_confirmation` | `initial_consultation` | 待确认 -> 初步咨询 |
| `trial` | `trial_in_progress` | 试标中 |
| `in_progress` | `project_in_progress` | 项目进行中 |
| `sent_to_client` | `sent_to_client` | 已发客户 |
| `client_feedback` | `client_feedback` | 客户反馈 |
| `cancelled` | `cancelled` | 已取消 |
| `partially_cancelled` | `partially_cancelled` | 已部分取消 |

### 3.3 新增 `annotation_project_status_history`

用于呈现“项目状态的改变过程”，并同时区分状态实际发生日期和系统修改时间。

| 字段 | 类型 | 约束/默认值 | 说明 |
|---|---|---|---|
| `id` | `UUID` | PK；默认 `gen_random_uuid()` | 主键 |
| `project_id` | `UUID` | FK -> `annotation_project.id`；非空；删除项目时级联删除 | 所属项目 |
| `from_status` | `VARCHAR(50)` | 可空 | 首条状态记录可为空 |
| `to_status` | `VARCHAR(50)` | 非空 | 变更后的状态 |
| `effective_on` | `DATE` | 非空 | 进入该业务状态的实际日期 |
| `changed_at` | `TIMESTAMP` | 非空；默认 `CURRENT_TIMESTAMP` | 系统实际操作时间 |
| `changed_by` | `UUID` | FK -> `app_user.id`；删除用户时置空 | 操作人 |
| `change_note` | `TEXT` | 可空 | 状态修改原因或说明 |

索引：

- `INDEX (project_id, effective_on DESC, changed_at DESC)`：项目状态时间线。
- `INDEX (to_status, effective_on)`：按状态及发生日期统计。

一致性要求：每次状态变化应在同一事务内同时更新 `annotation_project.project_status/status_effective_on` 并插入履历。

## 4. 标注员账号表

### 4.1 新增 `annotation_project_platform`

“项目名称”从项目关联获得；平台链接单独建表，以支持一个项目使用一个或多个标注平台。

| 字段 | 类型 | 约束/默认值 | 说明 |
|---|---|---|---|
| `id` | `UUID` | PK | 主键 |
| `project_id` | `UUID` | FK -> `annotation_project.id`；非空；级联删除 | 所属标注项目 |
| `platform_name` | `VARCHAR(150)` | 可空 | 平台名称；未填写时可从链接域名生成展示名称 |
| `platform_url` | `TEXT` | 非空 | 可编辑的平台链接 |
| `sequence_no` | `INTEGER` | 非空；大于 0 | 项目内排序 |
| `is_active` | `BOOLEAN` | 非空；默认 `TRUE` | 平台是否仍在使用 |
| `created_by` | `UUID` | FK -> `app_user.id`；可空 | 创建人 |
| `created_at` | `TIMESTAMP` | 非空；默认当前时间 | 创建时间 |
| `updated_at` | `TIMESTAMP` | 非空；默认当前时间 | 更新时间 |

约束：`UNIQUE (project_id, sequence_no)`；对标准化后的平台 URL 做项目内重复校验。

### 4.2 新增 `annotation_platform_member`

一行代表某标注员加入某个项目平台。标注员编号和姓名从 `resource_person` 获取。

| 字段 | 类型 | 约束/默认值 | 说明 |
|---|---|---|---|
| `id` | `UUID` | PK | 主键 |
| `platform_id` | `UUID` | FK -> `annotation_project_platform.id`；非空；级联删除 | 所属平台 |
| `person_id` | `UUID` | FK -> `resource_person.id`；可空；限制删除 | 使用该账号的标注员；允许先录入账号、后分配人员 |
| `nickname` | `VARCHAR(255)` | 可空 | 主账号昵称 |
| `registration_status` | `VARCHAR(30)` | 非空；默认 `unregistered`；CHECK 固定枚举 | 注册状态 |
| `sequence_no` | `INTEGER` | 非空；大于 0 | 平台表内人工排序 |
| `custom_values` | `JSONB` | 非空；默认 `{}` | 动态列数据 |
| `created_at` | `TIMESTAMP` | 非空；默认当前时间 | 创建时间 |
| `updated_at` | `TIMESTAMP` | 非空；默认当前时间 | 更新时间 |

约束与索引：

- `UNIQUE (platform_id, person_id)`：同一平台不重复添加同一标注员。
- `UNIQUE (platform_id, sequence_no)`：排序号唯一。
- `INDEX (person_id)`、`INDEX (registration_status)`。

注册状态固定为：`unregistered`（未注册）、`registering`（注册中）、`registered`（已注册）、`registration_failed`（注册失败）、`disabled`（已停用）、`not_required`（无需注册）。

### 4.3 新增 `annotation_platform_member_language`

账号表存在“语种”列且要求点击筛选，因此使用关联表记录平台成员在本项目中对应的一个或多个语种/语言方向。

| 字段 | 类型 | 约束/默认值 | 说明 |
|---|---|---|---|
| `member_id` | `UUID` | PK(1)；FK -> `annotation_platform_member.id`；级联删除 | 平台成员 |
| `language_item_id` | `UUID` | PK(2)；FK -> `annotation_project_language_item.id`；限制删除 | 项目语种或语言方向 |

应用层还需校验该 `language_item_id` 与平台所属项目一致。

### 4.4 新增 `annotation_platform_credential`

主账号和备份账号建成多行，不使用“备份账号 1、备份账号 2”横向字段。这样没有备份账号时自然无记录，有内容时才展示，并可支持多个备份账号。

| 字段 | 类型 | 约束/默认值 | 说明 |
|---|---|---|---|
| `id` | `UUID` | PK | 主键 |
| `member_id` | `UUID` | FK -> `annotation_platform_member.id`；非空；级联删除 | 所属平台成员 |
| `credential_kind` | `VARCHAR(20)` | 非空；CHECK `primary/backup` | 主账号或备份账号 |
| `sequence_no` | `INTEGER` | 非空；大于 0 | 同类凭据排序 |
| `display_nickname` | `VARCHAR(255)` | 可空 | 备份昵称；主账号为空时使用成员昵称 |
| `login_account_ciphertext` | `BYTEA` | 非空 | 登录账号密文 |
| `login_account_fingerprint` | `CHAR(64)` | 可空 | 账号 HMAC 指纹，用于查重但不暴露明文 |
| `password_ciphertext` | `BYTEA` | 非空 | 可逆加密后的密码；不能明文保存，也不能用不可逆密码哈希代替 |
| `encryption_key_version` | `VARCHAR(50)` | 非空 | 加密密钥版本，密钥本身不保存在数据库 |
| `is_active` | `BOOLEAN` | 非空；默认 `TRUE` | 凭据是否有效 |
| `password_updated_at` | `TIMESTAMP` | 可空 | 密码最后更新时间 |
| `created_at` | `TIMESTAMP` | 非空；默认当前时间 | 创建时间 |
| `updated_at` | `TIMESTAMP` | 非空；默认当前时间 | 更新时间 |

约束：

- `UNIQUE (member_id, credential_kind, sequence_no)`。
- PostgreSQL 部分唯一索引：同一成员只能有一个有效主账号。
- 禁止在日志、审计明细和普通列表接口中输出 `password_ciphertext`。

## 5. 试标流程表

### 5.1 新增 `annotation_trial_record`

一行代表“某项目、某标注员的一次试标轮次”。姓名、编号、昵称、账号、备份账号和注册状态均通过人员及平台成员关联取得，不在本表重复保存。

| 字段 | 类型 | 约束/默认值 | 说明 |
|---|---|---|---|
| `id` | `UUID` | PK | 主键 |
| `project_id` | `UUID` | FK -> `annotation_project.id`；非空；级联删除 | 试标项目 |
| `person_id` | `UUID` | FK -> `resource_person.id`；非空；限制删除 | 标注员 |
| `platform_member_id` | `UUID` | FK -> `annotation_platform_member.id`；可空；删除时置空 | 试标使用的平台账号 |
| `round_no` | `INTEGER` | 非空；默认 1；大于 0 | 试标轮次 |
| `sequence_no` | `INTEGER` | 非空；大于 0 | 项目/轮次内排序 |
| `willingness_text` | `TEXT` | 可空 | 文档要求“人工填写意愿”，按原话保留自由文本 |
| `trial_status` | `VARCHAR(30)` | 非空；默认 `pending`；CHECK 固定枚举 | 试标执行状态 |
| `trial_result` | `VARCHAR(30)` | 可空；CHECK 固定枚举 | 试标结果 |
| `result_note` | `TEXT` | 可空 | 结果或评语 |
| `custom_values` | `JSONB` | 非空；默认 `{}` | 动态列数据 |
| `created_by` | `UUID` | FK -> `app_user.id`；可空 | 创建人 |
| `created_at` | `TIMESTAMP` | 非空；默认当前时间 | 创建时间 |
| `updated_at` | `TIMESTAMP` | 非空；默认当前时间 | 更新时间 |

约束与索引：

- `UNIQUE (project_id, person_id, round_no)`。
- `UNIQUE (project_id, round_no, sequence_no)`。
- `INDEX (project_id, trial_status)`、`INDEX (person_id)`。
- 应校验 `platform_member_id` 的人员和项目分别与本记录一致。

`trial_status` 固定为 `pending/in_progress/submitted/reviewing/completed/cancelled`；`trial_result` 固定为 `passed/failed/partially_passed/withdrawn`。同一标注员允许在同一项目进行多轮试标，因此保留 `round_no`。

## 6. 标注流程表（正式项目）

### 6.1 扩展 `annotation_project_assignee`

现有表已保存项目、标注员、排序、安排状态、质量评分和评语，最适合作为正式标注流程的主记录。

新增字段：

| 字段 | 类型 | 约束/默认值 | 说明 |
|---|---|---|---|
| `assignment_role` | `VARCHAR(30)` | 非空；默认 `annotator`；CHECK `annotator/quality_inspector` | 独立区分标注员和质检员 |
| `language_item_id` | `UUID` | FK -> `annotation_project_language_item.id`；可空 | 本次安排对应的语种/语言方向 |
| `audio_duration_value` | `NUMERIC(18,3)` | 可空；大于等于 0 | 音频长度数值 |
| `audio_duration_unit` | `VARCHAR(20)` | 可空；CHECK `second/minute/hour` | 音频长度单位 |
| `custom_values` | `JSONB` | 非空；默认 `{}` | 动态列数据 |
| `created_at` | `TIMESTAMP` | 非空；默认当前时间 | 创建时间 |
| `updated_at` | `TIMESTAMP` | 非空；默认当前时间 | 更新时间 |

同一人员允许在同一项目负责多个语种，且不同语种价格可以不同。删除现有 `UNIQUE (project_id, person_id)`，改为 `UNIQUE NULLS NOT DISTINCT (project_id, person_id, language_item_id, assignment_role)`。`language_item_id` 存在时还需校验其属于同一个项目。

质检员作为独立人员保存：质检安排使用 `assignment_role='quality_inspector'`，不在标注员记录上只挂一个无法追溯人员的质检成本。

### 6.2 新增 `annotation_assignee_rate`

不把金额和单位拼成一个字符串。标注员与质检员各自通过 `annotation_project_assignee` 保存人员和角色，再在本表保存该安排对应的价格。

| 字段 | 类型 | 约束/默认值 | 说明 |
|---|---|---|---|
| `id` | `UUID` | PK | 主键 |
| `assignee_id` | `UUID` | FK -> `annotation_project_assignee.id`；非空；级联删除 | 正式标注安排 |
| `amount` | `NUMERIC(18,6)` | 非空；大于 0 | 单价金额 |
| `currency` | `VARCHAR(3)` | 可空；空值按现系统默认人民币展示 | ISO 4217 币种代码 |
| `unit` | `VARCHAR(30)` | 非空；CHECK `item/second/minute/hour` | 条、秒、分钟或小时 |
| `remarks` | `TEXT` | 可空 | 计价说明 |
| `created_at` | `TIMESTAMP` | 非空；默认当前时间 | 创建时间 |
| `updated_at` | `TIMESTAMP` | 非空；默认当前时间 | 更新时间 |

约束：`UNIQUE (assignee_id)`。价格角色由关联的 `annotation_project_assignee.assignment_role` 确定。

## 7. 动态新增业务列

### 7.1 新增 `annotation_custom_field_definition`

该表用于保存用户真正新增的业务字段，不等同于仅控制显示/隐藏的前端“字段设置”。

| 字段 | 类型 | 约束/默认值 | 说明 |
|---|---|---|---|
| `id` | `UUID` | PK | 动态字段 ID，同时作为 JSONB 键 |
| `project_id` | `UUID` | FK -> `annotation_project.id`；可空；级联删除 | 项目级字段；为空表示整个模块通用字段 |
| `table_code` | `VARCHAR(30)` | 非空；CHECK `project/account/trial/assignment` | 应用于哪张业务表 |
| `field_key` | `VARCHAR(100)` | 非空 | 稳定机器键，不随中文名称修改 |
| `field_label` | `VARCHAR(150)` | 非空 | 页面显示名称 |
| `data_type` | `VARCHAR(30)` | 非空 | `text/number/date/datetime/boolean/single_select/multi_select/url` |
| `options` | `JSONB` | 非空；默认 `[]` | 选择型字段选项 |
| `sequence_no` | `INTEGER` | 非空；大于 0 | 列顺序，可在插入列时整体重排 |
| `is_required` | `BOOLEAN` | 非空；默认 `FALSE` | 是否必填 |
| `is_active` | `BOOLEAN` | 非空；默认 `TRUE` | 停用后保留历史值但不再录入 |
| `created_by` | `UUID` | FK -> `app_user.id`；可空 | 创建人 |
| `created_at` | `TIMESTAMP` | 非空；默认当前时间 | 创建时间 |
| `updated_at` | `TIMESTAMP` | 非空；默认当前时间 | 更新时间 |

唯一约束：`UNIQUE NULLS NOT DISTINCT (project_id, table_code, field_key)`；排序索引 `(project_id, table_code, sequence_no)`。

作用域确定为：账号、试标、正式标注表的动态字段按项目独立定义，`project_id` 必须有值；标注项目主表的动态字段全局共用，`project_id` 为空。

各业务记录的 `custom_values` 格式示例：

```json
{
  "8f4b...动态字段UUID": "字段值",
  "d133...动态字段UUID": 12.5
}
```

使用定义 ID 而不是 `field_key` 作为键，可避免字段改名导致历史数据失联。数据库可增加 JSONB GIN 索引，但只有实际出现动态字段筛选需求后再添加，避免无效写入开销。

## 8. 资源需求管理

### 8.1 新增 `resource_request`

一条资源请求只来源于一个已保存并取得 ID 的业务项目，并且只对应一个请求类别。新增项目页面必须先保存项目草稿，再发出资源请求。项目类型、订单号、项目名称和客户信息在发起时自动获取；同时保留快照，避免源项目后续改名造成历史请求含义变化。当前项目状态由展示视图实时关联源项目。

| 字段 | 类型 | 约束/默认值 | 说明 |
|---|---|---|---|
| `id` | `UUID` | PK | 主键 |
| `request_no` | `VARCHAR(50)` | 非空；唯一 | 资源请求编号 |
| `source_type` | `VARCHAR(30)` | 非空 | `annotation/recruitment/interpretation/translation/other` |
| `request_category` | `VARCHAR(30)` | 非空 | 页面“项目类型”：`annotation_trial/annotation_formal/recruitment/interpretation/translation/other` |
| `annotation_project_id` | `UUID` | FK -> `annotation_project.id`；可空；限制删除 | 标注来源项目 |
| `recruitment_project_id` | `UUID` | FK -> `recruitment_project.id`；可空；限制删除 | 招聘来源项目 |
| `interpretation_project_id` | `UUID` | FK -> `interpretation_project.id`；可空；限制删除 | 口译来源项目 |
| `translation_project_id` | `UUID` | FK -> `translation_project.id`；可空；限制删除 | 笔译来源项目 |
| `other_source_name` | `VARCHAR(500)` | 可空 | `source_type=other` 时的人工来源名称 |
| `source_project_types_snapshot` | `JSONB` | 非空；默认 `[]` | 发起时源项目更细的业务内容，如音频标注、文本评测；与上面的六类请求类别不是同一概念 |
| `source_order_no_snapshot` | `VARCHAR(80)` | 可空 | 发起时订单号快照 |
| `source_project_name_snapshot` | `VARCHAR(500)` | 非空 | 发起时项目名称快照 |
| `source_status_snapshot` | `VARCHAR(50)` | 可空 | 发起时项目状态快照；当前状态通过视图实时取源表 |
| `client_id` | `UUID` | FK -> `client.id`；可空；限制删除 | 客户 |
| `sub_client_id` | `UUID` | FK -> `sub_client.id`；可空；置空 | 子客户 |
| `client_code_snapshot` | `VARCHAR(60)` | 可空 | 客户编号快照 |
| `client_short_name_snapshot` | `VARCHAR(100)` | 可空 | 客户简称快照 |
| `request_detail` | `TEXT` | 非空 | 人工填写的需求详情；当前阶段的主要承载字段 |
| `progress_percent` | `SMALLINT` | 非空；默认 0；CHECK 0~100 | 开拓进度条当前值 |
| `priority` | `VARCHAR(10)` | 非空；默认 `medium`；CHECK `high/medium/low` | 高、中、低 |
| `request_status` | `VARCHAR(30)` | 非空；默认 `submitted`；CHECK 固定枚举 | `draft/submitted/in_progress/fulfilled/cancelled` |
| `requested_by` | `UUID` | FK -> `app_user.id`；可空 | 发起人 |
| `requested_at` | `TIMESTAMP` | 非空；默认当前时间 | 发出请求时间 |
| `owner_id` | `UUID` | FK -> `app_user.id`；可空 | 资源开拓负责人 |
| `completed_at` | `TIMESTAMP` | 可空 | 完成时间 |
| `created_at` | `TIMESTAMP` | 非空；默认当前时间 | 创建时间 |
| `updated_at` | `TIMESTAMP` | 非空；默认当前时间 | 更新时间 |

核心 CHECK：

- `source_type` 为四类已有项目时，只允许对应的一个项目外键非空，其余项目外键必须为空。
- `source_type='other'` 时四个项目外键都为空，`other_source_name` 非空。
- `request_category` 必须与 `source_type` 一致；标注来源只能选择 `annotation_trial` 或 `annotation_formal`。
- 同一请求不允许同时关联多个项目或多个 `request_category`；标注项目的试标与正式项目资源需求分别创建请求。
- `completed_at` 不早于 `requested_at`。

索引：

- `(request_status, priority, requested_at DESC)`。
- `(source_type, requested_at DESC)`。
- 四个项目外键分别建立部分索引，仅索引非空记录。
- `(client_id)`、`(owner_id, request_status)`。

新增只读视图 `v_resource_request_display`，分别关联四类项目并输出统一的当前项目状态、当前订单号和当前项目名称；列表默认显示当前值，详情同时可显示发起时快照。

### 8.2 新增 `resource_request_item`

用于把“多个语种 + 各自人数 + 各自详情”结构化。本期即保留该表；页面初期仍可主要填写 `request_detail`，但结构化数据直接写入本表，避免以后拆分历史长文本。

| 字段 | 类型 | 约束/默认值 | 说明 |
|---|---|---|---|
| `id` | `UUID` | PK | 主键 |
| `request_id` | `UUID` | FK -> `resource_request.id`；非空；级联删除 | 所属请求 |
| `sequence_no` | `INTEGER` | 非空；大于 0 | 明细顺序 |
| `source_language_id` | `UUID` | FK -> `interpretation_language.id`；可空；限制删除 | 单语或源语种 |
| `target_language_id` | `UUID` | FK -> `interpretation_language.id`；可空；限制删除 | 目标语种；单语需求为空 |
| `required_count` | `INTEGER` | 可空；大于 0 | 需求人数 |
| `requirement_detail` | `TEXT` | 可空 | 该语种/方向的具体要求 |
| `created_at` | `TIMESTAMP` | 非空；默认当前时间 | 创建时间 |
| `updated_at` | `TIMESTAMP` | 非空；默认当前时间 | 更新时间 |

约束：`UNIQUE (request_id, sequence_no)`；目标语种存在时源语种必须存在且两者不同。

### 8.3 新增 `resource_request_progress_log`

进度条只保存当前百分比会丢失过程，因此增加轻量履历。

| 字段 | 类型 | 约束/默认值 | 说明 |
|---|---|---|---|
| `id` | `UUID` | PK | 主键 |
| `request_id` | `UUID` | FK -> `resource_request.id`；非空；级联删除 | 所属请求 |
| `progress_percent` | `SMALLINT` | 非空；CHECK 0~100 | 本次进度 |
| `progress_note` | `TEXT` | 可空 | 进度说明 |
| `changed_by` | `UUID` | FK -> `app_user.id`；可空 | 操作人 |
| `changed_at` | `TIMESTAMP` | 非空；默认当前时间 | 操作时间 |

索引：`INDEX (request_id, changed_at DESC)`。

## 9. 不重复落库的展示字段

| 页面字段 | 数据来源 |
|---|---|
| 序号 | 查询结果行号或 `sequence_no` |
| 标注员编号 | `resource_person.resource_code` |
| 姓名 | `resource_person.full_name` |
| 项目名称 | `annotation_project.project_name` |
| 客户简称/编号/全称 | `annotation_project` 关联 `client/sub_client` |
| 账号表语种 | `annotation_platform_member_language` 关联项目语言项 |
| 试标表账号/密码/备份账号/注册状态 | `annotation_trial_record -> annotation_platform_member -> annotation_platform_credential` |
| 资源请求当前项目状态 | `v_resource_request_display` 实时关联源项目 |

## 10. 已确认的业务决策

1. 一个标注项目允许配置多个标注平台，账号归属具体平台。
2. 账号、试标、正式标注表的动态字段按项目独立定义；标注项目主表动态字段全局共用。
3. 同一标注员允许在同一项目进行多轮试标。
4. 同一人员允许在同一项目负责多个语种，不同语种可以使用不同价格。
5. 质检员是独立人员，正式安排必须记录质检员身份及其价格。
6. 发出资源请求前必须先保存项目草稿并取得项目 ID。
7. 本期即保留并使用 `resource_request_item` 结构化语种、人数和详情。
8. 现有 `pending_confirmation`（待确认）映射为 `initial_consultation`（初步咨询）。
9. 注册状态采用：未注册、注册中、已注册、注册失败、已停用、无需注册。
10. 一条资源请求只关联一个来源项目和一个请求类别，不合并多个项目或多个类别。

## 11. 本阶段明确不做

- 不创建或执行数据库迁移。
- 不修改 SQLAlchemy 模型、Pydantic Schema、接口或前端页面。
- 不实现订单号/项目名称生成逻辑、状态确认弹窗、动态列交互和资源请求流程。
- 不设计工作台交接；需求文档首页提到口译、标注、招聘项目交接，但本次用户范围明确为数据库表单结构。
