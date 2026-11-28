<template><el-popover v-model:visible="visible" trigger="click" placement="left" :width="760" @show="open" @hide="pauseDraft"><template #reference><el-button link type="primary">{{row.payload?.rates?.length?'编辑组合单价':'填写组合单价'}}</el-button></template><div class="inline-interpretation-rates"><div class="inline-rates-header"><h3>{{row.order_no}} · 组合单价</h3><el-button link aria-label="关闭组合单价" @click="visible=false">×</el-button></div><AppForm v-if="ready" ref="form" :model="draft" label-position="top" :disabled="saving"><InterpretationFinanceFields v-model="draft" :directions="row.directions||[]" hide-totals/><el-alert v-if="error" :title="error" type="error" :closable="false"/><el-button type="primary" :loading="saving" @click="save">保存单价</el-button></AppForm></div></el-popover></template>
<script setup>
import {ref,reactive,nextTick} from 'vue'
import {useFormDraft} from '@/composables/useFormDraft'
import {ElMessage} from 'element-plus'
import AppForm from './AppForm.vue'
import InterpretationFinanceFields from './InterpretationFinanceFields.vue'
import {financeDraft,interpretationFinancePayload} from '@/utils/interpretationCustomerFinance'
import {saveInterpretationFinance} from '@/api/interpretationCustomerFinance'
const props=defineProps({row:{type:Object,required:true}}),emit=defineEmits(['saved'])
const draft=reactive(financeDraft({})),saving=ref(false),error=ref(''),form=ref(),ready=ref(false),visible=ref(false)
const {beginDraft,pauseDraft,clearDraft,startFreshDraft}=useFormDraft({namespace:'interpretation-inline-rates',form:draft,createDefault:()=>financeDraft({}),formRef:form})
async function open(){ready.value=false;Object.assign(draft,financeDraft(JSON.parse(JSON.stringify(props.row.payload||{}))),{id:props.row.id,priceRevision:props.row.revision});error.value='';await nextTick();await beginDraft('edit:'+props.row.id);ready.value=true}
async function save(){if(saving.value||!await form.value.validate().catch(()=>false))return;saving.value=true;error.value='';try{const saved=await saveInterpretationFinance('project',props.row.id,{revision:draft.priceRevision,...Object.fromEntries(['rates','has_overtime','overtime','adjusted_totals','fixed_totals','settlement_adjustments','explanation','settlement'].map(key=>[key,interpretationFinancePayload(draft)[key]]))});Object.assign(props.row,saved);draft.priceRevision=saved.revision;clearDraft();startFreshDraft('edit:'+props.row.id);emit('saved');ElMessage.success('组合单价已保存，总价已重新计算')}catch(e){error.value=e.detail||e.message||'单价保存失败'}finally{saving.value=false}}
</script>
<style scoped>.inline-interpretation-rates{max-height:min(560px,calc(100vh - 120px));overflow:auto;overflow-wrap:anywhere}.inline-interpretation-rates h3{margin-top:0}.inline-rates-header{display:flex;align-items:center;justify-content:space-between;gap:12px}.inline-rates-header .el-button{font-size:24px}</style>
