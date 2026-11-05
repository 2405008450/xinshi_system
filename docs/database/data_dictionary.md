# 数据字典

## 客户对账单（2026-11-03）

- 笔译客户财务窗口新增“收费设置 / 对账单”页签；对账单支持当前项目（含所选订单的下级）或该客户整月全部笔译项目（包含子客户）。账单月份优先采用本订单已登记月份，其次沿用最近上级，最后沿用母订单编号月份；编号无月份时回退客户接单时间月份。来稿日期直接使用母订单客户接单时间，按UTC+8展示。
- 新表 `customer_statement_preference`：`client_id UUID` 主键/FK `client.id`（删除级联），`tax_included boolean not null`（默认false），`revision integer not null`，`updated_by UUID` FK `app_user.id`（删除置空），`updated_at timestamptz not null`（UTC+8）。客户财务信息中的“单价含税”即时保存；未勾选时对账单采用不含税口径，已明确登记的两种税口径金额不互相推算或覆盖。
- 新表 `customer_statement_settings`：`key varchar(30)` 主键（公司配置使用company），`bank_name varchar(255)`，`account_name varchar(255)`，`account_number varchar(100)`，`stamp_image text`（经图片解码校验、去元数据及尺寸限制后的PNG data URL；空值采用示例章），`revision integer not null`，`updated_by UUID` FK `app_user.id`（删除置空），`updated_at timestamptz not null`（UTC+8）。账户及印章由全部客户对账单共用。
- 设置和税口径修改使用版本校验防止覆盖；读取需要客户或项目查看权限，修改需要客户管理写权限。迁移入口 `tools/apply_customer_statements_migration.py` 只创建这两张表及必要约束，不修改既有表；服务自动迁移保持关闭。
- `/translation-statements/preview` 和 `/translation-statements/excel` 使用同一生成逻辑：表头为“广州信实翻译服务公司 / 对账单”，包含来稿日期、项目名称、翻译方向、工作量及计价方式、含税/不含税单价、小计和备注。固定收费不做数量乘单价；只对最下级收费项或固定收费订单计费，父级明确调价单独列出差额，避免重复累计母子订单。
- 金额以Decimal逐条四舍五入到分，按币种合计；缺少单价、工作量或所选税口径时标为待补，合计注明仅含已登记金额。导出Excel携带预览内容SHA256，数据或账户印章变化时拒绝下载并要求重新生成。Excel和打印版均将透明印章作为合计左侧的浮动图层叠盖表格线；账户名、账号保持文本，避免丢失前导零及公式注入。

## 四类项目客户财务入口（2026-11-03）

- 项目客户财务窗口统一提供笔译财务、口译财务、标注财务、招聘财务页签，默认打开当前项目类型。其他页签仅按当前客户编号查询对应类型项目，不将不同类型财务写入当前项目。项目管理板块均提供“财务管理（客户）”子板块。
- 标注和招聘接口 `/project-customer-finance/{module}` 复用项目报价及税口径附表；标注保存保持报价ID和语言范围，沿用下级继承与独立修改规则；招聘仅修改税口径金额及货币。按币种分别汇总不含税、含税总价，未填金额不视为零。项目详情版本SHA256控制并发覆盖。
- 新表 `project_customer_finance_history`：`id UUID` 主键，`module varchar(20)`（标注/招聘），`project_id UUID`（多类型项目编号），`order_no varchar(50)`，`actor_id UUID`（FK `app_user.id`，删除置空），`actor_name varchar(255)` 姓名快照，`before JSON`、`after JSON` 财务快照，`created_at timestamptz`（UTC+8）。模块及项目ID索引；仅金额发生变更时与项目同事务写入。项目ID不设置单表外键，以保留不同类型及已删除项目的历史快照。
- 可重复执行脚本 `tools/apply_project_customer_finance_migration.py` 只创建上述新表及索引、约束，不修改既有表；启动自动迁移保持关闭。

## 四类项目的税口径价格附表

显式迁移 tools/apply_project_tax_prices_migration.py 只新增下列四张表，不修改旧表、不回填历史金额。各附表 id 是主键与业务行外键，随业务行级联删除。税口径与原业务记录同事务提交，由原模块的版本校验和权限规则控制。

| 新表 | id 关联对象 |
| --- | --- |
| annotation_project_price_item_tax | annotation_project_price_item.id |
| recruitment_project_tax | recruitment_project.id |
| customer_annotation_rate_tax | customer_annotation_rate.id |
| customer_translation_rate_tax | customer_translation_rate.id |

四表共用字段：unit_price_excl_tax（不含税单价）、unit_price_incl_tax（含税单价），均 numeric(18,6)；total_excl_tax（不含税总价）、total_incl_tax（含税总价），均 numeric(18,2)。全部可空，NULL 表示未明确填写，不表示零税率。客户参考价只使用单价两项；项目总价不写入参考价，也不随参考价同步或子项目复制而复制。

笔译项目收费继续使用既有收费表内的四项税口径字段；口译财务在既有 payload JSON 的每条 rates/overtime/adjusted_totals 内保存 tax_prices。同币种按口径分别汇总，含税/不含税不能混算。不预设税率，也不从一侧推算另一侧。未说明口径的原金额继续保留，显示“税口径未确认”。同步预览与版本比较包含含税/不含税单价，单独调整过的项目价格保留。

笔译项目计价方式从当前订单已填写的客户/我司字数统计生成，零值视为已填写；唯一项自动采用，多项必须选择。预统计沿用“不用以计算费用”的约定，不进入计价选项；客户参考价没有具体项目数量时继续保留口径配置。

### 笔译客户财务计价模式与表单入口

计价模式默认 metric（按数量），固定收费为 fixed。fixed 使用既有收费表 total_excl_tax / total_incl_tax 直接保存两种一口价，单价、统计口径与计价单位为空；不乘数量、不由子订单金额求和，也不被客户参考单价自动下发覆盖。模式切换保留在原财务审计链路。

母订单、子订单及独立子订单管理表单均在字数统计下提供“客户财务”入口，复用客户财务窗口，移除表单里的客户收费明细。表单内财务修改先保留在本地表单，随项目或子订单主表单同事务提交；取消主表单不另建项目或提前落库。按数量时新增 API 字段 language_pair 与 quantity_basis，写入既有 translation_charge_direction、translation_charge_quantity_basis 表，恢复后仍使用同一语种方向与统计来源；未新增旧表列。

## 客户标注单价（customer_annotation_rate）

客户管理 → 财务信息 → 标注中维护的多条客户单价；标注类型复用标注项目类型，货币与单位复用现有结算目录。只保存客户报价，不自动修改项目报价。显式运行 tools/apply_customer_annotation_rates_migration.py 初始化，不在服务启动时迁移。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid | 主键 |
| client_id | uuid | 关联 client.id，删除客户时级联删除，带索引 |
| project_type | varchar(50) | 标注类型，对应标注项目类型枚举 |
| amount | numeric(18,6) | 大于零的单价金额，最多六位小数 |
| currency | varchar(3) | CNY/USD/HKD/EUR/GBP，新增默认 CNY 人民币 |
| unit | varchar(30) | 复用结算单位键，如 item 条、minute 分钟、hour 小时 |
| revision | integer | 从 1 递增的并发版本，编辑及删除校验 |
| updated_by | uuid | 最后修改人，关联 app_user.id |
| updated_at | timestamptz | 最后修改时间，接口返回 +08:00 |

同一客户、标注类型、货币与单位组合唯一，允许同一类型配置不同单位的单价。

支持在客户资料查看关联标注项目的报价差异并逐条引入。读取、引入均校验客户及项目查看权限，引入另需客户管理权限与显式确认。引入前核对来源项目、报价及客户单价版本；类型缺失、单位或货币无法对应时提示补全。支持元/条等历史单位映射，保留项目原报价；不自动向标注项目下发客户单价。

口译客户参考价不录入数量，保存时固定数量为 1，项目实际数量及历史记录保持原语义；方向下拉复用系统语言对，保留项目财务表单自身的方向限制。

## 客户合作信息（client_cooperation）

客户管理“合作信息”选项卡的大文本内容，随客户新增/编辑同事务保存，复用客户 updated_at 乐观锁，与基本信息备注独立。通过显式迁移 tools/apply_client_cooperation_migration.py 创建，不在服务启动时迁移。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| client_id | uuid | 主键、外键关联 client.id，删除客户时级联删除 |
| content | text | 合作信息正文，非空，默认空文本 |


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

### `daily_report_idle_declaration`

工作报告空闲时间与声明确认。仅新增此表，不回填历史报告；不计入工作任务耗时。手工保存、确认及一次修订接口要求明确填写分钟数并确认声明。修改前后内容随报告修订快照保留。

| 字段 | 类型 | 规则 | 说明 |
| --- | --- | --- | --- |
| report_id | UUID | 主键、FK → daily_report.id，删除时级联 | 一份日报一条声明 |
| idle_minutes | integer | 非空，0～1440 | 空闲分钟数（含洗手间等所有非工作时间） |
| confirmed | boolean | 非空，必须为 true | 本人明确勾选确认 |
| declaration_text | text | 非空 | 确认时的完整声明原文 |
| declaration_version | integer | 非空 | 声明版本，目前为 1 |
| confirmed_at | timestamptz | 非空 | 实际确认时刻，接口 UTC+8 |

显式建表脚本：`tools/apply_work_report_idle_migration.py`；启动自动迁移保持关闭。

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

班次优先取每周安排（含固定班次），其次月度；仅节假日/调休日历中的工作日或已安排周末值班的日期统计，无班次不推算迟到。未知年份日历明确报错。迟到时长为缺席的班次工作分钟减 15 分钟宽限，扣除合法请假与休息，超过才算一次；尚未签退不计算加班。加班为实际打卡区间扣除午休 12:00–13:30、其他班间休息和请假后的出勤分钟，减去班次应工作分钟（已扣合法请假），负数取零。每条记录、个人周/月和管理汇总使用同一计算函数。上班班次快照不受后续排班编辑影响。

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

客户部居家班次白天包含10:30–12:00、13:30–18:00，晚间21:00–23:00单独打卡；两段不得重叠，第一段签退且预定结束后才能开始第二段。所有班次（含居家及居家加班）签退超过原考勤日18:50均须本人确认晚餐；有则扣20分钟，无则不扣，18:50整及之前不扣，同一天最多一次；跨日以原考勤日为准，补卡以实际应补下班时间为准。

提前于本段预定开始的有效时间，仅在本人签退确认已工作时计加班。加班排除午休、班间休息和请假。确认早餐前打卡则抵扣15分钟并记违纪一次。居家无效时间必须填写正数分钟及说明，从加班扣除。每日净额允许负值，用于同人同自然月抵扣；月累计最低0，尚余抵扣单独显示，不抵扣他人或跨月累计。原额、早餐、晚餐、无效时间和净额在查询时逐项返回，不隐藏抵扣过程。

新旧记录按人员日期去重；旧已完成记录保留原有计算语义，无确认数据不追溯补扣。旧未签退记录仅在本人主动打卡事务中延续并保留来源ID。个人 GET /attendance/mine 仅使用当前登录人ID；公司 GET /attendance/report 使用行政权限。两者共用计算，无自动绩效扣款动作。


### employee_employment（人员入职时间及年度年假额度来源，2026-10-28）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| user_id | UUID 主键、外键 app_user.id | 人员唯一对应，不修改 app_user 既有表结构 |
| hire_date | date 可空 | 组织架构—人员管理的“入职时间”，纯 UTC+8 业务日期；缺失不推定 |
| updated_at | timestamptz 非空 | 最后修改实际时刻，使用 UTC+8 业务时钟 |

由 tools/apply_employee_employment_migration.py 幂等创建新表，只创建新表及必要主外键，不回填现有人员入职日期。人员新增、编辑时与 AppUser 的变更共用事务；不传 hire_date 保持现值，显式 null 清空。仍遵循 system:users:write 权限。

现行公司年假额度规则：6月30日及以前入职，首年1天；7月1日起入职，首年0天，次年1月1日先获得1天且只发放一次。所有人员此后每满一个入职周年，再过3个月增加1天；除上述首次元旦发放外，不按每年1月1日重复增加。先计算周年日期，再顺延3个月；若目标月无对应日则取月末，闰日非闰年周年取2月末后再顺延。上限10天；未来尚未入职时0天；缺失日期时返回 null 并提示填写。

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

### 人才联系资料与企微群状态

- 现有 `resource_person.wechat_groups` 继续保存原多行群名，界面名称改为“所在企微小群”，不自动重分类或改写历史文本。
- `resource_person.wecom_large_groups` TEXT 可空：所在企微大群，接口最多 4000 字，多行手动填写。
- `resource_person.residence_timezone` VARCHAR(12) 可空：人才所在地固定 UTC 偏移，如 `UTC+8`、`UTC+5:30`、`UTC+5:45`，范围 UTC-12 至 UTC+14。不修改业务时间或日志的 UTC+8 规范，不推断未登记人才时区。
- `resource_person.contact_availability` VARCHAR(30) 可空：`anytime` 随时可联系、`morning` 上午、`afternoon` 下午、`evening` 晚间、`weekday_daytime` 工作日白天、`weekend` 周末、`appointment` 需提前预约。单选、允许清空，按人才所在地时区理解，不推算具体钟点。
- 详情响应 `wecom_small_group_status` / `wecom_large_group_status` 只读派生，分别通过开拓记录 `person_id` 及归档来源关联读取 `group` / `group_large` 最近跟进状态；历史 `已邀进群` 映射为 `已拉群`。无关联记录返回空；有关联但无该渠道跟进则显示未处理。未知历史状态只显示自定义状态，避免泄露原文。不开辟状态副本，不反向修改开拓记录及业绩。
- 使用 `tools/apply_talent_contact_profile_migration.py` 幂等新增三个可空字段及 `ck_resource_person_contact_availability` 检查约束，保留所有现有值，不接入启动自动迁移。云端已有表结构调整须单独授权。

### 人才商务与结算

新增独立表 `talent_settlement`，不增加人员主表字段：`person_id` UUID 主键及外键指向 `resource_person.id`（ON DELETE CASCADE）；`revision` INTEGER 非空从 1 递增；`bank_account`、`paypal_account`、`payoneer_account` VARCHAR(255) 可空，保留前导零及原始账号；`wechat_payment_code`、`alipay_payment_code` TEXT 可空，沿用受权截图引用及长期业务截图存储；`invoice_available` BOOLEAN 可空（未登记/可开票/不可开票），`invoice_entity` VARCHAR(255) 可空（可开票时必填实际实体或名义）；`gig_platform_calculation` BOOLEAN 非空默认业务值 false，表示是否参与灵工平台计算，不在此功能中自动执行结算计算；`prices` JSON 非空、按用户顺序保存价格明细；`updated_by` UUID 可空外键指向 `app_user.id`（ON DELETE SET NULL），`updated_at` TIMESTAMP WITH TIME ZONE 非空，后端 UTC+8 生成。

价格明细每行：`id` UUID 稳定标识；`category` 为 `interpretation` 口译、`written_translation` 笔译、`annotation` 标注、`collection` 采集；`amount` 非负 Decimal，最多 18 位、6 位小数，JSON 保存十进制字符串；`unit` 非空、最多 50 字，提供系统既有次、条、工作小时、有效小时及字、千字、小时、天、秒、分钟、页、张、项目，可填写其他单位；`currency` 使用 CNY/USD/HKD/EUR/GBP。每档案最多 100 行，允许多条同类价格，不自动覆盖项目管理中的正式计价。

