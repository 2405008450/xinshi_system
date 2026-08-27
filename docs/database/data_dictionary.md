# 数据字典

> 目标结构快照：2026-08-27 中国标准时间；来源：ORM 与账号资产库迁移 DDL。部署后可再次运行 `tools/generate_database_docs.py` 以实际 PostgreSQL 为准复核。

## 阅读说明

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
| `sub_project_name` | `varchar(255)` | 可空 | — | 子项目名称 |
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
| `project_id` | `uuid` | FK → translation_project.id；非空 | — | 关联翻译主订单 |
| `sender_user_id` | `uuid` | FK → app_user.id；可空 | — | 消息发送用户 |
| `sender_name` | `varchar(255)` | 非空 | — | 发送人姓名快照 |
| `content` | `text` | 非空 | — | 正文内容 |
| `message_type` | `varchar(30)` | 非空 | `'user'` | 消息类型 |
| `content_json` | `jsonb` | 可空 | — | 结构化富文本内容 |
| `metadata` | `jsonb` | 可空 | `'{}'` | 消息扩展元数据 |
| `created_at` | `timestamp` | 可空 | `当前时间` | 创建时间 |
| `updated_at` | `timestamp` | 可空 | `当前时间` | 最后更新时间 |

表级规则：索引 `ix_chat_project_message_project_created_at`：`project_id`, `created_at`；索引 `ix_chat_project_message_sender_user_id`：`sender_user_id`。

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
| `effective_on` | `date` | 非空 | — | effective on |
| `changed_at` | `timestamp` | 非空 | `当前时间` | 业务时间 |
| `changed_by` | `uuid` | FK → app_user.id；可空 | — | changed by |
| `change_note` | `text` | 可空 | — | change note |

表级规则：CHECK：`from_status IS NULL OR (from_status::text = ANY (ARRAY['initial_consultation'::character varying, 'consultation_no_result'::character varying, 'resource_sourcing'::character varying, 'resource_sourcing_cancelled'::character varying, 'trial_preparation'::character varying, 'trial_in_progress'::character varying, 'trial_passed'::character varying, 'trial_failed'::character varying, 'trial_partially_passed'::character varying, 'project_in_progress'::character varying, 'sent_to_client'::character varying, 'client_feedback'::character varying, 'cancelled'::character varying, 'partially_cancelled'::character varying]::text[]))`；CHECK：`to_status::text = ANY (ARRAY['initial_consultation'::character varying, 'consultation_no_result'::character varying, 'resource_sourcing'::character varying, 'resource_sourcing_cancelled'::character varying, 'trial_preparation'::character varying, 'trial_in_progress'::character varying, 'trial_passed'::character varying, 'trial_failed'::character varying, 'trial_partially_passed'::character varying, 'project_in_progress'::character varying, 'sent_to_client'::character varying, 'client_feedback'::character varying, 'cancelled'::character varying, 'partially_cancelled'::character varying]::text[])`；索引 `ix_annotation_status_history_status_date`：`to_status`, `effective_on`；索引 `ix_annotation_status_history_timeline`：`project_id`, `effective_on`, `changed_at`。

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

表级规则：CHECK：`sequence_no > 0`；CHECK：`table_code::text = ANY (ARRAY['project'::character varying, 'account'::character varying, 'trial'::character varying, 'assignment'::character varying]::text[])`；CHECK：项目和账号字段的 `project_id` 必须为空，试标和正式安排字段的 `project_id` 必须非空；CHECK：`data_type::text = ANY (ARRAY['text'::character varying, 'number'::character varying, 'date'::character varying, 'datetime'::character varying, 'boolean'::character varying, 'single_select'::character varying, 'multi_select'::character varying, 'url'::character varying]::text[])`；索引 `ix_annotation_custom_field_sequence`：`project_id`, `table_code`, `sequence_no`；唯一索引 `uq_annotation_custom_field_scope_key`：`project_id`, `table_code`, `field_key`。

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
