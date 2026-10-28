# 数据字典

## 标注会话创建登记（annotation_chat_conversation）

显式创建入口登记独立状态；历史默认参与人不能代替创建记录。已有聊天消息的项目视为已创建，但不补造历史创建时间。历史仅有成员、没有消息及创建登记的项目显示未创建，成员与关注数据保留。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| project_id | uuid | 主键，关联标注订单，一个订单仅一个会话 |
| created_by | uuid | 显式创建人，关联 app_user |
| created_at | timestamptz | 实际登记时间，UTC+8，不回填历史 |

## 标注员情况记录（annotation_annotator_progress）

聊天“添加进度 → 标注员情况”与标注项目管理进度窗口共用本表，按准确的主／子订单 ID 隔离。独立于客户进度和项目状态，不回填历史记录；由显式迁移脚本初始化，不在服务启动时建表。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid | 记录主键 |
| project_id | uuid | 标注订单 ID，关联 annotation_project |
| change_note | text | 标注员情况正文，1～10000 字，支持统一截图引用 |
| effective_on | timestamptz | 业务节点时间，UTC+8 |
| changed_at / changed_by | timestamptz / uuid | 首次登记时间／人员 |
| updated_at / updated_by | timestamptz / uuid | 版本时间／更新人员 |

> 目标结构快照：2026-08-27 中国标准时间；来源：ORM 与账号资产库迁移 DDL。部署后可再次运行 `tools/generate_database_docs.py` 以实际 PostgreSQL 为准复核。

## 阅读说明

### 2026-10-21 会话参与人访问边界

- `annotation_chat_member`、`chat_project_member_pref`、`chat_discussion_member` 中的记录分别表示标注、笔译、资源讨论的参与资格；模块查看权限、创建人身份、历史发言、关注和置顶不能在读取时新增参与人。单聊仍限定双方账号。
- `annotation_chat_default_participant`：所有账号共用的标注会话默认参与人名单，只在显式发起新会话时复制，并自动加入发起人；不修改已有会话参与人。
- 标注和笔译消息显式 @非参与人时，在同一发送事务中加入该人员；发送失败时一并回滚。新成员阅读基线设在本条消息之前，保留该条提及的未读提醒。
- 移出参与人或主动退出群组会删除对应成员记录并立即收回访问权，保留历史消息和附件；只有现有成员能够重新邀请，单纯退出会话窗口不改变成员资格。

| 字段 | 类型 | 约束 / 语义 |
| --- | --- | --- |
| user_id | uuid | PK，FK → app_user.id，删除账号时级联删除默认配置 |
| updated_by | uuid | NOT NULL，FK → app_user.id，最后配置人 |
| updated_at | timestamptz | NOT NULL，明确携带 UTC+8 的业务时间 |

显式迁移入口：`tools/apply_chat_participants_migration.py`。迁移不修改消息、附件、原有参与记录及默认参与人配置；可重复执行。首次迁移将原笔译项目负责人/历史参与人，以及原公共资源讨论的有权有效账号固化为参与记录。此后新账号不自动获得既有会话访问权。执行业务库迁移仍需单独授权。

- `PK`：主键；`FK`：外键；`UQ`：唯一约束；`组合 UQ`：字段参与组合唯一约束。
- 所有 `timestamp` 均为 PostgreSQL `timestamp without time zone`；应用连接会话时区固定为 `Asia/Hong_Kong`。
- JSONB 字段保存结构化快照或可扩展数据，具体 JSON 形状由应用层 schema/服务代码约束。
- 表级 CHECK、组合唯一约束和索引列在每张表字段清单后单独列出。

## 身份与权限

### `app_user`

系统登录用户、人员基础信息及固定任务配置。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `username` | `varchar(100)` | UQ；非空 | — | 登录用户名 |
| `password_hash` | `varchar(255)` | 非空 | — | 密码哈希；不是明文密码 |
| `full_name` | `varchar(255)` | 可空 | — | 用户姓名 |
| `email` | `varchar(255)` | 可空 | — | 电子邮箱 |
| `is_active` | `boolean` | 可空 | `true` | 账号是否启用 |
| `department` | `varchar(50)` | 可空 | — | 所属部门 |
| `fixed_tasks` | `jsonb` | 可空 | `'[]'` | 用户固定任务配置 |
| `created_at` | `timestamp` | 可空 | `当前时间` | 创建时间 |
| `updated_at` | `timestamp` | 可空 | `当前时间` | 最后更新时间 |

### `role`

角色定义。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `role_name` | `varchar(50)` | UQ；非空 | — | 角色名称 |
| `description` | `text` | 可空 | — | 描述 |

### `user_role`

用户与角色的多对多关联。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `user_id` | `uuid` | FK → app_user.id；组合 UQ；非空 | — | 关联用户 |
| `role_id` | `uuid` | FK → role.id；组合 UQ；非空 | — | 关联角色 |
| `created_at` | `timestamp` | 可空 | `当前时间` | 创建时间 |

表级规则：组合唯一：`user_id`, `role_id`。

### `role_permission`

角色拥有的细粒度权限。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `role_id` | `uuid` | FK → role.id；组合 UQ；非空 | — | 关联角色 |
| `permission_code` | `varchar(100)` | 组合 UQ；非空 | — | 权限编码 |
| `created_at` | `timestamp` | 可空 | `当前时间` | 创建时间 |

表级规则：组合唯一：`role_id`, `permission_code`。

## 客户与咨询

### `client`

母客户/主客户档案。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `client_code` | `varchar(50)` | UQ；非空 | — | 客户编码 |
| `client_name` | `varchar(255)` | 非空 | — | 客户全称 |
| `client_short_name` | `varchar(100)` | 非空 | — | 客户简称 |
| `english_name` | `varchar(255)` | 可空 | — | 英文全称 |
| `english_short_name` | `varchar(100)` | 可空 | — | 英文简称 |
| `client_manager` | `varchar(100)` | 可空 | — | 客户方负责人 |
| `manager_contact` | `varchar(100)` | 可空 | — | 负责人联系方式 |
| `field_level1` | `varchar(100)` | 可空 | — | 一级业务领域 |
| `field_level2` | `varchar(100)` | 可空 | — | 二级业务领域 |
| `country` | `varchar(50)` | 可空 | — | 国家 |
| `province` | `varchar(50)` | 可空 | — | 省/州 |
| `city` | `varchar(50)` | 可空 | — | 城市 |
| `district` | `varchar(50)` | 可空 | — | 区县 |
| `client_status` | `varchar(20)` | 可空 | `'pending'` | 客户状态 |
| `cooperation_start_date` | `timestamp` | 可空 | — | 合作开始时间 |
| `remarks` | `text` | 可空 | — | 备注 |
| `created_at` | `timestamp` | 可空 | `当前时间` | 创建时间 |
| `updated_at` | `timestamp` | 可空 | `当前时间` | 最后更新时间 |

### `sub_client`

母客户下属的子客户档案。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `parent_client_id` | `uuid` | FK → client.id；非空 | — | 所属母客户 |
| `sub_client_code` | `varchar(60)` | UQ；非空 | — | 子客户编码 |
| `client_name` | `varchar(255)` | 非空 | — | 客户全称 |
| `client_short_name` | `varchar(100)` | 非空 | — | 客户简称 |
| `english_name` | `varchar(255)` | 可空 | — | 英文全称 |
| `english_short_name` | `varchar(100)` | 可空 | — | 英文简称 |
| `client_manager` | `varchar(100)` | 可空 | — | 客户方负责人 |
| `manager_contact` | `varchar(100)` | 可空 | — | 负责人联系方式 |
| `field_level1` | `varchar(100)` | 可空 | — | 一级业务领域 |
| `field_level2` | `varchar(100)` | 可空 | — | 二级业务领域 |
| `country` | `varchar(50)` | 可空 | — | 国家 |
| `province` | `varchar(50)` | 可空 | — | 省/州 |
| `city` | `varchar(50)` | 可空 | — | 城市 |
| `district` | `varchar(50)` | 可空 | — | 区县 |
| `client_status` | `varchar(20)` | 可空 | `'pending'` | 客户状态 |
| `cooperation_start_date` | `timestamp` | 可空 | — | 合作开始时间 |
| `remarks` | `text` | 可空 | — | 备注 |
| `created_at` | `timestamp` | 可空 | `当前时间` | 创建时间 |
| `updated_at` | `timestamp` | 可空 | `当前时间` | 最后更新时间 |

### `client_contact`

客户拜访与跟进记录。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `client_id` | `uuid` | FK → client.id；可空 | — | 关联客户 |
| `client_code` | `varchar(50)` | 可空 | — | 客户编码 |
| `client_name` | `varchar(255)` | 可空 | — | 客户全称 |
| `client_short_name` | `varchar(100)` | 可空 | — | 客户简称 |
| `client_manager` | `varchar(100)` | 可空 | — | 客户方负责人 |
| `manager_contact` | `varchar(100)` | 可空 | — | 负责人联系方式 |
| `visit_count` | `integer` | 可空 | `0` | 拜访次数 |
| `visit_date` | `date` | 可空 | — | 拜访日期 |
| `visit_type` | `varchar(50)` | 可空 | — | 拜访方式 |
| `client_attitude` | `varchar(50)` | 可空 | — | 客户态度 |
| `description` | `text` | 可空 | — | 本次拜访/沟通说明 |
| `follow_up_count` | `integer` | 可空 | `0` | 跟进次数 |
| `follow_up_date` | `date` | 可空 | — | 跟进日期 |
| `follow_up_status` | `text` | 可空 | — | 跟进状态 |
| `remarks` | `text` | 可空 | — | 备注 |
| `created_at` | `timestamp` | 可空 | `当前时间` | 创建时间 |
| `updated_at` | `timestamp` | 可空 | `当前时间` | 最后更新时间 |

### `consultation`

售前咨询、来源及跟进过程。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `consultation_code` | `varchar(50)` | UQ；非空 | — | 咨询编号 |
| `client_id` | `uuid` | FK → client.id；可空 | — | 关联客户 |
| `sub_client_id` | `uuid` | FK → sub_client.id；可空 | — | 关联的 sub_client ID |
| `contact_name` | `varchar(255)` | 可空 | — | contact name |
| `customer_order_no` | `varchar(150)` | 可空 | — | customer order no |
| `project_name` | `varchar(500)` | 可空 | — | 项目名称 |
| `project_intake` | `jsonb` | 非空 | `'{}'` | project intake |
| `project_intake_version` | `integer` | 非空 | `1` | project intake version |
| `consultation_time` | `timestamp` | 可空 | — | 咨询时间 |
| `consultation_method` | `varchar(50)` | 可空 | — | 咨询方式 |
| `client_source` | `varchar(100)` | 可空 | — | 客户来源 |
| `source_keyword` | `varchar(255)` | 可空 | — | 来源关键词 |
| `consultation_description` | `text` | 可空 | — | 咨询内容描述 |
| `remarks` | `text` | 可空 | — | 备注 |
| `customer_service_id` | `uuid` | FK → app_user.id；可空 | — | 客服用户 |
| `sales_person_id` | `uuid` | FK → app_user.id；可空 | — | 销售用户 |
| `status` | `varchar(20)` | 可空 | `'pending'` | 咨询处理状态 |
| `consultation_type` | `varchar(50)` | 可空 | — | 咨询类型 |
| `handling_method` | `varchar(100)` | 可空 | — | 处理方式 |
| `editor_id` | `uuid` | FK → app_user.id；可空 | — | 编辑用户 |
| `follow_up_count` | `integer` | 可空 | `0` | 跟进次数 |
| `follow_up_time` | `timestamp` | 可空 | — | 最近/计划跟进时间 |
| `follow_up_status` | `varchar(20)` | 可空 | — | 跟进状态 |
| `follow_up_remarks` | `text` | 可空 | — | 跟进备注 |
| `follow_up_person_id` | `uuid` | FK → app_user.id；可空 | — | 跟进用户 |
| `created_at` | `timestamp` | 可空 | `当前时间` | 创建时间 |
| `updated_at` | `timestamp` | 可空 | `当前时间` | 最后更新时间 |

## 译员资源

### `translator`

译员资源、能力、联系方式及可用性档案。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `resource_person_id` | `uuid` | FK → resource_person.id；UQ；可空 | — | 关联的 resource_person ID |
| `translator_code` | `varchar(50)` | UQ；可空 | — | 译员编码 |
| `translator_name` | `varchar(255)` | 非空 | — | 译员姓名 |
| `cooperation_type` | `varchar(50)` | 可空 | — | 合作类型 |
| `contact_info` | `varchar(255)` | 可空 | — | 综合联系方式 |
| `translation_type` | `varchar(255)` | 可空 | — | 翻译类型/擅长类型 |
| `interpretation_level` | `varchar(20)` | 可空 | — | interpretation level |
| `quality_score` | `varchar(10)` | 可空 | — | 质量评分 |
| `direction` | `varchar(20)` | 可空 | — | 主要翻译方向 |
| `default_priority` | `integer` | 可空 | `0` | 默认资源优先级 |
| `schedule_remarks` | `text` | 可空 | — | 排班备注 |
| `languages` | `varchar(255)` | 可空 | — | 可承接语种 |
| `gender` | `varchar(10)` | 可空 | — | 性别 |
| `height` | `varchar(20)` | 可空 | — | 身高信息 |
| `appearance` | `varchar(100)` | 可空 | — | 形象描述 |
| `nationality` | `varchar(50)` | 可空 | — | 国籍 |
| `ethnicity` | `varchar(50)` | 可空 | — | 民族 |
| `phone` | `varchar(50)` | 可空 | — | 主要电话 |
| `phone2` | `varchar(50)` | 可空 | — | 备用电话 |
| `email1` | `varchar(100)` | 可空 | — | 主要邮箱 |
| `email2` | `varchar(100)` | 可空 | — | 备用邮箱 |
| `resume_path` | `varchar(500)` | 可空 | — | 简历文件路径 |
| `other_contact` | `varchar(255)` | 可空 | — | 其他联系方式 |
| `overdue_count` | `integer` | 可空 | `0` | 历史逾期次数 |
| `overall_rating` | `text` | 可空 | — | 综合评价 |
| `first_contact_date` | `timestamp` | 可空 | — | 首次沟通时间 |
| `remarks` | `text` | 可空 | — | 备注 |
| `status` | `varchar(20)` | 可空 | `'standby'` | 译员资源状态 |
| `available_time_slot` | `varchar(100)` | 可空 | — | 可用时间段 |
| `daily_accept_count` | `integer` | 可空 | — | 每日可接单数量 |
| `hourly_speed` | `integer` | 可空 | — | 每小时处理速度 |
| `daily_word_capacity` | `integer` | 可空 | — | 每日字数产能 |
| `can_cloud_edit` | `boolean` | 可空 | — | 是否可云端编辑 |
| `can_revision` | `boolean` | 可空 | — | 是否可修订 |
| `domain_skills` | `jsonb` | 可空 | `'[]'` | 领域技能列表 |
| `availability_updated_at` | `timestamp` | 可空 | — | 可用性最后更新时间 |
| `created_at` | `timestamp` | 可空 | `当前时间` | 创建时间 |
| `updated_at` | `timestamp` | 可空 | `当前时间` | 最后更新时间 |

### `translator_schedule`

译员按日的可用时段和剩余产能。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `translator_id` | `uuid` | FK → translator.id；组合 UQ；非空 | — | 关联译员 |
| `schedule_date` | `date` | 组合 UQ；非空 | — | 排班日期 |
| `availability_status` | `varchar(30)` | 非空 | `'available'` | availability status |
| `available_time_slot` | `varchar(100)` | 可空 | — | 可用时间段 |
| `remaining_capacity` | `integer` | 可空 | — | 当日剩余产能 |
| `source_type` | `varchar(30)` | 可空 | `'manual'` | 数据来源类型 |
| `source_ref` | `varchar(100)` | 可空 | — | 来源对象标识 |
| `last_confirmed_at` | `timestamp` | 可空 | — | 最近确认时间 |
| `remarks` | `text` | 可空 | — | 备注 |
| `created_at` | `timestamp` | 可空 | `当前时间` | 创建时间 |
| `updated_at` | `timestamp` | 可空 | `当前时间` | 最后更新时间 |

表级规则：组合唯一：`translator_id`, `schedule_date`。

## 项目与文件

### `translation_project`