主档新增/编辑请求 `settlement` 为可选嵌套对象；不传或为 null 时保留原结算资料。提供时与主档在同一事务内保存，使用 revision 防止旧表单覆盖。沿用人才联系方式查看权限；受限请求不能读取或改写结算资料，普通主档编辑不会清空结算资料。核重不自动合并收款信息，原档案资料保留。协议状态仅界面标记“待开发”，不保存虚构协议数据。

该表已按新表创建授权于 2026-10-29 在 William 对 `43.132.156.72:15432/xinshi_system` 完成初始化。`tools/apply_talent_settlement_migration.py` 幂等创建新表及 `ck_talent_settlement_revision`、`ck_talent_settlement_invoice_entity` 约束，不更改已有表、不回填历史数据、不接入启动自动迁移。

### 人才评价自动署名与修改历史

`talent_evaluation_change`：`id` UUID 主键；`person_id` UUID 非空外键指向 `resource_person.id`（ON DELETE CASCADE）；`group_key` VARCHAR(40) 非空评价分区键；`actor_id` UUID 可空外键指向 `app_user.id`（ON DELETE SET NULL）；`actor_account` VARCHAR(255) 非空保存实际登录账号快照；`before_values` / `after_values` JSON 非空保存分区内各评价字段的原值与新值；`created_at` TIMESTAMP WITH TIME ZONE 非空，后端生成 UTC+8 时间，接口明确携带 `+08:00`。索引 `ix_talent_evaluation_change_person_group_time(person_id, group_key, created_at, id)`。

记录人才分级、标注总体评价、配合度、守时度、音频标注、非音频标注、采集、口译、笔译及三类专业能力评价；同一评价项目的评分与具体评价共用最新评价人/时间，历史保留实际变更字段。新增、编辑、核重合并及撤销中的评价变更均与业务保存使用同一事务；无变化不追加，清空也留痕。历史无署名数据显示“未记录”，不补造历史评价人和时间。客户端不能写入署名、时间或历史。

详情响应 `evaluation_meta` 提供各评价项目最新账号和时间；`GET /talents/{id}/evaluation-history?group_key=...&skip=0&limit=10` 分页返回原值、新值、实际账号、UTC+8 时间，归档来源历史只读汇总。使用 `tools/apply_talent_evaluation_audit_migration.py` 幂等创建新表并验证列；仅新表创建已按 2026-10-25 授权于 2026-10-29 在 William 对 `43.132.156.72:15432/xinshi_system` 完成。启动自动迁移关闭，其余已有表迁移继续待单独授权。

### 人才综合表现分区

原 `overall_score`（1–10 分）与 `overall_rating` 保留字段及历史值，界面移动到“标注”区域的音频标注表现之前；标注区域还含音频、非音频及采集表现。配合度、守时度不改变。

新增 `resource_person.interpretation_rating` INTEGER 可空，一至六星（1–6）；`interpretation_rating_note` TEXT 可空，口译说明；`interpretation_domains` TEXT 可空，口译领域自由文本；`written_translation_score` INTEGER 可空，笔译总体评价（1–10 分）；`written_translation_evaluation` TEXT 可空，笔译具体评价。口译区固定提示“四星以上为可担任大型会议交传与同传”，不自动变更人才专业能力、项目安排资格或历史评级。

五个新字段由人才总库维护，招聘端创建不写入、编辑不覆盖；新增及历史档案默认未评定。使用 `tools/apply_talent_performance_domains_migration.py` 幂等增加字段及 `ck_resource_person_interpretation_rating`、`ck_resource_person_written_translation_score` 检查约束；不改历史数据，不接入启动自动迁移。云端已有表结构调整须单独授权。

### 人才分级与档案状态

人才分级：`resource_person.talent_grade` VARCHAR(20) 非空，数据库及接口默认 `pending`（待评定），可选 `S`、`A`、`B`、`C`、`pending`。表单位于综合表现的总体评价之前，详情同步展示。新增字段时所有存量档案均默认为待评定，不根据评分推算等级。使用 `tools/apply_talent_grade_migration.py` 幂等添加字段及 `ck_resource_person_talent_grade` 约束；重复执行保留已评定等级。人才分级由人才总库维护，招聘端编辑不覆盖。属于已有表结构变更，云端执行需单独授权，禁止接入启动自动迁移。

`resource_person.status`（VARCHAR(20)，默认 `standby`）可选值按顺序为：`standby` 备用、`active` 活跃、`dormant` 休眠、`blacklisted` 黑名单、`pending_activation` 待激活、`under_observation` 待观察。历史 `inactive` 停用继续兼容读取和保存，但不再提供下拉选项。能力状态 `resource_capability.status` 保持原有取值。使用 `tools/apply_talent_status_migration.py` 在事务内幂等更新 `ck_resource_person_status`；不改历史数据，不接入启动自动迁移。此操作修改已有表约束，云端执行须单独授权。

### 工作报告中午加班（现有 DailyReportItem.display_metadata 扩展）

不增加或改变工作报告表结构，使用现有 JSON 字段：lunch_overtime boolean、lunch_overtime_confirmed boolean、lunch_start / lunch_end HH:mm。选择有后先确认“中午确实加班且未顺延下午上班时间”，再创建独立工作行；沿用项目类型、项目搜索、订单、任务、工作量、单位，行内明显标记中午加班。实际时段限定12:00–13:30，耗时必须等于结束减开始，不同项目午间时段不能重叠，服务端同样校验。

报告编辑及只读快照可按项目/订单多关键词筛选、仅看中午加班；筛选不丢弃保存行，校验先显示全部字段。Excel和邮件保留午间标记与时段，快照保留声明。报告确认后，仅与已完成上下班打卡时段重叠的午间分钟计回考勤加班；草稿不计，跨项目时段合并防重，保留原扣午休、计回及实扣明细。不改变13:30等原定下午上班时间，不因午间工作自动顺延。个人与公司考勤、月累计采用同一计算，每次查询推导，不重复写加班计数。


### 人才身份证号码、视力与分区样音

`resource_person.identity_number` VARCHAR(50) 可空，在姓名与身份区域编辑，沿用受限资料权限及脱敏；保留前导零、字母，不自动推导生日、性别，不作为联系方式查重依据。`resource_person.eyesight` VARCHAR(255) 可空，基本信息区域自由填写裸眼、矫正或左右眼情况。`tools/apply_talent_identity_migration.py` 幂等新增两列，不回填历史；属于已有表变更，尚未执行，继续待单独授权。

口译及标注区域上传样音复用现有 `resource_person_attachment`，新增分类 `interpretation_sample` / `annotation_sample`；原 category 列 VARCHAR(30) 可容纳，无表结构变更。音视频原样保存，每区域最多10个、单个200MB；支持 MP3/WAV/M4A/AAC/FLAC/OGG/OPUS/WMA/AMR/AIFF 等音频与 MP4/MOV/MKV/AVI/WMV/WEBM/MPEG/3GP/FLV/RMVB 等视频。上传后按各自区域展示，提供浏览器播放及下载；不进行转码，浏览器缺少相应解码器时提示下载。新增状态先选择文件，保存主档后逐条上传，显示进度；已成功文件及时出队，失败保留以便重试，沿用附件权限、归档留存和删除清理。

照片细分补充：附件分类新增 `id_photo`（证件照）、`life_photo`（生活照），复用 `resource_person_attachment.category` VARCHAR(30)，无表结构变更；每类最多10张，JPG/JPEG、PNG、WebP，单张10MB。新增及编辑提供独立上传区和已保存列表，详情按分类展示。原 `photo` 数据保留为“未分类照片（历史）”，不猜测或回写旧照片类别；原音频及专业样音分类不变。

### 人才结构化经历、CAT 与多语言简历

`talent_resume_profile` 新表：`person_id` UUID 主键且外键关联 `resource_person.id`（级联删除）；`revision` INTEGER 非空且 >=1，保存时校验版本避免覆盖；`data` JSON 非空；`updated_by` UUID 可空外键关联 `app_user.id`；`updated_at` TIMESTAMP WITH TIME ZONE 非空，由后端生成 UTC+8 时间。主表保存与扩展资料同一事务。

JSON 的 `internships`、`annotation`、`interpretation`、`translation`、`other` 为经历数组（每类最多100条），每条含 UUID `id`、自由文本 `period`（起止年月日/年月，100字）、`organization` / `position`（255字）及 `description`，两行表格编辑。旧自由文本进入首条说明，不推测单位或日期；保存结构化工作经历时同步原主表摘要，以兼容列表和旧导出。`cat_tools` 为最多50项去重工具名，笔译区提供 Trados Studio、memoQ、Phrase TMS、Wordfast Pro、Smartcat、OmegaT 并允许补充。

中文教育经历继续使用原教育子表，增加初中、高中、小学、中专/职高、其他的字符串枚举；已有列无数据库检查约束，无需结构变更。第一行起止年月日、学校、专业、学历，第二行学习说明（原 remarks），旧毕业年份、院校分类、专业分类、辅修、学位保留。时间段通过新表 JSON `education_periods` 按原子表 ID 记录；不增加旧子表字段。

`versions` 以 `en` 或外文语言代码索引独立简历：姓名、称谓、性别、出生日期、国籍、所在地、成长地、职业、学历、身高、视力、语言、证书、技能、CAT、教育、实习及四类工作经历。简历页签提供中文、英文、31种外文（包括阿拉伯语及东南亚语言）；字段标题中文/English，下拉选项按所选语言显示，阿语、波斯语、希伯来语输入方向 RTL。编号、联系方式、档案状态、项目、评价与结算仍为共用业务资料，不复制到语言版本。后端拒绝语言版本中的业务字段，不自动翻译或复制中文内容。

`tools/apply_talent_resume_profile_migration.py` 幂等建表，通过隔离 SQLite 测试后，按 2026-10-25 新表授权，于2026-10-29 在 William 对 `43.132.156.72:15432/xinshi_system` 执行并校验通过；启动自动迁移关闭，无已有表结构或历史数据变更。

人才总库“新增人才”右键打开快速登记；左键保留完整新增。快速登记采用一人一行的可编辑表格，支持逐行或按数量增加（最多100行）、行内删除；列为所选1～2种姓名、1～2种联系方式（邮箱属于可选类型）、守时度及配合度。逐行保存，成功行移除、失败行保留内容和错误提示；每行独立维护幂等请求键，网络失败后重试不会受其他行保存影响。隐藏字段不提交；必填及邮箱格式校验、联系方式权限、核重与评价自动署名均复用已有能力，无数据库变更。完整新增/编辑表单“其他名字”使用直接输入的文本框，多个名字可换行，仍以原数组字段保存，兼容历史多个别名。

标注经历字段补充：`talent_resume_profile.data.annotation[]` 及各语言 `versions[locale].annotation[]` 增加可空 `workload`（最多255字，去除首尾空白），自由输入数量及单位，如“5000条 / 100小时”。界面将原 organization / position 标题改为“甲方/服务单位”/“标注类型”，不改存储键、不重写旧经历；保存中文标注经历时工作量一并进入原主表标注经验摘要，详情及多语言简历同步展示。复用现有 JSON，无表结构迁移。

简历年份：`talent_resume_profile.data.resume_year` 对应中文版本，各外文版本使用 `versions[locale].resume_year`；可空文本，最多50字，去除首尾空白，留空不自动填写年份。新增/编辑窗口的区域折叠按钮栏右侧直接输入，详情同步显示；按版本独立保存，可清空，省略字段不覆盖已有值。复用现有 JSON，无表结构迁移。

### 开拓须知

人才资源导航在“推荐拓展”右侧新增“开拓须知”，页面路径 `/resource-management/development-notices`，API 使用 `/project-notices/development`。复用笔译等须知的三级栏目、分组、卡片逐级进入、富文本正文、搜索、排序、删除及附件组件；内容以独立新表保存，不扩充或修改原项目须知表的 module 约束。已登录用户可查看，持 `talents:write` 或 `translators:write` 者可管理栏目、正文与附件，前后端一致；原笔译、口译、招聘须知仍沿用 projects 权限。

`development_notice_section`：`id` UUID 主键；`module` VARCHAR(20) 非空且固定 development；`section_key` VARCHAR(80) 非空唯一；`title` VARCHAR(100) 非空；`parent_id` UUID 可空，复合外键 `(module,parent_id)` 指向同表 `(module,id)`，RESTRICT；`sort_order` INTEGER 非空；`has_content` / `is_active` BOOLEAN 非空默认 true；`content_json` JSONB 可空；`search_text` TEXT 非空默认空；`updated_by` UUID 可空外键 app_user.id，SET NULL；`updated_at` / `structure_updated_at` TIMESTAMP WITH TIME ZONE 可空，写入及接口明确 UTC+8。唯一约束 `(module,id)`、索引 `(module,parent_id,sort_order)`；沿用事务级结构锁、正文与结构版本校验、软删除。

`development_notice_attachment`：`id` UUID 主键；`section_id` UUID 非空外键栏目表并索引；`original_name` VARCHAR(255)、`storage_name` VARCHAR(80) 唯一、`content_type` VARCHAR(255)、`file_size` INTEGER 非空（0<大小<=20971520）；`uploaded_by` UUID 可空外键 app_user.id，SET NULL；`uploaded_at` TIMESTAMP WITH TIME ZONE 非空，生成和返回 UTC+8。每栏目最多50个、单个20MB；格式与其他须知相同，文件目录为 PROJECT_NOTICE_UPLOAD_DIR/development，默认 data/project_notice_uploads/development。保留路径校验、栏目归属、权限、事务与文件清理行为。

`tools/apply_development_notices_migration.py` 幂等创建两张新表及必要约束索引；隔离测试通过后，按2026-10-25新表授权，于2026-10-29在 William 对 `43.132.156.72:15432/xinshi_system` 执行并校验通过。原表和历史内容未修改，启动自动迁移关闭。


## 迟到折算、补班与调休（2026-10-29）

- `attendance_comp_time_request`：新增调休申请与提交时分配快照表，不改动既有考勤/请假表。

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| id | UUID PK | 申请标识 |
| client_id | UUID UNIQUE | 重试幂等标识 |
| user_id | UUID FK app_user.id | 申请人 |
| start_at / end_at | timestamptz | UTC+8 调休时段 |
| minutes | integer | 按应出勤班次计算、向上取整的预留分钟 |
| reason | text | 必填事由 |
| status | varchar(20) | 当前仅可提交 pending；批准流程待开发 |
| allocation_snapshot | JSON | 提交时累计值班、每次请假补班来源及既有调休预留、所选班次快照；不嵌套历史申请快照 |
| created_at | timestamptz | UTC+8 提交时间 |

