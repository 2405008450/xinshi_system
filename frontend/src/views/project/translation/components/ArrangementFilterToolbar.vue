<template>
  <div class="arrangement-toolbar">
    <strong>项目安排</strong>
    <div class="arrangement-toolbar-actions">
      <el-button :disabled="confirming" :class="{'is-active-filter':shortcutActive('today')}" :aria-pressed="shortcutActive('today')" @click="shortcut('today')">今天回稿</el-button>
      <el-button :disabled="confirming" :class="{'is-active-filter':shortcutActive('tomorrow')}" :aria-pressed="shortcutActive('tomorrow')" @click="shortcut('tomorrow')">明日及前回稿</el-button>
      <ProjectStatusExclusionControl :model-value="excluded" :statuses="statuses" @update:model-value="setExcluded" />
      <el-button :type="excluded.includes('arranged')?'primary':''" :class="{'is-active-filter':excluded.includes('arranged')}" :aria-pressed="excluded.includes('arranged')" plain @click="toggleArranged">排除已安排</el-button>
      <el-popover v-model:visible="timeVisible" trigger="click" placement="bottom-end" :width="760" popper-class="arrangement-filter-popover">
        <template #reference><el-button :class="{'is-active-filter':timeCount}" :aria-pressed="timeCount>0" @click.capture="captureTimeClick">时间筛选<span v-if="timeCount">（{{timeCount}}）</span></el-button></template>
        <div class="arrangement-date-filters">
          <label><span>客户来稿时间（区间）</span><el-date-picker :model-value="reception" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" unlink-panels @update:model-value="updateRange('reception',$event)" /></label>
          <label><span>客户回稿时间（区间）</span><el-date-picker :model-value="deadline?.[0]?deadline:[]" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" unlink-panels @update:model-value="updateRange('deadline',$event)" /></label>
        </div>
        <p v-if="deadline?.[1]&&!deadline?.[0]">当前客户回稿范围：{{deadline[1]}} 及以前（含逾期项目）。</p>
        <div class="filter-footer"><el-button link @click="clearDates">清空时间条件</el-button></div>
      </el-popover>
      <TableColumnSettings settings-key="translation-arrangements" :model-value="columnKeys" :columns="columns" title="项目安排字段" :column-count="2" @update:model-value="$emit('update:columnKeys',$event)" @reset="$emit('reset-columns')" />
    </div>
  </div>
</template>
<script setup>
import {computed,ref} from 'vue'
import {ElMessageBox} from 'element-plus'
import TableColumnSettings from '@/components/common/TableColumnSettings.vue'
import ProjectStatusExclusionControl from './ProjectStatusExclusionControl.vue'
import {arrangementDeadlineShortcut} from '@/utils/arrangementFilters'
const props=defineProps({excluded:{type:Array,default:()=>[]},statuses:{type:Array,default:()=>[]},reception:{type:Array,default:()=>[]},deadline:{type:Array,default:()=>[]},columnKeys:{type:Array,default:()=>[]},columns:{type:Array,default:()=>[]}})
const emit=defineEmits(['update:excluded','update:reception','update:deadline','update:columnKeys','reset-columns','search'])
const confirming=ref(false),timeVisible=ref(false),timeCount=computed(()=>[props.reception,props.deadline].filter(value=>value?.some(Boolean)).length)
function setExcluded(values){emit('update:excluded',values);emit('search')}
function toggleArranged(){setExcluded(props.excluded.includes('arranged')?props.excluded.filter(value=>value!=='arranged'):[...props.excluded,'arranged'])}
function updateRange(key,value){emit(`update:${key}`,value||[]);emit('search')}
function clearDates(){emit('update:reception',[]);emit('update:deadline',[]);emit('search')}
function captureTimeClick(event){if(timeCount.value){event.stopImmediatePropagation();timeVisible.value=false;clearDates()}}
function shortcutActive(kind){const range=arrangementDeadlineShortcut(kind).range;return props.deadline?.length===2&&range.every((value,index)=>value===(props.deadline[index]||''))}
async function shortcut(kind){
  if(confirming.value)return
  if(shortcutActive(kind)){updateRange('deadline',[]);return}
  const value=arrangementDeadlineShortcut(kind)
  if(value.needsConfirmation){
    confirming.value=true
    try{await ElMessageBox.confirm(`现在已是凌晨，请确认是否是“${value.word}”（${value.date}，UTC+8）！`,'回稿日期确认',{confirmButtonText:`确认${value.word}`,cancelButtonText:'取消',type:'warning'})}
    catch{return}
    finally{confirming.value=false}
  }
  updateRange('deadline',value.range)
}
</script>
<style scoped>
.is-active-filter{--el-button-bg-color:#f1f5f9;--el-button-text-color:#334155;--el-button-border-color:#94a3b8;--el-button-hover-bg-color:#e2e8f0;--el-button-hover-text-color:#334155;--el-button-hover-border-color:#94a3b8;--el-button-active-bg-color:#e2e8f0;--el-button-active-border-color:#64748b}

.arrangement-toolbar{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:10px}.arrangement-toolbar>strong{font-size:16px;white-space:nowrap}.arrangement-toolbar-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-left:auto}.arrangement-toolbar-actions :deep(.el-button+.el-button){margin-left:0}.exclusion-options{display:grid;grid-template-columns:1fr 1fr;gap:2px 10px}.exclusion-options :deep(.el-checkbox){margin-right:0}.arrangement-date-filters{display:grid;grid-template-columns:1fr 1fr;gap:16px}.arrangement-date-filters label{display:flex;flex-direction:column;gap:8px;min-width:0}.arrangement-date-filters :deep(.el-date-editor){max-width:100%;width:100%}.filter-footer{display:flex;justify-content:flex-end;gap:12px;margin-top:12px;border-top:1px solid #e2e8f0;padding-top:10px}@media(max-width:640px){.arrangement-date-filters{grid-template-columns:1fr}.arrangement-toolbar-actions{margin-left:0}}
</style>
<style>.arrangement-filter-popover{max-width:calc(100vw - 32px)!important;max-height:min(560px,calc(100vh - 120px));overflow-y:auto}</style>