翻译主订单及各生产阶段进度。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `order_no` | `varchar(50)` | UQ；非空 | — | 主订单号 |
| `project_name` | `varchar(255)` | 非空 | — | 项目名称 |
| `source_file_name` | `varchar(255)` | 可空 | — | 母订单对应的真实文件名称 |
| `task_type` | `varchar(50)` | 可空 | — | 任务类型 |
| `consultation_id` | `uuid` | FK → consultation.id；UQ；可空 | — | 关联的 consultation ID |
| `file_type_secondary` | `varchar(100)` | 可空 | — | 二级文件类型 |
| `project_contract_type` | `varchar(100)` | 可空 | — | project contract type |
| `project_contract_status` | `varchar(100)` | 可空 | — | project contract status |
| `quotation_required` | `boolean` | 非空 | `false` | quotation required |
| `quotation_status` | `varchar(100)` | 可空 | — | quotation status |
| `quotation_path` | `text` | 可空 | — | quotation path |
| `customer_requirement_professional` | `text` | 可空 | — | customer requirement professional |
| `customer_requirement_special` | `text` | 可空 | — | customer requirement special |
| `client_id` | `uuid` | FK → client.id；可空 | — | 关联客户 |
| `sub_client_id` | `uuid` | FK → sub_client.id；可空 | — | 关联的 sub_client ID |
| `customer_order_no` | `varchar(100)` | 可空 | — | customer order no |
| `email_subject_preview` | `text` | 可空 | — | email subject preview |
| `service_content` | `varchar(255)` | 可空 | — | service content |
| `customer_reception_time` | `timestamp` | 可空 | — | 客户稿件接收时间 |
| `customer_deadline_time` | `timestamp` | 可空 | — | 客户要求截止时间 |
| `sent_to_client_time` | `timestamp` | 可空 | — | 发送客户时间 |
| `client_feedback` | `text` | 可空 | — | 客户反馈 |
| `language_pair` | `varchar(500)` | 可空 | — | 语言对 |
| `priority` | `varchar(50)` | 可空 | — | 优先级 |
| `project_status` | `varchar(50)` | 可空 | — | 项目状态 |
| `project_manager_id` | `uuid` | FK → app_user.id；可空 | — | 关联的 project_manager ID |
| `pm_confirmed_by` | `uuid` | FK → app_user.id；可空 | — | 项目经理确认人 |
| `major_project_manager_confirmation` | `varchar(255)` | 可空 | — | 大项目经理确认信息 |
| `translator_id` | `uuid` | FK → translator.id；可空 | — | 关联译员 |
| `translator_assignment_time` | `timestamp` | 可空 | — | 译员分配时间 |
| `translator_delivery_progress` | `varchar(20)` | 可空 | — | 译员交付进度 |
| `pre_review_qc_progress` | `varchar(20)` | 可空 | — | 审校前质检进度 |
| `review1_progress` | `varchar(20)` | 可空 | — | 一审进度 |
| `review2_progress` | `varchar(20)` | 可空 | — | 二审进度 |
| `post_review_qc_progress` | `varchar(20)` | 可空 | — | 审校后质检进度 |
| `layout_progress` | `varchar(20)` | 可空 | — | 排版进度 |
| `consolidation_progress` | `varchar(20)` | 可空 | — | 整合进度 |
| `created_by` | `uuid` | FK → app_user.id；可空 | — | 创建用户 |
| `created_at` | `timestamp` | 可空 | `当前时间` | 创建时间 |
| `updated_at` | `timestamp` | 可空 | `当前时间` | 最后更新时间 |
| `annotation_project_id` | `uuid` | 可空 | — | 关联的 annotation_project ID |
| `annotation_migrated_at` | `timestamp` | 可空 | — | 业务时间 |
| `network_file_path` | `varchar(500)` | 可空 | — | 网络共享文件路径 |
| `reference_file_path_one` | `varchar(500)` | 可空 | — | reference file path one |

### `translation_sub_order`

主订单拆分后的子订单。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `parent_project_id` | `uuid` | FK → translation_project.id；非空 | — | 所属翻译主订单 |
| `sub_order_no` | `varchar(60)` | UQ；非空 | — | 子订单号 |
| `sub_project_name` | `varchar(255)` | 可空 | — | 子订单文件名称（兼容保留的历史字段名） |
| `file_type_secondary` | `varchar(100)` | 可空 | — | 二级文件类型 |
| `language_pair` | `varchar(500)` | 可空 | — | 语言对 |
| `priority` | `varchar(50)` | 可空 | — | 优先级 |
| `customer_deadline_time` | `timestamp` | 可空 | — | 客户要求截止时间 |
| `sent_to_client_time` | `timestamp` | 可空 | — | 发送客户时间 |
| `client_feedback` | `text` | 可空 | — | 客户反馈 |
| `translator_id` | `uuid` | FK → translator.id；可空 | — | 关联译员 |
| `translator_assignment_time` | `timestamp` | 可空 | — | 译员分配时间 |
| `status` | `varchar(50)` | 可空 | `'pending'` | 子订单状态 |
| `translator_delivery_progress` | `varchar(20)` | 可空 | — | 译员交付进度 |
| `pre_review_qc_progress` | `varchar(20)` | 可空 | — | 审校前质检进度 |
| `review_progress` | `varchar(20)` | 可空 | — | 综合审校进度 |
| `review1_progress` | `varchar(20)` | 可空 | — | 一审进度 |
| `review2_progress` | `varchar(20)` | 可空 | — | 二审进度 |
| `post_review_qc_progress` | `varchar(20)` | 可空 | — | 审校后质检进度 |
| `layout_progress` | `varchar(20)` | 可空 | — | 排版进度 |
| `consolidation_progress` | `varchar(20)` | 可空 | — | 整合进度 |
| `network_file_path` | `varchar(500)` | 可空 | — | 网络共享文件路径 |
| `remarks` | `text` | 可空 | — | 备注 |
| `created_by` | `uuid` | FK → app_user.id；可空 | — | 创建用户 |
| `created_at` | `timestamp` | 可空 | `当前时间` | 创建时间 |
| `updated_at` | `timestamp` | 可空 | `当前时间` | 最后更新时间 |

### `project_file`

项目文件及各生产环节路径。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `translation_project_id` | `uuid` | FK → translation_project.id；非空 | — | 关联翻译主订单 |
| `file_name` | `varchar(255)` | 非空 | — | 文件名 |
| `storage_path` | `text` | 非空 | — | 实际存储路径 |
| `dispatch_path` | `text` | 可空 | — | 派稿环节路径 |
| `translation_path` | `text` | 可空 | — | 翻译环节路径 |
| `translator_return_path` | `text` | 可空 | — | translator return path |
| `client_delivery_path` | `text` | 可空 | — | 客户交付路径 |
| `project_feedback_path` | `text` | 可空 | — | project feedback path |
| `feedback_delivery_path` | `text` | 可空 | — | feedback delivery path |
| `translation_domain_level1` | `varchar(255)` | 可空 | — | translation domain level1 |
| `translation_domain_level2` | `varchar(255)` | 可空 | — | translation domain level2 |
| `file_type` | `varchar(255)` | 可空 | — | 文件业务类型 |
| `file_type_secondary` | `varchar(255)` | 可空 | — | 二级文件类型 |
| `file_format` | `varchar(100)` | 可空 | — | file format |
| `file_attribute_level1` | `varchar(255)` | 可空 | — | file attribute level1 |
| `file_attribute_level2` | `varchar(255)` | 可空 | — | file attribute level2 |
| `file_attribute_level3` | `varchar(255)` | 可空 | — | file attribute level3 |
| `file_difficulty` | `varchar(100)` | 可空 | — | file difficulty |
| `file_ext` | `varchar(20)` | 可空 | — | 扩展名 |
| `file_size` | `bigint` | 可空 | — | 文件大小（字节） |
| `storage_type` | `varchar(50)` | 可空 | — | 存储介质/类型 |
| `uploaded_by` | `uuid` | FK → app_user.id；可空 | — | 上传用户 |
| `created_at` | `timestamp` | 可空 | `当前时间` | 创建时间 |

## 工作流与交接

### `workflow_instance`

主订单或子订单当前工作流状态。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `translation_project_id` | `uuid` | FK → translation_project.id；可空 | — | 关联翻译主订单 |
| `sub_order_id` | `uuid` | FK → translation_sub_order.id；可空 | — | 关联翻译子订单 |
| `difficulty` | `varchar(20)` | 可空 | — | 项目难度 |
| `file_editable` | `boolean` | 可空 | — | 文件是否可编辑 |
| `current_stage_key` | `varchar(50)` | 非空 | `'reception'` | 当前工作流阶段键 |
| `current_assignee_id` | `uuid` | FK → app_user.id；可空 | — | 当前处理人 |
| `group_assign_role` | `varchar(50)` | 可空 | — | 组内分配所需角色 |
| `project_status` | `varchar(30)` | 可空 | `'pending'` | 项目状态 |
| `stage_notes` | `jsonb` | 可空 | `'{}'` | 各阶段备注映射 |
| `stage_data` | `jsonb` | 可空 | `'{}'` | 各阶段扩展数据 |
| `created_at` | `timestamp` | 可空 | `当前时间` | 创建时间 |
| `updated_at` | `timestamp` | 可空 | `当前时间` | 最后更新时间 |

### `workflow_log`

工作流阶段流转审计日志。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `workflow_instance_id` | `uuid` | FK → workflow_instance.id；非空 | — | 关联工作流实例 |
| `operator_id` | `uuid` | FK → app_user.id；可空 | — | 操作用户 |
| `from_stage` | `varchar(50)` | 可空 | — | 流转前阶段 |
| `to_stage` | `varchar(50)` | 可空 | — | 流转后阶段 |
| `direction` | `varchar(20)` | 可空 | — | 工作流流转方向 |
| `description` | `text` | 可空 | — | 流转动作描述 |
| `note` | `text` | 可空 | — | 流转备注 |
| `next_assignee_id` | `uuid` | FK → app_user.id；可空 | — | 下一处理人 |
| `created_at` | `timestamp` | 可空 | `当前时间` | 创建时间 |

### `workflow_handover_request`

请假/离职等场景的工作交接申请。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `requester_id` | `uuid` | FK → app_user.id；可空 | — | 交接发起人 |
| `target_user_id` | `uuid` | FK → app_user.id；非空 | — | 交接目标用户 |
| `handover_type` | `varchar(30)` | 非空 | — | 交接类型 |
| `reason_detail` | `varchar(500)` | 可空 | — | 交接原因 |
| `content` | `text` | 非空 | `''` | 正文内容 |
| `content_json` | `jsonb` | 可空 | — | 结构化富文本内容 |
| `status` | `varchar(20)` | 非空 | `'pending'` | 交接审批状态 |
| `decision_note` | `varchar(500)` | 可空 | — | 审批说明 |
| `decided_by` | `uuid` | FK → app_user.id；可空 | — | 审批人 |
| `created_at` | `timestamp` | 可空 | `当前时间` | 创建时间 |
| `decided_at` | `timestamp` | 可空 | — | 审批时间 |

表级规则：索引 `ix_wf_handover_target_status`：`target_user_id`, `status`。

### `workflow_handover_item`

交接申请所包含的工作流实例。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `request_id` | `uuid` | FK → workflow_handover_request.id；组合 UQ；组合 UQ；非空 | — | 关联交接申请 |
| `workflow_instance_id` | `uuid` | FK → workflow_instance.id；组合 UQ；可空 | — | 关联工作流实例 |
| `project_responsibility_id` | `uuid` | FK → project_workbench_responsibility.id；组合 UQ；可空 | — | 关联的 project_responsibility ID |
| `expected_assignee_id` | `uuid` | FK → app_user.id；可空 | — | 交接时预期处理人 |

表级规则：组合唯一：`request_id`, `workflow_instance_id`；组合唯一：`request_id`, `project_responsibility_id`；CHECK：`workflow_instance_id IS NOT NULL AND project_responsibility_id IS NULL OR workflow_instance_id IS NULL AND project_responsibility_id IS NOT NULL`。

### `workflow_handover_attachment`

交接申请与聊天附件的关联。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `request_id` | `uuid` | FK → workflow_handover_request.id；组合 UQ；非空 | — | 关联交接申请 |
| `attachment_id` | `uuid` | FK → chat_project_attachment.id；组合 UQ；非空 | — | 关联聊天附件 |

表级规则：组合唯一：`request_id`, `attachment_id`。

## 协作与通知

### `chat_project_enabled`

项目群聊启用状态。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `project_id` | `uuid` | FK → translation_project.id；UQ；非空 | — | 关联翻译主订单 |
| `enabled` | `boolean` | 非空 | `false` | 项目群聊是否启用 |
| `enabled_by` | `uuid` | FK → app_user.id；可空 | — | 启用/停用操作人 |
| `enabled_at` | `timestamp` | 可空 | — | 启用时间 |
| `updated_at` | `timestamp` | 可空 | `当前时间` | 最后更新时间 |

### `chat_project_message`

项目群聊消息。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `project_id` | `uuid` | FK → translation_project.id；可空 | — | 关联翻译主订单 |
| `annotation_project_id` | `uuid` | FK → annotation_project.id；可空 | — | 关联标注项目 |
| `sender_user_id` | `uuid` | FK → app_user.id；可空 | — | 消息发送用户 |
| `sender_name` | `varchar(255)` | 非空 | — | 发送人姓名快照 |
| `content` | `text` | 非空 | — | 正文内容 |
| `message_type` | `varchar(30)` | 非空 | `'user'` | 消息类型 |
| `content_json` | `jsonb` | 可空 | — | 结构化富文本内容 |
| `metadata` | `jsonb` | 可空 | `'{}'` | 消息扩展元数据 |
| `created_at` | `timestamp` | 可空 | `当前时间` | 创建时间 |
| `updated_at` | `timestamp` | 可空 | `当前时间` | 最后更新时间 |

表级规则：`project_id` 与 `annotation_project_id` 必须且只能填写一个；索引 `ix_chat_project_message_project_created_at`：`project_id`, `created_at`；索引 `ix_chat_project_message_annotation_created_at`：`annotation_project_id`, `created_at`；索引 `ix_chat_project_message_sender_user_id`：`sender_user_id`。

### `chat_project_mention`

群聊消息中的用户提及。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `message_id` | `uuid` | FK → chat_project_message.id；组合 UQ；非空 | — | 关联聊天消息 |
| `mentioned_user_id` | `uuid` | FK → app_user.id；组合 UQ；非空 | — | 被提及用户 |
| `mentioned_user_name` | `varchar(255)` | 非空 | — | 被提及用户名快照 |
| `created_at` | `timestamp` | 可空 | `当前时间` | 创建时间 |

表级规则：组合唯一：`message_id`, `mentioned_user_id`；索引 `ix_chat_project_mention_user_id`：`mentioned_user_id`。

### `chat_project_attachment`

项目群聊上传的附件实体。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `uploaded_by` | `uuid` | FK → app_user.id；可空 | — | 上传用户 |
| `original_name` | `varchar(255)` | 非空 | — | 上传时原始文件名 |
| `storage_name` | `varchar(255)` | UQ；非空 | — | 存储系统中的唯一文件名 |
| `content_type` | `varchar(100)` | 非空 | — | MIME 类型 |
| `file_size` | `bigint` | 非空 | — | 文件大小（字节） |
| `created_at` | `timestamp` | 可空 | `当前时间` | 创建时间 |

表级规则：索引 `ix_chat_project_attachment_created_at`：`created_at`。

### `chat_project_message_attachment`

群聊消息与附件的多对多关联。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `message_id` | `uuid` | FK → chat_project_message.id；组合 UQ；非空 | — | 关联聊天消息 |
| `attachment_id` | `uuid` | FK → chat_project_attachment.id；组合 UQ；非空 | — | 关联聊天附件 |
| `created_at` | `timestamp` | 可空 | `当前时间` | 创建时间 |

表级规则：组合唯一：`message_id`, `attachment_id`；索引 `ix_chat_message_attachment_attachment_id`：`attachment_id`。

### `app_notification`

站内通知及已读状态。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `recipient_user_id` | `uuid` | FK → app_user.id；非空 | — | 通知接收用户 |
| `title` | `varchar(255)` | 非空 | — | 标题 |
| `content` | `text` | 非空 | — | 正文内容 |
| `notification_type` | `varchar(50)` | 非空 | `'workflow'` | 通知类型 |
| `is_read` | `boolean` | 非空 | `false` | 是否已读 |
| `read_at` | `timestamp` | 可空 | — | 阅读时间 |
| `related_project_id` | `uuid` | FK → translation_project.id；可空 | — | 通知关联的翻译主订单 |
| `related_project_type` | `varchar(30)` | 可空 | — | related project type |
| `related_entity_id` | `uuid` | 可空 | — | 关联的 related_entity ID |
| `created_at` | `timestamp` | 可空 | `当前时间` | 创建时间 |

## 财务

### `finance_record`

项目维度的报价、结算和开票信息。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `project_id` | `uuid` | FK → translation_project.id；UQ；非空 | — | 关联翻译主订单 |
| `sales_person_id` | `uuid` | FK → app_user.id；可空 | — | 销售用户 |
| `follow_up_person_id` | `uuid` | FK → app_user.id；可空 | — | 跟进用户 |
| `settlement_method` | `varchar(50)` | 可空 | — | 结算方式 |
| `unit_price_excl_tax` | `numeric(14, 2)` | 可空 | — | 未税单价 |
| `unit_price_incl_tax` | `numeric(14, 2)` | 可空 | — | 含税单价 |
| `total_excl_tax` | `numeric(14, 2)` | 可空 | — | 未税总额 |
| `total_incl_tax` | `numeric(14, 2)` | 可空 | — | 含税总额 |
| `invoice_status` | `varchar(20)` | 非空 | `'unissued'` | 开票状态 |
| `remarks` | `text` | 可空 | — | 备注 |
| `edited_by` | `uuid` | FK → app_user.id；可空 | — | edited by |
| `created_at` | `timestamp` | 可空 | `当前时间` | 创建时间 |
| `updated_at` | `timestamp` | 可空 | `当前时间` | 最后更新时间 |

### `finance_payment`