- 索引 `ix_attendance_comp_time_user_start (user_id, start_at)`。迁移 `tools/apply_attendance_comp_time_migration.py` 幂等只建新表及必要约束索引，关闭启动自动迁移。
- 迟到从原15分钟宽限后统计，扣除已请假/休息，按 `late:<clock UUID>` 派生可追溯请假来源；与 `AttendanceLeave` 主动申请来源区分，不复制生成正式请假或群发通知。报表请假总额=申请请假+迟到折假，保留各次来源及区间，不双扣。
- 自然月按同人加班净额判断：≤600分钟免追责1次，>600且≤1200分钟免3次，>1200分钟免5次；超过的每次迟到在年终奖区域记录打卡来源。当前月暂计并随月净额更新，已过月按现有记录重算，不是锁定结算。年终奖计算/兑现待开发，不自动罚款。
- 自入职月起累计到当前月；入职首月剩余自然日（含入职当天）≤15天免该月1天值班基数，不计平均月份分母。实际累计周末值班天数/计入月份数>1才可申请调休。首月免基数时该月实际值班都作多值班；其余月首个实际值班日作1天基数，后续按日期作多值班。
- 仅已完成打卡、班次快照 `weekend_duty=true` 的周末值班，含居家；扣除休息、请假和已确认无效时间后按实际班次内分钟计算。同日合并；客户居家两段均完成才计1天。公司居家加班 `overtime_only`、未签退、法定节假日、调休工作日不计普通周末额外值班；未知日历年份不生成此额度。
- 申请请假（含已提交的未来请假）及迟到折假按日期FIFO先占多值班分钟，再分配已有待审批/已批准调休；同一来源分钟不重复分配。列表明确每次请假已补、待补以及对应值班日期。历史额度变化导致已申请额度不足时显示缺口，须后续批准流程复核。
- 调休仅本人电脑端提交，用户锁串行化、客户端幂等、校验未来时段/既有请假和调休重叠/应出勤时长/可用额度。pending预留，不生成已批准EmployeeLeave，也不免除打卡。人事公司视图受HR权限保护，个人只看自己。
- 节假日值班区域先展示“100元/天补贴+调休，待开发”；不生成节假日补贴或节假日调休记录。
- 历史值班只据系统实际记录，不推算系统外记录；入职时间缺失不授予调休额度。界面汇总和详情明确规则与来源。

- 补充：无值班的累计月份亦须补足每月1天基数，多值班先抵累计缺额，再抵请假、再预留调休，界面逐项显示基数用途。本人可撤回pending申请，保留原快照及cancelled_at/cancelled_by、释放预留；正式请假也校验与调休申请的时段冲突。


## 请假年假优先抵扣与调整审计（2026-10-29）

- 自然年按请假实际发生日期FIFO优先抵扣已生效年假，含申请请假及迟到折算；按本日完整班次分钟折算一天，不固定假定8小时。未来请假单独预留，不能提前使用周年再过3个月尚未生效的新增额度；跨年申请逐日分别归属，不将整张申请重复扣除。
- 年假不足部分仍待补班；人事可整次改为不扣年假而扣工资，或恢复年假优先。已抵年假/明确扣工资的时间不再补班。工资先记录时长，不推算薪酬金额。调整释放额度会按时间顺序供其他请假重新分配。入职时间或班次缺失不猜测，标为待完善。自动分配源于真实持久化请假/打卡，不复制伪造正式请假单。
- `attendance_leave_settlement`：`source_key varchar(64) PK`（application:请假UUID 或 lateness:打卡UUID）、`user_id UUID FK app_user`（索引）、`mode varchar(20)`（auto/wage）、`revision integer`、`updated_by UUID FK app_user`、`updated_at timestamptz`。仅手工调整建记录，无手调时默认auto。
- `attendance_leave_settlement_audit`：`id UUID PK`、`client_id UUID UNIQUE`（幂等）、`source_key FK attendance_leave_settlement.source_key`、`user_id UUID FK app_user`（索引）、`actor_id UUID FK app_user`、`actor_name varchar(255)`、`before_mode/after_mode varchar(20)`、`revision integer`、`reason text`（必填）、`before_snapshot/after_snapshot JSON`（受影响年度完整分配快照，不嵌套历史审计）、`created_at timestamptz`。索引 `(source_key, created_at)`。历史不可覆盖；列表返回来源相关快照，避免重复传输全年度无关记录。
- 手调仅HR电脑端，可查原方式/新方式、人员、UTC+8时间、原因、来源和前后金额基数（时长）。用户锁串行化、revision防覆盖、client_id防重；个人仅看自己，公司数据须HR权限。来源是一张完整请假（所有日期，含跨年）或本次迟到打卡。
- `tools/apply_attendance_annual_leave_migration.py` 幂等仅创建上述2张新表及索引约束，不修改既有表，启动自动迁移保持关闭。
- 法定假居家/加班独立预留区域，待开发，不自动归入普通居家额度或生成加班和补贴。考勤管理和工作台各区均有对应简要规则，并提供全部规则说明按钮。

## 人事招聘需求（2026-10-29）

- 独立于业务招聘项目；招聘管理位于入职管理左边，访问权限沿用HR行政部。
- 新表 `hr_recruitment_requirement`：id UUID PK；client_id UUID UNIQUE（新增幂等）；demand_no varchar(32) UNIQUE；request_date date；position varchar(200)；reason text；headcount integer（服务端校验1..100000整数）；details text；revision integer；is_deleted boolean；created_by/updated_by UUID FK app_user；created_at/updated_at timestamptz。索引 `(request_date, is_deleted)`。
- 需求编号按需求日期分日生成RT-YYMMDD-NNN，如RT-261029-001。PostgreSQL按日事务锁串行分配；编号不可手填，修改需求日期不改变已有编号。软删除记录继续保留编号，不回收序号。
- 搜索按空白分词AND，可跨编号、日期、岗位、原因、人数、具体需求匹配，%/_等作字面量；列表与总数同条件，400ms防抖、回车、清空立即查询、取消旧请求和防止旧结果覆盖。
- 新增/编辑使用AppForm与公共拖拽弹窗、字段搜索、固定页脚；具体需求占两列/双倍列表宽度，支持展开编辑及Popover查看全文。列表字段可配置、按用户持久化；统一删除管理及批量强确认，逐项记录失败结果、末页回退；revision保护编辑与删除。
- `tools/apply_hr_recruitment_migration.py` 幂等仅创建新表和必要索引约束，不改动原招聘项目或入职表。


### 项目客户经理调整记录（project_client_manager_change）

笔译、口译、招聘项目新增时默认由当前填写人担任客户经理，手工新增及咨询确认建项使用同一规则。标注项目复用 annotation_manager_change_log；子订单沿用既有继承机制。修改客户经理必须提供非空原因，项目与记录在同一事务内保存。客户档案经理不随项目调整而变化；不回填历史项目。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid | 调整记录主键 |
| project_type | varchar(30) | translation / interpretation / recruitment |
| project_id | uuid | 项目标识，项目删除后保留记录 |
| revision | integer | 每个项目递增版本；类型、项目、版本唯一 |
| previous_manager_id / new_manager_id | uuid | 调整前后账号，可空 |
| previous_manager_name / new_manager_name | varchar(255) | 调整时姓名快照 |
| actor_user_id / actor_name | uuid / varchar(255) | 操作人及姓名快照 |
| reason | varchar(500) | 必填调整原因，创建时自动记录默认分配说明 |
| changed_at | timestamptz | UTC+8 生成与接口输出 |

笔译、口译取最高 revision 的记录作为项目级客户经理；没有记录的历史项目继续显示原客户档案经理。招聘保持原生 client_manager_id 字段并同步留痕。查询、列表、详情及导出沿用同一客户经理来源。GET /project-client-managers/{project_type}/{project_id}/history 要求 projects:read，分页返回调整前后人员、原因、操作人、时间；标注类型适配既有日志。创建脚本 tools/apply_project_client_manager_migration.py 只创建新表及必要唯一约束、索引，不修改任何已有业务表或记录。


## 办公室管理与人员城市（2026-10-29）

- 组织架构增加办公室管理，第一分区为办公室人数设置；默认配置广州办公室、深圳南山办公室、上海办公室，城市分别为广州/深圳/上海。允许新增其他城市、办公室名称与工位数设置。工位数初始NULL表示待设置，可明确填0，不推算现有工位数。
- `organization_office_site`：id UUID PK；city varchar(100)；city_key varchar(100) UNIQUE（trim/casefold）；name varchar(200)；seats integer NULL（0..100000）；revision integer；created_at/updated_at timestamptz。默认城市采用稳定UUID，迁移重复执行不重置工位或已修改名称。
- `employee_office_city`：user_id UUID PK/FK app_user.id；office_city_id UUID FK organization_office_site.id（索引）；updated_at timestamptz。不修改既有app_user结构；未填城市不创建关联，清空删除关联，PATCH/PUT未提供城市时保留原关联。城市更名通过ID关联实时显示新名称，不批量改写人员。
- 实际人数按人员管理is_active=true且is_deleted=false统计，跨部门不重复；请假不减少人数。另显示未删除登记人员数（含停用）及未设置城市的在用人数。点击实际人数打开人员管理同城市且在用的筛选列表，列表和总数复用同条件，可清除办公室筛选。
- 人员新增/编辑姓名后增加城市下拉，只能选办公室管理的城市；列表、详情、创建/修改响应同步城市。用户新建/修改和城市保存共用事务，服务端验证城市ID，无效城市不写人员变更。城市字典姓名/工位变更不修改已有人员其他属性。
- 办公室查看受system:users:read/write保护，编辑受system:users:write保护；仅城市名称选项供已登录人员使用，不含人数。工位/城市修改revision防覆盖、城市唯一约束防重复；UTC+8时间。
- 迁移tools/apply_office_management_migration.py只创建上述两张新表及必要约束索引，并在新表初始化三座默认办公室；不推断分配现有人员城市、不变更既有人事数据，启动自动迁移保持关闭。

## 招聘城市（2026-10-29）

- 招聘需求新增招聘城市，表单顺序为需求日期→招聘城市→招聘岗位，列表和详情同步展示，关键词搜索覆盖招聘城市。可选择办公室城市，也可输入其他招聘城市；输入招聘城市不自动创建办公室，不自动变更人员城市。
- 新表`hr_recruitment_requirement_city`：requirement_id UUID PK/FK hr_recruitment_requirement.id；city varchar(100)。可为空未填写（不建关联）；旧记录不猜测城市，旧客户端未提供字段时保留原值。需求编号仍按需求日期生成，城市修改不改变需求编号。
- tools/apply_hr_recruitment_city_migration.py幂等仅创建关联新表，不ALTER原招聘需求表。城市保存与需求新增/修改同一事务；列表按主表批量带出城市，关联唯一，筛选/总数不重复计数。


## 人事招聘过程（2026-10-29）

- 招聘管理划分招聘需求、招聘过程两个可折叠区域；不复用业务招聘项目的候选人表。招聘过程关联需求ID，城市、岗位在读取时从原需求及其城市关联同步，禁止独立填写，不复制易失效文本。需求更新后界面刷新显示新值；原需求删除不级联删除候选过程，标记原需求已删除，保留原关联可继续补面试，但不能向已删需求新增过程。
- 新表 `hr_recruitment_candidate`，模型HrRecruitmentCandidate（避免与业务RecruitmentCandidate混淆）：id UUID PK，client_id UUID UNIQUE（新增幂等），requirement_id UUID FK hr_recruitment_requirement.id；applicant_name varchar(200)；first_interview_at/second_interview_at timestamptz NULL；first_interview_done/second_interview_done boolean；first_result/second_result text；willingness varchar(30)（空=待确认、candidate_withdrew=候选人放弃、company_declined=信实放弃、yes=是）；willingness_reason text；onboarding_date date NULL；actual_onboarded boolean NULL（仅预留，不开放写入）；revision integer，is_deleted boolean；created_by/updated_by UUID FK app_user；created_at/updated_at timestamptz。索引 `(requirement_id,is_deleted)`。
- 应聘人点击弹窗编辑姓名和两轮面试。任一轮选是必须填对应时间及结果；选否不保存该轮结果（可保留安排时间）。时间输入须带时区，接口归一UTC+8。二面不强制先有一面，未另设用户未定义的流程限制。
- 入职意愿选候选人放弃/信实放弃必须弹窗填原因；选是必须弹窗填入职日期，自动带入主表入职时间；不自动认定是否已入职，不创建人员档案。待确认不填放弃原因或入职日期。是否入职为只读预留，API拒绝写入预留字段及伪造城市/岗位。
- HR权限沿用行政部，面试弹窗通过公共AppForm动态必填规则、公共拖拽弹窗及字段定位，固定头尾和中部滚动；候选人姓名可点击直接编辑面试。主表字段设置、详情小窗、关键词AND搜索、400ms防抖取消旧请求、分页同条件、删除管理、revision冲突保护和新增client_id幂等。
- tools/apply_hr_recruitment_process_migration.py幂等仅创建新表及必要索引约束，不ALTER原招聘需求、候选人或人员表；自动迁移保持关闭。


### 固定班次类型补充（2026-10-30）

复用 `fixed_shift_config.assignments` JSON 与 `attendance_clock_session`，不新增或修改物理表字段。

- `fixed_early_early`：固定早早班08:30–12:00、13:30–16:00，每天可多组打卡，不限定上下午；`multiple_clock_sessions=true`。每组仍按完整班次08:30–16:00判断加班，仅当天首次打卡判断迟到；续打快照`continuation=true`。已有当日分段记录不改写，新增组使用多组规则。与既有轮班早早班 `early_early`（18:00结束）独立。
- `management`：管理/管培生08:50–12:00、13:30–20:00。
- `flexible`：不设预定时间，工作日/休息日均可主动多组打卡；不判迟到，记录 `work_minutes`，无预定时间不自动将全部时长认定为加班。上一组未签退不得开始下一组。普通组序号0、1、3、4……，既有2仍专用于公司要求居家加班；接口 `next_segment` 决定下次序号，`segment_count=null` 表示不限制组数。
- 上述三类仅在固定配置和本人打卡/考勤呈现，不占每周/月轮班单元格；服务端过滤轮班人员候选及旧公开快照，禁止通过普通排班接口伪造这些班次代码。考勤按生效版本解析，不回写既有打卡快照。
- `home_rotation`：居家轮班资格标记，保留原周早晚班安排，允许调班/复制/转移/互换，不锁定单元格；快照保留 `home_rotation`、`home_office_day`。签退要求居家有效工作声明和可选无效时间说明；签退超过原考勤日18:50同样确认晚餐，有则扣20分钟；不创建普通居家申请或消耗其额度。
- 所有班次多组打卡签退超过原考勤日18:50且本人确认进食晚餐时最多扣一次20分钟；后续快照保存 `dinner_already_deducted` 防止重复。固定班次标记不触发晚餐抵扣；公司要求居家加班仍独立。
- 指定人员配置入口 `tools/configure_named_fixed_shifts.py`：默认只读预览；显式执行需同时核对主机、项目、Git、数据库、配置版本及8个账号和真实姓名。仅调整指定人员，保留其余人员，不改组织归属、不生成打卡和通知；已应用时不重复提升版本。


### 行政部组织架构权限（2026-10-30）

不修改角色关联或数据库结构。在服务端按当前有效主部门、跨部门成员及部门别名，向在用行政部人员动态授予 `system:users:read` 与 `system:organization:write`；移出行政部后立即撤销动态授予，原有角色授权独立保留。新增组织架构权限覆盖部门目录、人员归属/职务、人员基础资料增删改、办公室配置和工作报告/任务查看设置。Ethan、Jimmy和超级管理员的既有部门管理权限保留。不会自动授予系统用户管理、角色分配、密码重置、邮件账号管理等额外权限。前端使用会话接口返回的有效权限，服务端每次写入独立校验。行政部编辑报告查看规则时，始终保留赵震锋作为原配置主体，不自动把操作人加入报告查看范围；审计操作者仍记录实际登录人员。


### 招聘需求计划到岗日期与招聘过程自动呈现（2026-10-30）

新表 `hr_recruitment_requirement_schedule`：`requirement_id` UUID主键并外键关联`hr_recruitment_requirement.id`，`planned_onboarding_date` DATE非空。关联记录不存在表示未填写；接口支持填写、清空，更新接口省略该字段时保留原值。沿用需求版本、操作者与更新时间，并支持关键字日期搜索。此日期是招聘需求的计划目标，与候选人的实际意愿入职日期相互独立，不自动改写候选人日期。迁移`tools/apply_hr_recruitment_schedule_migration.py`只幂等创建该新表，不改既有表及业务数据。

