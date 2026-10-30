<template>
  <section class="report-snapshot">
    <el-descriptions :column="2" border size="small"><el-descriptions-item label="姓名">{{report.user_name||'-'}}</el-descriptions-item><el-descriptions-item label="日期">{{report.report_date||'-'}}</el-descriptions-item><el-descriptions-item label="补充说明" :span="2">{{report.supplemental_note||'-'}}</el-descriptions-item></el-descriptions>
    <div class="snapshot-filter"><el-input v-model="projectFilter" placeholder="筛选项目名称或订单号" clearable /><el-checkbox v-model="onlyLunch">仅看中午加班</el-checkbox></div>
    <article v-for="(item,index) in report.items||[]" :key="item.display_metadata?._feedback_key||item.id||index" v-show="matchesItem(item)" :class="{'is-child':item.display_metadata?.parent_item_key}">
      <small v-if="['consultation_handoff','technical_development'].includes(item.display_metadata?.source)">{{item.display_metadata.source==='technical_development'?'开发任务':'新咨询对接'}} · 添加时间：{{formatBusinessDateTime(item.display_metadata.added_at)}}</small>
      <header><el-tag v-if="item.display_metadata?.lunch_overtime" type="warning">中午加班 {{item.display_metadata.lunch_start}}–{{item.display_metadata.lunch_end}}</el-tag><strong>{{outline[index]}} {{item.display_metadata?.parent_item_key?'└ 二级工作':'·'}} {{item.task_name||item.task_type}}</strong><el-button v-if="feedback" link type="primary" @click="$emit('feedback',item.display_metadata?._feedback_key||item.id)">反馈此项</el-button></header>
      <p v-if="item.display_metadata?.lunch_overtime">已声明中午确实加班，且未顺延下午上班时间。</p><el-descriptions :column="2" border size="small"><el-descriptions-item label="工作类型" :span="2">{{(item.display_metadata?.report_types||[item.task_type]).map(value=>value.replace('::',' / ')).join('、')}}</el-descriptions-item><el-descriptions-item label="订单号"><ReportItemLink v-if="item.display_metadata?.order_no" :row="item" kind="project" :text="item.display_metadata.order_no" /><span v-else>-</span></el-descriptions-item><el-descriptions-item label="项目名称"><ReportItemLink v-if="item.task_name" :row="item" kind="task" :text="item.task_name" /><span v-else>-</span></el-descriptions-item><el-descriptions-item label="具体任务" :span="2"><ReportItemLink v-if="item.progress_content" :row="item" kind="task" :text="item.progress_content" /><span v-else>-</span></el-descriptions-item><el-descriptions-item label="工作量">{{item.display_metadata?.quantity??'-'}} {{item.display_metadata?.quantity_unit==='其他'?item.display_metadata?.quantity_unit_other:item.display_metadata?.quantity_unit}}</el-descriptions-item><el-descriptions-item label="耗时">{{durationLabel(item.duration_minutes)}}</el-descriptions-item><el-descriptions-item v-if="item.result_content" label="工作成果" :span="2">{{item.result_content}}</el-descriptions-item></el-descriptions>
    </article>
  </section>
</template>
<script setup>
import {formatBusinessDateTime} from '@/utils/dateTime'
import ReportItemLink from './ReportItemLink.vue'
import {durationLabel} from '@/utils/workReportForm'
import {computed,ref,watch,onBeforeUnmount} from 'vue'
import {matchesSearch} from '@/utils/searchMatching'
import {reportOutline} from '@/utils/workReportHierarchy'
const props=defineProps({report:{type:Object,required:true},feedback:Boolean})
const projectFilter=ref(''),appliedFilter=ref(''),onlyLunch=ref(false);let timer
watch(projectFilter,value=>{clearTimeout(timer);if(!value)appliedFilter.value='';else timer=setTimeout(()=>{appliedFilter.value=value},400)})
onBeforeUnmount(()=>clearTimeout(timer))
const matchesItem=item=>(!onlyLunch.value||item.display_metadata?.lunch_overtime)&&matchesSearch(`${item.task_name} ${item.display_metadata?.order_no||''}`,appliedFilter.value)
const outline=computed(()=>reportOutline(props.report.items||[]))
defineEmits(['feedback'])
</script>
<style scoped>.report-snapshot{white-space:pre-wrap;overflow-wrap:anywhere}.report-snapshot article{margin-top:16px}.report-snapshot header{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:6px}.report-snapshot :deep(.el-descriptions__cell){word-break:break-word}</style>
<style scoped>.report-snapshot article.is-child{margin-left:24px;border-left:4px solid #409eff;padding:10px;background:#eff6ff}</style>

<style scoped>.snapshot-filter{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-top:12px}.snapshot-filter .el-input{width:260px}</style>
