// 当前真实组件的演示截图；不包含真实客户、财务或考勤资料。
const base='/help/20261129/'
const shot=(name,caption)=>({src:base+name,alt:caption,caption:caption+'（演示数据，点击图片放大）'})
export const helpScreenshotCatalog={
 regions:shot('chat-regions.jpg','会话：从左到右为功能导航、会话分组、会话列表和聊天内容区'),
 folders:shot('chat-personal-root.jpg','会话分组：点击整行展开或折叠，自定义目录位于公共目录之后'),
 personal:shot('personal-folders.jpg','自定义：文件夹中可同时整理项目群、普通群和单聊'),
 personalCreate:shot('personal-folder-create.jpg','自定义右侧＋：新建仅当前账号可见的个人文件夹'),
 favorites:shot('favorites-four-tabs.jpg','分组区星星打开收藏夹：消息收藏、各类项目、技术/开发项目、其他会话/群'),
 favoriteProjects:shot('favorites-projects.jpg','收藏夹→各类项目：按类型整理，支持搜索、类型置前和底部分页'),
 favoriteAdd:shot('favorites-add.jpg','收藏夹→加入收藏：搜索项目、订单号或会话后选择加入'),
 favoriteMessages:shot('favorite-messages.jpg','收藏夹→消息收藏：定位原消息、移除标签或取消收藏'),
 tagEditor:shot('favorite-tag-editor.jpg','消息收藏→标签：色块与名称一起显示，可搜索、创建或多选标签'),
 tagSave:shot('favorite-tag-save.jpg','标签选定后再次按 Enter，或点击保存；×只移除当前消息的标签'),
 tagFilter:shot('favorite-tag-filter.jpg','消息收藏上方的标签下拉：按色块和名称筛选'),
 mention:shot('mention-collapsed.jpg','@我：发送人区域默认折叠，未读提示与消息来源一起显示'),
 mentionMulti:shot('mention-multiple.jpg','展开发送人后可同时选择多人，再次点击取消该人；全部清除人员限制'),
 format:shot('chat-text-format.jpg','输入区→文字格式：红蓝文字、浅蓝/黄色高亮、加粗及三种颜色的下划线'),
 search:shot('chat-history-search.jpg','聊天窗口右上角搜索：消息类型、发送人、日期、消息收藏和文字格式可组合筛选'),
 notifications:shot('notification-filters.jpg','通知查询栏：关键词、类型、阅读状态、发送人、执行状态共同生效'),
 execution:shot('notification-execution.jpg','执行状态下拉：待执行、已收到、执行中、已完成、已取消或不涉及执行'),
 entry:shot('project-conversation-entry.jpg','项目管理→操作→…：未创建时显示创建会话，已有会话显示进入会话'),
 closed:shot('chat-recent-closed.jpg','会话列表→最近关闭：恢复会话或移除关闭记录，不删除消息'),
 statistics:shot('statistics-filters.jpg','四类项目→数据统计：日期在上方，统计周期在左、客户查询在右'),
 advanced:shot('statistics-advanced.jpg','数据统计→高级筛选：选择日期依据和计费口径'),
 charts:shot('statistics-customer-charts.jpg','周期概览或客户明细下方：新老客户、订单数量和金额分布，点击扇形或文字查看客户'),
 reasons:shot('statistics-reasons.jpg','口译/招聘→查看未成交原因：一级原因饼图'),
 reasonLevels:shot('statistics-reason-levels.jpg','点击原因后进入下一级，顶部面包屑与返回上一级保留路径'),
 reasonCustomers:shot('statistics-reason-customers.jpg','原因或状态饼图→客户明细：每页10条，可继续查看客户及订单'),
 cohort:shot('client-cohort.jpg','客户管理→新老客户：自动判断、手动调整及原因说明'),
 client:shot('client-editor.jpg','客户管理→新增或编辑：基本信息、客户关系和财务信息分区填写'),
 progress:shot('interpretation-progress.jpg','口译项目→项目进度：状态、节点时间、具体进度与保存方式'),
 progressTypes:shot('interpretation-progress-types.jpg','进度类型下拉：项目进度、客户进度、译员情况'),
 customerProgress:shot('interpretation-customer-progress.jpg','客户进度：默认提醒该项目负责人中的其他人，可调整后保存'),
 cancel:shot('project-cancellation-reasons.jpg','项目取消或原因复核：选择分级原因，保留原说明并填写补充信息'),
 requirements:shot('interpretation-requirements.png','新增/编辑口译项目→译员要求与安排：方向人数带入、条件填写及底部发送操作'),
 rates:shot('interpretation-rates.png','口译方向→组合单价：同一方向可分别登记天、半天等单位、数量及小计'),
 financeSettings:shot('finance-customer-settings.png','客户及子客户结算设置：单据需求、账期与结算对象分别维护'),
 financeDocuments:shot('finance-documents.png','发票窗口：结算项目、开票资料、截图备注与修改记录'),
 financeNotes:shot('finance-total-notes.png','价格与付款→总价与说明：计费口径、调整金额、内部说明及客户说明'),
 payment:shot('payment-match.jpg','已付全款：核对付款币种、金额和对应项目总价'),
 meeting:shot('meeting-entry.jpg','会话导航→会议：新增会议、日期范围、状态、回执及详情入口'),
 meetingCreate:shot('meeting-create.jpg','新增会议：编号自动生成，参与部门与人员在同一框多选，底部确认按钮固定'),
 report:shot('work-report-form.jpg','会话…→工作报告：直接打开填写窗口，底部保存和确认按钮始终可见'),
 reportRow:shot('work-report-new-row.jpg','工作报告新增一行：任务/项目类型、订单、客户名、具体任务和耗时分别填写'),
 status:shot('workbench-status.png','工作台→状态汇报：待进行、进行中、已进行任务与工作报告衔接'),
 reminder:shot('status-reminder.png','网页内状态汇报提醒：进入填写或稍后填写，区别于铃铛和Windows通知'),
 talent:shot('talent-registration.png','登记新译员：联系方式与简历路径；校验失败会定位需要补充的字段'),
 note:shot('development-note.jpg','会话→开发笔记：正文格式、截图、文件、保存与保存历史，入口按账号授权显示')
}
const refs={
 会话:{'chat-start':['regions'],'chat-folders':['folders'],'chat-recent-all':['regions','closed'],'chat-favorites':['favorites','favoriteProjects'],'chat-recent-closed':['closed'],'chat-mentions':['mention','mentionMulti'],'chat-history-search':['search'],'chat-text-format':['format'],'chat-notifications':['notifications','execution'],'chat-project-events':['entry'],'chat-project-report':['report','reportRow'],'chat-personal-folders':['personal','personalCreate'],'chat-message-tags':['favoriteMessages','tagEditor','tagSave','tagFilter'],'chat-development-notes':['note']},
 口译:{'project-basics':['requirements'],'project-name':['requirements'],'schedule-locations':['requirements'],'demand-release':['requirements'],'demand-language-count':['requirements'],'demand-office':['requirements'],'customer-requirements':['requirements'],'interpreter-arrangement':['requirements','rates'],'send-demand':['requirements'],'public-demand-execution':['notifications'],'demand-settings':['notifications'],'interpretation-settings':['requirements','entry'],'finance-unified-workflow':['financeNotes','rates'],'finance-customer-settings':['financeSettings'],'finance-period-documents':['financeSettings','financeDocuments'],'finance-payments-ledger':['payment'],'progress-tracks':['progressTypes','customerProgress'],'cancellation-review':['cancel','reasonLevels'],'statistics-current':['statistics','charts','reasonCustomers']},
 笔译:{'project-intake-report':['report'],'received-notifications':['notifications'],'business-statistics':['statistics','charts'],'finance':['financeNotes','payment'],'finance-sub-client':['financeSettings'],'finance-notes-sync':['financeNotes'],'finance-statements-current':['financeDocuments'],'project-conversation-entry':['entry'],'draft-number-search':['reportRow']},
 工作台:{'report-categories':['reportRow'],'report-idle':['report'],'workbench-tasks':['status'],'today-collaboration':['regions'],'report-shift-duration':['report'],'reports-period-order':['reportRow'],'reports-feedback-audience':['notifications'],'attendance-department-pages':['status'],'report-client-and-paths':['reportRow'],'status-reminder':['reminder']},
 会议:{'meeting-create':['meeting','meetingCreate'],'meeting-status':['meeting'],'meeting-types':['meetingCreate'],'meeting-agendas':['meetingCreate'],'meeting-receipts':['meeting','notifications'],'meeting-actual':['report'],'meeting-records':['meetingCreate','reportRow']},
 财务:{'workflow-overview':['financeNotes','financeDocuments'],'workflow-sync':['financeSettings'],'entries':['financeSettings'],'price-entry':['financeNotes'],'pricing-and-settlement':['financeNotes'],'document-and-receipt':['financeDocuments'],'finance-work-report':['report'],'interpretation-finance-flow':['rates','financeNotes'],'annotation-recruitment-finance-flow':['financeNotes'],'statement-requirement-independent':['financeSettings'],'pricing':['financeNotes'],'reference':['financeSettings'],'required':['financeSettings'],'invoice-request':['financeDocuments'],'payment':['payment'],'sync':['financeSettings'],'recent':['payment'],'business-statistics':['statistics','charts'],'full-payment-verification':['payment']},
 客户管理:{'customer-entry':['client'],'customer-record':['client'],'customer-registration-source':['client'],'customer-name-history':['client'],'customer-children':['client'],'customer-finance':['financeSettings'],'customer-sub-client-settlement':['financeSettings'],'customer-history':['client'],'customer-invoice-profiles':['financeDocuments'],'customer-sub-client-statements':['financeSettings'],'customer-collection-rebate':['payment'],'oral-finance-preferences':['financeSettings'],'customer-cohort':['cohort']},
 招聘:{'project-entry':['entry'],'project-query':['statistics'],'project-cancellation':['cancel','reasons'],'project-statistics':['charts','reasonCustomers'],'project-report':['reportRow'],'project-files':['reportRow']},
 标注:{'project-entry':['entry'],'project-query':['statistics'],'project-statistics':['charts'],'project-report':['reportRow'],'project-files':['reportRow'],'annotation-status':['status']}
}
export function helpSectionImages(moduleLabel,section){
 const named=(refs[moduleLabel]?.[section.id]||[]).map(key=>helpScreenshotCatalog[key]).filter(Boolean)
 const all=[...(section.images||[]),...(section.image?[section.image]:[]),...named]
 return [...new Map(all.map(image=>[image.src,image])).values()]
}