招聘过程列表自动包含每个有效需求：没有在用应聘人时返回`is_placeholder=true`、`id=requirement:<UUID>`的只读需求行，并实时关联需求编号、城市、岗位；不落库、不生成空姓名应聘人。点击“添加应聘人”后直接以该需求创建真实应聘人记录；有多位应聘人时各自保留独立面试与入职意愿记录，需求信息实时共享。删除最后一位应聘人后仍显示该需求；删除需求后不再产生空需求行，已有应聘人的历史记录继续保留并显示原需求已删除。需求行不能作为应聘人批量删除；搜索、分页和总数在同一数据库查询中包含自动需求行与真实应聘人，避免列表和总数不一致。


### 办公室区域工位（2026-10-30）

新表`organization_office_area`：`office_id` UUID外键关联`organization_office_site.id`，与整数`position`组成主键；`name` VARCHAR(100)区域名称；`seats` INTEGER非负工位数。区域按position显示，每个办公室区域名称去空格后忽略大小写不得重复，最多100个区域，总数最多100000。

办公室写入接口增加可选`areas:[{name,seats}]`。有分区时`OfficeSite.seats`由各分区自动合计，保存使用原办公室版本锁，保证分区与总数原子更新；省略areas保留原分区，空数组显式清空分区恢复独立总工位设置。统计实际人数仍按人员城市，不推断每人的区域座位。

用户明确指定广州：总经理室1位、财务室2位、管理区6位、大办公区26位，合计35位。`tools/apply_office_area_migration.py`只幂等建新表；`tools/configure_guangzhou_office_areas.py`默认只读预览，显式执行需核对目标、主机、目录、Git和广州办公室版本，仅保存广州指定分区和合计，不更改其他办公室、人员城市或人数。

组织架构页面移至人事管理首个区域`/hr-management/organization`，排班管理位于其后；旧`/users`和`/departments`入口保留查询条件重定向，以兼容办公室人员筛选及原书签。迁移仅改变导航，原有组织架构权限保持，非人事账号不会因此获得排班考勤权限；办公室及人员子区域保持在组织架构内。


### 居家小时申请、补卡确认与跨日顺延（2026-10-30）

本次仅新增三表，不修改既有表结构。迁移入口`tools/apply_attendance_corrections_migration.py`幂等创建：

- `home_office_application_duration`：`application_id` UUID主键并外键关联`home_office_application.id`，`minutes` INTEGER申请分钟数，接口只接受120/240/480。旧申请无关联行时按原一整天480分钟解释，不补写、改写历史数据。
- `attendance_clock_correction`：UUID主键、全局唯一`client_id`，员工外键`user_id`、考勤`day`、`kind`（in/out）、原打卡外键`record_id`（待补首次上班可空）、组号`segment`、申请实际时间`requested_at`（timestamptz）、原因`reason`、可选证据截图引用`evidence`、声明`declarations` JSON、状态`status`（pending/confirmed/cancelled）、原始快照`original` JSON、仅服务端追加的`history` JSON、UTC+8提交及确认时间、确认人外键。待确认不会修改实际打卡，任一在用行政成员可确认；版本/原快照变化拒绝覆盖，可由本人撤回再申请。确认时验证不与其他工作组重叠，记录实际操作者、前后快照，保留全过程。证据复用公共截图编辑框及授权机制，长期保存；本人仅查本人，行政查全体。
- `attendance_start_adjustment`：UUID主键、唯一来源打卡外键`source_clock_id`、员工外键、后续日期`day`、组号`segment`、`next_start`（timestamptz）、原因、仅追加的`history` JSON、创建时间。history记录原上班、签退、后续上班及已存在后续记录的基准变化。相同来源重新确认时撤销其原有基准后再应用，避免多个日期重复豁免。补下班必填实际下班时间、下次/第二天上班时间及原因；行政确认后同步此基准。

居家月额度：每月最多16小时，其中可拆分8小时限2+2+4或4+4（先后顺序不限），2小时最多2次，另外8小时须单次整段申请。每次选2/4/8小时，同一日期不重复申请。季度仍最多4天、半年8天、年度12天及入职当年折算，按480分钟=1天核算；待审批也占额度，原年度补录仍按天换算。公司要求的居家加班不计入。普通居家及资格的审批仍待开发，不因打卡视为获批。

2/4小时申请当日普通打卡最多两组，两组不绑定上下午时间；必须前一组签退后开始后一组，后组不重复记首次迟到。已有超过两组普通记录时不接受当日部分时长申请。不改变班次预定上下班时刻或居家固定轮班属性。

真实签退超过下一次预定上班时刻时，仍可签退，必须填写原因和晚于签退的后续上班时间；保留真实签退时刻，不伪造回填。系统将后续组快照的`late_start_at`设置为此基准，原15分钟宽限保留；迟到折算请假和年终奖追责共用此计算。不把顺延前的空档自动计算为加班。行政部收到记录通知，员工和行政均可查看全程。

新增接口：GET/POST `/attendance/clock-corrections`；POST `/{id}/confirm`（行政）和`/{id}/cancel`（本人待确认）；现有check-out新增`cross_day_reason`、带时区`next_start`。补卡写入、确认仍只支持电脑端，手机继续仅支持请假和延迟上班。通知只发相关人员，确认后刷新本人工作台；行政通知可直达考勤管理的补卡与跨日记录区。所有时间按UTC+8，测试使用隔离SQLite及拦截API，不生成真实申请、打卡或通知。

### 技术开发任务（2026-10-30）

仅新增 `technical_development_task`、`technical_development_progress`、`technical_development_feedback` 三表，由 `tools/apply_technical_development_migration.py` 显式幂等创建，启动不迁移，不改动既有表或业务数据。

- `technical_development_task`：`id` UUID主键；`parent_id` 可空自关联外键及索引；`name` VARCHAR(300)；`content` TEXT具体任务；`arranger_id`、`executor_id` UUID关联app_user；`due_at` TIMESTAMPTZ可空预定完成时间；`progress` INTEGER默认0且约束0—100；`progress_updated_at` TIMESTAMPTZ可空；`adjustment` TEXT反馈后调整；`notes` TEXT备注；`revision` INTEGER乐观版本；`created_by`、`updated_by` UUID关联app_user；`created_at`、`updated_at` TIMESTAMPTZ。三级共用同一结构，每个任务独立维护所有字段。
- `technical_development_progress`：`id` UUID主键；`task_id` UUID外键及索引；`previous_percentage` INTEGER修改前进度；`percentage` INTEGER修改后进度且约束1—100；`content` TEXT具体进度；`reason` TEXT修改原因；`author_id` UUID用户外键、`author_name` VARCHAR(255)姓名快照；`created_at` TIMESTAMPTZ。每次保存追加记录，回退必须填写原因；不提供历史覆盖接口。
- `technical_development_feedback`：`id` UUID主键；`task_id` UUID外键及索引；`content` TEXT非空反馈；`author_id` UUID用户外键、`author_name` VARCHAR(255)姓名快照；`created_at` TIMESTAMPTZ。全体在职用户可追加反馈，作者与时间由登录会话和服务端生成。

登录且在职、未删除的用户可查看及协作维护本模块；安排人目录为在职人员（赵震锋、运坚依次置顶），执行人按共享部门查询能力限定技术部/IT部，并包含跨部门成员。已有历史人员允许原值保留，改选必须满足当前目录。所有写入和移动校验版本；PostgreSQL事务级咨询锁串行树写入，拒绝循环、第四级及带下属整体移动后超三级。进度与历史在同一事务保存，反馈单独追加。时间生成、序列化和展示统一UTC+8。

接口前缀 `/technical-development`：GET `/people`；GET/POST `/tasks`；GET/PUT `/tasks/{id}`；PUT `/tasks/{id}/parent`；POST `/tasks/{id}/progress`、`/tasks/{id}/feedback`。前端 `/technology-management/development` 使用统一字段设置、详情Popover、可拖拽长表单、表单字段定位；拖拽改父级及“调整层级”选择器均由服务端最终校验。

### 技术任务编号、工作报告与部门权限（2026-10-30）

新增 `technical_development_task_number`：`task_id` UUID主键及任务外键；`task_no` VARCHAR(40)唯一编号；`number_date` DATE香港自然日；`sequence` INTEGER正整数；日期与流水号联合唯一。编号格式 `DT-YYMMDD-NNN`，按自然日归零，超过999继续增长而不回绕；与报告07:00归日独立。所有层级使用同一流水池，创建与分号在同一事务、同一树锁内完成。旧任务仅初始化新增映射，按原创建香港日期编号，原任务不更新；编号不随编辑、移层级改变。

新增 `technical_development_report_receipt`：`request_id` UUID主键；`task_id` UUID任务外键；`user_id` UUID账号外键；`report_id` UUID日报外键；`item_key` UUID唯一稳定工作行键；`created_at` TIMESTAMPTZ。仅在用户点击“确认添加”时向本人当前工作报告草稿追加；表单类型、订单号、项目名称和具体任务均可修改，原技术任务不被回写。添加弹窗完整提供工作量、单位（含自定义单位）和耗时，必填并校验后随工作行保存；任务/项目类型支持多选。添加时间在确认时由后端生成带 +08:00 的真实时刻，在报告编辑与快照中显示；弹窗展示报告日期及系统记录时间说明。所有技术任务、子任务、分工及技术需求汇总入口共用该弹窗。历史草稿仍允许在报告补齐，不推算实际工作时间。已确认报告拒绝追加，须先撤回。请求重试返回首次报告，包括跨07:00重试，不重复加行。

报告原表结构不变，`DailyReportItem.display_metadata`保存 `source=technical_development`、`technical_task_id`、`added_at`、`_feedback_key`、`report_types`和可编辑订单号。来源ID稳定，不因用户修改编号/名称丢失关联；刷新汇总和旧编辑窗口保存保留来源。报告编号链接显示任务详情，项目名称链接显示UTC+8按天分组的原始具体进度、前后百分比、原因、人员和时间；两个入口复用同一技术任务引用组件。

技术开发权限已收窄为开发/IT部在职成员（兼容开发部、开发/IT部、技术部、IT部及组织别名/跨部门成员关系），无超级管理员绕过。后端包括人员目录、任务、进度、反馈和报告添加均再次校验；认证用户可读 `/technical-development/access` 获取本人的布尔入口权限。前端菜单、路由按此值控制，定期及部门变更后刷新。明确指定的ethan、thomas仅新增IT部成员关系，保留原主部门和其他职务；脚本 `tools/configure_technical_department_members.py` 默认只读预览、核对部门版本，显式 `--apply` 执行。新表及编号初始化入口为 `tools/apply_technical_development_number_migration.py`，启动自动迁移保持关闭。

### 公司开发反馈与具名意见（2026-10-30）

新增 `development_feedback_sheet`（`task_id` UUID主键/技术任务外键、`created_by` UUID账号外键、`created_at` TIMESTAMPTZ）；同一任务只能生成一张反馈表，重复生成返回原表。每级开发任务均可由开发/IT部生成，首次生成创建一条可填写反馈；不自动复制原任务的反馈意见。

新增 `development_feedback`：`id` UUID主键；`request_id` UUID唯一创建重试凭证；`task_id` UUID关联反馈表并建索引；`feedback_no` VARCHAR(40)唯一，按香港自然日分配 `FB-YYMMDD-NNN`（超过999继续增长）；`submitted_on` DATE自动提交日期；`submitted_by` UUID账号外键、`submitted_name` VARCHAR(255)、`submitted_username` VARCHAR(100)均从登录会话生成；`module` VARCHAR(300)功能模块；`content` TEXT反馈内容；`urgency` VARCHAR(10)低/中/高/紧急，默认中；`attachments` TEXT附件链接与现有受保护截图引用；`status` VARCHAR(20)待处理/处理中/已解决/暂不处理，默认待处理；`assignee_id` UUID可空人员外键，改选限定开发/IT部在职人员；`result` TEXT处理结果；`completed_on` DATE可空完成日期；`notes` TEXT备注；`revision` INTEGER乐观版本；`created_at`、`updated_at` TIMESTAMPTZ。日期编号分配使用独立事务锁，单元格修改使用行锁和版本，前端同一反馈的不同字段保存串行，避免覆盖其他单元格。

新增 `development_feedback_opinion`：`id` UUID主键；`feedback_id` UUID反馈外键/索引；`kind` VARCHAR(20)限定william/development；`content` TEXT；`author_id` UUID账号外键、`author_name` VARCHAR(255)、`author_username` VARCHAR(100)账号快照；`created_at` TIMESTAMPTZ。意见每次保存追加，按`expected_latest_id`防止陈旧编辑覆盖；William意见仅williamzhao可填写，开发部门意见仅开发/IT部成员可填写，均显示姓名、账号和香港时间。全公司在职人员可查看、在已生成任务表中提交反馈；普通字段由反馈人、William、开发/IT部编辑，系统编号及身份字段不可修改。

`/company-management/development-feedback` 为公司管理“开发反馈”子板块，按“（开发）任务名称”折叠，全部业务字段使用直接编辑表格，支持字段设置、自动保存与截图上传。原公司资料入口与栏目查询参数保留。API前缀 `/development-feedback`：GET列表；POST `/tasks/{id}/generate`、`/tasks/{id}/rows`；GET/PATCH `/rows/{id}`；POST `/rows/{id}/opinions`。截图沿用既有上传、授权中间件及业务长期存储，禁止伪造其他人的截图引用。显式建表入口`tools/apply_development_feedback_migration.py`仅创建上述新表。

### 技术完成日期与开发部门奖励（2026-10-30）

新增 `technical_task_completion`：`task_id` UUID任务主键外键；`completed_on` DATE可空实际完成日期；`due_on` DATE香港日历预定日期快照；`executor_id` UUID执行人外键；`on_time` BOOLEAN可空，完成日期不晚于预定日期为是，未填完成日期为待完成；`revision` INTEGER评定版本；`updated_at` TIMESTAMPTZ。

新增 `technical_task_completion_change`：`id` UUID主键、`request_id` UUID唯一重试凭证、`task_id` UUID任务外键/索引；`previous_date`、`completed_on`、`previous_due_on`、`due_on` DATE日期前后值；`previous_executor_id`、`executor_id` UUID人员外键；`on_time` BOOLEAN；`revision` INTEGER评定版本；`reason` TEXT；`author_id` UUID人员外键、`author_name` VARCHAR(255)、`author_username` VARCHAR(100)；`created_at` TIMESTAMPTZ。修改或清空已填写完成日期必须说明原因；预定日期、执行人变化也追加记录并重新评定。无预定完成时间不能填写实际完成日期；仅有日期精度，不推断完成当天的具体时刻。

新增 `technical_task_incentive`：`id` UUID主键；`request_id` UUID唯一提交凭证；`task_id` UUID任务外键/索引；`assessment_revision` INTEGER所属评定版本；`sequence` INTEGER金额修改序号，与任务和评定版本联合唯一；`executor_id` UUID外键、`executor_name` VARCHAR(255)执行人快照；`kind` VARCHAR(20)reward/deduction（按时给予奖励，否则抵消奖金）；`amount` NUMERIC(14,2)非负金额；`completed_on`、`due_on` DATE评定日期快照；`reason` TEXT金额说明/修改原因；`author_id` UUID、`author_name` VARCHAR(255)、`author_username` VARCHAR(100)操作者；`created_at` TIMESTAMPTZ。金额调整保留原记录、必须填写原因，只统计当前日期评定版本的最后一条金额。日期/预定日/执行人调整后旧金额退出当前统计，但历史不可覆盖；未登记金额的评定单独显示待登记。不自动生成奖金金额，不联动实际工资支付。

