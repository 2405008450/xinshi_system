<template>
  <DraggableFormDialog :model-value="modelValue" title="复制 / 转移 / 互换" default-maximized maximize-target=".hr-workspace-content" append-to-body non-modal :modal="false" modal-penetrable :lock-scroll="false" width="min(1000px, calc(100vw - 32px))" top="5vh" :close-on-click-modal="false" :before-close="close" @update:model-value="$emit('update:modelValue',$event)">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" title="复制 / 转移 / 互换" placeholder="搜索来源周、目标周等" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="editorBodyRef"><WeekPlanOperations v-if="modelValue" ref="operationsRef" :source-week="sourceWeek" :kind="kind" active @busy="setBusy" @state="operationState=$event" @saved="$emit('saved')" /></div>
    <template #footer><el-button :disabled="busy" @click="close()">关闭</el-button><el-button type="primary" :loading="busy" :disabled="!operationState.ready||busy" @click="operationsRef?.submit()">{{operationState.label}}</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {ref,watch} from 'vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import {currentShiftWeek} from '@/utils/monthlyShift'
import WeekPlanOperations from './WeekPlanOperations.vue'
const props=defineProps({modelValue:Boolean,kind:{type:String,default:'shift'},sourceWeek:{type:String,default:()=>currentShiftWeek()}}),emit=defineEmits(['update:modelValue','saved','busy'])
const editorBodyRef=ref(null),operationsRef=ref(null),busy=ref(false),operationState=ref({ready:false,label:'确认复制'})
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(editorBodyRef)
function setBusy(value){busy.value=value;emit('busy',value)}
function close(done){if(busy.value)return;if(typeof done==='function')done();else emit('update:modelValue',false)}
watch(()=>props.modelValue,value=>{if(value){clearFieldSearch();operationState.value={ready:false,label:'确认复制'}}})
</script>
