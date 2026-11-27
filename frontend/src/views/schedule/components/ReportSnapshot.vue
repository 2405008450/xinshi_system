<template>
  <section class="report-snapshot">
    <ReportDailyNotices :idle-minutes="report.idle_minutes" :items="report.items || []" />
    <el-descriptions :column="2" border size="small"><el-descriptions-item label="姓名">{{report.user_name||'-'}}</el-descriptions-item><el-descriptions-item label="报告日期">{{report.report_date||'-'}}</el-descriptions-item><el-descriptions-item label="班次"><span>{{report.shift?.label || '未安排'}}</span><span v-if="report.shift?.periods?.length"> · {{report.shift.periods.join(' / ')}}</span></el-descriptions-item><el-descriptions-item label="总计时间">{{durationLabel(totalMinutes)}}</el-descriptions-item><el-descriptions-item label="上班打卡时间"><template v-if="report.clock_sessions?.length"><div v-for="(session,index) in report.clock_sessions" :key="index">{{report.clock_sessions.length>1?`第${index+1}段：`:''}}{{formatBusinessDateTime(session.check_in)}}</div></template><span v-else>{{report.clock_sessions==null?'打卡记录暂不可用':'未打卡'}}</span></el-descriptions-item><el-descriptions-item label="下班打卡时间"><template v-if="report.clock_sessions?.length"><div v-for="(session,index) in report.clock_sessions" :key="index">{{report.clock_sessions.length>1?`第${index+1}段：`:''}}{{session.check_out?formatBusinessDateTime(session.check_out):'未下班打卡'}}</div></template><span v-else>{{report.clock_sessions==null?'打卡记录暂不可用':'未打卡'}}</span></el-descriptions-item><el-descriptions-item label="提交时间">{{formatBusinessDateTime(report.finalized_at)}}</el-descriptions-item><el-descriptions-item label="补充说明" :span="2"><ScreenshotText :text="report.supplemental_note || '-'" /></el-descriptions-item></el-descriptions>
    <ReportIdleTime v-if="report.idle_minutes!=null" :minutes="report.idle_minutes" :confirmed="report.idle_declaration_confirmed" :declaration-text="report.idle_declaration_text||''" />
    <div class="snapshot-filter"><el-input v-model="projectFilter" placeholder="筛选项目名称或订单号" clearable /><el-checkbox v-model="onlyLunch">仅看中午加班</el-checkbox></div>
    <div class="report-type-actions"><el-button :type="sortByType?'primary':'default'" @click="sortByType=!sortByType">{{sortByType?'恢复原顺序':'按任务类型排序'}}</el-button></div>
    <section v-if="sortByType" class="report-type-summary">
      <p>按整份报告的大类、子类分别累计，不受项目筛选影响。同一任务在同一大类只计一次；多选子类或大类时分别计入对应分类，各分类用时可能重叠，顶部总计时间不重复计算。</p>
      <section v-for="group in typeSummary" :key="group.type" class="report-type-group">
        <header><strong>{{group.label}}</strong><strong>累计 {{durationLabel(group.minutes)}}</strong></header>
        <section v-for="child in group.children" :key="child.type" class="report-type-subgroup">
          <header><strong>子类：{{child.label}}</strong><span>累计 {{durationLabel(child.minutes)}}</span></header>
          <el-table :data="child.tasks" border size="small"><el-table-column prop="name" label="项目 / 任务" min-width="160" /><el-table-column label="具体任务" min-width="220"><template #default="{row}"><ScreenshotText :text="row.content||'-'" /></template></el-table-column><el-table-column prop="count" label="记录数" width="85" /><el-table-column label="累计时间" min-width="130"><template #default="{row}">{{durationLabel(row.minutes)}}</template></el-table-column></el-table>
        </section>
      </section>
    </section>
    <article v-for="{item,index} in displayedItems" :key="item.display_metadata?._feedback_key||item.id||index" v-show="matchesItem(item)" :class="{'is-child':item.display_metadata?.parent_item_key}">
      <small v-if="['consultation_handoff','technical_development'].includes(item.display_metadata?.source)">{{item.display_metadata.source==='technical_development'?'开发任务':'新咨询对接'}} · 添加时间：{{formatBusinessDateTime(item.display_metadata.added_at)}}</small>
      <header><el-tag v-if="item.display_metadata?.lunch_overtime" type="warning">中午加班 {{item.display_metadata.lunch_start}}–{{item.display_metadata.lunch_end}}</el-tag><strong>{{outline[index]}} {{item.display_metadata?.parent_item_key?'└ 二级工作':'·'}} {{item.task_name||item.task_type}}</strong><el-button v-if="feedback" link type="primary" @click="$emit('feedback',item.display_metadata?._feedback_key||item.id)">反馈此项</el-button></header>
      <p v-if="item.display_metadata?.lunch_overtime">已声明中午确实加班，且未顺延下午上班时间。</p><el-descriptions :column="2" border size="small"><el-descriptions-item label="工作类型" :span="2">{{(item.display_metadata?.report_types||[item.task_type]).map(value=>value.replace('::',' / ')).join('、')}}</el-descriptions-item><el-descriptions-item label="订单号"><ReportItemLink v-if="item.display_metadata?.order_no" :row="item" kind="project" :text="item.display_metadata.order_no" /><span v-else>-</span></el-descriptions-item><el-descriptions-item label="项目名称"><ReportItemLink v-if="item.task_name" :row="item" kind="task" :text="item.task_name" /><span v-else>-</span></el-descriptions-item><el-descriptions-item label="具体任务" :span="2"><ScreenshotText v-if="screenshotIds(item.progress_content).length" :text="item.progress_content" /><ReportItemLink v-else-if="item.progress_content" :row="item" kind="task" :text="item.progress_content" /><span v-else>-</span></el-descriptions-item><el-descriptions-item label="工作量">{{item.display_metadata?.quantity??'-'}} {{item.display_metadata?.quantity_unit==='其他'?item.display_metadata?.quantity_unit_other:item.display_metadata?.quantity_unit}}</el-descriptions-item><el-descriptions-item label="耗时">{{durationLabel(item.duration_minutes)}}</el-descriptions-item><el-descriptions-item v-if="item.result_content" label="工作成果" :span="2"><ScreenshotText :text="item.result_content" /></el-descriptions-item></el-descriptions>
    </article>
  </section>
