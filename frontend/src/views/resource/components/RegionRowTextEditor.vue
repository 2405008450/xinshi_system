<template>
  <DraggableFormDialog v-model="visible" width="min(900px, calc(100vw - 32px))" top="5vh" append-to-body class="region-row-text-dialog" :close-on-click-modal="false">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" title="去字后重新匹配" subtitle="勾选要删除的字，原文件内容保留；保存后同步更新所有汇总" placeholder="搜索当前页行号或来源列" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="bodyRef">
      <AppForm :model="form" label-position="top" @submit.prevent="submit">
        <section v-for="entry in visibleEntries" :key="entry.index" data-dialog-field-search-group :data-dialog-field-search-group-title="`原第${entry.sourceRow}行`" class="region-row-edit-section">
          <strong>原第 {{ entry.sourceRow }} 行</strong>
          <el-form-item v-for="column in columns" :key="column.index" :label="`原第${entry.sourceRow}行 · ${column.label}`">
            <div class="region-row-edit-cell">
              <div class="muted">原文：{{ entry.original[column.index] || '-' }} <el-button link @click="restore(entry,column.index)">恢复原文</el-button></div>
              <el-checkbox-group v-model="entry.removed[column.index]" :aria-label="`第${entry.sourceRow}行${column.label}要删除的字`">
                <el-checkbox v-for="(char, position) in Array.from(entry.values[column.index] || '')" :key="position" :value="position" border :aria-label="`第${position+1}字：${char}`">{{ char === ' ' ? '空格' : char }}</el-checkbox>
              </el-checkbox-group>
              <div>本次去字后：{{ edited(entry,column.index) || '（空）' }}</div>
              <div>实际匹配：<strong>{{ prepareRegionSource(edited(entry,column.index),rules) || '（空，不匹配）' }}</strong></div>
            </div>
          </el-form-item>
        </section>
        <el-alert v-if="error" :title="error" type="error" :closable="false" />
      </AppForm>
    </div>
    <template #footer><el-pagination v-if="form.entries.length>10" v-model:current-page="page" :page-size="10" :total="form.entries.length" layout="total,prev,pager,next" /><span>未勾选的字保留。</span><el-button @click="visible=false">取消</el-button><el-button type="primary" @click="submit">保存并重新匹配</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import { ref,reactive,computed,nextTick } from 'vue'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import { useDialogFieldSearch } from '@/composables/useDialogFieldSearch'
import { prepareRegionSource,removeRegionCharacters } from '@/utils/regionMatchInput'
const props=defineProps({columns:{type:Array,default:()=>[]},rules:{type:Object,default:()=>({})}})
const emit=defineEmits(['apply'])
const visible=ref(false),bodyRef=ref(),error=ref(''),form=reactive({entries:[]})
const page=ref(1),visibleEntries=computed(()=>form.entries.slice((page.value-1)*10,page.value*10))
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,locateDialogFieldByLabel,clearFieldSearch}=useDialogFieldSearch(bodyRef)
function edited(entry,column){return removeRegionCharacters(entry.values[column],entry.removed[column])}
function restore(entry,column){entry.values[column]=entry.original[column];entry.removed[column]=[]}
function open(rows,overrides){
 error.value='';page.value=1;clearFieldSearch()
 form.entries=rows.map(row=>({index:row.index,sourceRow:row.sourceRow,original:[...row.values],values:row.values.map((value,column)=>overrides[row.index]?.[column]??value),removed:Object.fromEntries(props.columns.map(column=>[column.index,[]]))}))
 visible.value=true
}
async function submit(){
 for(const [index,entry] of form.entries.entries())for(const column of props.columns){
  if(entry.original[column.index]?.trim()&&!prepareRegionSource(edited(entry,column.index),props.rules).trim()){
   error.value=`原第${entry.sourceRow}行 · ${column.label}不能删成空文字，请保留至少一个字`;page.value=Math.floor(index/10)+1;await nextTick();await locateDialogFieldByLabel(`原第${entry.sourceRow}行 · ${column.label}`);return
  }
 }
 emit('apply',Object.fromEntries(form.entries.map(entry=>[entry.index,Object.fromEntries(props.columns.map(column=>[column.index,edited(entry,column.index)]))])))
 visible.value=false
}
defineExpose({open})
</script>
<style>
.region-row-text-dialog{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}
.region-row-text-dialog>.el-dialog__header,.region-row-text-dialog>.el-dialog__footer{flex-shrink:0}
.region-row-text-dialog>.el-dialog__body{flex:1;min-height:0;overflow:auto}
.region-row-text-dialog>.el-dialog__footer{display:flex;gap:10px;align-items:center;justify-content:flex-end;flex-wrap:wrap;border-top:1px solid var(--el-border-color-light)}
.region-row-edit-section{border-bottom:1px solid var(--el-border-color-light);padding:10px 0}
.region-row-edit-cell{width:100%;line-height:1.8;overflow-wrap:anywhere}.region-row-edit-cell .el-checkbox{margin:4px 6px 4px 0}.region-row-edit-cell .muted{font-size:12px;color:var(--el-text-color-secondary)}
</style>
