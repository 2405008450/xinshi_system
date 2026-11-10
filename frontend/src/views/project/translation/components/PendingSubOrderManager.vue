<template>
  <DraggableFormDialog :model-value="modelValue" class="pending-suborder-manager" title="子订单管理 · 保存前填写" width="min(1500px, calc(100vw - 32px))" top="4vh" append-to-body @update:model-value="visible=>visible?$emit('update:modelValue',true):cancel()">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" title="子订单管理 · 保存前填写" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="editorBodyRef" class="pending-suborder-body">
    <el-alert title="此处填写的是尚未保存的子订单。每个文件订单至少填写一项我司统计或客户统计；预统计不作为完成资料。确认后随母订单一起保存。" type="info" :closable="false" />
    <el-alert v-if="directionOnly" title="各翻译方向复制母订单统计，可独立修改；母订单保留原登记数量，不累加方向子订单。" type="info" :closable="false" />
    <VerticalSplitPanels v-if="modelValue" top-label="统计填写区" bottom-label="子订单编辑区" :default-ratio=".5" :min-top="140" :min-bottom="140">
    <template #top>
    <SubOrderStatisticsGrid ref="grid" :rows="rows" editable local @saved="persist" />
    </template>
    <template #bottom>
    <div class="pending-suborder-editor">
    <AppForm v-if="selected" :model="selected" label-width="130px">
      <el-form-item label="编辑子订单"><el-select v-model="selectedId" style="width:100%"><el-option v-for="row in rows" :key="row.id" :value="row.id" :label="row.subOrderNo+' / '+row.subProjectName" /></el-select></el-form-item>
      <OrderInheritedExtras :model="selected" />
      <el-form-item label="翻译方向" prop="languagePair"><LanguagePairSelect v-model="selected.languagePair" :single="selected.id.split('.').length>=4" :show-hint="false" /><div class="pending-language-hint">默认复制母订单，可单独编辑；已单独修改的方向保留。</div></el-form-item>
      <el-form-item label="文本类型"><el-input v-model="selected.fileTypeSecondary" /></el-form-item>
      <el-form-item label="原文路径"><el-input v-model="selected.networkFilePath" clearable placeholder="自动填写“同上一级订单”，可单独修改" /></el-form-item>
      <el-form-item label="客户交稿时间"><el-date-picker v-model="selected.customerDeadlineTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" format="YYYY-MM-DD HH:mm" /></el-form-item>
    </AppForm></div>
    </template>
    </VerticalSplitPanels></div>
    <template #footer><el-button @click="cancel">返回母订单</el-button><el-button type="primary" @click="confirm">{{ directionOnly?'确认子订单资料':'汇总至母订单并确认' }}</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {computed,ref,watch} from 'vue'
import {ElMessage} from 'element-plus'
import SubOrderStatisticsGrid from './SubOrderStatisticsGrid.vue'
import VerticalSplitPanels from '@/components/common/VerticalSplitPanels.vue'
import OrderInheritedExtras from './OrderInheritedExtras.vue'
import LanguagePairSelect from '@/components/LanguagePairSelect.vue'
import {pendingChildRows,missingChildStatistics,initialChildDetails,rollUpPendingRows,aggregatePendingStatistics,isDirectionOnlySplit,inheritPendingLanguage} from '@/utils/translationChildSubmission'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import {normalizeWordCountMatrix} from '@/utils/wordCountMatrix'
import {splitLanguagePairs} from '@/utils/languagePair'
const props=defineProps({modelValue:Boolean,form:{type:Object,required:true}})
const emit=defineEmits(['update:modelValue','confirmed'])
const rows=ref([]),selectedId=ref(''),grid=ref(null)
const editorBodyRef=ref(null)
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(editorBodyRef)
const selected=computed(()=>rows.value.find(row=>row.id===selectedId.value))
const directionOnly=computed(()=>isDirectionOnlySplit(props.form))
watch(()=>props.modelValue,visible=>{if(visible){rows.value=pendingChildRows(props.form);selectedId.value=rows.value[0]?.id||''}})
for(const key of ['serviceContent','customerRequirementProfessional','customerRequirementSpecial','remarks','fileTypeSecondary','customerDeadlineTime','languagePair']){
 watch(()=>[selected.value?.id,selected.value?.[key]],([id,value],[oldId,oldValue])=>{
  if(!id||id!==oldId)return
  const parent=selected.value
  if(key==='languagePair'){inheritPendingLanguage(rows.value,parent.subOrderNo,oldValue,value);return}
  for(const child of rows.value)if(child.subOrderNo.startsWith(parent.subOrderNo+'.')&&child[key]===oldValue)child[key]=value
 })
}
function persist(){
 if(!props.form.pendingFolderImport&&!String(props.form.initialSubOrderNamesText||'').trim()&&splitLanguagePairs(props.form.languagePair).length>1&&props.form.wordCountMatrixSource!=='suborder_aggregate')props.form.pendingDirectionWordCountMatrix=normalizeWordCountMatrix(props.form.wordCountMatrix)
 rollUpPendingRows(rows.value);props.form.pendingSubOrderDetails=initialChildDetails(rows.value,props.form)
}
async function cancel(){await grid.value?.save();persist();emit('update:modelValue',false)}
async function confirm(){
 await grid.value?.save();persist()
 if(!rows.value.length){ElMessage.warning('请先读取文件或添加子订单，再填写字数');return}
 const missing=missingChildStatistics(rows.value)
 if(missing.length){ElMessage.warning('请填写我司统计或客户统计：'+missing.slice(0,5).map(row=>row.subOrderNo).join('、'));return}
 if(directionOnly.value){
  if(props.form.wordCountMatrixSource==='suborder_aggregate'&&props.form.pendingDirectionWordCountMatrix)props.form.wordCountMatrix=normalizeWordCountMatrix(props.form.pendingDirectionWordCountMatrix)
  props.form.wordCountMatrixSource='project'
 }else{
  props.form.wordCountMatrix=aggregatePendingStatistics(rows.value)
  props.form.wordCountMatrixSource='suborder_aggregate'
 }
 props.form.wordCountSubOrderCount=rows.value.length
 emit('update:modelValue',false);emit('confirmed')
}
</script>
<style>
.pending-suborder-manager{display:flex;flex-direction:column;height:90vh;max-height:92vh;overflow:hidden}
.pending-suborder-manager>.el-dialog__body{display:flex;flex:1;min-height:0;overflow:hidden}
.pending-suborder-manager>.el-dialog__header,.pending-suborder-manager>.el-dialog__footer{flex:none}
.pending-suborder-body{display:flex;flex:1;flex-direction:column;min-height:0;min-width:0;gap:12px}
.pending-suborder-body>.el-alert{flex:none}
.pending-suborder-manager .suborder-statistics-grid{height:100%;min-height:0;display:flex;flex-direction:column;overflow:hidden}
.pending-suborder-manager .statistics-actions{flex:none;margin:0 0 8px}
.pending-suborder-manager .statistics-scroll{flex:1;min-height:0;max-height:none}
.pending-suborder-editor{height:100%;min-height:0;overflow:auto;box-sizing:border-box;padding:12px 12px 0 0}
.pending-language-hint{font-size:12px;color:var(--el-text-color-secondary);width:100%;line-height:1.6}
</style>
