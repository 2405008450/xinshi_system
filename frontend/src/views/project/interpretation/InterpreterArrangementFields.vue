<template><div class="interpreter-arrangement-fields"><el-form-item label="口译方向" :prop="`${prefix}.languageIds`" :rules="[{type:'array',required:!!row.translatorId,min:1,message:'请选择译员承担的口译方向',trigger:'change'}]"><el-select :model-value="directionKey" placeholder="无法自动匹配时请人工选择" @update:model-value="row.languageIds=String($event||'').split('|').filter(Boolean)"><el-option v-for="direction in directions" :key="direction.languageIds.join('|')" :value="direction.languageIds.join('|')" :label="direction.label"/></el-select><small v-if="matching">正在根据母语、第一外语匹配…</small><small v-else-if="directions.length>1&&!row.languageIds?.length">未找到唯一匹配方向，请人工选择。</small></el-form-item><InterpretationCombinationRates v-if="row.translatorId" v-model="row.rates" :directions="selectedDirections" :prefix="`${prefix}.rates`"/><el-form-item label="译员合同路径" :prop="`${prefix}.contractPath`"><PathInput v-model="row.contractPath" placeholder="填写此译员已签署合同的路径" @open="emit('open-path',row.contractPath)" @copy="emit('copy-path',row.contractPath)"/></el-form-item><details v-if="row.cancellationIssues?.length"><summary>取消相关问题（{{row.cancellationIssues.length}}）</summary><div v-for="(issue,index) in row.cancellationIssues" :key="index"><strong>{{issue.reason_path.join(' / ')}}</strong><p>{{issue.explanation}}</p><ScreenshotText :text="issue.note||''"/></div></details><details><summary>评价/备注</summary><el-form-item label="客户评价" :prop="`${prefix}.customerRating`"><el-select v-model="row.customerRating" clearable><el-option v-for="rating in ratingOptions" :key="rating.value" :label="rating.label" :value="rating.value"/></el-select></el-form-item><el-form-item label="评价/备注" :prop="`${prefix}.evaluationNote`"><el-input v-model="row.evaluationNote" type="textarea" :rows="2"/></el-form-item></details></div></template>
<script setup>
import {computed,onBeforeUnmount,ref,watch} from 'vue'
import api from '@/api'
import ScreenshotText from '@/components/common/ScreenshotText.vue'
import PathInput from '@/components/common/PathInput.vue'
import InterpretationCombinationRates from '@/components/common/InterpretationCombinationRates.vue'
import {ratingOptions} from '@/utils/interpretationProjectDetail'
import {taxPriceForm} from '@/utils/taxPrices'
const emit=defineEmits(['open-path','copy-path'])
const row=defineModel({type:Object,required:true})
const props=defineProps({directions:{type:Array,default:()=>[]},prefix:String})
row.value.languageIds=(row.value.languageIds||[]).filter(Boolean);row.value.contractPath??='';row.value.rates??=[]
for(const rate of row.value.rates){if(!rate.taxPrices)rate.taxPrices=taxPriceForm(rate.tax_prices);for(const key of ['amount','quantity','hours'])if(rate[key]!=null&&typeof rate[key]!=='number')rate[key]=Number(rate[key])}
const directionKey=computed(()=>row.value.languageIds?.join('|')||'')
const selectedDirections=computed(()=>props.directions.filter(direction=>direction.languageIds.join('|')===directionKey.value))
const matching=ref(false),profile=ref(null);let seq=0,controller
function match(){
 if(props.directions.length===1){if(directionKey.value!==props.directions[0].languageIds.join('|'))row.value.languageIds=[...props.directions[0].languageIds];return}
 if(props.directions.some(direction=>direction.languageIds.join('|')===directionKey.value))return
 const skills=profile.value?.language_skills||[],foreign=skills.filter(item=>item.role==='foreign'),first=Math.min(...foreign.map(item=>item.priority))
 const ids=new Set(skills.filter(item=>item.role==='native'||item.role==='foreign'&&item.priority===first).map(item=>item.language_id))
 const options=props.directions.filter(direction=>direction.languageIds.every(id=>ids.has(id)))
 const next=options.length===1?options[0].languageIds:[]
 if(directionKey.value!==next.join('|'))row.value.languageIds=[...next]
}
watch(()=>row.value.translatorId,async(id,previous)=>{const current=++seq;controller?.abort();profile.value=null;if(previous&&previous!==id){row.value.languageIds=[];row.value.rates=[];row.value.contractPath=''}if(!id)return;if(props.directions.some(direction=>direction.languageIds.join('|')===directionKey.value)){matching.value=false;return}matching.value=true;controller=new AbortController();try{const data=await api.get(`/talent-options/profile/${id}`,{signal:controller.signal});if(current===seq){profile.value=data;match()}}catch{if(current===seq)match()}finally{if(current===seq)matching.value=false}},{immediate:true,flush:'sync'})
watch(()=>props.directions,match,{deep:true});onBeforeUnmount(()=>{seq++;controller?.abort()})
</script>
<style scoped>.interpreter-arrangement-fields{margin-top:10px}.el-select{width:100%}small{font-size:12px;color:var(--el-text-color-secondary)}summary{cursor:pointer;margin:12px 0}details .el-form-item{margin-top:12px}</style>