财务记录的定金/中期款/尾款明细。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `finance_id` | `uuid` | FK → finance_record.id；组合 UQ；非空 | — | 关联财务记录 |
| `stage_type` | `varchar(20)` | 组合 UQ；非空 | — | 款项阶段：定金/中期/尾款 |
| `stage_no` | `integer` | 组合 UQ；非空 | `1` | 同阶段序号 |
| `planned_amount` | `numeric(14, 2)` | 可空 | — | 计划收款金额 |
| `actual_amount` | `numeric(14, 2)` | 可空 | — | 实际收款金额 |
| `payment_time` | `timestamp` | 可空 | — | 收款时间 |
| `payment_method` | `varchar(50)` | 可空 | — | 收款方式 |
| `confirmed_by` | `uuid` | FK → app_user.id；可空 | — | 收款确认人 |
| `confirmed_at` | `timestamp` | 可空 | — | 确认时间 |
| `created_at` | `timestamp` | 可空 | `当前时间` | 创建时间 |
| `updated_at` | `timestamp` | 可空 | `当前时间` | 最后更新时间 |

表级规则：组合唯一：`finance_id`, `stage_type`, `stage_no`。

## 任务与日报

### `non_project_task_recurrence`

非项目周期任务模板。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `task_type` | `varchar(50)` | 非空 | — | 任务类型 |
| `task_name` | `varchar(255)` | 非空 | — | 任务名称 |
| `assigner_id` | `uuid` | FK → app_user.id；非空 | — | 任务分配人 |
| `assignee_id` | `uuid` | FK → app_user.id；非空 | — | 任务执行人 |
| `frequency` | `varchar(20)` | 非空 | — | 重复频率 |
| `weekdays` | `jsonb` | 可空 | — | 每周执行日列表 |
| `month_day` | `integer` | 可空 | — | 每月执行日 |
| `default_due_time` | `time` | 可空 | — | 默认截止时刻 |
| `start_date` | `date` | 非空 | — | 开始日期 |
| `end_date` | `date` | 可空 | — | 结束日期 |
| `remark` | `text` | 可空 | — | remark |
| `is_active` | `boolean` | 非空 | `true` | 账号是否启用 |
| `created_at` | `timestamp` | 非空 | `当前时间` | 创建时间 |
| `updated_at` | `timestamp` | 非空 | `当前时间` | 最后更新时间 |

表级规则：CHECK：`frequency::text = ANY (ARRAY['daily'::character varying, 'workday'::character varying, 'weekly'::character varying, 'monthly'::character varying]::text[])`。

### `non_project_task`

一次性的或周期生成的非项目任务。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `task_type` | `varchar(50)` | 非空 | — | 任务类型 |
| `task_name` | `varchar(255)` | 非空 | — | 任务名称 |
| `assigner_id` | `uuid` | FK → app_user.id；非空 | — | 任务分配人 |
| `assignee_id` | `uuid` | FK → app_user.id；非空 | — | 任务执行人 |
| `assigned_at` | `timestamp` | 非空 | `当前时间` | 分配时间 |
| `planned_completion_at` | `timestamp` | 可空 | — | 计划完成时间 |
| `actual_completion_at` | `timestamp` | 可空 | — | 实际完成时间 |
| `status` | `varchar(20)` | 非空 | `'pending'` | 任务状态 |
| `remark` | `text` | 可空 | — | remark |
| `recurrence_template_id` | `uuid` | FK → non_project_task_recurrence.id；组合 UQ；可空 | — | 来源周期模板 |
| `occurrence_date` | `date` | 组合 UQ；可空 | — | 周期任务发生日期 |
| `source_key` | `varchar(128)` | UQ；可空 | — | 外部/生成来源幂等键 |
| `created_at` | `timestamp` | 非空 | `当前时间` | 创建时间 |
| `updated_at` | `timestamp` | 非空 | `当前时间` | 最后更新时间 |

表级规则：组合唯一：`recurrence_template_id`, `occurrence_date`；CHECK：`status::text = ANY (ARRAY['pending'::character varying, 'in_progress'::character varying, 'completed'::character varying, 'cancelled'::character varying]::text[])`；索引 `ix_non_project_task_assignee_status`：`assignee_id`, `status`；索引 `ix_non_project_task_planned_completion`：`planned_completion_at`。

### `non_project_task_event`

非项目任务状态变更事件。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `task_id` | `uuid` | FK → non_project_task.id；非空 | — | 关联任务 |
| `operator_id` | `uuid` | FK → app_user.id；可空 | — | 操作用户 |
| `event_type` | `varchar(30)` | 非空 | — | 事件类型 |
| `from_status` | `varchar(20)` | 可空 | — | 变更前状态 |
| `to_status` | `varchar(20)` | 可空 | — | 变更后状态 |
| `detail` | `jsonb` | 可空 | — | 事件扩展详情 |
| `created_at` | `timestamp` | 非空 | `当前时间` | 创建时间 |

表级规则：索引 `ix_non_project_task_event_task_created`：`task_id`, `created_at`。

### `work_entry`

用户每日项目/非项目工作投入记录。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `user_id` | `uuid` | FK → app_user.id；非空 | — | 关联用户 |
| `work_date` | `date` | 非空 | — | 工作日期 |
| `workflow_instance_id` | `uuid` | FK → workflow_instance.id；可空 | — | 关联工作流实例 |
| `project_responsibility_id` | `uuid` | FK → project_workbench_responsibility.id；可空 | — | 关联的 project_responsibility ID |
| `non_project_task_id` | `uuid` | FK → non_project_task.id；可空 | — | 关联非项目任务 |
| `progress_content` | `text` | 非空 | — | 工作进展内容 |
| `duration_minutes` | `integer` | 非空 | `0` | 投入时长（分钟） |
| `result_content` | `text` | 可空 | — | 工作结果 |
| `created_at` | `timestamp` | 非空 | `当前时间` | 创建时间 |
| `updated_at` | `timestamp` | 非空 | `当前时间` | 最后更新时间 |

表级规则：CHECK：`duration_minutes >= 0`；CHECK：`( CASE     WHEN workflow_instance_id IS NOT NULL THEN 1     ELSE 0 END + CASE     WHEN project_responsibility_id IS NOT NULL THEN 1     ELSE 0 END + CASE     WHEN non_project_task_id IS NOT NULL THEN 1     ELSE 0 END) = 1`；索引 `ix_work_entry_user_date`：`user_id`, `work_date`。

### `daily_report`

用户日清日报头及定稿状态。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `user_id` | `uuid` | FK → app_user.id；组合 UQ；非空 | — | 关联用户 |
| `report_date` | `date` | 组合 UQ；非空 | — | 日报日期 |
| `status` | `varchar(20)` | 非空 | `'draft'` | 日报状态：草稿/已定稿 |
| `supplemental_note` | `text` | 可空 | — | 日报补充说明 |
| `generated_at` | `timestamp` | 非空 | `当前时间` | 日报生成时间 |
| `finalized_at` | `timestamp` | 可空 | — | 日报定稿时间 |
| `created_at` | `timestamp` | 非空 | `当前时间` | 创建时间 |
| `updated_at` | `timestamp` | 非空 | `当前时间` | 最后更新时间 |

表级规则：组合唯一：`user_id`, `report_date`；CHECK：`status::text = ANY (ARRAY['draft'::character varying, 'finalized'::character varying]::text[])`；索引 `ix_daily_report_user_date`：`user_id`, `report_date`。

### `daily_report_item`

日报中的工作条目快照。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `report_id` | `uuid` | FK → daily_report.id；非空 | — | 关联日报 |
| `source_type` | `varchar(20)` | 非空 | — | 数据来源类型 |
| `source_id` | `uuid` | 可空 | — | 来源业务对象 ID |
| `task_type` | `varchar(50)` | 非空 | — | 任务类型 |
| `task_name` | `varchar(255)` | 非空 | — | 任务名称 |
| `progress_content` | `text` | 非空 | — | 工作进展内容 |
| `result_content` | `text` | 可空 | — | 工作结果 |
| `duration_minutes` | `integer` | 非空 | `0` | 投入时长（分钟） |
| `display_metadata` | `jsonb` | 可空 | — | 展示所需扩展快照 |
| `sort_order` | `integer` | 非空 | — | 显示顺序 |
| `created_at` | `timestamp` | 非空 | `当前时间` | 创建时间 |

表级规则：CHECK：`source_type::text = ANY (ARRAY['project'::character varying, 'non_project'::character varying, 'manual'::character varying]::text[])`。

## 排班与请假

### `work_schedule`

部门每日排班快照及紧急任务表。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `schedule_date` | `date` | UQ；非空 | — | 排班日期 |
| `shift_table` | `jsonb` | 可空 | `'[]'` | 值班表 JSON 快照 |
| `leave_notes` | `jsonb` | 可空 | `'[]'` | 请假信息 JSON 快照 |
| `urgent_table_zh_en` | `jsonb` | 可空 | `'[]'` | 中译英紧急任务表 |
| `urgent_table_en_zh` | `jsonb` | 可空 | `'[]'` | 英译中紧急任务表 |
| `dept_person_data` | `jsonb` | 可空 | `'[]'` | 部门人员数据快照 |
| `not_scheduled_tasks` | `jsonb` | 可空 | `'[]'` | 未排期任务快照 |
| `pm_rotation_order` | `varchar(500)` | 可空 | — | 项目经理轮值顺序 |
| `updated_by` | `uuid` | 可空 | — | 最后更新用户；当前无数据库外键 |
| `created_at` | `timestamp` | 可空 | `当前时间` | 创建时间 |
| `updated_at` | `timestamp` | 可空 | `当前时间` | 最后更新时间 |

### `employee_leave`

员工请假区间记录。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `employee_id` | `uuid` | FK → app_user.id；非空 | — | 员工 UUID；当前无数据库外键 |
| `employee_name` | `varchar(100)` | 非空 | — | 员工姓名快照 |
| `start_date` | `timestamp` | 非空 | — | 开始日期 |
| `end_date` | `timestamp` | 非空 | — | 结束日期 |
| `leave_type` | `varchar(50)` | 可空 | — | 请假类型 |
| `reason` | `varchar(500)` | 可空 | — | 请假原因 |
| `created_by` | `uuid` | FK → app_user.id；可空 | — | 创建用户 |
| `updated_by` | `uuid` | FK → app_user.id；可空 | — | 最后更新用户；当前无数据库外键 |
| `created_at` | `timestamp` | 可空 | `当前时间` | 创建时间 |
| `updated_at` | `timestamp` | 可空 | `当前时间` | 最后更新时间 |

表级规则：索引 `ix_employee_leave_employee_time`：`employee_id`, `start_date`, `end_date`。

## 稿件安排

### `manuscript_dispatch`

一次主订单/子订单稿件派发批次。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `entity_type` | `varchar(20)` | 非空 | — | 业务实体类型：主订单或子订单 |
| `translation_project_id` | `uuid` | FK → translation_project.id；非空 | — | 关联翻译主订单 |
| `sub_order_id` | `uuid` | FK → translation_sub_order.id；可空 | — | 关联翻译子订单 |
| `order_no_snapshot` | `varchar(80)` | 非空 | — | 派发时订单号快照 |
| `project_name_snapshot` | `varchar(255)` | 非空 | — | 派发时项目名称快照 |
| `status` | `varchar(20)` | 非空 | `'draft'` | 派发批次状态 |
| `remarks` | `text` | 可空 | — | 派发批次备注 |
| `created_by` | `uuid` | FK → app_user.id；可空 | — | 创建用户 |
| `created_by_name` | `varchar(255)` | 可空 | — | 创建人姓名快照 |
| `created_at` | `timestamp` | 非空 | `当前时间` | 创建时间 |
| `updated_at` | `timestamp` | 非空 | `当前时间` | 最后更新时间 |
| `confirmed_at` | `timestamp` | 可空 | — | 确认时间 |
| `cancelled_at` | `timestamp` | 可空 | — | 取消时间 |
| `previous_order_status` | `varchar(50)` | 可空 | — | previous order status |

表级规则：CHECK：`entity_type::text = 'project'::text AND sub_order_id IS NULL OR entity_type::text = 'suborder'::text AND sub_order_id IS NOT NULL`；CHECK：`status::text = ANY (ARRAY['draft'::character varying, 'ready'::character varying, 'partially_sent'::character varying, 'sent'::character varying, 'cancelled'::character varying]::text[])`；索引 `ix_manuscript_dispatch_order_created`：`order_no_snapshot`, `created_at`；索引 `ix_manuscript_dispatch_project_status`：`translation_project_id`, `status`。

### `manuscript_arrangement`

派发批次内针对译员的稿件安排与邮件结果。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `dispatch_id` | `uuid` | FK → manuscript_dispatch.id；组合 UQ；可空 | — | 所属派发批次 |
| `entity_type` | `varchar(20)` | 非空 | — | 业务实体类型：主订单或子订单 |
| `translation_project_id` | `uuid` | FK → translation_project.id；非空 | — | 关联翻译主订单 |
| `sub_order_id` | `uuid` | FK → translation_sub_order.id；可空 | — | 关联翻译子订单 |
| `translator_id` | `uuid` | FK → translator.id；组合 UQ；非空 | — | 关联译员 |
| `order_no_snapshot` | `varchar(80)` | 非空 | — | 派发时订单号快照 |
| `project_name_snapshot` | `varchar(255)` | 非空 | — | 派发时项目名称快照 |
| `translator_name_snapshot` | `varchar(255)` | 非空 | — | 派发时译员姓名快照 |
| `cooperation_type_snapshot` | `varchar(50)` | 可空 | — | 派发时合作类型快照 |
| `recipient_email` | `varchar(255)` | 可空 | — | 译员收件邮箱 |
| `translation_scope` | `text` | 可空 | — | 翻译范围说明 |
| `settlement_method` | `varchar(100)` | 可空 | — | 结算方式 |
| `custom_settlement_method` | `varchar(100)` | 可空 | — | 自定义结算方式 |
| `translator_unit_price` | `numeric(14, 4)` | 可空 | — | 译员单价 |
| `translator_total_price` | `numeric(14, 2)` | 可空 | — | 译员总价 |
| `planned_delivery_at` | `timestamp` | 可空 | — | 计划交付时间 |
| `manuscript_source_path` | `text` | 可空 | — | 稿件源文件路径 |
| `email_subject` | `varchar(500)` | 可空 | — | 派稿邮件主题 |
| `email_body` | `text` | 可空 | — | 派稿邮件正文 |
| `remarks` | `text` | 可空 | — | 单个译员安排备注 |
| `status` | `varchar(20)` | 非空 | `'draft'` | 单个译员安排/邮件状态 |
| `created_by` | `uuid` | FK → app_user.id；可空 | — | 创建用户 |
| `created_by_name` | `varchar(255)` | 可空 | — | 创建人姓名快照 |
| `created_at` | `timestamp` | 非空 | `当前时间` | 创建时间 |
| `updated_at` | `timestamp` | 非空 | `当前时间` | 最后更新时间 |
| `send_attempted_at` | `timestamp` | 可空 | — | 最近发送尝试时间 |
| `sent_at` | `timestamp` | 可空 | — | 邮件发送成功时间 |
| `delivery_recipient` | `varchar(255)` | 可空 | — | 实际投递收件人 |
| `delivery_mode` | `varchar(20)` | 可空 | — | 投递模式：测试/正式等 |
| `smtp_message_id` | `varchar(255)` | 可空 | — | SMTP 服务返回的消息 ID |
| `send_error` | `text` | 可空 | — | 最近发送错误 |

表级规则：组合唯一：`dispatch_id`, `translator_id`；CHECK：`entity_type::text = ANY (ARRAY['project'::character varying, 'suborder'::character varying]::text[])`；CHECK：`status::text = ANY (ARRAY['draft'::character varying, 'ready'::character varying, 'sent'::character varying, 'failed'::character varying, 'cancelled'::character varying]::text[])`；索引 `ix_manuscript_arrangement_project_status`：`translation_project_id`, `status`；索引 `ix_manuscript_arrangement_translator_status`：`translator_id`, `status`。

### `manuscript_delivery_milestone`

稿件安排的阶段性/最终交付节点。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `arrangement_id` | `uuid` | FK → manuscript_arrangement.id；组合 UQ；非空 | — | 关联稿件安排 |
| `milestone_type` | `varchar(20)` | 非空 | — | 节点类型：阶段/最终 |
| `name` | `varchar(100)` | 非空 | — | 节点名称 |
| `sequence_no` | `integer` | 组合 UQ；非空 | — | 节点顺序号 |
| `planned_at` | `timestamp` | 可空 | — | 计划节点时间 |
| `created_at` | `timestamp` | 非空 | `当前时间` | 创建时间 |
| `updated_at` | `timestamp` | 非空 | `当前时间` | 最后更新时间 |

表级规则：组合唯一：`arrangement_id`, `sequence_no`；CHECK：`sequence_no >= 1`；CHECK：`milestone_type::text = ANY (ARRAY['phase'::character varying, 'final'::character varying]::text[])`；索引 `ix_manuscript_milestone_planned_at`：`planned_at`。

## 标注运营

### `annotation_project`

