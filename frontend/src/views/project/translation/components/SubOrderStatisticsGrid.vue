<template>
  <section class="suborder-statistics-grid">
    <div class="statistics-actions"><strong>统计填写</strong><span>可直接输入、Tab切换，或从Excel粘贴多行四列。各订单独立填报，不自动汇总；修改统计口径后输入新值，会替换该行原口径。</span><el-button :loading="saving" :disabled="!editable || !pendingCount" type="primary" @click="save">{{ local?'暂存统计':'保存统计' }}（{{ pendingCount }} 单）</el-button></div>
    <p v-if="failure" role="alert" class="statistics-error">{{ failure }}</p>
    <div class="statistics-scroll"><table ref="grid"><thead><tr><th class="statistics-index">序号</th><th>订单号</th><th>项目名称</th><th class="statistics-relative-path">相对路径</th><th v-for="dim in dimensions" :key="dim.key">{{ dim.label }}<select v-model="metrics[dim.key]" :aria-label="dim.label+'统计口径'"><option v-for="item in metricOptions" :value="item.key" :key="item.key">{{ item.label }}</option></select></th></tr></thead>
      <tbody><tr v-for="(row,r) in rows" :key="row.id"><td class="statistics-index">{{ r+1 }}</td><td>{{ row.subOrderNo }}</td><td :style="{paddingLeft:(row.subOrderNo.split('.').length-2)*16+8+'px'}">{{ row.subProjectName }}</td><td class="statistics-relative-path">{{ relativePath(row) }}</td><td v-for="(dim,c) in dimensions" :key="dim.key"><input :value="value(row,dim.key)" :readonly="!editable" :disabled="saving" :aria-label="row.subOrderNo+' '+dim.label" inputmode="decimal" :data-row="r" :data-col="c" @input="setValue(row,dim.key,$event.target.value)" @paste="paste($event,r,c)" @keydown.enter.prevent="focus(r+1,c)" @keydown.down.prevent="focus(r+1,c)" @keydown.up.prevent="focus(r-1,c)" @keydown.left.prevent="focus(r,c-1)" @keydown.right.prevent="focus(r,c+1)" /></td></tr></tbody></table></div>
  </section>
</template>
<script setup>
import {computed,reactive,ref} from 'vue'
import {ElMessage} from 'element-plus'
import {patchWordCountMatrix} from '@/api/wordCountMatrices'
import {normalizeWordCountMatrix} from '@/utils/wordCountMatrix'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
const props=defineProps({rows:{type:Array,default:()=>[]},rootPath:{type:String,default:''},editable:Boolean,local:Boolean})
const emit=defineEmits(['saved'])
const pathRoots=computed(()=>[...new Set([...props.rows.map(item=>item.folderInfo?.rootPath),props.rootPath]
 .filter(Boolean).map(path=>String(path).replace(/\\/g,'/').replace(/\/+$/,'')))].sort((a,b)=>b.length-a.length))
