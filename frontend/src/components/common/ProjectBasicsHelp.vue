<template><ProjectOperationHelp :title="label+'项目操作帮助'" :module-label="label" :intro="'查阅'+label+'项目的会话、查询、统计与日常协作入口。'" :sections="sections" updated-at="2026-11-29" :id-prefix="module+'-basics-help-'"/></template>
<script setup>
import {computed} from 'vue'
import ProjectOperationHelp from './ProjectOperationHelp.vue'
const props=defineProps({module:{type:String,default:'recruitment'}})
const label=computed(()=>props.module==='annotation'?'标注':'招聘')
const sections=computed(()=>[
 {id:'project-entry',group:'项目协作',title:'创建与进入项目会话',steps:[`在${label.value}项目管理列表，点击操作中的更多按钮，再选择创建会话或进入会话。会话导航中的项目列表也提供同样入口。`,'已有会话沿用原记录；进入不会重复发送项目概览。创建需项目编辑权限，查看权限不能代替会话参与资格。','打开会话后可发送文字、截图和文件。会话顶部星星收藏整个会话，消息右键的消息收藏只收藏单条内容。']},
 {id:'project-query',group:'查找与统计',title:'查询、项目状态与我的项目',paragraphs:['关键词按空白分成多个词，每个词都要命中，顺序不限；停顿400毫秒自动查询，也可回车或点击查询。高级条件在浮窗中组合使用。','会话的项目状态目录和日期文件夹是两种呈现方式；会话标题上的项目状态显示当前项目本身的状态。我的项目只按本账号的项目经理或客户经理归属筛选。']},
 {id:'project-statistics',group:'查找与统计',title:'数据统计与客户明细',steps:['在项目列表点击数据统计，选择日期和周期；母订单按单计数，不重复累计下级订单。','按客户全称、简称或编号查询。金额分币种展示，不把不同币种直接相加；新老客户按四类项目合并判断。','点击饼图扇形或文字打开客户明细，每页10条；主查询条件及图表范围需要一起核对。']},
 ...(props.module==='recruitment'?[{id:'project-cancellation',group:'项目协作',title:'项目取消必须填写原因',paragraphs:['招聘项目调整为取消时必须选择或填写取消原因；不要只改状态后留下空说明。','未成交原因可在统计中逐级查看，点击扇形或文字打开客户明细；多选原因时，同一项目可进入多个原因分类。']}]:[{id:'annotation-status',group:'项目协作',title:'状态汇报、进度与工作报告',paragraphs:['从状态汇报整理待进行、进行中与已进行任务，再按实际操作填写工作量和耗时。','状态汇报与工作报告是不同记录；填写完成后按相应入口保存或确认，不把本机草稿等同于正式保存。']}]),
 {id:'project-report',group:'项目协作',title:'会话内填写工作报告',paragraphs:['会话右上角…→工作报告，直接弹出本人填写窗口，不跳到工作台选项卡。','项目任务自动带入客户名；未关联订单的任务可搜索并选择客户。工作量摘要可打开只读表单，报告中的项目路径、原文路径按原权限查看。']},
 {id:'project-files',group:'项目协作',title:'项目文件、文件路径与查看权限',paragraphs:['从项目或会话中提供的文件入口打开项目文件。路径显示或复制不代表该机器已经取得共享目录权限。','会话参与人、项目权限和文件权限分别检查；收藏、个人目录及打开帮助不会扩大任何访问权限。']}
])
</script>