业务数据表。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `order_no` | `varchar(50)` | UQ；非空 | — | 主订单号 |
| `project_name` | `varchar(500)` | 可空 | — | 项目名称 |
| `project_types` | `jsonb` | 非空 | `'[]'` | project types |
| `task_description` | `text` | 可空 | — | task description |
| `consultation_id` | `uuid` | FK → consultation.id；UQ；可空 | — | 关联的 consultation ID |
| `client_id` | `uuid` | FK → client.id；可空 | — | 关联客户 |
| `sub_client_id` | `uuid` | FK → sub_client.id；可空 | — | 关联的 sub_client ID |
| `contact_name` | `varchar(255)` | 可空 | — | contact name |
| `customer_order_no` | `varchar(150)` | 可空 | — | customer order no |
| `email_subject_preview` | `varchar(1000)` | 可空 | — | email subject preview |
| `project_status` | `varchar(50)` | 非空 | `'initial_consultation'` | 项目状态 |
| `language_region` | `varchar(255)` | 可空 | — | language region |
| `status_effective_on` | `date` | 非空 | `CURRENT_DATE` | status effective on |
| `custom_values` | `jsonb` | 非空 | `'{}'` | custom values |
| `potential_demand` | `text` | 可空 | — | potential demand |
| `project_path` | `text` | 可空 | — | project path |
| `quotation_path` | `text` | 可空 | — | quotation path |
| `contract_path` | `text` | 可空 | — | contract path |
| `task_dispatched_at` | `timestamp` | 可空 | — | 业务时间 |
| `task_submitted_at` | `timestamp` | 可空 | — | 业务时间 |
| `client_manager_id` | `uuid` | FK → app_user.id；可空 | — | 关联的 client_manager ID |
| `customer_consultation_time` | `timestamp` | 可空 | — | customer consultation time |
| `customer_confirmation_time` | `timestamp` | 可空 | — | customer confirmation time |
| `legacy_translation_project_id` | `uuid` | FK → translation_project.id；UQ；可空 | — | 关联的 legacy_translation_project ID |
| `legacy_order_no` | `varchar(50)` | 可空 | — | legacy order no |
| `legacy_status` | `varchar(50)` | 可空 | — | legacy status |
| `created_by` | `uuid` | FK → app_user.id；可空 | — | 创建用户 |
| `created_at` | `timestamp` | 非空 | `当前时间` | 创建时间 |
| `updated_at` | `timestamp` | 非空 | `当前时间` | 最后更新时间 |

表级规则：CHECK：`project_status::text = ANY (ARRAY['initial_consultation'::character varying, 'consultation_no_result'::character varying, 'resource_sourcing'::character varying, 'resource_sourcing_cancelled'::character varying, 'trial_preparation'::character varying, 'trial_in_progress'::character varying, 'trial_passed'::character varying, 'trial_failed'::character varying, 'trial_partially_passed'::character varying, 'project_in_progress'::character varying, 'sent_to_client'::character varying, 'client_feedback'::character varying, 'cancelled'::character varying, 'partially_cancelled'::character varying]::text[])`；CHECK：`task_submitted_at IS NULL OR task_dispatched_at IS NULL OR task_submitted_at >= task_dispatched_at`；索引 `ix_annotation_project_client`：`client_id`；索引 `ix_annotation_project_client_manager`：`client_manager_id`；索引 `ix_annotation_project_created_at`：`created_at`；索引 `ix_annotation_project_status`：`project_status`。

### `annotation_project_language_item`

业务数据表。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `project_id` | `uuid` | FK → annotation_project.id；组合 UQ；非空 | — | 关联翻译主订单 |
| `sequence_no` | `integer` | 组合 UQ；非空 | — | 节点顺序号 |
| `source_language_id` | `uuid` | FK → interpretation_language.id；非空 | — | 关联的 source_language ID |
| `target_language_id` | `uuid` | FK → interpretation_language.id；可空 | — | 关联的 target_language ID |

表级规则：组合唯一：`project_id`, `sequence_no`；CHECK：`target_language_id IS NULL OR source_language_id <> target_language_id`。

### `annotation_project_price_item`

业务数据表。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `project_id` | `uuid` | FK → annotation_project.id；组合 UQ；非空 | — | 关联翻译主订单 |
| `sequence_no` | `integer` | 组合 UQ；非空 | — | 节点顺序号 |
| `project_type` | `varchar(50)` | 可空 | — | project type |
| `source_language_id` | `uuid` | FK → interpretation_language.id；可空 | — | 关联的 source_language ID |
| `target_language_id` | `uuid` | FK → interpretation_language.id；可空 | — | 关联的 target_language ID |
| `amount` | `numeric(18, 6)` | 非空 | — | amount |
| `currency` | `varchar(3)` | 可空 | — | currency |
| `unit` | `varchar(50)` | 非空 | — | unit |
| `remarks` | `text` | 可空 | — | 备注 |

表级规则：组合唯一：`project_id`, `sequence_no`；CHECK：`amount > 0::numeric`；CHECK：`target_language_id IS NULL OR source_language_id IS NOT NULL`。

### `annotation_project_assignee`

业务数据表。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `project_id` | `uuid` | FK → annotation_project.id；组合 UQ；非空 | — | 关联翻译主订单 |
| `person_id` | `uuid` | FK → resource_person.id；非空 | — | 关联的 person ID |
| `sequence_no` | `integer` | 组合 UQ；非空 | — | 节点顺序号 |
| `assignment_status` | `varchar(30)` | 非空 | `'assigned'` | assignment status |
| `quality_score` | `varchar(50)` | 可空 | — | 质量评分 |
| `evaluation_note` | `text` | 可空 | — | evaluation note |
| `assignment_role` | `varchar(30)` | 非空 | `'annotator'` | assignment role |
| `language_item_id` | `uuid` | FK → annotation_project_language_item.id；可空 | — | 关联的 language_item ID |
| `audio_duration_value` | `numeric(18, 3)` | 可空 | — | audio duration value |
| `audio_duration_unit` | `varchar(20)` | 可空 | — | audio duration unit |
| `custom_values` | `jsonb` | 非空 | `'{}'` | custom values |
| `created_at` | `timestamp` | 非空 | `当前时间` | 创建时间 |
| `updated_at` | `timestamp` | 非空 | `当前时间` | 最后更新时间 |

表级规则：组合唯一：`project_id`, `sequence_no`；CHECK：`audio_duration_unit IS NULL OR (audio_duration_unit::text = ANY (ARRAY['second'::character varying, 'minute'::character varying, 'hour'::character varying]::text[]))`；CHECK：`audio_duration_value IS NULL OR audio_duration_value >= 0::numeric`；CHECK：`assignment_role::text = ANY (ARRAY['annotator'::character varying, 'quality_inspector'::character varying]::text[])`；索引 `ix_annotation_assignee_person`：`person_id`；唯一索引 `uq_annotation_project_assignee_scope`：`project_id`, `person_id`, `language_item_id`, `assignment_role`。

### `annotation_project_status_history`

标注项目状态实际生效日期与变更履历。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `project_id` | `uuid` | FK → annotation_project.id；非空 | — | 关联翻译主订单 |
| `from_status` | `varchar(50)` | 可空 | — | 变更前状态 |
| `to_status` | `varchar(50)` | 非空 | — | 变更后状态 |
| `effective_on` | `timestamp` | 非空 | — | 进度节点或状态实际生效时间 |
| `changed_at` | `timestamp` | 非空 | `当前时间` | 系统实际填写时间 |
| `changed_by` | `uuid` | FK → app_user.id；可空 | — | changed by |
| `change_note` | `text` | 可空 | — | change note |

表级规则：`from_status` 和 `to_status` 使用标注项目状态枚举 CHECK；索引 `ix_annotation_status_history_status_date`：`to_status`, `effective_on`；索引 `ix_annotation_status_history_timeline`：`project_id`, `effective_on DESC`, `changed_at DESC`；索引 `ix_annotation_status_history_effective_search`：`effective_on DESC`, `changed_at DESC`, `id DESC`；GIN trigram 索引 `ix_annotation_status_history_change_note_trgm`：非空 `change_note`，用于项目进度正文包含检索。

### `annotation_platform`

客户级标注平台资产。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `client_id` | `uuid` | FK → client.id；可空 | — | 关联客户 |
| `sub_client_id` | `uuid` | FK → sub_client.id；可空 | — | 关联子客户 |
| `origin_project_id` | `uuid` | FK → annotation_project.id；可空 | — | 首次登记来源项目 |
| `platform_name` | `varchar(150)` | 可空 | — | 平台名称 |
| `platform_url` | `text` | 非空 | — | 平台链接 |
| `platform_url_normalized` | `text` | 组合 UQ；非空 | — | 规范化链接 |
| `login_notes` | `text` | 可空 | — | 登录和二次验证说明 |
| `is_active` | `boolean` | 非空 | `true` | 是否启用 |
| `sequence_no` | `integer` | 组合 UQ；非空 | — | 客户内顺序 |
| `created_by` | `uuid` | FK → app_user.id；可空 | — | 创建用户 |
| `created_at` | `timestamp` | 非空 | `当前时间` | 创建时间 |
| `updated_at` | `timestamp` | 非空 | `当前时间` | 最后更新时间 |

表级规则：组合唯一：`client_id`, `sequence_no`；唯一索引 `uq_annotation_platform_client_url`：`client_id`, `platform_url_normalized`（NULLS NOT DISTINCT）；索引 `ix_annotation_platform_normalized_url`：`platform_url_normalized`。

### `annotation_platform_account`

标注平台账号资产；登录账号和密码按业务约定明文存储。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `platform_id` | `uuid` | FK → annotation_platform.id；组合 UQ；非空 | — | 关联平台 |
| `parent_account_id` | `uuid` | FK → annotation_platform_account.id；可空 | — | 备用账号的主账号 |
| `nickname` | `varchar(255)` | 可空 | — | 账号昵称 |
| `login_account` | `text` | 可空 | — | 登录账号明文 |
| `login_account_normalized` | `text` | 组合 UQ；可空 | — | 平台内查重的规范化账号 |
| `password` | `text` | 可空 | — | 登录密码明文 |
| `account_status` | `varchar(20)` | 非空 | `'available'` | 账号状态 |
| `registration_status` | `varchar(30)` | 非空 | `'unregistered'` | 注册状态 |
| `account_source` | `varchar(30)` | 非空 | `'client_provided'` | 账号来源 |
| `expires_on` | `date` | 可空 | — | 到期日 |
| `remarks` | `text` | 可空 | — | 备注 |
| `custom_values` | `jsonb` | 非空 | `'{}'` | 全局账号动态字段值 |
| `sequence_no` | `integer` | 组合 UQ；非空 | — | 平台内顺序 |
| `password_updated_at` | `timestamp` | 可空 | — | 当前密码更新时间 |
| `created_by` | `uuid` | FK → app_user.id；可空 | — | 创建用户 |
| `created_at` | `timestamp` | 非空 | `当前时间` | 创建时间 |
| `updated_at` | `timestamp` | 非空 | `当前时间` | 最后更新时间 |

表级规则：组合唯一：`platform_id`, `login_account_normalized`；组合唯一：`platform_id`, `sequence_no`；已注册账号必须同时存在账号和密码；账号状态、注册状态和来源均受 CHECK 约束。

### `annotation_account_assignment`

账号与标注员、项目的分配履历。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `account_id` | `uuid` | FK → annotation_platform_account.id；非空 | — | 账号资产 |
| `person_id` | `uuid` | FK → resource_person.id；非空 | — | 标注员 |
| `project_id` | `uuid` | FK → annotation_project.id；可空 | — | 使用项目 |
| `assigned_on` | `date` | 非空 | `CURRENT_DATE` | 分配日期 |
| `released_on` | `date` | 可空 | — | 释放日期 |
| `release_reason` | `varchar(30)` | 可空 | — | 释放原因 |
| `assignment_note` | `text` | 可空 | — | 分配说明 |
| `custom_values` | `jsonb` | 非空 | `'{}'` | 项目账号动态字段值，释放后随履历保留 |
| `assigned_by` | `uuid` | FK → app_user.id；可空 | — | 分配操作人 |
| `created_at` | `timestamp` | 非空 | `当前时间` | 创建时间 |
| `updated_at` | `timestamp` | 非空 | `当前时间` | 最后更新时间 |

表级规则：释放日期不得早于分配日期；唯一索引 `uq_annotation_assignment_active`：`account_id`（仅 `released_on IS NULL`）。

### `annotation_account_assignment_language`

账号分配所覆盖的项目语种。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `assignment_id` | `uuid` | PK；FK → annotation_account_assignment.id；非空 | — | 账号分配 |
| `language_item_id` | `uuid` | PK；FK → annotation_project_language_item.id；非空 | — | 项目语种 |

### `annotation_custom_field_image`

项目账号动态图片字段的受控文件元数据；原文件保存在 `ANNOTATION_CUSTOM_FIELD_IMAGE_DIR`。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | 图片 UUID |
| `project_id` | `uuid` | FK → annotation_project.id；非空 | — | 所属项目 |
| `field_definition_id` | `uuid` | FK → annotation_custom_field_definition.id；非空 | — | 图片动态字段 |
| `uploaded_by` | `uuid` | FK → app_user.id；可空 | — | 上传用户 |
| `original_name` | `varchar(255)` | 非空 | — | 原始文件名 |
| `storage_name` | `varchar(255)` | UQ；非空 | — | 服务端随机文件名 |
| `content_type` | `varchar(100)` | 非空 | — | 已校验 MIME |
| `file_size` | `bigint` | 非空 | — | 文件字节数 |
| `created_at` | `timestamp` | 非空 | `当前时间` | 上传时间 |

### `annotation_account_assignment_image`

项目账号分配、动态字段与图片的关联；同一分配的同一字段最多一张图片，释放后的分配仍保留关联。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | 关联 UUID |
| `assignment_id` | `uuid` | FK → annotation_account_assignment.id；非空 | — | 账号分配履历 |
| `field_definition_id` | `uuid` | FK → annotation_custom_field_definition.id；非空 | — | 图片动态字段 |
| `image_id` | `uuid` | FK → annotation_custom_field_image.id；非空 | — | 图片资源 |
| `created_at` | `timestamp` | 非空 | `当前时间` | 关联时间 |

表级规则：组合唯一：`assignment_id`, `field_definition_id`。

### `annotation_account_password_history`

账号历史密码明文及修改履历。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `account_id` | `uuid` | FK → annotation_platform_account.id；非空 | — | 账号资产 |
| `password` | `text` | 非空 | — | 历史密码明文 |
| `effective_from` | `timestamp` | 非空 | — | 原生效时间 |
| `replaced_at` | `timestamp` | 非空 | `当前时间` | 替换时间 |
| `changed_by` | `uuid` | FK → app_user.id；可空 | — | 修改用户 |

### `annotation_credential_access_log`

账号明文凭据查看审计。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `account_id` | `uuid` | FK → annotation_platform_account.id；非空 | — | 账号资产 |
| `user_id` | `uuid` | FK → app_user.id；可空 | — | 查看用户 |
| `accessed_at` | `timestamp` | 非空 | `当前时间` | 查看时间 |
| `access_reason` | `text` | 可空 | — | 查看原因 |
| `client_ip` | `varchar(64)` | 可空 | — | 客户端 IP |

### `annotation_trial_record`

标注员分轮次试标过程与结果。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `project_id` | `uuid` | FK → annotation_project.id；组合 UQ；组合 UQ；非空 | — | 关联翻译主订单 |
| `person_id` | `uuid` | FK → resource_person.id；组合 UQ；非空 | — | 关联的 person ID |
| `platform_account_id` | `uuid` | FK → annotation_platform_account.id；可空 | — | 试标使用的账号资产 |
| `round_no` | `integer` | 组合 UQ；组合 UQ；非空 | `1` | round no |
| `sequence_no` | `integer` | 组合 UQ；非空 | — | 节点顺序号 |
| `willingness_text` | `text` | 可空 | — | willingness text |
| `trial_status` | `varchar(30)` | 非空 | `'pending'` | trial status |
| `trial_result` | `varchar(30)` | 可空 | — | trial result |
| `result_note` | `text` | 可空 | — | result note |
| `custom_values` | `jsonb` | 非空 | `'{}'` | custom values |
| `created_by` | `uuid` | FK → app_user.id；可空 | — | 创建用户 |
| `created_at` | `timestamp` | 非空 | `当前时间` | 创建时间 |
| `updated_at` | `timestamp` | 非空 | `当前时间` | 最后更新时间 |

表级规则：组合唯一：`project_id`, `person_id`, `round_no`；组合唯一：`project_id`, `round_no`, `sequence_no`；CHECK：`trial_result IS NULL OR (trial_result::text = ANY (ARRAY['passed'::character varying, 'failed'::character varying, 'partially_passed'::character varying, 'withdrawn'::character varying]::text[]))`；CHECK：`round_no > 0 AND sequence_no > 0`；CHECK：`trial_status::text = ANY (ARRAY['pending'::character varying, 'in_progress'::character varying, 'submitted'::character varying, 'reviewing'::character varying, 'completed'::character varying, 'cancelled'::character varying]::text[])`；索引 `ix_annotation_trial_person`：`person_id`；索引 `ix_annotation_trial_project_status`：`project_id`, `trial_status`。

### `annotation_assignee_rate`

正式标注或质检安排的人员计价。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `assignee_id` | `uuid` | FK → annotation_project_assignee.id；UQ；非空 | — | 任务执行人 |
| `amount` | `numeric(18, 6)` | 非空 | — | amount |
| `currency` | `varchar(3)` | 可空 | — | currency |
| `unit` | `varchar(30)` | 非空 | — | unit |
| `remarks` | `text` | 可空 | — | 备注 |
| `created_at` | `timestamp` | 非空 | `当前时间` | 创建时间 |
| `updated_at` | `timestamp` | 非空 | `当前时间` | 最后更新时间 |

表级规则：CHECK：`amount > 0::numeric`；CHECK：`unit::text = ANY (ARRAY['item'::character varying, 'second'::character varying, 'minute'::character varying, 'hour'::character varying]::text[])`。

### `annotation_custom_field_definition`