function relativePath(row){
 const full=String(row.networkFilePath||'').replace(/\\/g,'/').replace(/\/+$/,'')
 for(const base of pathRoots.value){
  if(full.toLowerCase()===base.toLowerCase()||full.toLowerCase().startsWith(base.toLowerCase()+'/'))return (base.split('/').at(-1)+full.slice(base.length)).replace(/\//g,'\\')
 }
 return row.folderInfo?.relativePath?.replace(/\//g,'\\')||'-'
}

const dimensions=[{key:'company',label:'我司统计'},{key:'customer',label:'客户统计'},{key:'preliminary',label:'预统计（不用以计算费用）'},{key:'translator_estimate',label:'译员预定'}]
const metricOptions=[{key:'words',label:'字数'},{key:'characters_no_spaces',label:'字符数（不计空格）'},{key:'cjk_chars_korean_words',label:'中文字符和朝鲜语单词'},{key:'foreign_words',label:'外文字数'},{key:'documents',label:'份数'},{key:'pages',label:'页数'},{key:'minutes',label:'分钟'},{key:'hours',label:'小时'}]
const metrics=reactive(Object.fromEntries(dimensions.map(dim=>[dim.key,'words'])))
const changes=reactive({}),saving=ref(false),failure=ref(''),grid=ref(null)
const pendingCount=computed(()=>Object.keys(changes).length)
const savedValues=(row,dim)=>{const matrix=normalizeWordCountMatrix(row.wordCountMatrix);return matrix[dim==='translator_estimate'?'translatorEstimate':dim]||{}}
const value=(row,dim)=>Object.hasOwn(changes[row.id]?.[dim]||{},metrics[dim]) ? changes[row.id][dim][metrics[dim]]??'' : savedValues(row,dim)[metrics[dim]]??''
function setValue(row,dim,text){
 if(!props.editable||saving.value)return
 const metric=metrics[dim],number=text.trim()===''?null:Number(text)
 if(number!==null&&(!Number.isFinite(number)||number<0||number>9999999999||(!['minutes','hours'].includes(metric)&&!Number.isInteger(number)))){failure.value='统计须填写非负数；字数、份数、页数须为整数。';return}
 failure.value=''
 changes[row.id]??={}
 const next={...(changes[row.id][dim]||{})}
 if(number!==null){
   if(['company','customer'].includes(dim))for(const option of metricOptions)if(option.key!==metric)next[option.key]=null
   if(metric==='minutes')next.hours=null
   if(metric==='hours')next.minutes=null
 }
 next[metric]=number
 changes[row.id][dim]=next
}
function focus(r,c){grid.value?.querySelector(`input[data-row="${r}"][data-col="${c}"]`)?.focus()}
function paste(event,r,c){
 const text=event.clipboardData?.getData('text/plain')||''
 if(!/[\t\r\n]/.test(text))return
 event.preventDefault()
 const lines=text.replace(/\r\n?/g,'\n').replace(/\n$/,'').split('\n')
 for(let i=0;i<lines.length;i++)for(const [j,cell] of lines[i].split('\t').entries())if(props.rows[r+i]&&dimensions[c+j])setValue(props.rows[r+i],dimensions[c+j].key,cell)
}
async function save(){
 if(saving.value||!props.editable)return
 saving.value=true;failure.value=''
 let count=0;const errors=[]
 try{
  for(const [id,dimensionsChanged] of Object.entries(changes)){
   const cells=[]
   for(const [dimension,values] of Object.entries(dimensionsChanged))for(const [metric_type,value] of Object.entries(values))cells.push({scope:'entity',dimension,metric_type,value})
   try{
    if(props.local){
      const row=props.rows.find(item=>item.id===id)
      const matrix=normalizeWordCountMatrix(row.wordCountMatrix)
      for(const cell of cells){const key=cell.dimension==='translator_estimate'?'translatorEstimate':cell.dimension;matrix[key]??={};matrix[key][cell.metric_type]=cell.value}
      row.wordCountMatrix=matrix
    }else await patchWordCountMatrix('suborder',id,{changes:cells})
    delete changes[id];count++
   }catch(error){errors.push(getLocalizedErrorMessage(error,'保存失败'))}
  }
  if(count){emit('saved');ElMessage.success(props.local?`已暂存${count}单统计，随母订单一起保存`:`已保存${count}单统计`)}
  if(errors.length)failure.value=`${errors.length}单未保存，填写内容已保留：${errors[0]}`
 }finally{saving.value=false}
}
defineExpose({save})
</script>
<style scoped>
.statistics-relative-path{min-width:260px;max-width:420px;overflow-wrap:anywhere;user-select:text;white-space:pre-wrap}
.statistics-index{width:60px;min-width:60px;text-align:center}
.statistics-actions{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:12px 0}.statistics-actions span{font-size:12px;color:var(--el-text-color-secondary)}.statistics-scroll{max-height:65vh;overflow:auto}table{border-collapse:collapse;width:100%;min-width:1050px}th,td{border:1px solid #dce3ec;padding:8px;text-align:left}th{background:#f1f5f9;position:sticky;top:0;z-index:1}th select{display:block;width:100%;margin-top:6px;background:white;border:1px solid #cbd5e1;padding:5px}input{width:100%;min-width:100px;box-sizing:border-box;border:1px solid #cbd5e1;padding:8px;background:#fff;color:#334155}input:focus{outline:2px solid #3b82f6}.aggregate{background:#f1f5f9}small{color:#64748b}.statistics-error{color:#dc2626}
</style>
