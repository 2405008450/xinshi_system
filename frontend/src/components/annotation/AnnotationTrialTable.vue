<template>
  <el-table ref="tableRef" :data="rows" v-loading="loading" border row-key="id" @selection-change="$emit('selection-change',$event)">
    <el-table-column v-if="deleteMode" type="selection" width="48" fixed="left" />
    <el-table-column type="index" label="序号" width="65" fixed="left" />
    <el-table-column v-for="column in columns" :key="column.key" :label="column.label" :prop="column.key" :width="column.width" :min-width="column.minWidth" :show-overflow-tooltip="column.tooltip!==false">
      <template #default="{row}">
        <template v-if="column.key==='activityType'">{{ activityLabels[row.activityType]||'-' }}</template>
        <template v-else-if="column.key==='dutyRole'">{{ dutyLabels[row.dutyRole]||'-' }}</template>
        <el-tag v-else-if="column.key==='candidateStage'" :type="stageType(row.candidateStage)" size="small">{{ stageLabels[row.candidateStage]||'-' }}</el-tag>
        <el-tag v-else-if="column.key==='willingnessLevel'&&row.willingnessLevel" :type="levelType(row.willingnessLevel)" size="small">{{ levelLabels[row.willingnessLevel] }}</el-tag>
        <template v-else-if="column.key==='willingnessLevel'">-</template>
        <template v-else-if="column.key==='quote'">{{ quoteText(row) }}</template>
        <template v-else-if="column.key==='trialResult'">{{ resultLabels[row.trialResult]||'-' }}</template>
        <template v-else-if="column.key==='latestFollowUp'">{{ latestFollowUpText(row) }}</template>
        <template v-else-if="column.type==='datetime'">{{ formatDateTime(row[column.key]) }}</template>
        <template v-else-if="column.customField">{{ customText(row.customValues?.[column.customField.id]) }}</template>
        <template v-else>{{ text(row[column.key]) }}</template>
      </template>
    </el-table-column>
    <el-table-column label="详情" width="90" fixed="right" align="center">
      <template #default="{row}"><BusinessDetailPopover :row="row" title="试标/试采记录详情"><template #content><AnnotationTrialDetail :row="row" :custom-fields="customFields" /></template></BusinessDetailPopover></template>
    </el-table-column>
    <el-table-column v-if="!deleteMode" label="操作" width="210" fixed="right" align="center">
      <template #default="{row}"><div class="trial-row-actions"><el-button link type="primary" @click="$emit('follow-up',row)">跟进</el-button><el-button link type="primary" @click="$emit('accounts',row)">账号</el-button><PrimaryEditButton v-if="canWrite" @click="$emit('edit',row)" /></div></template>
    </el-table-column>
  </el-table>
</template>

<script setup>
import { ref } from 'vue'
import AnnotationTrialDetail from './AnnotationTrialDetail.vue'
import BusinessDetailPopover from '@/components/common/BusinessDetailPopover.vue'
import PrimaryEditButton from '@/components/common/PrimaryEditButton.vue'
import { formatDateTimeMinute as formatDateTime } from '@/utils/dateTime'

defineProps({rows:{type:Array,default:()=>[]},columns:{type:Array,default:()=>[]},customFields:{type:Array,default:()=>[]},loading:{type:Boolean,default:false},deleteMode:{type:Boolean,default:false},canWrite:{type:Boolean,default:false}})
defineEmits(['selection-change','follow-up','accounts','edit'])
const tableRef=ref(null)
defineExpose({clearSelection:()=>tableRef.value?.clearSelection?.()})
const activityLabels={trial:'试标',collection:'试采'},dutyLabels={executor:'执行',quality_inspector:'质检'}
const stageLabels={backup:'备选',contacted:'已联系',pending_confirmation:'待确认',confirmed:'已确认',in_progress:'进行中',submitted:'已提交',reviewed:'已评审',withdrawn:'已退出'}
const resultLabels={passed:'通过',failed:'未通过',partially_passed:'部分通过',withdrawn:'退出'},levelLabels={high:'高',medium:'中',low:'低'},billingLabels={occurrence:'次',item:'条',work_hour:'工作小时',effective_hour:'有效小时'}
const stageType=value=>({backup:'info',contacted:'',pending_confirmation:'warning',confirmed:'primary',in_progress:'primary',submitted:'warning',reviewed:'success',withdrawn:'danger'}[value]||'info')
const levelType=value=>({high:'success',medium:'warning',low:'info'}[value]||'info')
const text=value=>value===null||value===undefined||value===''?'-':String(value)
const customText=value=>Array.isArray(value)?value.join('、')||'-':value===true?'是':value===false?'否':text(value)
const quoteText=row=>row.quoteAmount?`${row.quoteAmount} ${row.quoteCurrency||'CNY'} / ${billingLabels[row.billingUnit]||'-'}`:'-'
const latestFollowUpText=row=>row.latestFollowUpAt?`${row.latestFollowUpByName||'未知用户'} · ${formatDateTime(row.latestFollowUpAt)}`:'-'
</script>

<style scoped>.trial-row-actions{display:inline-flex;align-items:center;gap:4px;white-space:nowrap}</style>