标注域动态业务字段定义。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `project_id` | `uuid` | FK → annotation_project.id；可空 | — | 关联翻译主订单 |
| `table_code` | `varchar(30)` | 非空 | — | table code |
| `field_key` | `varchar(100)` | 非空 | — | field key |
| `field_label` | `varchar(150)` | 非空 | — | field label |
| `data_type` | `varchar(30)` | 非空 | — | data type |
| `options` | `jsonb` | 非空 | `'[]'` | options |
| `sequence_no` | `integer` | 非空 | — | 节点顺序号 |
| `is_required` | `boolean` | 非空 | `false` | is required |
| `is_active` | `boolean` | 非空 | `true` | 账号是否启用 |
| `created_by` | `uuid` | FK → app_user.id；可空 | — | 创建用户 |
| `created_at` | `timestamp` | 非空 | `当前时间` | 创建时间 |
| `updated_at` | `timestamp` | 非空 | `当前时间` | 最后更新时间 |

表级规则：CHECK：`sequence_no > 0`；`table_code` 支持 `project/account/trial/assignment/account_assignment`；项目和账号字段的 `project_id` 必须为空，试标、正式安排和项目账号字段的 `project_id` 必须非空；普通字段类型支持 `text/number/date/datetime/boolean/single_select/multi_select/url`，`image` 仅允许 `account_assignment`；索引 `ix_annotation_custom_field_sequence`：`project_id`, `table_code`, `sequence_no`；唯一索引 `uq_annotation_custom_field_scope_key`：`project_id`, `table_code`, `field_key`。

## 资源需求

### `resource_request`

跨业务来源的资源需求主记录与快照。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `request_no` | `varchar(50)` | UQ；非空 | — | request no |
| `source_type` | `varchar(30)` | 非空 | — | 数据来源类型 |
| `request_category` | `varchar(30)` | 非空 | — | request category |
| `annotation_project_id` | `uuid` | FK → annotation_project.id；可空 | — | 关联的 annotation_project ID |
| `recruitment_project_id` | `uuid` | FK → recruitment_project.id；可空 | — | 关联的 recruitment_project ID |
| `interpretation_project_id` | `uuid` | FK → interpretation_project.id；可空 | — | 关联的 interpretation_project ID |
| `translation_project_id` | `uuid` | FK → translation_project.id；可空 | — | 关联翻译主订单 |
| `other_source_name` | `varchar(500)` | 可空 | — | other source name |
| `source_project_types_snapshot` | `jsonb` | 非空 | `'[]'` | source project types snapshot |
| `source_order_no_snapshot` | `varchar(80)` | 可空 | — | source order no snapshot |
| `source_project_name_snapshot` | `varchar(500)` | 非空 | — | source project name snapshot |
| `source_status_snapshot` | `varchar(50)` | 可空 | — | source status snapshot |
| `client_id` | `uuid` | FK → client.id；可空 | — | 关联客户 |
| `sub_client_id` | `uuid` | FK → sub_client.id；可空 | — | 关联的 sub_client ID |
| `client_code_snapshot` | `varchar(60)` | 可空 | — | client code snapshot |
| `client_short_name_snapshot` | `varchar(100)` | 可空 | — | client short name snapshot |
| `request_detail` | `text` | 非空 | — | request detail |
| `progress_percent` | `smallint` | 非空 | `0` | progress percent |
| `priority` | `varchar(10)` | 非空 | `'medium'` | 优先级 |
| `request_status` | `varchar(30)` | 非空 | `'submitted'` | request status |
| `requested_by` | `uuid` | FK → app_user.id；可空 | — | requested by |
| `requested_at` | `timestamp` | 非空 | `当前时间` | 业务时间 |
| `owner_id` | `uuid` | FK → app_user.id；可空 | — | 关联的 owner ID |
| `completed_at` | `timestamp` | 可空 | — | 业务时间 |
| `created_at` | `timestamp` | 非空 | `当前时间` | 创建时间 |
| `updated_at` | `timestamp` | 非空 | `当前时间` | 最后更新时间 |

表级规则：CHECK：`request_category::text = ANY (ARRAY['annotation_trial'::character varying, 'annotation_formal'::character varying, 'recruitment'::character varying, 'interpretation'::character varying, 'translation'::character varying, 'other'::character varying]::text[])`；CHECK：`source_type::text = 'annotation'::text AND (request_category::text = ANY (ARRAY['annotation_trial'::character varying, 'annotation_formal'::character varying]::text[])) OR source_type::text = request_category::text`；CHECK：`completed_at IS NULL OR completed_at >= requested_at`；CHECK：`priority::text = ANY (ARRAY['high'::character varying, 'medium'::character varying, 'low'::character varying]::text[])`；CHECK：`progress_percent >= 0 AND progress_percent <= 100`；CHECK：`source_type::text = ANY (ARRAY['annotation'::character varying, 'recruitment'::character varying, 'interpretation'::character varying, 'translation'::character varying, 'other'::character varying]::text[])`；CHECK：`source_type::text = 'annotation'::text AND annotation_project_id IS NOT NULL AND recruitment_project_id IS NULL AND interpretation_project_id IS NULL AND translation_project_id IS NULL AND other_source_name IS NULL OR source_type::text = 'recruitment'::text AND annotation_project_id IS NULL AND recruitment_project_id IS NOT NULL AND interpretation_project_id IS NULL AND translation_project_id IS NULL AND other_source_name IS NULL OR source_type::text = 'interpretation'::text AND annotation_project_id IS NULL AND recruitment_project_id IS NULL AND interpretation_project_id IS NOT NULL AND translation_project_id IS NULL AND other_source_name IS NULL OR source_type::text = 'translation'::text AND annotation_project_id IS NULL AND recruitment_project_id IS NULL AND interpretation_project_id IS NULL AND translation_project_id IS NOT NULL AND other_source_name IS NULL OR source_type::text = 'other'::text AND annotation_project_id IS NULL AND recruitment_project_id IS NULL AND interpretation_project_id IS NULL AND translation_project_id IS NULL AND other_source_name IS NOT NULL`；CHECK：`request_status::text = ANY (ARRAY['draft'::character varying, 'submitted'::character varying, 'in_progress'::character varying, 'fulfilled'::character varying, 'cancelled'::character varying]::text[])`；索引 `ix_resource_request_annotation`：`annotation_project_id`；索引 `ix_resource_request_client`：`client_id`；索引 `ix_resource_request_interpretation`：`interpretation_project_id`；索引 `ix_resource_request_owner_status`：`owner_id`, `request_status`；索引 `ix_resource_request_recruitment`：`recruitment_project_id`；索引 `ix_resource_request_source`：`source_type`, `requested_at`；索引 `ix_resource_request_status_priority`：`request_status`, `priority`, `requested_at`；索引 `ix_resource_request_translation`：`translation_project_id`。

### `resource_request_item`

资源需求的语种、人数与要求明细。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `request_id` | `uuid` | FK → resource_request.id；组合 UQ；非空 | — | 关联交接申请 |
| `sequence_no` | `integer` | 组合 UQ；非空 | — | 节点顺序号 |
| `source_language_id` | `uuid` | FK → interpretation_language.id；可空 | — | 关联的 source_language ID |
| `target_language_id` | `uuid` | FK → interpretation_language.id；可空 | — | 关联的 target_language ID |
| `required_count` | `integer` | 可空 | — | required count |
| `requirement_detail` | `text` | 可空 | — | requirement detail |
| `created_at` | `timestamp` | 非空 | `当前时间` | 创建时间 |
| `updated_at` | `timestamp` | 非空 | `当前时间` | 最后更新时间 |

表级规则：组合唯一：`request_id`, `sequence_no`；CHECK：`required_count IS NULL OR required_count > 0`；CHECK：`target_language_id IS NULL OR source_language_id IS NOT NULL AND source_language_id <> target_language_id`；CHECK：`sequence_no > 0`。

### `resource_request_progress_log`

资源开拓进度变化履历。

| 字段 | 类型 | 约束 | 默认值 | 中文说明 |
|---|---|---|---|---|
| `id` | `uuid` | PK；非空 | `gen_random_uuid()` | UUID 主键 |
| `request_id` | `uuid` | FK → resource_request.id；非空 | — | 关联交接申请 |
| `progress_percent` | `smallint` | 非空 | — | progress percent |
| `progress_note` | `text` | 可空 | — | progress note |
| `changed_by` | `uuid` | FK → app_user.id；可空 | — | changed by |
| `changed_at` | `timestamp` | 非空 | `当前时间` | 业务时间 |

表级规则：CHECK：`progress_percent >= 0 AND progress_percent <= 100`；索引 `ix_resource_request_progress_timeline`：`request_id`, `changed_at`。

## 视图

### `v_finance_record_display`

财务展示视图：以 `finance_record` 为主表，连接 `translation_project` 和 `client`，输出订单号、客户简称、项目名称、项目状态、报价金额、开票状态等列表展示字段。


### chat_message_view（逐条消息阅读回执）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| conversation_kind | varchar(20), PK | annotation / translation / direct / discussion |
| conversation_id | UUID, PK | 当前独立会话 ID，主子订单互相隔离 |
| message_id | varchar(64), PK | 项目/私聊 UUID 消息号或讨论整数消息号；读取与写入均核对所属会话 |
| user_id | UUID, PK, FK app_user | 实际查看者；按当前参与人筛选统计，不包含发送者 |
| seen_at | timestamptz | 首次实际可见且页面前台聚焦的时间；UTC+8 接口展示 |

迁移：`tools/apply_chat_message_views_migration.py`，幂等创建空表，不回填历史阅读，不与关注/未读游标/收到确认混用；需显式数据库维护授权后执行。

### system_department（统一部门目录）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | UUID, PK | 稳定部门标识 |
| name | varchar(50), unique | 当前部门名称 |
| aliases | JSON | 本部门历史名称，供历史数据和旧请求映射 |
| revision | integer | 并发编辑版本号 |
| updated_by | UUID | 最近编辑账号 |
| created_at / updated_at | timestamptz | UTC+8 业务时间 |

管理仅允许实际登录用户名 ethan、jimmy（不区分大小写）和 admin/超级管理员角色；所有登录用户可读取部门选项。改名在同一事务同步 app_user.department 以及 work_schedule JSON 内 dept/department 字段，不修改任务、备注和历史审计自由文本。旧名称保留映射。迁移 `tools/apply_department_catalog_migration.py` 幂等创建目录，导入预置及现有非空部门；初始化不修改人员、排班，须另获明确数据库迁移授权后执行。

### 八类聊天总结（resource_development_issue 扩展）

`category`：arrangement=信息同步、request=提出需求、idea=想法讨论、decision=决策批复、execution=任务执行、problem=问题/异常、risk=风险隐患、standard=规则标准。沿用原四类编码，不删除或合并历史事项。

新增 `summary_data JSON NOT NULL DEFAULT '{}'`：specific_classification（具体分类，200字）、planned_completion_at（预定完成时刻，明确+08:00）、follower_user_ids（跟进人UUID数组）、actual_progress（实际进度，10000字）、notify_user_ids（显式选择的同步人员）、notify_department_ids（同步部门，稳定目录UUID）。任务时间、跟进人与进度仅适用于 execution。created_at 为保存时间，筛选日期按 UTC+8 的闭开区间查询。

新增 `resource_issue_audience`：issue_id UUID（FK resource_development_issue，级联删除）、kind varchar(24)（follower / notify_user / notify_department）、target_id UUID；三者组成主键，按 kind/target_id/issue_id 建索引。部门保存时解析当前有效成员，notify_user 保存去重后的实际通知及授权对象，不因部门后续新增人员自动开放历史总结。

保存与业务通知在同一事务内落库，提交后再推送；通知类型 chat_summary，目标实体为总结ID，业务通知可打开对应总结。跟进人仅可单独更新任务进度，不能修改正文或通知范围；来源聊天仍独立验证原会话参与人权限。迁移 `tools/apply_chat_summary_migration.py` 只扩展字段/约束及范围表，不补发历史通知；须明确数据库迁移授权。
# 标注进度默认提及配置（2026-10-22）

`annotation_progress_mention_defaults`：所有账号共用的标注项目默认 @ 名单。id=1 为进度发送默认名单，id=2 为新增项目默认名单；后者首次使用预选有效账号“赵震锋”，保存后使用人工配置。仅由显式保存设置维护，不修改历史会话或参与人。

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| id | integer PK | 1=进度；2=新增标注项目 |
| user_ids | JSON | 默认人员 UUID 列表 |
| department_ids | JSON | 默认部门 UUID 列表；发送时展开有效人员 |
| updated_by | UUID FK app_user | 最后修改人 |
| updated_at | timestamptz | 最后修改实际时间，接口 UTC+8 |

迁移入口：`tools/apply_annotation_progress_mentions_migration.py`。每次结构迁移先取得用户单独确认。客户／项目进度可携带 `chat_delivery`：`send_to_chat`、`user_ids`、`department_ids`；进度和对应订单消息在同一事务保存，发送后沿用会话 @ 提醒、自动邀请规则，不修改主／子订单归属。

`annotation_project.task_image_upload_ids`：JSONB，非空、默认 `[]`，最多9个具体任务截图的资料上传 UUID。复用 `annotation_material_upload/file/version` 及文件授权、生命周期；只接收 PNG/JPEG/GIF/WebP，每张最多10MB。截图归入项目资料“具体任务截图”，文本继续保存在原 `task_description`，不将图片编码写入文本。

迁移入口：`tools/apply_annotation_task_images_migration.py`，执行前每次单独确认。新增项目的 `chat_delivery` 仅控制本订单通知；消息正文保留九项字段的可搜索文本，`content_json.type=annotation_creation` 保存字段卡片，截图通过 `chat_project_attachment` 的 `material:<upload UUID>:<随机 UUID>` 引用当前订单资料。下载须先验证会话参与权限及当前订单的资料版本关联。


### 通用编辑截图（2026-10-22 经用户确认建表）

- `editor_screenshot_blob`：`sha256 varchar(64)` 主键，`content bytea` 压缩图片（延迟加载），`content_type varchar(40)`、`byte_size integer`。相同图片内容去重，单图压缩后不超过2MB。
- `editor_screenshot`：`id uuid` 主键，`blob_sha256 varchar(64)` 可空外键，`uploaded_by uuid` 人员外键，`created_at timestamptz`，`retention_kind varchar(16)`（business/chat），`expires_at timestamptz` 可空。业务图片永久；聊天截图30天后清除内容引用、保留过期占位。业务表中的原文字字段保存 `![截图](screenshot://UUID#签名)` 引用（签名阻止旧接口伪造图片引用；认证签名密钥轮换时须一并规划图片引用兼容），原历史文字不转换。
- `editor_screenshot_grant`：`id uuid` 主键，`user_id uuid` 人员外键，`image_ids json`，`expires_at timestamptz`。只有已通过业务接口授权且实际返回的图片才能获得10分钟读取授权；授权与账号绑定，过期清理。聊天图片下载额外按原消息参与权限和消息时间验证。
- 将聊天截图保存到业务记录后，该引用提升为长期保存；聊天内仍按消息创建时间限制30天。清理图片字节不删除文字、业务资料及非图片文件。现有云端文件附件不在此建表迁移中删除。
- 可重复迁移：`tools/apply_editor_screenshots_migration.py`；服务启动不创建或迁移表。

### 组织架构与跨部门人员（2026-10-22，经用户确认创建并初始化）

`system_department_member`：`department_id uuid`（FK system_department，级联删除）、`user_id uuid`（FK app_user，级联删除）组成主键；`position varchar(50)` 非空默认空串，部门内业务职务，不赋予任何系统权限；`created_at`、`updated_at timestamptz`，UTC+8。按 user_id 建索引，以便查看一个人的全部部门。

迁移 `tools/apply_organization_members_migration.py` 导入现有主部门归属，保留 `app_user.department` 作为主部门，不改历史排班或权限。显式 `--initialize-annotation` 时仅在“标注项目部”不存在时创建并加入已核对的17位人员和职务；重复运行不恢复之后人工移出的标注项目部成员。结构变更必须先获得用户单独确认，不由服务启动触发。

系统管理统一入口为“组织架构”，人员管理与部门名册在同一板块。`GET /departments/organization` 返回姓名、账号、主部门及全部部门/职务；`PUT /departments/{id}/members` 仅 ethan、jimmy、超级管理员可保存，通过部门 revision 防止覆盖他人修改。移出主部门时使用其余部门作为主部门或置空。人员筛选、部门通知及标注默认@按跨部门名册匹配并去重。

### 资源需求多版本与通知回执（2026-10-23，经用户确认完成结构初始化）

- `resource_request.request_detail` 保留历史内容，界面改称总体需求；新增 `request_content JSONB NOT NULL DEFAULT '{}'`，保存 `versions:[{name,content}]`，不改写历史详情。新增 `partial_requested boolean NOT NULL DEFAULT false`、`partial_sequence integer NOT NULL DEFAULT 0`。仅母订单且有子订单可标记部分语种；发送时锁来源项目，以来源项目分配递增批次，标题保存为“部分语种（n）原项目名”。项目名本体不修改。`uq_resource_request_partial_batch` 对 annotation_project_id/partial_sequence（大于0）唯一。
- `resource_request_dispatch`：id UUID PK；request_id UUID FK resource_request（RESTRICT），sender_id UUID FK app_user（RESTRICT），kind varchar(16)（circle/post/development/cancellation），idempotency_key varchar(128) 全局唯一，snapshot JSON 不可变完整需求快照，created_at timestamptz。按 request_id、sender_id 建索引。
- `resource_request_dispatch_recipient`：dispatch_id UUID FK dispatch（CASCADE）与 user_id UUID FK app_user（RESTRICT）联合主键；received_at、processed_at timestamptz，可空。按 user_id/dispatch_id 建索引。回执仅本人操作，已处理必须先已收到；同状态重试不重复通知。
- 发送人及指定接收人可读快照；仅 active 的标注项目部成员可作为新发送目标。通知类型 `resource_request_dispatch` 属业务通知，继续使用红色未读数字。发送、接收和处理通知含项目名称；快照及新回执使用 UTC+8。通知入库与批次/回执同事务，提交后推送。
- 显式迁移：`tools/apply_resource_request_dispatch_migration.py`。仅新增三列、唯一索引和两表，不补发历史通知，不填造历史回执；每次执行云端结构迁移前单独确认。

