<template>
  <DraggableFormDialog :model-value="modelValue" class="pending-suborder-manager" title="子订单管理 · 保存前填写" width="min(1500px, calc(100vw - 32px))" top="4vh" append-to-body @update:model-value="visible=>visible?$emit('update:modelValue',true):cancel()">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" title="子订单管理 · 保存前填写" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="editorBodyRef">
    <el-alert title="此处填写的是尚未保存的子订单。每个文件订单至少填写一项我司统计或客户统计；预统计不作为完成资料。确认后随母订单一起保存。" type="info" :closable="false" />
    <SubOrderStatisticsGrid ref="grid" :rows="rows" editable local @saved="persist" />
    <AppForm v-if="selected" :model="selected" label-width="130px">
      <el-form-item label="编辑子订单"><el-select v-model="selectedId" style="width:100%"><el-option v-for="row in rows" :key="row.id" :value="row.id" :label="row.subOrderNo+' / '+row.subProjectName" /></el-select></el-form-item>
      <OrderInheritedExtras :model="selected" />
      <el-form-item label="文本类型"><el-input v-model="selected.fileTypeSecondary" /></el-form-item>
      <el-form-item label="客户交稿时间"><el-date-picker v-model="selected.customerDeadlineTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" format="YYYY-MM-DD HH:mm" /></el-form-item>
    </AppForm></div>
    <template #footer><el-button @click="cancel">返回母订单</el-button><el-button type="primary" @click="confirm">汇总至母订单并确认</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {computed,ref,watch} from 'vue'
import {ElMessage} from 'element-plus'
import SubOrderStatisticsGrid from './SubOrderStatisticsGrid.vue'
import OrderInheritedExtras from './OrderInheritedExtras.vue'
import {pendingChildRows,missingChildStatistics,initialChildDetails,rollUpPendingRows,aggregatePendingStatistics} from '@/utils/translationChildSubmission'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
const props=defineProps({modelValue:Boolean,form:{type:Object,required:true}})
const emit=defineEmits(['update:modelValue','confirmed'])
const rows=ref([]),selectedId=ref(''),grid=ref(null)
const editorBodyRef=ref(null)
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(editorBodyRef)
const selected=computed(()=>rows.value.find(row=>row.id===selectedId.value))
watch(()=>props.modelValue,visible=>{if(visible){rows.value=pendingChildRows(props.form);selectedId.value=rows.value[0]?.id||''}})
for(const key of ['serviceContent','customerRequirementProfessional','customerRequirementSpecial','remarks','fileTypeSecondary','customerDeadlineTime']){
 watch(()=>[selected.value?.id,selected.value?.[key]],([id,value],[oldId,oldValue])=>{
  if(!id||id!==oldId)return
  const parent=selected.value
  for(const child of rows.value)if(child.subOrderNo.startsWith(parent.subOrderNo+'.')&&child[key]===oldValue)child[key]=value
 })
}
function persist(){rollUpPendingRows(rows.value);props.form.pendingSubOrderDetails=initialChildDetails(rows.value,props.form)}
async function cancel(){await grid.value?.save();persist();emit('update:modelValue',false)}
async function confirm(){
 await grid.value?.save();persist()
 if(!rows.value.length){ElMessage.warning('请先读取文件或添加子订单，再填写字数');return}
 const missing=missingChildStatistics(rows.value)
 if(missing.length){ElMessage.warning('请填写我司统计或客户统计：'+missing.slice(0,5).map(row=>row.subOrderNo).join('、'));return}
 props.form.wordCountMatrix=aggregatePendingStatistics(rows.value)
 props.form.wordCountMatrixSource='suborder_aggregate'
 props.form.wordCountSubOrderCount=rows.value.length
 emit('update:modelValue',false);emit('confirmed')
}
</script>
<style>
.pending-suborder-manager{display:flex;flex-direction:column;max-height:92vh;overflow:hidden}.pending-suborder-manager>.el-dialog__body{min-height:0;overflow:auto}.pending-suborder-manager>.el-dialog__header,.pending-suborder-manager>.el-dialog__footer{flex:none}.pending-suborder-manager .statistics-scroll{max-height:40vh}
</style>
