<template>
  <section class="report-snapshot">
    <el-descriptions :column="2" border size="small"><el-descriptions-item label="姓名">{{report.user_name||'-'}}</el-descriptions-item><el-descriptions-item label="日期">{{report.report_date||'-'}}</el-descriptions-item><el-descriptions-item label="补充说明" :span="2">{{report.supplemental_note||'-'}}</el-descriptions-item></el-descriptions>
    <article v-for="(item,index) in report.items||[]" :key="item.display_metadata?._feedback_key||item.id||index" :class="{'is-child':item.display_metadata?.parent_item_key}">
      <small v-if="item.display_metadata?.source==='consultation_handoff'">新咨询对接 · 追加于 {{formatBusinessDateTime(item.display_metadata.added_at)}}</small>
      <header><strong>{{outline[index]}} {{item.display_metadata?.parent_item_key?'└ 二级工作':'·'}} {{item.task_name||item.task_type}}</strong><el-button v-if="feedback" link type="primary" @click="$emit('feedback',item.display_metadata?._feedback_key||item.id)">反馈此项</el-button></header>
      <el-descriptions :column="2" border size="small"><el-descriptions-item label="工作类型" :span="2">{{(item.display_metadata?.report_types||[item.task_type]).map(value=>value.replace('::',' / ')).join('、')}}</el-descriptions-item><el-descriptions-item label="订单号">{{item.display_metadata?.order_no||'-'}}</el-descriptions-item><el-descriptions-item label="项目名称">{{item.task_name||'-'}}</el-descriptions-item><el-descriptions-item label="具体任务" :span="2">{{item.progress_content||'-'}}</el-descriptions-item><el-descriptions-item label="工作量">{{item.display_metadata?.quantity??'-'}} {{item.display_metadata?.quantity_unit==='其他'?item.display_metadata?.quantity_unit_other:item.display_metadata?.quantity_unit}}</el-descriptions-item><el-descriptions-item label="耗时">{{durationLabel(item.duration_minutes)}}</el-descriptions-item><el-descriptions-item v-if="item.result_content" label="工作成果" :span="2">{{item.result_content}}</el-descriptions-item></el-descriptions>
    </article>
  </section>
</template>
<script setup>
import {formatBusinessDateTime} from '@/utils/dateTime'
import {durationLabel} from '@/utils/workReportForm'
import {computed} from 'vue'
import {reportOutline} from '@/utils/workReportHierarchy'
const props=defineProps({report:{type:Object,required:true},feedback:Boolean})
const outline=computed(()=>reportOutline(props.report.items||[]))
defineEmits(['feedback'])
</script>
<style scoped>.report-snapshot{white-space:pre-wrap;overflow-wrap:anywhere}.report-snapshot article{margin-top:16px}.report-snapshot header{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:6px}.report-snapshot :deep(.el-descriptions__cell){word-break:break-word}</style>
<style scoped>.report-snapshot article.is-child{margin-left:24px;border-left:4px solid #409eff;padding:10px;background:#eff6ff}</style>