资源需求三种发送方式分别最多5次；development 复用现有批次和回执表，快照的 send_log_id 关联原发送进度日志。历史发送只按原日志统计，不补造接收人和回执。重复请求使用幂等标识，不重复计数或通知。此次扩展不新增表或字段。

取消通知（2026-10-27）：复用批次与接收人表，kind=cancellation，sender_id 为取消操作人；snapshot 在原需求快照上附加 cancelled_kind、original_dispatch_id，幂等键 cancel-dispatch:{原批次UUID}。原批次与回执不改写；取消批次 received_at 表示“确认收到取消通知”，仅原接收人可确认，重复确认不重复通知。取消操作人收到确认通知。发圈／发帖分别取消所有尚未取消批次，资源开拓取消同时更新 demand_status、request_status 为 cancelled；新发送批次独立处理。发送、取消、处理回执按需求行锁串行执行；取消和通知同事务。此次扩展不新增表或字段，不补发历史通知。

### 人员逻辑删除（2026-10-23，已单独确认并执行迁移）
app_user 新增 is_deleted boolean NOT NULL DEFAULT false、deleted_at timestamptz NULL。删除时停用账号并写入 UTC+8 删除时间；人员列表及组织架构排除已删除人员，历史业务外键、姓名、排班、请假、消息及审计保留。用户名和邮箱继续保留唯一性，避免历史身份被新人员复用。

### 发帖平台执行回执（已单独确认并执行迁移）
resource_request_execution_reply：id UUID PK，dispatch_id UUID FK resource_request_dispatch（RESTRICT）并索引，user_id UUID FK app_user（RESTRICT），platforms JSON（平台 id/name/parent_name 快照），content TEXT，idempotency_key varchar(128) UNIQUE，created_at timestamptz。每次回复独立保留，不因渠道后续编辑或删除改写。

### 标注业务默认接收人（已单独确认并执行迁移）
resource_request_dispatch_default：kind varchar(16) PK（circle/post/development），user_ids JSON NULL（NULL 按初始规则生成，[] 明确清空），revision integer，updated_by UUID FK app_user，updated_at timestamptz。发帖可选全公司启用人员；发圈、需求可选标注项目部。共用配置不改写已发送通知。

资源需求 request_content.versions 的每个版本新增 copied_from_task 布尔 JSON 属性（默认 false），标记发帖版、询问版是否自动复制自标注项目 task_description；页面按此属性在内容首行显示红色加粗提示。复用现有 JSON 字段，无数据库结构变更；人工正文不会被覆盖。

### 总结查看权限（2026-10-24）
复用 resource_development_issue.summary_data JSON：view_all（true 全体；false 指定范围；null/缺失沿用历史关联权限）、view_user_ids（人员 UUID 字符串数组）、view_department_ids（部门 UUID 字符串数组）。新表单默认全体，历史记录不回填；保存人和已有统筹管理权限保留。部门按当前主部门及多部门成员动态匹配；通知对象必须在指定查看范围内。列表、详情及写入共用权限查询，原会话权限不变。本次无表、列或约束变更。


### work_report_category（工作报告自定义二级分类）

通过 `tools/apply_work_report_categories_migration.py` 显式初始化，不随服务启动迁移。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | UUID | 主键，应用生成 |
| scope | varchar(36) | 项目分类使用 `*` 全局共享，其余分类使用用户 UUID 隔离 |
| parent | varchar(20) | 项目工作、非项目工作、外勤工作、管理工作 |
| name | varchar(80) | 自定义二级分类名称 |

`scope + parent + name` 唯一。默认分类由代码提供。只有超级管理员可新增项目分类；其他类别用户自行新增。
日报 `display_metadata.report_types` 保留旧项目值，新二级分类使用 `一级::二级`。仅纯非项目工作允许订单号、项目名称为空；其他手工行的订单号、项目名称、具体任务、工作量、单位、耗时必填。所有工作报告字段禁止截图引用。


### work_report_access_rule（工作报告查看匹配规则）

通过 `tools/apply_work_report_access_migration.py` 显式初始化；不在启动时建表，不自动写入授权规则。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | UUID | 应用生成的规则主键 |
| name | varchar(100) | 匹配规则名称 |
| viewers_all | boolean | 是否允许全体在职启用人员查看 |
| viewer_ids | JSONB | 查看人 UUID 数组；保存时保留赵震锋 |
| senders_all | boolean | 全体启用成员（包括无部门人员） |
| all_departments | boolean | 当前目录全部部门，随名册动态变化 |
| department_ids | JSONB | 指定发送人部门 UUID 数组 |
| sender_ids | JSONB | 额外指定发送人 UUID 数组 |
| enabled | boolean | 规则启用状态 |
| revision | integer | 乐观锁版本，从 1 开始 |
| updated_at | timestamptz | UTC+8 业务时钟写入，接口携带 +08:00 |
| updated_by | UUID | 最后配置人 |

设置读写仅限已核对的赵震锋账号 `williamzhao`，超级管理员角色无额外绕过权限。查看范围是启用规则的并集；同一规则中部门与个人发送范围取并集。部门按当前主部门、历史别名和跨部门成员动态匹配；已停用/删除人员排除。只共享已确认日报，列表、可选发送人和详情都在后端应用同一范围，撤回和规则停用立即阻断新请求。初始查看人预选为 Ethan、Thomas、卢少妃、Lulu、黄运坚、刘家铭、梁翠珍、李宇琪及赵震锋；只在配置人显式保存规则后生效。本功能不自动发送邮件，沿用现有邮件发送操作。


### work_report_feedback（逐项反馈与来回沟通）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | UUID | 消息主键 |
| report_id | UUID | 所属日报，外键 daily_report，删除时级联 |
| item_key | varchar(36) | 工作项稳定标识；新版保存于 display_metadata._feedback_key，历史行回退为明细 UUID |
| item_snapshot | JSONB | 原始工作类型、名称、具体任务；工作行删除或改写后仍保留沟通语境 |
| author_id | UUID | 发言人，外键 app_user |
| author_name | varchar(255) | 发言时姓名快照 |
| content | text | 纯文字沟通，最多4000字 |
| created_at | timestamptz | UTC+8 业务时钟；接口 +08:00 |

索引 report_id + item_key + created_at。当前有权查看人可发起反馈，报告作者可回复既有反馈，双方可多次沟通。赵震锋、Lulu 可查看全部沟通；该监督权不自动授予整份报告的查看权。普通查看人撤权后不能继续读取或回复；作者仍可查看自己的沟通。历史工作项删除后消息保留。

### work_report_revision（一次修订快照）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | UUID | 主键 |
| report_id | UUID | 所属日报，唯一约束 uq_work_report_one_revision，外键 daily_report |
| before_data | JSONB | 修订前完整报告快照 |
| after_data | JSONB | 修订后完整报告快照 |
| created_by | UUID | 报告作者 |
| created_at | timestamptz | 修订时间，UTC+8 |

报告确认后最多修订一次（包括已发邮件报告），以日报行锁和唯一约束限制并发；保存前后快照与正文在同一事务中提交。无实际修改不消耗机会。已确认报告不再通过撤回绕过次数限制。修订后可再次发送，既有邮件投递快照保留。系统记录修订时沿用已确认快照，不重新汇总。所有新表由 tools/apply_work_report_review_migration.py 显式创建，不随启动建表。

### 工作日报告统计口径

仅赵震锋及当前行政部（主部门或跨部门成员）可以统计。仅已确认报告计为已写；当前启用未删除人员，自账号创建日期起统计，未来日期不计。2025、2026 年使用国务院公布的放假及调休安排，未知年份拒绝统计，不按普通周末推测。按日给出应写、已写、未写人数与人员 UUID；按周/月返回每人缺报的全部具体工作日。部门及姓名筛选在同一查询范围内应用，跨部门人员去重。人员范围采用当前名册，不以此替代历史劳动关系或请假考勤。

### 新咨询对接及工作报告二级行（2026-10-24）

复用 consultation.project_intake 的保留键 `_work_report_capture`，不新增数据库字段。该键由后端写入及保护，普通创建、编辑和售前字段更新不得覆盖。保存 owner_id、pending/completed 状态、created_at、item_key；完成时增加 report_id、report_date、completed_at 以及 original_entry 初始录入快照。本人 pending 列表支持刷新恢复必填窗口；提交锁定用户、咨询与日报，重复请求返回同一结果，不重复追加。

新咨询对接写入既有 daily_report_item，display_metadata 保存 source=consultation_handoff、consultation_id、consultation_code、added_at（+08:00）及稳定 _feedback_key。已确认日报直接追加，保留旧明细、确认状态与确认时间，不占用一次修订机会；保存陈旧草稿或重新汇总不得删除自动追加项。有权查看者通过 daily_report_updated 实时通知重新读取；所有实际读取仍重新核验当前权限。

工作报告业务日按 UTC+8 每日 07:00 换日；自动归属及默认今天使用该业务日。显式选择的报告日期和历史记录不批量改写。按发生时刻汇总的事件范围为所选日期 07:00（含）至次日 07:00（不含）；按明确 work_date 填写的记录保持原日期语义。

二级工作项使用 daily_report_item.display_metadata.parent_item_key 指向同份报告父项的 _feedback_key；最多两级，同项目身份（订单号、类型、项目名称）沿用父项，具体任务、工作量、单位和耗时独立填写。后端校验父项属于同一报告、拒绝循环关系，手工重复订单自动归并，并按父项及其子项连续排序；界面、查看快照与 Excel 使用 1、1.1、1.2 编号体现层级。

查看规则复用 work_report_access_rule：除自动保留的赵震锋外仅指定一名查看人的启用规则视为该人的个人专属规则，优先于该人适用的多人共享或全体查看规则；同人的多条专属规则仍取并集。赵震锋仅含本人查看人的规则为其个人范围。停用个人规则后回退共享规则。个人范围可选择全体成员、全部部门，或搜索并多选指定部门及人员；部门与人员取并集并去重。只有赵震锋可以读取和编辑设置；赵震锋及 Lulu 的全部沟通监督权限独立于报告范围。
## 标注项目进度编辑与删除留痕（2026-10-25）

复用 `project_operation_audit`，`operation_type` 增加 `progress_edit`，保留原有 `progress_delete`；迁移脚本为 `tools/apply_annotation_progress_edit_audit_migration.py`，仅调整 `ck_project_operation_audit_operation` 约束，无新增列。未经单独授权不执行云端迁移。

`operation_source` 分别为 `progress_record_edit` / `progress_record_delete`。`project_snapshot` 保存 `record_part`（`progress` / `status_note`）、编辑前后 `before_progress_record` / `after_progress_record` 或删除前 `deleted_progress_record`。快照包含记录 ID、正文、节点时间、原创建人与更新时间；新快照时间明确携带 `+08:00`。审计操作人及操作时间沿用既有字段。

状态变更说明删除只清空说明，不删除状态节点或改变当前状态；普通进度删除后从审计重建只读占位和历史入口。所有有项目查看权限的登录用户可编辑、删除项目进度记录及查看其留痕，不授予其他项目管理权限。读取既有删除审计兼容旧无时区时间，按项目既有 UTC+8 本地时间解释，不回写历史值。


## 笔译项目安排与今日任务（2026-10-25）

### translation_project_arrangement

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid PK | 人员任务 ID |
| project_id | uuid FK | 笔译母项目，项目删除时级联删除 |
| assignee_id | uuid FK | 被安排人员，禁止删除引用人员 |
| assigned_by | uuid FK | 安排人 |
| content | text | 可修改的具体任务，必填 |
| work_date | date | 安排日期；默认使用工作报告 UTC+8 七点换日业务日 |
| estimated_minutes | integer | 预计需要时间，0 表示未填，最大 1440 分钟 |
| actual_minutes | integer | 实际花费时间，完成时取已验证报告耗时 |
| status | varchar(20) | pending 待进行、in_progress 进行中、completed 已完成 |
| revision | integer | 更新及完成请求必须携带的乐观锁版本 |
| created_at / updated_at / completed_at | timestamptz | 业务时刻，接口按 +08:00 序列化 |
| report_item_id | uuid nullable | 完成时创建的日报明细 ID；报告重写后通过 metadata.arrangement_id 追溯 |

索引：assignee_id + work_date；project_id。完成任务必须使用完整工作报告行校验，禁止直接设置 completed；任务状态与追加报告在单事务中提交。报告行以 manual 来源存储，source_id 为任务 ID，display_metadata.source 为 project_arrangement，带 arrangement_id、order_no、project_type 及稳定反馈键。陈旧报告编辑窗口或重新汇总不得丢弃该来源的现有记录。已确认日报先撤回才能继续追加，不自动撤回或修改已确认报告。

查看他人任务严格复用工作报告 receiving_rules / sender_ids_for_rules，按当前部门成员关系解析，不因项目写权限、统计权限或超级管理员身份扩大个人任务查看范围。项目列表中的项目安排仅供具有 projects:read 的账号查看，修改安排需 projects:write；本人可填写用时、更新执行状态，只有本人可完成并录入自己的工作报告。

迁移入口：tools/apply_project_arrangement_migration.py。仅显式执行，无启动自动迁移；执行云端结构调整须另行确认。

### translation_arrangement_plan（项目安排执行顺序）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| project_id | uuid PK / FK | 笔译项目；同项目全部安排批次共用执行顺序 |
| ordered_task_ids | json | 按执行先后保存任务 UUID 字符串，新安排追加末尾 |
| revision | integer | 方案并发版本，排序必须匹配所见版本 |
| updated_by | uuid nullable | 最近修改人 |
| updated_at | timestamptz | 最近修改时刻，接口按 +08:00 输出 |

### translation_arrangement_history（不可覆盖的安排快照）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid PK | 历史记录 ID |
| project_id | uuid FK | 笔译项目 |
| revision | integer | 与 project_id 组成唯一约束的历史版本 |
| operation | varchar(30) | assign 新增安排、edit 修改内容/状态/用时、reorder 调整顺序、complete 完成并入报告、baseline 已有安排首次快照 |
| actor_id / actor_name | uuid / varchar(255) | 操作人及姓名快照 |
| before_snapshot / after_snapshot | json | 前后项目状态、有序任务明细、安排人、日期、内容、状态和用时 |
| created_at | timestamptz | 操作时刻，接口按 +08:00 输出 |

索引：project_id + created_at。历史通过新增快照保存，不提供编辑或删除历史接口。第一次修改旧安排时补录 baseline，不伪造此前无法追溯的操作。

安排、修改、完成与排序先锁定项目；快照和变更在同一事务提交。排序必须提交全部任务 ID，拒绝遗漏、重复、跨项目及过期版本。个人今日任务返回步骤、姓名、状态和 ID 组成的顺序，不随序列返回其他人的任务内容。

项目状态新增 arranged（已安排），沿用现有字符字段，无须变更旧表。保存新安排时仅将前期状态改为已安排，不覆盖暂停、取消、交付等后续状态。历史安排不做批量状态改写。

迁移：tools/apply_arrangement_history_migration.py，仅创建上述两张新表，不修改原表或已有业务记录；按用户 2026-10-25 长期授权，执行前后醒目提示。

### personal_daily_task（自行填写的今日任务）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid PK | 自主任务 ID |
| user_id | uuid FK | 填写人，仅本人可编辑和完成 |
| work_date | date | 安排日期，默认沿用工作报告 UTC+8 七点换日业务日 |
| report_row | json | 任务类型、具体任务、项目身份、工作量及单位等填写内容；完成前允许暂不填工作量、单位和耗时 |
| estimated_minutes / actual_minutes | integer | 预计和实际分钟数，0 表示未填写，范围 0～1440 |
| status | varchar(20) | pending、in_progress、completed |
| revision | integer | 编辑、完成时的乐观锁版本 |
| report_item_id | uuid nullable | 完成时新增的工作报告明细 ID；报告重写后通过 metadata.personal_task_id 追溯 |
| created_at / updated_at | timestamptz | 创建及修改时刻，接口按 +08:00 输出 |

索引：user_id + work_date；状态及用时有 CHECK 约束。自行填写不改变项目的人员安排、执行顺序或项目状态。项目类型关联由统一项目身份目录选择，服务端核验类型和项目 ID，并带出规范订单号与项目名称。其他字段由人员填写。

个人任务完成与追加完整工作报告使用共同事务帮助函数，表单缺项、报告已确认或保存失败时不标记完成。报告来源为 manual，metadata.source=personal_daily_task，带 personal_task_id 和稳定反馈键；陈旧报告编辑器和重新汇总不得丢弃这类记录。

今日任务与分派任务通过数据库 UNION 统一分页、统计；查看他人任务沿用工作报告查看范围与部门筛选规则。默认今日查询包含此前未完成事项，显式日期范围查询严格按安排日期取值且包含已完成任务。昨日、前日为单日，上周和前一周为周一至周日的上一个、上上个自然周。