</template>
<script setup>
import { screenshotIds } from '@/utils/screenshotReferences'
import ScreenshotText from '@/components/common/ScreenshotText.vue'
import {formatBusinessDateTime} from '@/utils/dateTime'
import ReportItemLink from './ReportItemLink.vue'
import ReportIdleTime from './ReportIdleTime.vue'
import ReportDailyNotices from './ReportDailyNotices.vue'
import {durationLabel} from '@/utils/workReportForm'
import {summarizeReportTypes,reportItemsSortedByType} from '@/utils/workReportTypeSummary'
import {computed,ref,watch,onBeforeUnmount} from 'vue'
import {matchesSearch} from '@/utils/searchMatching'
import {reportOutline} from '@/utils/workReportHierarchy'
const props=defineProps({report:{type:Object,required:true},feedback:Boolean})
const totalMinutes=computed(()=>(props.report.items||[]).reduce((sum,item)=>sum+(Number(item.duration_minutes)||0),0))
const sortByType=ref(false)
const typeSummary=computed(()=>summarizeReportTypes(props.report.items||[]))
const displayedItems=computed(()=>sortByType.value?reportItemsSortedByType(props.report.items||[]):(props.report.items||[]).map((item,index)=>({item,index})))
const projectFilter=ref(''),appliedFilter=ref(''),onlyLunch=ref(false);let timer
watch(projectFilter,value=>{clearTimeout(timer);if(!value)appliedFilter.value='';else timer=setTimeout(()=>{appliedFilter.value=value},400)})
onBeforeUnmount(()=>clearTimeout(timer))
const matchesItem=item=>(!onlyLunch.value||item.display_metadata?.lunch_overtime)&&matchesSearch(`${item.task_name} ${item.display_metadata?.order_no||''}`,appliedFilter.value)
const outline=computed(()=>reportOutline(props.report.items||[]))
defineEmits(['feedback'])
</script>
<style scoped>
.report-snapshot :deep(.el-descriptions__table){display:block;width:100%;border-right:1px solid var(--el-border-color-lighter);border-bottom:1px solid var(--el-border-color-lighter)}
.report-snapshot :deep(.el-descriptions__table>tbody){display:block;width:100%}
.report-snapshot :deep(.el-descriptions__table>tbody>tr){display:grid;grid-template-columns:16% 34% 16% 34%;width:100%}
.report-snapshot :deep(.el-descriptions__cell){box-sizing:border-box;min-width:0;width:auto!important;border:0;border-top:1px solid var(--el-border-color-lighter);border-left:1px solid var(--el-border-color-lighter);overflow-wrap:anywhere}
.report-snapshot :deep(.el-descriptions__content[colspan="3"]){grid-column:span 3}
.report-snapshot :deep(.el-descriptions__content .el-button){max-width:100%;height:auto;white-space:normal;text-align:left;overflow-wrap:anywhere}
.report-snapshot :deep(.el-descriptions__content .el-button>span){min-width:0;white-space:normal;overflow-wrap:anywhere}
@media(max-width:600px){.report-snapshot :deep(.el-descriptions__table>tbody>tr){grid-template-columns:100px minmax(0,1fr)}.report-snapshot :deep(.el-descriptions__content[colspan="3"]){grid-column:span 1}}
</style>
<style scoped>.report-type-actions{margin-top:12px}.report-type-summary>p{font-size:13px;color:#64748b;line-height:1.6;white-space:normal}.report-type-group{margin-top:16px}.report-type-group>header{padding:10px 12px;background:#f1f5f9;border-radius:4px;flex-wrap:wrap}.report-type-subgroup{margin:12px 0 0 16px}.report-type-subgroup>header{flex-wrap:wrap;font-size:14px}.report-type-group :deep(.el-table .cell){white-space:normal;overflow-wrap:anywhere}@media(max-width:600px){.report-type-subgroup{margin-left:0}}</style>
<style scoped>.report-snapshot{white-space:pre-wrap;overflow-wrap:anywhere}.report-snapshot article{margin-top:16px}.report-snapshot header{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:6px}.report-snapshot :deep(.el-descriptions__cell){word-break:break-word}</style>
<style scoped>.report-snapshot article.is-child>header{border-left:4px solid #409eff;padding:8px 10px;background:#eff6ff}</style>

<style scoped>.snapshot-filter{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-top:12px}.snapshot-filter .el-input{width:260px}</style>