技术开发主表新增“完成日期”“是否按时完成”，保存日期后按是/否进入奖励/抵消金额窗口，可取消暂不登记；编辑态也可调整日期。KPI原模拟表单已替换为“开发部门奖励”，按执行人汇总奖励、抵消奖金、相互抵消、奖励余额和待抵消余额，并展示任务明细及全程调整记录。按人分别取奖励/抵消最小值，不允许跨人抵消，部门合计为各人余额与抵消之和。技术人员可维护本模块；KPI统计继续遵循既有人事管理权限，窄范围的日期和金额历史只允许开发/IT部或人事管理人员读取。

API：GET/PUT `/technical-development/tasks/{id}/completion`；POST `/{id}/incentive`；GET `/technical-development/incentives`。显式建表入口`tools/apply_technical_incentives_migration.py`仅创建三个新表，原技术任务表不加列、不回填，启动自动迁移关闭。所有实际时刻按UTC+8生成、序列化与展示，纯日期保持DATE语义，金额全程使用Decimal并以两位小数字符串传输。

### 技术需求汇总带入开发任务及报告（2026-10-30）

新增 `technical_requirement_task_link`：`room_id` UUID主键，关联`annotation_technical_room.room_id`；`task_id` UUID唯一任务外键；`base_name` VARCHAR(300)原项目名称快照；`suffix` VARCHAR(80)允许追加的补充文字；`source_revision` INTEGER复制时的需求汇总版本；`created_by`、`updated_by` UUID人员外键；`created_at`、`updated_at` TIMESTAMPTZ。仅增加新关联表，不改原技术需求或任务表。一个技术需求会话对应同一个开发任务，重复进入编辑原任务，不重复创建。

需求汇总“保存汇总”右侧新增“加至开发任务”“加至工作报告”，沿用仅开发/IT部的任务访问权限；来源内容还须满足原技术会话参与人权限。跳转前先保存未保存的汇总，失败则停止；带入项目名称、技术需求汇总和默认本人执行人（可选其他IT部人员）。任务原项目名使用ReadonlyField展示，最多追加80字补充；后端对关联任务的普通编辑接口也限制原项目名不能改写。任务编号只在点击保存任务时自动分配，任务与关联在同一事务保存；需求汇总版本过期、重复创建或任务版本过期均拒绝覆盖。

未保存开发任务时，“加至工作报告”明确提示先编辑保存任务。已保存时使用稳定关联task_id，复用工作报告确认弹窗；编号、名称、具体任务均带入并可在报告中修改，不回写原开发任务，原编号与各天具体进度的链接不因报告文本变化丢失。来源汇总可能较长，技术任务具体任务允许100000字，报告自身10000字限制继续保留。

新API GET/POST `/technical-development/requirements/{room_id}`，POST校验开发部门身份、会话成员、来源版本和任务版本。任务响应增加可空`source`元数据以保持从任务列表进入编辑时的锁名规则。显式建表入口`tools/apply_technical_requirement_task_migration.py`仅创建关联表，启动不迁移。


### weekend_night_duty_plan（周末夜间值班，2026-10-30）

独立于普通居家申请，按月主键保存；只创建新表，不修改既有表。`month` DATE 主键；`assignments` JSON 为行政编辑安排（user_id/date/mode，standalone或continuation）；`published` JSON 为工作台与打卡使用的已同步快照；`revision`、`published_revision` INTEGER 乐观锁及发布版本；`editing` BOOLEAN 发布后锁定；`history` JSON 逐次保存操作者、+08:00时间、前后安排及publication_revision（未同步记录不对公众展示）；`updated_by` UUID、`updated_at` TIMESTAMPTZ。

仅周六周日19:00–23:00，客户/销售人员；400毫秒保存，手动同步发布，修改后需再同步。单独与接续夜间均不折算半天；已完成打卡的有效分钟直接计入多值班，先抵扣待补班请假，不冲抵每月白天1天基数，不计入白天月均天数；接续须先同步同日白天值班，白天18:00结束，夜间第二组独立打卡；接续晚间与白天分开核算并抵扣请假。白天和夜间发布互相校验，不允许单独夜间与同日白天值班冲突，也不能撤销接续依赖的白天值班。夜间居家标记直接进入打卡快照，不写home_office_application、不扣普通居家额度；签退沿用居家真实性声明和无效分钟抵扣。原周末基数、补班优先、节假日待开发规则保留，夜间只按分钟抵扣，所有多值班先抵扣待补班请假，剩余按既有调休条件处理，不得重复抵扣。

### 多执行人与独立分工（2026-10-30）

新增 `technical_task_collaboration`：`task_id` UUID任务主键外键；`created_by` UUID人员外键；`created_at` TIMESTAMPTZ。记录该任务采用按人分工；原任务编号及原三级层级保持。

新增 `technical_task_allocation`：`id` UUID主键；`root_task_id` UUID协作任务外键/索引；`execution_task_id` UUID独立执行记录外键且唯一；`executor_id` UUID人员外键；`active` BOOLEAN是否当前分工；`position` INTEGER顺序；`updated_at` TIMESTAMPTZ。同任务与执行人联合唯一。独立执行记录复用技术任务表，但不作为第四级任务、不进入主任务树；每个人分配独立DT编号、分工文字、预定完成时间、进度历史、完成日期、日期调整历史和金额台账。主任务显示全部执行人，完成日期与奖金入口改为“按分工分别记录/计算”。

任务Create/Update及技术需求带入支持可选`allocations:[{executor_id,content,due_at}]`；分工人员不能重复，第一人与原兼容`executor_id`一致，每人必须填写非空具体分工，人员限定开发/IT部且保留既有历史人员语义。新任务不提交allocations时完全兼容原单人模式。多人选择自动弹出公共可拖拽分工表单，支持按人不同的预定日期；保存主任务时与分工、独立编号原子保存。原分工调整复用执行记录ID，不新建重复编号；只重新评定日期变化人员，其他人的完成与金额不受影响。

协调主任务禁止直接登记完成日期、奖金或追加报告；必须选择个人分工。独立执行记录不能移动到主任务树或作为结构上级，普通编辑须经原任务分工窗口。原任务三级层级及子任务保持不变。分工窗口提供每人进度、日期与金额窗口、调整记录、加至工作报告；报告带入该人独立分工编号和具体任务，原技术汇总入口默认当前人的分工，没有本人分工时提供选择窗口。

KPI仅统计个人执行记录，不重复统计协调主任务。原单人已有完成/金额改成多人时，保留原始记录，并向原执行人的独立分工承接日期和仍适用金额，记录承接来源；原主记录作为历史不重复计入。移出人员的已完成金额与历史继续保留，不因删除当前分工自动抹掉已登记金额，停用分工不能登记新日期/金额；未登记金额的停用分工不计待处理。多人改为一人后仍通过稳定分工记录维护，不丢失历史。

新增表由`tools/apply_technical_allocations_migration.py`显式幂等创建，不调整既有表结构、不回填旧任务，启动自动迁移继续关闭。新增执行记录属于用户保存分工时的正常业务写入。时间沿用UTC+8，金额沿用Decimal及按人抵消规则。


### 技术开发层级编号、互换与删除管理（2026-10-30）

新增 `technical_task_hierarchy_number`：`task_id` UUID 主键、任务外键；`task_no` VARCHAR(40) 非空唯一。母任务使用 DT-日期-流水号，子任务追加 .001，三级任务再追加 .001。初始化只写入新映射表，不修改原任务及原编号表。拖动变更层级时同步更新整个下属编号；互换位置时对节点和父子引用作原子置换，并交换对应位置编号，任务 UUID、名称、内容、进度、反馈、日期及奖励归属不变。所有写操作复用树级事务锁，互换校验双方版本。所有任务展示、分工、反馈和奖励编号读取此映射。

新增 `technical_task_deletion`：`task_id` UUID 主键、任务外键；`deleted_by` UUID 账号外键；`deleted_at` TIMESTAMPTZ，使用 UTC+8。删除后不再进入技术开发列表或作为上级任务，不再允许修改或新增报告；原工作报告、进度、反馈和奖励记录保留，历史任务引用仍可只读查看。多人任务删除时同步标记其分工执行记录。存在未删除子任务的母任务拒绝单独删除；批量选择含母子任务时，前端按三级、子任务、母任务顺序逐条处理，失败项保留选择。编号不因删除而被重新使用。

显式幂等初始化入口为 `tools/apply_technical_task_management_migration.py`；启动自动迁移保持关闭。技术开发主表移除独立详情列，任务编号点击打开详情小窗；页面级删除管理采用公共工具栏和确认流程，树表选择不联动下属任务。


### 技术开发任务会话与部门分组（2026-10-30）

新增 `technical_task_conversation`：`task_id` UUID 主键、技术任务外键；`room_id` UUID 非空唯一、会话分类外键；`created_by` UUID 账号外键；`created_at` TIMESTAMPTZ（UTC+8）。每个技术任务仅关联一个讨论会话，创建/重新打开幂等，持有任务树事务锁。首次创建加入当前开发/IT部在用成员，后续打开补齐新成员；原消息、阅读进度及个人偏好保留。删除任务不删除既有会话和聊天记录。会话展示名称实时读取层级编号及任务名称，编号调整或任务改名后同步展示。

会话分组新增内置虚拟目录“技术/开发项目”（`dcb1f917-6000-4000-8000-000000000012`，ruleKey=technical），仅开发/IT部可见。任务会话作为其下属讨论分类统一归集，复用讨论消息、附件、引用、参与人、未读和置顶功能。目录及讨论列表、直接访问、参与人、邀请、提及、附件和历史检索统一校验部门权限，已有非IT成员关系不能绕过。非IT超级管理员同样不例外。

用户明确要求将现有“技术/开发沟通”原会话移动至新分组并置顶；保留原会话UUID、成员、原消息及阅读记录，为现有IT成员补齐参与关系并设为置顶。分组中该群优先显示。显式脚本 `tools/apply_technical_task_conversation_migration.py` 默认仅创建新表；移动操作必须指定 `--configure-general`、原会话版本和操作账号，执行前核对主机、目录、Git提交、数据库及唯一匹配。启动自动迁移保持关闭。


### 笔译项目简短记录（translation_project_note）

项目表单底部“简短记录”可追加最多200字的纯文本，列表每页10条，时间倒序；只允许追加与读取，不提供修改和删除接口。新增项目需先保存，再添加记录。记录独立保存，不改变或覆盖正在编辑的项目字段、updated_at。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid | 主键 |
| project_id | uuid | 笔译项目ID；无外键，以保留项目删除后的记录 |
| request_id | uuid | 客户端重试标识；与项目ID组合唯一，防止重复保存 |
| content | varchar(200) | 去除首尾空白后非空的记录内容 |
| actor_user_id | uuid | 后端从登录身份取得的操作人ID |
| actor_name / actor_username | varchar(255) / varchar(100) | 操作时姓名及账号快照，后续改名不影响记录 |
| created_at | timestamptz | UTC+8生成，接口携带+08:00 |

索引 ix_translation_project_note_project_time(project_id,created_at,id)；唯一约束 uq_translation_project_note_request(project_id,request_id)。GET/POST /projects/translation/{project_id}/short-notes 分别要求 projects:read / projects:write，验证项目存在且不是已迁移的标注项目。POST锁定项目行，校验重试身份及内容；客户端不能指定操作人或时间。迁移 tools/apply_translation_project_note_migration.py 可重复执行，仅创建本表和必要约束、索引，启动自动迁移保持关闭。

### `editor_draft`

仅保存尚未正式提交的编辑内容，不触发业务保存、报告确认或发送。账号隔离；本机400毫秒备份，云端3秒合并、最多20份一批、同一客户端单请求执行。乐观版本冲突保留本机内容，不覆盖云端新版。

| 字段 | 类型 | 规则 | 说明 |
| --- | --- | --- | --- |
| user_id | UUID | 复合主键、FK → app_user.id，删除级联 | 当前登录用户，接口不能指定其他人 |
| namespace | varchar(80) | 复合主键 | 模块，例如 work-report、global、form:client |
| draft_key | varchar(220) | 复合主键 | 记录身份；工作报告为报告日期 |
| payload | jsonb | 可空，单份不超过256KB | 不完整草稿；null为已清除的版本标记 |
| revision | integer | 非空 | 每次实际变化递增，防止旧窗口覆盖 |
| updated_at | timestamptz | 非空 | 实际保存时刻，接口转换为UTC+8 |

迁移脚本 `tools/apply_editor_drafts_migration.py` 仅创建此表，不回填、不修改业务表；启动自动迁移保持关闭。工作报告正式保存与草稿清除同事务执行，保留清除版本以拒绝旧请求重新写回。


### 笔译各级订单文件名称约束（2026-10-31）

新建及修改名称使用同一校验：非空、最多255个Unicode字符、单个真实文件名、尾部为已识别扩展名；禁止路径及Windows文件名禁用字符。格式源为 frontend/src/config/translationFileExtensions.json，18类共514个去重后缀，另支持 .r00～.r99、.z00～.z99、.000～.999 分卷后缀。以已识别后缀和文件名分隔边界检查多文件，不直接按普通逗号或空格切开；复合 .tar.gz 与 .docx.zip 都是单个文件。未知后缀提示核对，不能以版本号冒充；不验证实际文件内容或进行解压。

Python translation_file_name_rules.py 与前端 translationFileName.js 共用格式源和样例；母订单source_file_name/project_name同步，子订单sub_project_name、批量子订单、行内改名、稿件安排回写统一校验。读取原文目录时必须恰好一个有效文件，不再拼接多个文件或截断名称。批量导入允许多行，但每行生成独立子订单；按数量生成将序号放在扩展名前。历史记录不自动重写，不改名的局部状态/进度更新仍兼容旧数据。

订单号详情入口复用同一完整项目表单，含基础信息、进度跟踪、子订单、项目文件页签及简短记录。完整详情打开前重新读取项目，查看用户禁用表单编辑并隐藏保存操作；项目文件页签沿用原权限。无数据库结构变更。

### 简单需求、收到回复及各级订单安排（2026-10-31）

既有简短记录保留只读历史入口；新界面使用“简单需求”。项目状态增加 `simple_requirement`（简单需求）、`source_file_simple_requirement`（原文件+简单需求），既有状态字段无需结构调整。

`translation_simple_requirement`：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid | 主键 |
| project_id | uuid | 外键 translation_project.id，删除项目时级联 |
| request_id | uuid | 与 project_id 组合唯一，重试不重复保存或通知 |
| original_text / translated_text | varchar(2000) | 原文非空，译文可空；仅去除首尾空白 |
| chargeable | boolean NOT NULL | 每条必须明确选择收费或不收费；不代替项目金额计算 |
| previous_status / saved_status | varchar(50) | 保存前项目状态与本次选定状态 |
| actor_user_id | uuid | 登录操作人，服务端取得 |
| actor_name / actor_username | varchar(255) / varchar(100) | 操作时姓名和账号快照 |
| created_at | timestamptz | UTC+8生成，接口显式+08:00 |

索引 `ix_translation_simple_requirement_project_time(project_id,created_at,id)`；唯一约束 `uq_translation_simple_requirement_request(project_id,request_id)`。锁定项目后核对原状态及更新时间，需求、状态、接收人及通知在同一事务写入。列表接口按创建时间及ID倒序分页，默认10条。