今日任务表单允许所有人员新增一行或多行，不要求已有分派任务。`POST /project-arrangements/personal-batch` 每次接收 1～100 行；所有行完成类型、项目关联校验后统一事务保存，任一行无效不创建任务。各行独立计时、编辑和完成，保存时保留项目继承值并移除表单内父行引用，不新增表或字段。

工作报告与任务查看共用规则；Lulu（lulu）、Ethan（ethan）使用赵震锋（williamzhao）当前生效的查看规则，包括个人规则优先级，并具有相同的报告统计及沟通查看能力。停用或删除的账号不生效。设置修改仍仅限赵震锋，界面标题统一为“工作报告与任务查看设置”；不改写已有规则数据。

迁移：tools/apply_personal_daily_task_migration.py，仅创建新表及必要索引、约束，不修改旧表或已有业务数据；按用户长期授权在执行前后醒目提示。

### monthly_shift_plan（月度班次安排，2026-10-25）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| month | date PK | 月份首日；界面与接口月份为 YYYY-MM，按 UTC+8 日历月份计算 |
| assignments | json | user_id、department、shift 数组；同一人员每月仅一项，均经后端校验 |
| revision | integer | 整月乐观锁版本，调班及撤销均检查版本后统一事务保存 |
| updated_by | uuid | 最近调整人 |
| updated_at | timestamptz | UTC+8 操作时间，接口显式 +08:00 |

排班管理归入侧栏“人事管理”，仅在用且未删除的行政部成员可读写，包括当前跨部门名册及部门别名；超级管理员角色不绕过部门限制。工作台“排班安排”接口仅返回本人班次，无他人选择参数及编辑入口。六个排班行组：客户/销售部、HR部、项目部（翻译+标注）、排版部、IT部门、行政部；每周、每月班次及周末值班均包含行政部。客户与销售仅在本模块合并显示，不改组织架构、部门筛选或已有人员归属。班次存储保留全部工作时段，客户部居家晚班包括 21:00–23:00；不推断周末、节假日或请假制度，不改旧日排班数据。

迁移：tools/apply_monthly_shift_migration.py，仅创建新表，不修改旧表及已有业务记录。默认展示下月；快捷上月、本月按 UTC+8 当前日历月份定位。历史月份独立保存，切换月份不复制或覆盖其他月份。

### translation_arrangement_instruction（项目安排共同说明，2026-10-25）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| project_id | uuid PK/FK | translation_project.id，项目删除时级联删除 |
| content | text | 本项目所有被安排人员可见的共同说明；最多 10000 字 |
| revision | integer | 共同说明独立乐观锁版本 |
| updated_by | uuid | 最近编辑人 |
| updated_at | timestamptz | UTC+8 编辑时间 |

说明与每个人的具体任务分别保存。批量安排可在同一事务中保存说明和个人任务；说明版本冲突则全部不提交。修改共同说明须有 projects:write，使用与任务编辑一致的项目锁顺序，并记录安排历史的 before/after 快照。今日任务及有权查看任务的人可查看共同说明；完成任务加入工作报告时，仍以个人任务内容作为“具体任务”，不以共同说明代替。历史快照只在项目级保存说明，避免在每个任务中重复存储。旧任务无说明时返回空文字，无历史内容回填。

迁移：tools/apply_arrangement_instruction_migration.py，仅新建说明表，不修改已有任务表结构或业务记录；执行前后按长期授权醒目提示目标与结果。

### weekend_duty_plan（周末值班安排，2026-10-25）

仅行政部可读取、调整，与 monthly_shift_plan 独立存储。由 tools/apply_weekend_duty_migration.py 幂等创建；启动不自动建表。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| month | date，主键 | 所属月份第一天，如 2026-11-01 |
| assignments | JSON | 数组项含 user_id（UUID文本）、department（参与排班分组代码）、date（YYYY-MM-DD） |
| revision | integer | 乐观锁版本，空月为0，首次保存为1，后续递增 |
| updated_by | UUID | 最近调整人，复用现有账号目录 |
| updated_at | timestamptz | UTC+8 当前时刻，接口明确携带 +08:00 |

覆盖当前月所有周六及周日；不将该功能当作法定节假日安排或调休规则，节假日安排暂为待开发。参与分组沿用班次安排：客户/销售、HR、项目（翻译及标注）、排版、IT。相同人员可安排不同日期，每人同日只能出现一次，月份必须匹配；保存校验行政权限、当前参与人员名单、版本与日历范围，锁定月度行，并以月主键处理并发首次创建。停用人员的原安排可保留或移除，不能新增安排。左侧次数为本月右侧出现次数，含0次筛选及各次数人数，跨部门同人统计去重。左侧拖入为增加该日，右侧拖动为移动该次，拖回左侧只撤销对应日期；不修改既有班次表。

接口 GET/PUT /monthly-shifts/weekend-duty?month=YYYY-MM。GET包含 dates、departments、assignments、revision、ready、updated_at；PUT需携带 revision 和完整 assignments，冲突返回409。组织归属不随排班展示分组改变。

### weekly_shift_plan（每周班次安排，2026-10-25）

按香港时间日历周（周一至周日）单独保存，与既有 monthly_shift_plan、weekend_duty_plan 独立。管理入口默认每周安排，本周/上周/下周和月度快捷按钮默认收起、可展开；本人只读视图同步支持每周与月度选择，不混用或自动覆盖历史月度安排。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| week_start | date，主键 | 所属周的周一，跨月、跨年仍为同一条周记录 |
| assignments | JSON | 数组项 user_id、department、shift；同一人员每周只能安排一个班次，不同周可独立安排 |
| revision | integer | 版本，未创建为0；写入锁定周记录，冲突返回409 |
| updated_by | UUID | 最近调整人 |
| updated_at | timestamptz | UTC+8 当前时刻；接口携带 +08:00 |

GET/PUT /monthly-shifts/weekly?week=YYYY-MM-DD：行政部门可管理，输入周内任意日期归一至周一，响应包含 week_start、week_end、ready、revision、assignments、shifts、departments。GET /monthly-shifts/weekly/mine?week=YYYY-MM-DD：仅返回登录人自己的 assignment，不接受其他用户选择。参与部门及班次沿用 monthly_shift；停用人员旧记录可保留或移除，不允许新增无效人员。周与月保留各自版本及主键，不进行历史数据迁移。由 tools/apply_weekly_shift_migration.py 显式幂等建表，启动不自动迁移。


### fixed_shift_config（固定班次人员配置，2026-10-25）

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| id | integer PK | 单例配置键，业务固定为 1 |
| assignments | json | current 固定人员列表（user_id、department、shift，每人唯一）；versions 按 week_start/month_start 保留生效快照 |
| revision | integer | 乐观锁版本，防止覆盖其他管理员的修改 |
| updated_by | uuid | 最后设置的行政部账号 |
| updated_at | timestamptz | UTC+8 业务更新时间 |

GET/PUT /monthly-shifts/fixed 仅允许在用行政部成员访问。新增配置由 tools/apply_fixed_shift_migration.py 幂等创建，不修改既有表。固定班次按 UTC+8 当前日期应用于本周及以后周、本月及以后月：读取时合并到相同单元格，保存时服务端强制保留固定位置，员工只读视图同步生效。设置前的历史周期不受影响，已自动带入的历史周期按生效快照保留，不随之后改班或取消固定消失；停用或删除账号不再带入当前及未来周期。取消固定后，已保存的周期记录仍保留，未保存周期不再自动带入。周末值班不使用固定班次配置。启动不执行结构迁移。


### attendance_day / attendance_leave（旧版打卡兼容及现行请假，2026-10-25）

2026-10-28 起自动登录打卡已停用，以下登录打卡描述仅记录旧版字段来源。现行手动打卡及分段确认见 attendance_clock_session；旧已完成打卡不追溯重算。

`attendance_day`：id UUID 主键；user_id UUID 外键 app_user；day 业务自然日（UTC+8）；check_in / check_out timestamptz（首次电脑登录、首次下班按钮提交时间）；shift_snapshot JSON（打卡当日班次与各工作时段）；created_at timestamptz。唯一约束 uq_attendance_user_day(user_id, day)，日期索引 ix_attendance_day_date。重复登录和签退均不覆盖首次记录。

`attendance_leave`：id UUID 主键（同步旧 employee_leave 使用相同 id）；client_id UUID 唯一请求键；user_id UUID 外键 app_user；start_at / end_at timestamptz；reason text（1–500 字）；days JSON（逐日班次及班次内请假分钟快照）；created_at timestamptz。按 user_id/start_at/end_at 建索引。请假日期最多跨 31 天，时段不能重叠，必须至少覆盖一个有效工作班次；不计午休与班间休息。审批待开发，保存即生效。

接口 /attendance/today、/check-out、/leave/preview、/leave、/mine 只处理本人；/attendance/report 仅行政部可读，姓名/账号关键词和组织部门范围同时用于明细、总数、人员累计及周期合计。统计按周一至周日或自然月。工作台“排班安排”更名“排班与考勤”，旧考勤页面只是空数据演示 UI，已替换；本迁移不删除其他现有业务表。

桌面端成功登录或有效会话次日重新进入系统（POST /attendance/arrival）时，由服务端时间生成上班打卡，校验 UA、Client Hints 及客户端设备类型（手机/平板不计）；登录失败不打卡。每日保留首次登录；没有有效班次不生成记录，并返回明确状态。登记失败不伪造成功，不影响正常登录。下班按钮必须成功提交事务并重读后才返回打卡成功；手机禁止签退。跨午夜最多取前一天未签退记录，自然日期独立于工作报告 07:00 规则。

班次优先取每周安排（含固定班次），其次月度；仅节假日/调休日历中的工作日或已安排周末值班的日期统计，无班次不推算迟到。未知年份日历明确报错。迟到时长为缺席的班次工作分钟减 10 分钟宽限，扣除合法请假与休息，超过才算一次；尚未签退不计算加班。加班为实际打卡区间扣除午休 12:00–13:30、其他班间休息和请假后的出勤分钟，减去班次应工作分钟（已扣合法请假），负数取零。每条记录、个人周/月和管理汇总使用同一计算函数。上班班次快照不受后续排班编辑影响。

请假与旧 employee_leave、全体在用未删除人员的业务铃铛通知、逐人私聊会话消息在同一事务落库，失败全部回滚，幂等重试不重复群发；提交后才 WebSocket 提醒。通知正文含请假人、时段、时长、原因。新请假暂不允许从旧管理入口改/删，避免通知与快照不一致。新表初始化使用 tools/apply_attendance_migration.py 显式幂等执行，不启用启动自动迁移。
## 资源开拓自定义字段（2026-10-26）

字段定义复用 `resource_development_option`，`kind=custom_field`、`name` 为名称（最多100字），不修改选项表结构；同名忽略大小写复用，最多100个字段。新建 `resource_development_custom_value`：`record_id` UUID 与 `field_id` UUID 为联合主键，分别外键指向开拓记录与选项表，均 ON DELETE CASCADE；`value` TEXT 非空默认空串，单字段最多20000字。通过 `tools/apply_development_custom_fields_migration.py` 显式幂等初始化，启动自动迁移保持关闭。

录入接口 `custom_fields` 为字段 UUID 到文本的映射；未提交字段保留旧值，显式空串清空。值与主记录同事务保存，记录到现有 `resource_development_audit`（`entity_type=record_custom_fields`），非授权人员的自由文本按受限内容展示。字段设置使用 `custom_field:<UUID>` 独立列；自定义资源账号使用 `custom_account:<小写名称>` 独立列，从已登记账号中只读汇总名称，不迁移历史账号。两类动态列都按本人或代录权限进行值筛选。

## 人才路径窗口修改记录（2026-10-26）

`talent_path_change`：`id` UUID 主键；`person_id` UUID 非空外键指向 `resource_person.id`（ON DELETE CASCADE）；`actor_id` UUID 可空外键指向 `app_user.id`（ON DELETE SET NULL）；`actor_name` VARCHAR(255) 非空保存操作人姓名快照；`changes` JSON 非空，按字段键保存 `{before, after}`；`created_at` TIMESTAMP 非空，使用业务 UTC+8 本地时间生成，接口带 `+08:00`。索引 `ix_talent_path_change_person_time(person_id, created_at, id)`。使用 `tools/apply_talent_path_history_migration.py` 显式幂等创建，不启用启动自动迁移。

路径窗口 PATCH `/talents/{id}/path-fields` 只允许人才编号、姓名、三种区域信息、路径及既有联系方式字段；`changes` 与 `expected_values` 字段集合须相同，逐字段核对原值防止并发覆盖，仅写入实际改动并与修改记录同事务提交。联系方式编辑及历史明文继续仅超级管理员可用，非授权用户历史值遮罩。GET `/talents/{id}/path-history` 分页查看本窗口自功能启用后的修改记录，不生成历史补记。

## 资源开拓扩展账号（2026-10-26）

新增表 `resource_development_resource_contact`，以 `record_id`（UUID）为主键及指向 `resource_development_record.id` 的外键，删除记录时级联删除扩展账号。`whatsapp` 为 VARCHAR(100)，非空默认空串；`custom_accounts` 为 JSON，非空默认空数组，元素为 `{name, value}`，名称最多 50 字、账号最多 100 字，每条开拓记录最多 30 个自定义账号，名称忽略大小写去重。旧客户端未提交时保留既有值，显式空值清空。保存与开拓记录处于同一事务，修改记录写入现有审计表（entity_type=`record_contacts`）。权限与资源手机、微信号一致；无权访问时账号值遮罩，账号检索限本人或有代录权限者。原记录表不增加列，不更改历史数据。使用 `tools/apply_resource_development_contacts_migration.py` 显式幂等初始化，不在启动时自动迁移。

人才总库“路径登记”复用 `resource_person.resume_path`，去除首尾空格、制表、换行及全角空格后非空为“有”，NULL、空串及纯空白为“无”；不检查文件或 UNC 的实际存在性，无结构变更。接口 field_filters 字段 `resume_path_registered`，布尔 eq，统一用于列表与总数。

## 资源需求三类发送说明（2026-10-26）

复用 `resource_request.request_content` JSONB 的 `dispatch_notes` 对象；`circle`、`post`、`development` 分别保存发圈需求、发帖需求、资源开拓需求管理的可选说明，每项最长 10000 字，默认空字符串，无新增表、列或数据库迁移。旧客户端未提交的说明保留原值，显式空字符串清空对应说明。发送批次继续冻结完整 `request_content` 快照，接收人查看本次对应类型的说明，后续修改不回写历史通知。


### chat_discussion_mention（讨论提及关系，2026-10-27）

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| message_id | BIGINT，联合主键，外键 | chat_discussion_message.id；随消息删除级联 |
| user_id | UUID，联合主键，外键 | 被提及的有效用户；发送者自动排除 |
| user_name | VARCHAR(255) | 发送时的被提及姓名快照 |
| is_all | BOOLEAN | 是否由 @所有人 展开；仅当前会话有效成员 |
| notification_id | UUID，可空、唯一、外键 | 对应 app_notification.id；通知删除后置空 |

索引：ix_discussion_mention_user_message(user_id, message_id)。讨论消息本身不改结构，纯文本 @ 不产生记录；撤回消息不进入 @我 和未读统计。新增通知类型 discussion_chat_mention 归入聊天提醒。项目群及私聊沿用 chat_project_mention，并在消息 event_data.mention_all 标记全体提醒，无须修改已有表。


### 讨论消息操作与总结来源（2026-10-27）

- `chat_discussion_message_action`：复合主键 `message_id`（讨论消息 bigint 外键）、`user_id`（用户 UUID 外键）；`user_name` 为人员快照，`favorited_at`、`acknowledged_at` 为 UTC+8 带时区时间。收藏按用户隔离，收到回执仅当前会话成员可读。
- `chat_discussion_issue_source`：`issue_id` 为总结 UUID 主键及外键，`room_id` 为会话 UUID（索引），`message_id` 为讨论消息 bigint 外键，`category` 为收录类别；`message_id + category` 唯一，防止重复保存。保留既有总结来源枚举结构不变，讨论来源通过此表识别，接口返回真实 `discussion` 来源及消息编号。聊天撤回后保留已保存总结快照，但跳转原消息受当前成员权限和撤回状态约束。
- 迁移：`tools/apply_discussion_actions_migration.py` 仅幂等创建上述新表及必要约束、索引，不更改已有表。


### 项目技术需求（2026-10-27）

- `annotation_technical_room`：`project_id` 为标注项目 UUID 主键/外键，每项目一个独立技术会话；`room_id` 为独立讨论分类 UUID 唯一外键。`requirements` 是可编辑的需求汇总，`revision` 为乐观锁版本；`created_by/updated_by`、`created_at/updated_at` 记录人员与 UTC+8 带时区时间。默认加入点击者、当前项目经理、黎涛/黄萌/伟豪/赵震锋以及 IT 部全体现有有效员工；额外人员从有效员工目录多选。实际访问仍校验讨论成员。
- `annotation_technical_append`：`id` UUID 主键；`room_id` 技术会话 UUID 外键，`request_id` 与会话联合唯一，`message_id` 为来源讨论消息 bigint 外键，`created_by/created_at` 记录加入人和 UTC+8 时间。追加请求重试不重复写入；不同段落之间使用空行。
- 迁移 `tools/apply_technical_requirements_migration.py` 仅幂等创建上述两表及必要索引、约束，不修改已有表。

### 聊天电脑在线共享心跳（2026-10-28）