`translation_simple_requirement_recipient`：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid | 主键 |
| requirement_id | uuid | 外键至简单需求，级联删除 |
| user_id / user_name | uuid / varchar(255) | 接收账号及发送时姓名快照 |
| notification_id | uuid | 本次通知ID；通知清理不删除收到回复记录 |
| received_at | timestamptz NULL | 本人明确回复收到的时间，已读不能替代 |
| reply | varchar(500) NULL | 首次收到回复内容，默认“收到” |

唯一约束 `uq_translation_simple_requirement_recipient(requirement_id,user_id)`；索引 `ix_translation_simple_requirement_recipient_user(user_id,received_at)`。通知人必须为笔译项目部当前有效人员（兼容主部门及跨部门归属），默认唯一匹配账号 shaofei，支持多选。发送人、接收人及有项目查看权限者可查看需求；仅接收人本人可回复，回复幂等且原子追加发送人通知。业务通知类型为 `translation_simple_requirement`、`translation_simple_requirement_receipt`；通知创建时间沿用香港本地无时区字段语义，既有通知 read_at 继续使用 UTC 无时区语义，两种时间的本功能接口均明确转换为+08:00。不改变其他通知历史时间解释。

`translation_arrangement_order_target`：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| arrangement_id | uuid | 主键、外键 translation_project_arrangement.id，级联删除 |
| sub_order_id | uuid | 下级订单身份；不设删除级联，保留删除后的快照 |
| order_no / project_name | varchar(60) / varchar(255) | 安排时订单号与文件名称快照 |
| order_level | integer | 子订单为2，编号追加层级为3等 |
| previous_order_status | varchar(50) NULL | 安排前下级订单状态 |

索引 `ix_translation_arrangement_order_target_sub_order_id(sub_order_id)`。母订单安排沿用原表，无附属行；旧请求未指定目标时仍安排母订单。新请求 `target_order_ids` 明确列出目标，不自动包含下级；验证真实 parent_project_id 归属、重复目标及单批最多100项展开后任务。下级层级按母订单号后的数字点分段识别，三级归属其存在的编号上级，缺失上级时仍在母订单下呈现。每个所选订单与每位人员生成独立任务、保留统一执行顺序及修改历史；只更新所选订单的可安排状态。任务列表、执行顺序、历史及完成报告均包含实际订单号、名称和层级，工作报告不替换成母订单编号。下级删除后使用保存时快照并返回 target_deleted。

安排接口向任务本人及按既有工作报告规则授权的查看人返回母项目的 `customer_requirement_professional`、`customer_requirement_special`；项目安排和今日任务共用只读客户要求小窗。部门显示选择只保存在按“项目安排+当前账号”隔离的浏览器配置，不改变组织归属或权限。

迁移 `tools/apply_translation_requirement_migration.py` 仅创建以上三张新表及索引、约束，可重复执行；启动自动迁移保持关闭。组织架构的本次明确人员追加由独立 `tools/ensure_translation_project_department.py` 执行，与结构迁移分开，不覆盖已有部门归属，不在后续迁移时自动补回被人工移出的成员。

### 简单需求客户回稿时间、状态下拉与项目经理安排（2026-11-01）

弹窗复用既有 `translation_project.customer_deadline_time` 字段，保存时间和选择状态分别独立操作，核对项目更新时间防止旧窗口覆盖新数据。状态可选择完整笔译状态目录；保存简单需求沿用当前选定状态，不再限制为两种状态。日期按香港时间编辑、生成带+08:00的接口值，旧项目日期字段继续保存香港本地无时区值。父项目表单只同步本次明确修改的回稿时间及状态，不覆盖其他尚未保存字段。

`translation_requirement_dispatch`：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid | 主键 |
| project_id | uuid | 外键 translation_project.id，删除项目时级联 |
| request_id | uuid | 与项目组合唯一；发送失败重试不重复通知 |
| requirement_id | uuid NULL | 关联的已保存需求；服务端验证同一项目，不级联删除历史快照 |
| requirement_snapshot | json NULL | 发送时关联需求的原文、译文、收费选择等快照 |
| content | varchar(10000) | 安排具体内容，去除首尾空白后非空，项目/安排查看者共同可见 |
| customer_deadline_time | timestamptz NULL | 发送时客户回稿时间，区别于之后修改的当前回稿时间 |
| actor_user_id | uuid | 发送人，登录身份取得 |
| actor_name / actor_username | varchar(255) / varchar(100) | 发送时姓名及账号快照 |
| created_at | timestamptz | 发送时间，接口+08:00 |

唯一约束 `uq_translation_requirement_dispatch_request(project_id,request_id)`；索引 `ix_translation_requirement_dispatch_project_time(project_id,created_at,id)`。发送时锁定项目并核对更新时间、通知人部门、有效账号及关联需求归属；原文/译文未保存的草稿不作为关联内容发送。安排、全部接收人及全部通知同事务保存；创建安排不改变父项目版本和业务状态。

`translation_requirement_dispatch_recipient`：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid | 主键 |
| dispatch_id | uuid | 外键至安排，删除安排时级联 |
| user_id / user_name | uuid / varchar(255) | 所选笔译项目部账号及姓名快照 |
| notification_id | uuid | 本次发送给该接收人的通知ID |

唯一约束 `uq_translation_requirement_dispatch_recipient(dispatch_id,user_id)`；user_id 索引。发送人、有项目查看权限者及安排的接收人可查看共有内容；接收人不必额外拥有项目管理权限即可查看本人安排与回复回执。查看权限不授予其他人代为回复的权限。

`translation_requirement_event`：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid | 主键 |
| project_id | uuid | 外键至项目，删除项目时级联 |
| subject_kind / subject_id | varchar(20) / uuid | project、requirement 或 dispatch 的业务身份 |
| event_kind | varchar(20) | project_update、received 或 completed |
| event_key | varchar(180) UNIQUE | 设置按项目+请求ID去重，回执按类型+业务ID+本人ID+步骤去重 |
| actor_user_id | uuid | 实际登录操作人 |
| actor_name / actor_username | varchar(255) / varchar(100) | 操作时姓名与账号快照 |
| payload | json | 项目设置的提交值、修改前后值与原保存结果；或回执 reply 文本，最多500字 |
| created_at | timestamptz | 实际操作时间，接口+08:00 |

检查约束 `ck_translation_requirement_event_kind` 限制项目事件为 project_update，需求/安排事件为 received/completed；索引 `ix_translation_requirement_event_subject(subject_kind,subject_id,event_kind,actor_user_id)` 及 `ix_translation_requirement_event_project_time(project_id,created_at,id)`。项目设置重试返回首次保存的版本，不让旧表单接受其他人后来修改的版本。只有被发送人本人可以回复，锁定其接收人行后依次记录“收到”“已完成”，重复点击不追加回执或通知。旧简单需求的收到时间沿用既有 recipient 行，新增已完成回执写入事件表，不改旧表结构。完成回执不自动改变整个项目状态。

项目经理安排通知类型 `translation_simple_dispatch`，回执通知类型 `translation_simple_dispatch_receipt`；均通过系统通知打开同一可拖动回执窗口。安排、回执、状态/时间修改列表默认10条分页；原需求记录及历史简短记录继续可见。迁移 `tools/apply_translation_dispatch_migration.py` 只创建上述三张新表及约束索引，不修改原有表，启动自动迁移保持关闭。


### 标注项目今日状态汇报（2026-11-01）

- `annotation_work_day`：本人项目按工作报告日（UTC+8、07:00换日）唯一；保存今日进行中/今日暂不进行、预计还需时间、首次进入进行中时间及乐观锁 revision。次日不沿用昨日安排。
- `annotation_work_submission`：每日项目各时点（11、15、18、21、end_shift）唯一汇报；保存完成进度、当日累计分钟、安排与剩余时间快照、提交时间。累计用时不得下降；重复提交拒绝。
- `annotation_work_reminder`：用户、自然日、时点唯一，记录已弹提醒的时间，避免多窗口重复。按班次区间、请假、考勤下班状态判断，周末按已发布值班安排处理。
- 每次汇报原子写入现有 `annotation_project_status_history` 的 progress 记录及当日 `daily_report_item`；同一用户/项目/工作报告日汇总一项，任务类型为标注项目，用时取最新累计值；`display_metadata.source=annotation_work_status`、`annotation_work_day_id` 和 `_feedback_key` 保持关联，旧编辑窗口与重新汇总不得覆盖或丢失汇报。
- 新字段 submitted_at、updated_at、entered_at、reminded_at 使用 timestamptz，接口显式 +08:00；现有进度与报告无时区字段沿用 UTC+8 本地时间存储。迁移仅创建上述三张新表及必要约束，不修改现有表、不回填业务数据；启动自动迁移关闭。

- `annotation_work_availability`：用户/工作报告日/时点唯一的空闲状态（是/否）、预计空闲时间（未定、30分钟内、30-60分钟、1-2小时、2-5小时）、revision 与 timestamptz 更新时间。选择是必须有预估，选择否清空预估。同步工作报告补充说明，不将预计空闲时间计为实际耗时；本功能实际创建四张新表。


### non_project_task_content（非项目任务具体内容）
仅新增扩展表，既有任务及周期模板表结构保持不变，无历史回填。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | UUID | 主键 |
| task_id | UUID，可空 | 非项目任务外键，唯一，级联删除 |
| recurrence_id | UUID，可空 | 周期模板外键，唯一，级联删除 |
| content | TEXT | 具体任务，接口最多10000字，与备注独立 |

两个外键必须且只能填写一个；周期生成时复制模板内容。更新时间沿用所属任务/模板现有的UTC+8业务时间字段。
迁移入口：`tools/apply_non_project_task_content_migration.py`，仅创建新表及必要约束，支持重复执行。

### 标注今日安排状态持续保留（2026-11-01）

- 安排状态及预计还需时间读取当前用户/项目截至当日最近一次人工选择，跨天保持；未调整的项目默认今日进行中。每日汇报、累计耗时及空闲状态仍按工作报告日单独保存。
- 创建当日记录时沿用最近记录的 revision 再递增，避免跨天覆盖旧窗口。今日安排仅显示有效项目中安排状态为进行中的项目；“今日暂不进行”及“全部项目”入口保留恢复能力，列表与总数复用相同 SQL 条件。
- 项目进度上下文按所点项目 ID 查询并核对本人经理归属；每次打开独立表单实例。此调整无需结构迁移和历史数据回填。


### 标注今日具体操作（2026-11-01）

复用 `personal_daily_task`，无需结构迁移。`report_row.display_metadata.operation_source=annotation_daily_operation` 标识标注操作；`operation_stage` 为 `pending`（待进行）、`in_progress`（进行中）、`performed`（已进行）。每个项目的每个具体操作独立保存一行；关联项目由后端核对本人经理归属和今日安排后带出订单号、项目名称及标注项目类型。

- `estimated_minutes` 保存今日预计花费时间；首次进入已进行阶段时复制到 `actual_minutes`，之后实际用时可独立修改。
- `report_row.display_metadata.quantity/quantity_unit` 保存工作量和单位，加入报告时必填。
- `report_item_id` 非空表示已加入报告；加入前持久状态为 pending/in_progress，加入后状态为 completed，阶段仍为 performed。已加入操作不可再次编辑，报告内容在工作报告编辑。
- 按本人和 UTC+8 每日07:00换日的 `work_date` 隔离，跨日旧窗口拒绝写入；revision 防止并发覆盖。加入日报锁定用户及操作并在同一事务写入，重复点击返回已有结果，不重复追加。日报沿用 personal_daily_task 来源，重新汇总和旧草稿保存时保留已加入行。
- 标注操作从笔译今日任务列表排除，显示在状态汇报窗口下方的三个任务区。无历史数据回填、云端部署或结构迁移。


### 状态汇报任务区多业务入口（2026-11-01）

继续复用 `personal_daily_task`，不创建或修改表结构。`report_row.display_metadata.operation_source=annotation_daily_operation` 兼容历史标注任务区标识，新增口译项目、招聘项目、非项目工作和笔译任务也使用该标识；具体类型以 `report_types` 为准。非项目工作不要求项目 ID、订单号和项目名称。

- 点击笔译项目直接读取本人的未完成 `translation_project_arrangement` 和笔译类型自主任务，不附加日期、项目状态、人员筛选，也不分页截断；保留原任务订单/子订单、项目名称、内容和用时。
- `linked_source` 为 assigned/personal，`linked_task_id` 为原任务 UUID；同一用户、工作报告日及来源任务只加入一次。重复点击另一任务区不会重置已加入任务的阶段或编辑内容。
- 加入报告复用原任务完成事务，原任务、任务区记录和报告行一次提交；原入口已完成时识别已有 report_item_id，不重复追加。完成事务统一先锁本人，再锁项目、任务及报告。
- 任务区仍按工作报告日（UTC+8每日07:00换日）保存；标注项目选择仍只显示今日进行中的项目。口译、招聘复用工作报告项目选择器；非项目任务直接填写具体操作、预计用时。


### 工作台口译“我的任务”范围（2026-11-01）

只影响工作台的本人项目目录及任务区口译项目选择，不调整口译项目管理、通用工作报告项目目录。`kuangjiao`（旷姣）、`zixia`（紫霞）账号显示所有非取消、非已结款项目；其他口译项目部成员只显示本人为当前客户经理的同类项目，项目经理身份不额外扩大范围。客户经理以最新项目交接记录为准；没有交接记录时匹配所选母/子客户档案中的客户经理，不以咨询客服身份代替客户经理。

`cancelled`、`settled` 及其中文历史值排除；已部分取消、已结束但未结款项目继续保留。列表与总数使用同一筛选表达式；任务区口译选择默认不限订单日期，并在新建任务提交时复核范围。复用现有数据，无结构迁移或历史数据改写。


### interpretation_work_day：口译项目今日安排（2026-11-02）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | UUID 主键 | 安排记录 ID |
| user_id | UUID 非空 | app_user 外键，级联删除 |
| project_id | UUID 非空 | interpretation_project 外键，级联删除 |
| work_date | DATE 非空 | 工作报告日，UTC+8每日07:00换日 |
| arrangement_status | VARCHAR(20) 非空 | in_progress 今日进行中 / not_today 今日暂不进行 |
| remaining_time | VARCHAR(20) 可空 | 与标注今日安排相同的六档预计还需时间 |
| entered_at | TIMESTAMPTZ 可空 | 当日首次进行时间，接口明确 +08:00 |
| revision | INTEGER 非空 | 正整数并发版本，跨天创建时沿用最近版本递增 |
| updated_at | TIMESTAMPTZ 非空 | UTC+8实际更新时间 |

唯一约束 `(user_id, project_id, work_date)`；状态、预计还需时间和 revision 含检查约束。读取本人/项目截至工作报告日最近一次记录，跨天不重置；未调整时默认今日进行中。安排独立于口译业务状态，不改写取消、结款等项目枚举。

工作台口译列表右侧使用“今日安排”入口，复用标注弹窗、字段搜索、拖动、固定底栏和校验；权限沿用口译“我的任务”范围。项目总览仍按未取消、未结款显示；任务区口译选择进一步排除本人安排为今日暂不进行的项目。

迁移：`tools/apply_interpretation_work_arrangement_migration.py`，仅创建该新表和必要约束，重复执行安全；不修改既有表或历史数据，服务启动不自动迁移。

### 笔译客户财务计价与小计（2026-11-02）

客户多语种参考价扩展（2026-11-02）：

财务修改记录扩展（2026-11-02）：`translation_customer_finance_event`（UUID主键、母项目ID外键/索引，删除级联、操作人ID及姓名快照、操作时间timestamptz）；`translation_customer_finance_event_item`（事件ID外键+订单ID联合主键、订单ID索引、订单号/项目名快照、修改前后JSON）。订单ID不设对子订单的外键，保留下级订单删除前的审计快照。记录价格、语种/货币/口径、调整后总价、说明、账单月份、继承与汇总变化；无实际变化不追加记录。价格、客户参考价回写及审计同事务，记录失败则全部回滚。查询支持按母项目/下级订单筛选与每页10条分页；查看权限沿用笔译项目查看权限。仅记录功能启用后的修改，不伪造过去记录。创建迁移为`tools/apply_translation_finance_audit_migration.py`，仅创建两张新表及必要约束。

客户财务默认筛选本人作为客户经理的订单，并自动打开客户经理筛选窗口；可切换全部或指定姓名。有项目经理变更记录时按最新记录的用户ID匹配；仅无记录的历史项目精确匹配客户档案经理姓名/用户名，避免同名或已清空经理的项目错误回退。列表、总数、客户小计使用同一条件。

客户经理筛选修正（2026-11-02）：“指定客户经理”改为客户部成员多选，人员来自组织架构的主部门及跨部门归属，兼容部门别名；销售部不并入客户部。包含未删除的停用成员并标识停用，便于查询其历史订单。前端提交重复查询参数`manager_ids`，不再传显示姓名作模糊检索。后端以项目最新客户经理用户ID作OR匹配，只有没有项目经理记录的历史订单才按选中人员的姓名/用户名精确回退；同名其他ID、已清空经理及部分姓名匹配不回退。指定人员条件优先于本人默认值，取消不提交草稿，确认后列表/总数/所有分页客户小计复用相同条件。无需新增或迁移数据表。

计价口径与同月订单同步（2026-11-02）：

- 新表`translation_charge_quantity_basis`：收费项ID主键/FK到`translation_sub_order_charge_item.id`（删除级联）、`mode varchar(40) not null`。保存计价数据来源，不改变旧收费表的metric枚举约束。新单价默认`customer_auto`；唯一已填的客户统计栏自动采用，零视为已填；客户多栏时须明确选择，记为`customer_auto:指标`。`company_characters_no_spaces`、`company_words`、`company_cjk_chars_korean_words`、`company_foreign_words`、`company_documents`、`company_pages`分别读取我司六种统计（字符数不计空格、字数、中朝、外文、份数、页数）。旧价格无附属行时仍按原客户指标计算，不自动改写。参考价的既有metric字符串字段保存对应模式，客户端与财务页共用选择器。
- 财务表单在调整后总价之前展示计算得出的总价，按草稿单价实时计算；有下级时按执行保存后的继承规则汇总，保留独立改价的下级，避免重复累计各级数量。缺少数量或客户多栏未选择时标记待填写，不计为零。
- 同月同步只以已保存的来源价格及账单月份为准，按同客户ID、同月份、同语种方向预览母/子/三级及更深订单，未独立登记月份的下级沿用最近上级；若整棵订单仅有一个已登记月份，母订单使用该月份。无可确定月份的订单不参与。确认时再次核对来源和全部匹配订单版本，并同事务更新各级单价及审计；保留数量、说明和能保留的手动调价，不能合并调价时整次回滚并提示具体订单。不写客户参考价，不改其他客户、其他月份或其他方向的订单。
- 可重复执行创建脚本：`tools/apply_translation_quantity_basis_migration.py`，仅创建该新表及必要约束；启动自动迁移保持关闭。

- `customer_translation_rate`：UUID主键，客户ID（FK，删除级联）、计价键SHA256、语种方向、单价Numeric(14,4)、货币、统计口径、计价数量Numeric(14,4)、版本、启用状态、操作人、更新时间timestamptz。唯一约束`(client_id,rate_key)`；金额非负、计价数量正数、版本正数。键由规范语种方向、货币、口径、计价数量组成。
- `translation_charge_direction`：收费项ID主键/FK（删除级联）、语种方向、参考价ID（FK，删除置空）、采用的参考价版本。不更改旧收费表；历史收费项未有关联时继续使用订单原方向展示。
- `customer_translation_rate_history`：UUID主键、客户ID（FK，删除级联）及索引、操作人ID/姓名快照、来源（客户资料/项目同步）、变更前后JSON快照、创建时间timestamptz。保留停用参考价的历史；客户参考价下发与项目价格调整均保留审计快照。
- 同步规则（2026-11-02）：客户参考价自动下发至无单价或仍与原客户参考价一致的项目；项目独立调整过的价格保留。项目回写客户必须点击并确认，校验客户及项目版本并具备写入权限；仅合并本次参考价，不删除客户其他方向。客户财务区域显示全部已登记订单的单价差异（不受客户经理筛选影响），可逐订单确认客户→项目或项目→客户。同步不改变项目数量、加班费、独立总价调整及说明；所有价格变更与审计同事务保存。
- 默认采用客户统计（`customer_auto`），只有一栏已填时直接采用，多栏时明确选择；也可选我司统计的字符数不计空格、字数、中朝、外文、份数或页数。多个方向分别计价，各币种小计，下级仅继承匹配方向。
- 可重复执行迁移：`tools/apply_customer_translation_rates_migration.py`，仅创建上述三张表及必要索引约束；常驻服务不自动迁移。

计价金额仍复用 `translation_sub_order_charge_item` 的母/子订单归属、单价、币种、统计口径、计价单位、账单月份、调整金额及说明字段；参考价与语种关联使用上列三张扩展表，不修改旧收费表结构。客户财务入口支持多条按语种方向计价的收费项；固定收费等其他明细不覆盖或删除。

- 默认人民币；“字数”映射客户统计维度 `characters_no_spaces`，默认每一个字符计价；“份数”“页数”分别映射 `documents`、`pages`，默认每份、每页计价。金额使用 Decimal、按分四舍五入；缺少数量不当作零。
- 母订单单价复制到无独立价格或仍与原上级价格一致的下级；单独修改后的下级价格保留。新增下级在同一创建事务中继承最近上级价格及账单月份，不复制调整金额。
- 订单层级沿订单号重建。存在下级的订单按直接下级金额汇总，最低层订单按自身数量计价，避免同时计入母/子/三级订单的数量。不同币种分别汇总。
- 账单月份筛选按母订单号中的年月判断，支持 TP-YYMMDD-NNN 与历史 TP-YYYYMMDD-NNN；同母订单的各级下级金额一并计入，不按收费项的登记月份拆分。客户、客户经理及关键词均支持多关键词包含匹配。分页、总数、客户小计复用相同条件；客户小计覆盖全部匹配母订单，不只统计当前页。
- 保存使用整棵订单树的价格/数量/更新时间版本摘要校验，并锁定母、子订单；过期表单返回 409。更新已有无时区字段时写入香港本地时间。服务启动不执行迁移。


### 口译客户财务及调整历史（2026-11-02）

- `interpretation_customer_finance`：`id`（字符串UUID主键）、`project_id`（口译项目FK，唯一，可空，级联删除）、`client_id`（客户FK，唯一，可空，级联删除）、`revision`（整数乐观锁版本）、`payload`（JSON）。项目与客户归属必须且只能设置一个。
- `payload` 保存按方向组合的 `rates`（金额、货币、单位、数量、每日/半天小时数、含午餐时间）、加班费开关与总加班费、分币种调整后总价及说明。客户参考价同步只传递单价，不把项目数量、加班费或总价调整复制到客户。
- `interpretation_customer_finance_history`：`id`（字符串UUID主键）、`finance_id`（财务记录FK及索引，级联删除）、`revision`、`actor_id`（用户FK，删除置空）、`actor_name`、`before`/`after`（JSON完整快照）、`created_at`（带时区时间，接口UTC+8）。
- 客户参考价自动带入匹配方向的项目；仍沿用原单价的项目在客户改价时自动更新，保留各项目数量、加班费和调整后总价。独立改价的项目在客户财务区域显示差异，需选择同步方向并确认。项目普通保存不回写客户；显式同步须校验客户版本、项目版本及写入权限。
- 迁移入口 `tools/apply_interpretation_customer_finance_migration.py` 只创建这两张新表及必要索引约束，可重复执行；自动启动迁移保持关闭。

### 笔译预统计及交互调整（2026-11-02）

- 新表 `preliminary_word_count_metric`：`id uuid` 主键；`project_id uuid`、`sub_order_id uuid` 分别外键到母订单、子订单（级联删除），必须且只能填写一个；`metric_type varchar(40)` 使用既有六类指标；`count_value bigint` 非负；`updated_by uuid` 外键到用户（删除置空）；`updated_at timestamptz` 保存明确 UTC+8 的业务时间。项目/指标及子订单/指标分别唯一。迁移入口 `tools/apply_preliminary_word_count_migration.py` 仅创建新表及约束，可重复执行，不修改原字数表。
- 项目矩阵新增 `preliminary`，界面位于“客户统计”之后，显示“预统计（不用以计算费用）”。新增、编辑、各级订单、列表、导出及统计展示共用该维度；客户及我司计费口径均不读取预统计。
- 母订单存在子订单时名称可无扩展名，仍不允许包含多个文件名。新建接口可传 `initial_sub_order_names`（最多100个完整文件名），与母订单同事务创建；没有子订单的独立项目仍校验完整扩展名。
- 客户经理筛选使用独立可拖拽窗口，人员下拉不触发外部点击关闭；支持本人、多选指定及不指定人（全部订单，包括未指定经理）。取消不改变原条件，确认后列表、总数及客户小计使用相同条件。
- 新增笔译项目每次直接打开空白表单，不读取或恢复新增草稿，不显示草稿提示。切换前暂停原编辑草稿，项目ID、订单号、版本及客户/统计/时间字段不从旧内容带入；已有编辑草稿逻辑保持原用途。
- 项目同步客户参考价前重新读取客户最新参考价，显示客户名称/编号及同语种方向的价格、货币、统计口径、数量单位与差异，无对应方向明确提示新增。用户最终确认后再写入，继续校验项目和客户参考价版本；取消及关闭比较窗不写业务数据。


### 笔译字数逐级汇总（2026-11-03）

按订单号点号层级识别直接下级：二级子订单汇总到一级子订单，一级子订单汇总到母订单。四个来源（我司统计、客户统计、预统计、译员预估）的六种计量口径分别求和；空白不视为零，全部空白保持空白，显式零参与汇总。有下级时忽略父级原独立值，避免父级和下级重复相加；无下级继续使用自身统计。汇总在读取时批量计算，不回填历史统计、不改变表结构；列表、详情、字数弹窗、稿件安排和财务数据读取共用相同逻辑。汇总单元格只读，独立矩阵修改接口拒绝直接修改汇总值，完整项目表单保存跳过汇总节点的矩阵。预统计仍不参与计费。

### 客户对账单独立编排（2026-11-04）

- `customer_statement_workspace`：`client_id uuid` 主键/FK 到 `client`（级联删除）；一个客户共用一个编排空间。`revision integer` 为乐观锁；`payload json` 保存 `boards`（对账单编号、名称、抬头/账户/印章/月份文案、显示覆盖、税口径标签、画布 x/y）、`tasks`（以订单 UUID 为唯一键，包含唯一的 `board_id`、独立账单月份、收费行及首次导入 `original` 快照）、`roots`（生成汇总所需的订单树快照）。`updated_by uuid` FK 到用户（删除置空），`updated_at timestamptz` 使用 UTC+8。
- `customer_statement_workspace_history`：`id uuid` 主键；`client_id uuid` FK 到编排表（级联删除、索引）；`revision integer`、`actor_id uuid`（用户FK、删除置空）、`actor_name varchar(255)`、`action varchar(100)`、`changes json`（变更字段及前后值）、`before/after json`（完整编排快照）、`created_at timestamptz`（接口明确 `+08:00`）。恢复操作仍新增审计记录，不删除历史。
- 多月合并导入只添加尚未编排的任务，不覆盖已编辑内容或移动后的归属。任务按订单UUID唯一归属，同一订单的所有语种收费明细一起移动；只修改对账单，不回写项目名称、收费、工作量或原账单月份。修改、移动及恢复必须确认并校验版本；写入时锁定客户及其编排行。
- 行内容可编辑日期、项目名称、翻译方向、数量、计价文案、单价、计价数量、税口径文案、货币、小计和备注，订单号和任务身份不允许修改。抬头、账户、印章、展示月份和画布位置独立保存。调整小计参与导出合计；同时显示父子时汇总参考行不重复计费。不同币种分别合计。
- `tools/apply_customer_statement_workspace_migration.py` 可重复执行，只创建上述新表及索引/外键，不修改已有表；服务启动自动迁移继续关闭。预览、打印和Excel均读取已保存编排；导出检查编排版本，多个对账单输出到同一Excel的不同工作表。


### 客户类型（2026-11-04）

新增 `client_customer_type` 附属表：`id`（UUID 主键）、`client_id`（母客户外键，删除级联）、`sub_client_id`（子客户外键，删除级联）、`customer_type`（必填，限定个人客户／企业客户／行政/事业单位／社会团体／国际组织／NGO）、`updated_at`（带时区，UTC+8）。两个客户外键恰有一个非空，各自唯一。笔译项目客户财务右侧、客户管理基本信息显示同一类型；项目有子客户时读写子客户，否则读写母客户。两边保存共用一份类型记录，读取项目列表批量加载，不复制历史项目。未选择类型保持空白，清空后同步清除；项目保存与类型写入处于同一事务，未传类型的既有接口不清空已存类型。仅创建新表及必要约束，不修改已有表列。


### 项目报价单与单据要求（2026-11-04）

新增 `translation_project_documents`：`project_id`（UUID 主键，引用笔译项目并删除级联）、`statement_required`（可空布尔）、`quotation_data`（报价单 JSON，含标题、客户名称、服务明细、数量、单位、单价、货币及说明）、`quotation_revision`（非空整数，初始 0）、`updated_by`（操作人外键）、`updated_at`（带时区 UTC+8）。报价需求沿用原 `quotation_required` 字段。个人客户默认不需报价单和对账单，其他客户默认不需报价单、需对账单；显式勾选可覆盖默认值。项目表单与财务管理共用报价单弹窗及单份报价内容，新项目报价随主表单事务保存，财务入口直接保存并检查报价修订号；冲突返回 409。对账单勾选直接复用现有 CustomerStatementDialog，新项目需先保存再编排对账单。金额使用十进制定点运算、分币种合计，报价内容独立于项目实际收费。仅创建此新表及外键约束，不修改已有表。

#### 对账单需求确认与客户分组查看（2026-11-04）

- 对账单窗口分为“是否需对账单”“对账单查看”。需求页按母订单编号月份筛选（默认 UTC+8 本月，提供上个月快捷按钮），列表及总数使用同一条件；主表格直接修改 `statement_required`，复用 `translation_project_documents`，不新增重复字段。专用字段更新接口校验旧布尔值和项目更新时间，锁定项目后仅修改该字段并保留操作人/UTC+8更新时间，报价内容不变；项目主表单与列表共用同一值。
- 查看页以客户为入口，支持多关键词搜索、多选客户、按客户展开/收起独立编排区，不再要求选择项目。默认候选客户至少有一个需对账单的笔译项目；关闭该选项后可选择有笔译项目或已有编排记录的客户。显式项目要求优先，未设置时沿用母/子客户类型默认规则；子客户项目归入其母客户，已迁移标注项目排除。
- 编排可直接按 `client_id` 读取及合并导入；按客户导入固定覆盖该客户全部项目，月份仍由用户选择。可勾选“仅导入需对账单项目”，只影响本次新增任务，不移除已有编排。不同客户的任务归属、修改记录、导出和恢复保持隔离。本轮不修改数据库结构。