- `chat_desktop_heartbeat`：`user_id`（UUID）、`client_id`（UUID）组成主键，每个电脑页面独立租约；`sequence` 为递增请求序号，防止乱序心跳覆盖退出状态；`active` 表示页面是否主动结束；`last_seen_at` 为服务端生成的 UTC+8 带时区心跳时间，设时间索引。
- 电脑端独立 HTTP 心跳每 25 秒上报，WebSocket 心跳及恢复前台可触发补报；最近 120 秒内任何一条有效电脑租约或当前进程实时电脑连接存在即显示在线。已观察租约全部失效显示离线；从未观察或共享表未初始化时显示未知。手机不写入电脑租约。
- `tools/apply_chat_presence_migration.py` 幂等创建新表与索引，不修改已有表及业务数据；常驻服务不自动迁移。
- 2026-10-28 检测补充：后端自动从已鉴权的电脑 WebSocket 连接采集共享租约，建立、存活检查、断开分别更新，不要求旧前端实现 HTTP 心跳；Uvicorn 协议层 ping/pong 持续核对连接。独立 HTTP 心跳仍提供补偿，页面 pagehide 与退出登录前通过 keepalive 上报结束；每个连接/页面独立编号，关闭其中一个不使其他在线连接离线。无任何采集来源时仍为未知，不用登录时间、排班或未读状态推算电脑在线。


### weekly_shift_publication（周班次已同步快照，2026-10-28）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| week_start | date，主键 | 自然周周一；跨月周共用同一主键 |
| assignments | JSON | 已同步的人员、部门、班次及固定标记；不叠加实时草稿或固定配置 |
| revision | integer | 同步版本，从1递增 |
| draft_revision | integer | 本次同步所对应的 weekly_shift_draft.revision |
| editing_enabled | boolean | 是否已点击“同步后修改”；同步完成后关闭 |
| published_by | UUID | 同步操作人 |
| published_at | timestamptz | 实际同步时间，接口明确为 UTC+8 |

weekly_shift_plan 保留既有字段和兼容公开语义；行政管理草稿独立保存在 weekly_shift_draft，只有手动同步才更新旧公开表。停止操作400毫秒后保存草稿；GET /monthly-shifts/weekly/overview 与 /weekly/mine 只读取本快照，未同步的周返回空安排。固定配置变更只影响管理草稿，不自动更新已同步快照。考勤周安排同样读取已同步快照。同步成功后向全部在用人员广播 weekly_shift_published，工作台按所查看周期刷新，无新增高频轮询。

### weekly_shift_audit（周班次修改记录，2026-10-28）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | UUID，主键 | 修改记录标识 |
| week_start | date，非空 | 所属自然周周一 |
| action | varchar(32) | draft_save、enable_edit、publish、copy、move、swap |
| revision | integer | 当时的草稿版本 |
| publication_revision | integer，可空 | 对应同步版本；为空表示尚未同步，不对普通人员公开 |
| changes | JSON | 人员姓名与逐人修改前后部门、班次、固定标记；不含请假详情 |
| actor_id / actor_name | UUID / varchar(255) | 操作人与当时姓名快照 |
| created_at | timestamptz | 实际操作时间，接口 UTC+8 |

索引 ix_weekly_shift_audit_week_time(week_start, created_at)。修改记录按周分页；行政人员可查看未同步记录，全部人员工作台仅可查看 publication_revision 非空的记录。POST /weekly/sync 校验草稿版本、同步版本和固定配置版本；POST /weekly/enable-edit 开启同步后修改。草稿无实质变化不重复递增版本或写审计。复制、转移、互换仅改变草稿，必须再手动同步。

tools/apply_weekly_shift_publication_migration.py 只幂等创建 weekly_shift_draft、weekly_shift_publication、weekly_shift_audit 三张新表及其索引；不改变旧表、不初始化发布现有排班，不在服务启动时迁移。

### weekly_shift_draft（独立周排班草稿，2026-10-28）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| week_start | date，主键 | 周一，跨月共用 |
| assignments | JSON | 尚未发布的排班草稿，不供工作台读取 |
| revision | integer | 草稿乐观锁版本；首次从旧公开表编辑时沿用其基线再递增 |
| updated_by | UUID | 最近草稿修改人 |
| updated_at | timestamptz | UTC+8 实际修改时间 |

新草稿、复制、转移和互换均只写本表。尚无独立草稿时，管理端只读旧 weekly_shift_plan 作为编辑基线，不自动复制或改写历史记录。手动同步同时发布快照并更新旧公开表，以免尚未升级的工作台读取到未同步的编辑。同步新建草稿基线属于用户主动同步动作，不由迁移脚本执行。


### 周末值班独立保存与同步（2026-10-28）

四张新表由 tools/apply_weekend_duty_management_migration.py 幂等创建；不在启动时迁移，不初始化发布历史数据，不改变已有表结构。

| 表 | 字段 | 类型与语义 |
| --- | --- | --- |
| weekend_duty_draft | month / assignments / revision | date 主键（每月首日）/ JSON 逐人逐日安排与固定标记 / integer 乐观锁版本 |
| weekend_duty_draft | updated_by / updated_at | UUID 最近修改人 / timestamptz UTC+8 实际时间 |
| weekend_duty_publication | month / assignments / revision / draft_revision | date 主键 / JSON 同步时完整快照 / integer 同步版本及对应草稿版本 |
| weekend_duty_publication | editing_enabled / published_by / published_at | boolean 同步后锁定、点击“修改”解锁 / UUID 同步人 / timestamptz |
| weekend_duty_audit | id / month / action / revision / publication_revision | UUID 主键 / date 月份 / varchar(32) draft_save、enable_edit、publish、copy、move、swap / integer 草稿版本 / nullable integer 同步版本 |
| weekend_duty_audit | changes / actor_id / actor_name / created_at | JSON 姓名与修改前后部门、日期、固定标记 / UUID / varchar(255) / timestamptz |
| weekend_duty_fixed_config | id / assignments / revision / updated_by / updated_at | integer 主键1 / JSON current 与按 effective_from 记录的 versions / integer 配置版本 / UUID / timestamptz |

索引 ix_weekend_duty_audit_month_time(month, created_at)。固定配置的 weekdays 使用 Python 周序号5（周六）、6（周日），配置自香港时间当天生效。旧日期沿用相应历史配置。固定生成结果只影响管理端待同步内容；工作台和考勤只读取 publication 快照。

停止操作400毫秒后 PUT /monthly-shifts/weekend-duty 只写独立草稿与私有审计，GET 保留无草稿时只读旧 weekend_duty_plan 的基线兼容。POST /weekend-duty/sync 校验草稿、发布与固定配置版本后更新快照及旧公开表，并广播 weekend_duty_published；同步后表单锁定，POST /weekend-duty/enable-edit 开启修改。修改记录随同步向全部在用人员公开，未同步审计仅行政可见。

POST /weekend-duty/transfer 将来源周六、周日对应到目标周六、周日。跨月时原子校验并锁定所有涉及月份与固定配置；只替换目标日期的非固定安排，保留其他日期和固定安排。操作本身不发布，需分别同步涉及的月份。


### attendance_clock_session（手动分段打卡及确认，2026-10-28）

由 tools/apply_attendance_clock_migration.py 仅创建新表，不改变 attendance_day / attendance_leave，不回填历史数据。上班打卡由本人阅读早餐提示后主动完成；登录与 /attendance/arrival 不再写入上班打卡。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | UUID 主键 | 打卡段标识，下班确认必须传本人记录ID |
| user_id | UUID 外键 app_user.id | 所属人员，接口从登录身份取得 |
| day | date 非空 | UTC+8 上班打卡所属业务日期；跨日下班仍归此日 |
| segment | integer 非空 | 普通班次0；客户部居家白天0、晚间1 |
| check_in / check_out | timestamptz | 服务端实际时刻；重复点击保留首次值 |
| shift_snapshot | JSON | 打卡时班次、固定标记、完整时段和本段时段、clock_policy=manual-v1 |
| confirmations | JSON | 早餐提示确认、提前到达是否工作、早餐后打卡确认、晚餐选择、是否扣无效时间、分钟数和原因、确认时间；兼容本人主动延续的旧记录ID |
| created_at | timestamptz | UTC+8 创建时间 |

唯一约束 uq_attendance_clock_segment(user_id,day,segment)，索引 ix_attendance_clock_user_day(user_id,day)。服务端按人员事务锁串行处理，不能代他人打卡，手机端不得上下班打卡。未填写必需的是/否确认不得签退。

客户部居家班次白天包含10:30–12:00、13:30–18:00，晚间21:00–23:00单独打卡；两段不得重叠，第一段签退且预定结束后才能开始第二段。居家班不扣晚餐。固定班次普通单段每天扣20分钟，不与晚班、晚晚班的晚餐选择重复扣。其他晚班、晚晚班选择有进食晚餐扣20分钟，选择无则不扣。

提前于本段预定开始的有效时间，仅在本人签退确认已工作时计加班。加班排除午休、班间休息和请假。确认早餐前打卡则抵扣15分钟并记违纪一次。居家无效时间必须填写正数分钟及说明，从加班扣除。每日净额允许负值，用于同人同自然月抵扣；月累计最低0，尚余抵扣单独显示，不抵扣他人或跨月累计。原额、早餐、晚餐、无效时间和净额在查询时逐项返回，不隐藏抵扣过程。

新旧记录按人员日期去重；旧已完成记录保留原有计算语义，无确认数据不追溯补扣。旧未签退记录仅在本人主动打卡事务中延续并保留来源ID。个人 GET /attendance/mine 仅使用当前登录人ID；公司 GET /attendance/report 使用行政权限。两者共用计算，无自动绩效扣款动作。


### employee_employment（人员入职时间及年度年假额度来源，2026-10-28）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| user_id | UUID 主键、外键 app_user.id | 人员唯一对应，不修改 app_user 既有表结构 |
| hire_date | date 可空 | 组织架构—人员管理的“入职时间”，纯 UTC+8 业务日期；缺失不推定 |
| updated_at | timestamptz 非空 | 最后修改实际时刻，使用 UTC+8 业务时钟 |

由 tools/apply_employee_employment_migration.py 幂等创建新表，只创建新表及必要主外键，不回填现有人员入职日期。人员新增、编辑时与 AppUser 的变更共用事务；不传 hire_date 保持现值，显式 null 清空。仍遵循 system:users:write 权限。

现行公司年假额度规则：6月30日及以前入职，首年1天；7月1日起入职，首年0天。此后每满一个入职周年，再过3个月增加1天，不按1月1日统一增加。先计算周年日期，再顺延3个月；若目标月无对应日则取月末，闰日非闰年周年取2月末后再顺延。上限10天；未来尚未入职时0天；缺失日期时返回 null 并提示填写。

例如2025-06-30入职，2026-09-29额度1天，2026-09-30额度2天；2025-07-01入职，2026-09-30额度0天，2026-10-01额度1天。额度为年度可享天数，不代表扣除已休年假的余额，未从普通请假原因文字猜测年假使用量。

人员接口以批量读取补充 hire_date、annual_leave_year、annual_leave_days、annual_leave_next_increase；年假额度为按业务日实时推导的只读字段，不另存可被修改的计数。考勤个人接口只带当前人员额度，公司接口在权限内按人员返回。当前年份按当前 UTC+8 业务日计算，历史年度按该年12月31日计算。界面规则说明与表单即时预览采用同一算法，覆盖月底、闰年、首年、周年延迟及封顶边界。


### home_office_qualification / home_office_application / home_office_annual_usage（居家办公，2026-10-28）

三张新表由 tools/apply_home_office_migration.py 幂等创建，不改变已有表，不初始化历史居家天数。资格申请和日期申请只保存待审批并通知，审批操作待开发。

| 表 | 字段 | 类型与语义 |
| --- | --- | --- |
| home_office_qualification | id / client_id / user_id | UUID 主键 / UUID 唯一幂等标识 / UUID 外键 app_user |
| home_office_qualification | reason / status / approver_id / created_at | Text 必填理由 / varchar(24) pending / UUID 指定总经理 / timestamptz |
| home_office_application | id / client_id / user_id | UUID 主键 / UUID 唯一幂等标识 / UUID 外键 app_user |
| home_office_application | requested_date / reason / status / created_at | date 每次1个工作日 / Text 可选说明 / varchar(24) pending / timestamptz |
| home_office_annual_usage | user_id / year | UUID 外键 app_user + integer 联合主键 |
| home_office_annual_usage | used_days / revision / history | integer 普通居家系统外历史天数，可0，可据实记录超额 / integer 乐观锁 / JSON 补录前后、原因、操作人及UTC+8时刻 |
| home_office_annual_usage | updated_by / updated_at | UUID 外键 app_user / timestamptz |

索引 ix_home_office_qualification_user(user_id,created_at)、ix_home_office_application_user_date(user_id,requested_date)，唯一约束 uq_home_office_user_date(user_id,requested_date)。按人员事务锁串行校验，年度补录与申请使用相同锁，不能通过并发越过额度。

资格：按入职日期顺延日历月，满3个月可提交资格申请，理由必填，批准人为行政部职务“总经理”的赵震锋；满6个月自动有资格。资格申请待审批不视为获批，满6个月自动资格不依赖审批状态。缺入职日期提示填写，不推定资格。tools/configure_home_office_approver.py 仅按用户明确指令配置赵震锋的行政部总经理职务，先唯一匹配在用姓名与行政部，保留其他部门成员、主部门及职务，不更改系统角色。

普通居家额度：按自然月最多2次、自然季度4天、自然半年8天、自然年最多12天，待审批和已批准申请均占用额度。自然季度为1–3月、4–6月、7–9月、10–12月，半年为1–6月、7–12月。年度额度按入职满3个月之后在该年剩余月份折算：一个月覆盖至少20个日历日计1天，不足20日不计；完整年度最多12天。多个上限同时达到时全部提示并阻止新增申请。用户已明确自然年口径，不附加滚动12个月上限。

年度占用＝行政补录的普通居家系统外历史天数＋系统内待审批/已批准日期申请。补录不得重复包含系统已有日期申请，不包含公司要求居家加班；只有年度总数时不编造月、季度或半年分配。当前年度未补录时不能申请，须先登记实际数（含0天）；未来尚未发生的年度按历史数0预留申请。历史超额可据实补录，后续申请一律禁止。补录只允许行政部编辑当前年，记录每次修改，提交后推送 home_office_usage_changed 刷新本人工作台。个人接口只读本人，行政接口可看全体及最近500条申请。

普通有居家申请的日期，打卡快照标记 home_office_day；包括待审批日期也要求签退真实工作声明，但不因此授予资格或批准申请。客户部居家晚班仍两段；其他普通居家按原班次，签退可填写扣除无效分钟及原因。

### 公司要求居家加班（attendance_clock_session.segment=2）

独立类型 work_mode=company_home_overtime，无需居家资格或普通居家申请，不写 home_office_application，不占上述月、季度、半年、年度及补录额度。打卡快照 overtime_only=true、home_office_day=true，实际已打卡时间扣除午休、请假及本人确认的无效时间后计加班；早餐前打卡仍执行既有15分钟抵扣及违纪规则。公司居家加班不出现“提前到达公司”确认，不借用普通居家日期审批状态。

同一日一组独立上下班打卡，不能与尚未结束的普通打卡同时开始，重复点击保留首次时刻。日报统计按实际时刻排序并保留普通班次身份，详细分段明确标识公司要求居家加班。人事管理居家区域另列公司要求居家加班打卡记录，不混入普通居家次数。

### attendance_delay_start（延迟上班申请，2026-10-28）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id / client_id | UUID 主键 / UUID 唯一 | 申请与幂等标识 |
| user_id | UUID 外键 app_user | 申请人，取当前登录身份 |
| requested_start | timestamptz | 预计上班时刻，接口必须带时区并转换为UTC+8 |
| reason | Text | 必填事由 |
| created_at | timestamptz | 实际申请时刻 |

索引 ix_attendance_delay_start_user_time(user_id,requested_start)。tools/apply_attendance_delay_start_migration.py 仅幂等创建本表，不改变其他表。手机和电脑可申请；提交与全体在用人员的业务铃铛、私聊通知同事务，失败回滚，成功提交后才推送；重试不重复通知。沿用请假全体通知通道。没有定义新的延迟批准流程，申请只留档，不自动改变原班次或免除迟到；本人及权限内公司考勤明细显示申请理由和预计时刻。

排班考勤移动端写入仅允许请假、延迟上班申请；打卡、居家资格、普通居家申请、年度补录及排班写入在服务端阻止手机请求。手机可查看有权限的只读信息。

### 工作报告中午加班（现有 DailyReportItem.display_metadata 扩展）

不增加或改变工作报告表结构，使用现有 JSON 字段：lunch_overtime boolean、lunch_overtime_confirmed boolean、lunch_start / lunch_end HH:mm。选择有后先确认“中午确实加班且未顺延下午上班时间”，再创建独立工作行；沿用项目类型、项目搜索、订单、任务、工作量、单位，行内明显标记中午加班。实际时段限定12:00–13:30，耗时必须等于结束减开始，不同项目午间时段不能重叠，服务端同样校验。

报告编辑及只读快照可按项目/订单多关键词筛选、仅看中午加班；筛选不丢弃保存行，校验先显示全部字段。Excel和邮件保留午间标记与时段，快照保留声明。报告确认后，仅与已完成上下班打卡时段重叠的午间分钟计回考勤加班；草稿不计，跨项目时段合并防重，保留原扣午休、计回及实扣明细。不改变13:30等原定下午上班时间，不因午间工作自动顺延。个人与公司考勤、月累计采用同一计算，每次查询推导，不重复写加班计数。