### 笔译付款情况共用窗口（2026-11-04）

项目表单与财务管理的付款情况复用既有 `finance_record` / `finance_payment`，不新增或修改表结构。新增 `/translation-payments/{project_id}` 查询及保存入口，按项目隔离，读权限为 projects:read 或 finance:read，写权限为 projects:write 或 finance:write。仅替换付款明细，保留原结账方式、发票、总价、备注等财务字段；保留已有付款记录 ID 和未修改记录的确认信息。修改过的明细清除旧确认状态。使用版本摘要防止旧响应覆盖新付款；金额固定为两位小数生成摘要，避免保存前后 Decimal 表示不同引起伪冲突。时间按 UTC+8 传输，既有无时区字段继续保存 UTC+8 业务本地时间。新项目付款草稿通过 payment_draft/payment_version 随项目同事务保存。

## 笔译付款确认与支付凭证（2026-11-04）

收费设置与财务管理付款情况共用母订单付款确认，阶段金额明细继续复用 `finance_record` / `finance_payment`，不自动以确认类型推算金额。

| 表 | 字段 | 含义 |
| --- | --- | --- |
| translation_payment_confirmation | project_id | 母订单 UUID，主键，关联 translation_project |
| translation_payment_confirmation | revision | 乐观锁版本，从 1 递增 |
| translation_payment_confirmation | is_paid | 是否已确认付款，与定金／全款状态对应 |
| translation_payment_confirmation | payment_option | 新界面提供 deposit 已付定金、full 已付全款；兼容历史 once 分次付款。Text 可封装 type、account、full_payment JSON，无需改表 |
| translation_payment_confirmation | proofs | 支付备注及签名截图引用，最多 20000 字符、9 张截图 |
| translation_payment_confirmation | updated_by / updated_at | 修改用户与带时区时间，接口统一 +08:00 |
| translation_payment_confirmation_history | id / project_id / revision | 历史 UUID、母订单与付款确认版本 |
| translation_payment_confirmation_history | actor_id / actor_name | 操作人及姓名快照 |
| translation_payment_confirmation_history | before / after | 修改前后 JSON，包含凭证引用 |
| translation_payment_confirmation_history | created_at | 带时区操作时间，接口统一 +08:00 |

截图字节复用 `editor_screenshot_blob`，业务图片保留类型为 business、expires_at 为空，不随聊天图片到期清理；取消勾选保留截图，移除当前引用不移除历史凭证。所有入口保存时校验付款 revision，防止旧窗口覆盖新付款记录。初始化脚本 `tools/apply_translation_payment_confirmation_migration.py` 可重复执行，仅创建上述两表及必要索引，不更改现有表。

付款账户扩展：`payment_option` 的物理类型保持 Text；有付款账户时存储 JSON 文本 `{"type":"deposit","account":"广州公司公账"}`，兼容历史纯类型值 `full/deposit/once`。接口仍分别提供 `payment_option` 与 `payment_account`（最多50字），无需结构迁移。历史 before/after 保存同样的接口快照；付款明细账户仍复用 `finance_payment.payment_method`。预置账户及自定义账户由公共选择器提供，自定义值随付款记录保存；本机选项缓存按用户隔离。

付款联动与全款核对：实际付款明细有正金额时同步为定金／部分付款，不以“已登记的预定金额全部支付”判定整单全款。手工确认全款时保留已有明细，界面无需继续填写明细。`full_payment` 保存已付金额 `amount`、`currency`、选定项目总价 `total_key`、`reference_label`、`reference_amount`、`match_status`（matched／mismatch）和 `mismatch_reason`。接口以 `full_payment_amount`、`full_payment_currency`、`full_payment_total_key`、`full_match_status`、`full_reference_label`、`full_reference_amount`、`mismatch_reason` 分别返回；金额不匹配时原因必填，标签及比对快照纳入原有修改历史。收费总价变更后重新核对并记录标签变化；未登记金额的历史全款返回 unverified，不伪造匹配结果。付款确认和明细在同一事务中保存，并继续校验付款版本及确认 revision。

尾款累计核对：付款确认为定金且明细包含尾款时，使用全部明细的实际金额累计（各次必须填写，零值有效），复用全款总价匹配、差异原因和历史记录机制。`full_payment.source=details` 表示服务器根据明细生成；`manual` 表示直接全款确认。累计金额不得由客户端覆盖。移除尾款后清除累计核对状态，保留其他明细。


### translation_duration_metric（笔译分钟／小时统计）

新建独立附属表；不改变 `word_count_metric` 和收费明细的既有约束。项目、子订单、稿件安排三种归属必须且只能有一种；同一归属及统计维度只保存一个时长单元格。

| 字段 | 含义 |
| --- | --- |
| id | UUID 主键 |
| project_id / sub_order_id / arrangement_id | 项目、子订单或译员安排；外键删除级联 |
| dimension | company、customer、preliminary、translator_estimate，或安排下的 planned、actual |
| metric_type | minutes 或 hours，二选一 |
| count_value | Numeric(14,4)，非负，零为已填写 |
| updated_by | 修改人，外键置空 |
| updated_at | 带时区时间，UTC+8 |

我司统计、客户统计每行的普通数量及时间合计只能填写一项；修改接口合并清空／填写后校验，历史多项数据不批量删除。父级仍汇总下级，混合分钟和小时统一为分钟。财务 `customer_auto` 自动先用客户唯一已填项，无客户统计则取我司唯一已填项，均未填时返回补录提示；明确选择我司口径时按所选口径计算。时间计价通过既有 `translation_charge_quantity_basis.mode` 保存真实单位，收费表物理 metric_type 使用兼容占位，不将占位用于计价。


对账单需求默认规则：`translation_project_documents.statement_required` 非空时保留手工选择；未手工指定时，个人客户、一次全款确认、或含尾款明细累计与项目总价匹配的已付清项目默认不需对账单，定金和未付清分期不自动取消。Python 读取、SQL 筛选、对账单客户候选及导入共用同一有效值。主表单与“是否需对账单”页签使用同一修改接口和并发检查；子订单随母订单。
客户参考价采用与同步：完整匹配语种方向、实际计量单位、币种、单价对应数量；客户报价必须明确单位，历史自动口径需编辑明确后选用。项目可保留我司／客户来源选择。跨订单批量同步只更新完整匹配项，不覆盖不同单位或币种的收费项，并在预览中列出跳过项。单／多订单客户筛选先应用当前查询条件，再按母订单计数；多订单按客户整体分页，小计基于全部筛选结果。

财务主表账单月份：可识别的笔译订单号按编号年月自动生成，子订单沿用母订单编号月份；展示、筛选、收费窗口及同月单价同步保持一致。`recorded_billing_month` 只保留收费记录中的原始月份，读取不回写历史数据。新保存收费按订单年月写入，审计记录保留原始月份变化。无法识别的历史编号回退已有收费月份，不再默认采用操作当月；对账单工作区跨月调整仍独立保存。


### 笔译财务父子汇总及客户单据分栏（2026-11-05）

- 有下级的订单按下级递归累计各统计单位；我司统计、客户统计分别累计，标记 `suborder_aggregate`，允许父级存在多个单位。末级仍限制每维只填一个统计单位。
- 财务父级的 `price_aggregate`、`prices.source_orders`、`calculated_totals_excl_tax`、`calculated_totals_incl_tax` 为接口派生信息，不落库；父级只读显示来源单价与总价，末级改价逐级刷新，避免重复计费。旧父级收费记录保留在 `recorded_*`，不作为额外金额相加。
- 列表取消独立的“调整后总价”列。不含税及含税总价分别显示计算额、调整后金额；调整值复用原有字段，表示替换后的最终金额，清空恢复计算额，零值有效。
- 对账单管理按订单所属账单月份划分客户；任一项目需对账单则归入需对账单栏，否则归入无需栏。跨栏调整仅改该客户所选月份项目的 `translation_project_documents.statement_required`，不删除已有对账单、不改其他月份。使用项目集合及更新时间摘要校验并发，提交时锁定客户和项目。
- 对账单标题客户经理取当前显示项目的实际归属，支持项目经理转交记录、多位客户经理及未分配状态；不读取登录账号代替。以上均复用已有表，无新增表或数据库结构变更。


### 对账单待入账任务（2026-11-05）

复用 `customer_statement_workspace.payload.tasks`，不新增表或修改已有表结构。任务唯一键不变；`pending=true` 时 `board_id=null`，`month` 为目标账单月份，`pending_from` 保存调配前月份和对账单，`pending_actor`、`pending_at` 保存操作人及 UTC+8 时间。原始项目、收费和订单月份均不修改。

生成月份时在客户锁及工作区版本校验内自动接收目标月份的全部待入账任务；不受原订单月份、当前项目范围或需对账单筛选排除。任务原文及单价等已编辑内容保留。任务字典保证唯一归属，重复生成不重复加入，所有变更与自动纳入清单进入既有历史表的前后快照。删除已接收待入账任务的账单时，这些任务退回待入账，避免重建遗漏；撤销待入账恢复调配前归属，原账单已删除则拒绝撤销并保留队列。

客户月份列表额外包含该月有待入账的客户，即使该月没有原生订单；待入账客户不允许直接移入无需对账单栏。原月份重新导入保留队列状态；多份同月份对账单要求明确目标，失败不消费待入账任务。


### 对账单专门授权及历史重组（2026-11-05）

- `customer_statement_grant`：主键 `(user_id, client_id)`，`edit_content` 控制内容编辑，`cross_client` 控制跨客户调配；`revision` 乐观版本，`granted_by` 授权人，`updated_at` UTC+8 时间。仅已核对账号 `williamzhao`（赵震锋）可以配置或撤销，其他管理员角色不替代该授权。赵震锋保留账单内容与跨客户管理权限。
- `customer_statement_grant_event`：每次授权／撤销保存人员、客户、操作人及姓名、修改前后权限 JSON 与 UTC+8 时间；既有记录不覆盖。
- `customer_statement_task_owner`：`task_id` 主键确保任务跨客户唯一归属，`client_id` 指向当前归属客户；旧账单在用户执行保存动作时登记，不做维护性回填。重新导入跳过其他客户已持有任务，历史恢复也不得制造重复归属。
- 同客户合并、分拆、任务移动及账单重命名不要求内容编辑授权；正文、单价、金额、抬头及恢复原始内容需授权。跨客户需所有来源与目标客户的跨客户授权；迁入任务保留不可由字段编辑修改的 `origin_client_id`、`origin_client_name` 和订单号，正文修改同时校验归属与所有来源客户的内容权限。
- 跨客户操作按客户编号顺序加锁，复核版本与权限，以单一数据库事务保存各客户工作区、任务归属及历史快照；共享 `operation_id` 关联多方记录。失败全量回滚，不允许单独恢复一方跨客户历史，反向调配需走同一跨客户入口。
- 同客户调整复用已有历史表，存储完整 `before/after`；历史接口提供完整快照及逐字段差异。汇总调整无法无损分摊到部分任务、或合并冲突时拒绝处理，不静默丢失或重复金额。


对账单授权支持人员与客户多选，按所选人员×客户组合在同一事务中批量保存；每个组合独立校验 revision 并写入授权调整记录。任一组合版本过期则全部拒绝，不部分提交。混合权限可保留原值，明确选择后才统一变更；无新增表或字段。


财务主表与对账单的客户经理入口复用同一筛选窗口和状态（本人／全部／指定多人）。是否需对账单列表与客户分组复用 `finance_manager_scope.manager_fields`，使用项目最新客户经理身份及历史精确姓名匹配。客户分组待入账按原项目经理筛选，跨客户来源计入归属客户；需求跨栏修改也限定为当前经理与月份范围，版本校验沿用相同范围。仅调整展示与筛选，不修改项目经理归属数据，无结构变更。
### translation_finance_note（笔译财务说明）

按母/子订单保存独立说明，不修改项目名称等原始项目字段。原收费备注作为内部说明读取；存在收费项时内部说明同步其 `remarks`，无收费项时使用本表。客户说明单独保存。新生成对账单只带入客户说明，客户说明为空则备注留空，禁止回退到内部说明或原项目备注。历史对账单快照保持原内容，可通过“更新客户备注”确认同步并保留前后记录。

| 字段 | 含义 |
| --- | --- |
| order_id | 订单 UUID，主键，等于母订单或子订单 ID |
| project_id | 母项目 ID，关联 translation_project，删除级联 |
| sub_order_id | 子订单 ID，可空且唯一，关联 translation_sub_order，删除级联 |
| internal_note | 内部说明，无收费项时的保存位置 |
| customer_note | 客户说明，默认空字符串，作为生成对账单的对外备注 |
| revision | 每次说明修改递增，参与财务版本校验 |
| updated_by | 修改人，关联 app_user，删除置空 |
| updated_at | 修改时间，带时区，业务时间 UTC+8 |

说明修改同时写入既有财务修改记录，保留修改前后内容。初始化脚本：`tools/apply_translation_finance_notes_migration.py`，仅幂等创建新表，不回填旧表。

### customer_statement_company（对账单公司主体）

独立保存公司主体，不修改既有设置表。`key` varchar(30) 主键，当前为 company；`company` varchar(255) 必填，限广州总公司、深圳分公司、上海分公司；`updated_by` UUID 关联 app_user，删除人员时置空；`updated_at` timestamptz，统一 UTC+8。设置修订号沿用 customer_statement_settings.revision，同事务保存。默认广州信实翻译服务有限公司，新生成对账单保存主体快照，历史抬头不回填。

### client_project_confirmation（项目曾确认凭据）

`project_id` UUID 主键并关联 translation_project，删除项目时级联删除；`received_at` timestamptz，可空，记录该项目来稿时间；`confirmed_at` timestamptz 非空，首次确认时间，统一 UTC+8。项目进入已确认、后续正常节点或从已确认回退时，同一业务事务记录凭据并自动更新客户/子客户合作状态。客户列表和详情按相同派生表达式读取历史已确认/正常后续节点，读取不回填业务表；待确认或未确认即取消不自动认定合作。

对账单工作区 JSON 的 fields.issue_date 保存首次生成日期（UTC+8业务日期），读取不随当天改变；旧账单从首次出现的历史版本时间还原展示日期，缺失历史时留空，不回写原数据。

### customer_statement_default（客户对账单默认需求）

client_id UUID 主键关联 client，删除客户级联删除；choice varchar(20)，限 required（默认需）、not_required（默认不需）、unknown（未知）；updated_by UUID 关联 app_user，删除人员置空；updated_at timestamptz 统一 UTC+8。与客户税口径配置共用 customer_statement_preference.revision，同一事务保存。只作为 translation_project_documents.statement_required 为空时的派生默认，明确项目选择优先，已付全款的未设置项目默认不需，未知时沿用客户类型规则，不批量回写项目。

### customer_statement_progress（客户月度对账单进度）

client_id UUID 关联 client、billing_month varchar(7) 联合主键；progress varchar(20) 限 not_started（未开始）、partial（部分完成）、completed（全部完成），无记录时按未开始展示；revision integer 乐观版本；updated_by UUID 关联 app_user；updated_at timestamptz，统一 UTC+8。进度按客户及账单月份独立保存，客户经理筛选不改变该客户当月进度。

### customer_statement_progress_event（对账单进度调整记录）

id UUID 主键；client_id UUID 关联 client，billing_month varchar(7)，分别有索引；before/after varchar(20) 保存调整前后进度；actor_id UUID 关联 app_user，actor_name varchar(255) 保存调整人快照；created_at timestamptz 统一 UTC+8。与进度修改同事务写入，重复提交同状态不增加变化记录。
