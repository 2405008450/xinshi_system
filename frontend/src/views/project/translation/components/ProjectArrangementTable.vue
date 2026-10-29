<template>
  <div class="arrangement-projects" v-loading="loading">
    <div ref="headerRoot" class="project-summary project-summary--header" :style="gridStyle"><span data-column-key="__index">序号</span><span v-for="column in orderedColumns" :key="column.key" :data-column-key="column.key" class="arrangement-column-drag" title="拖动表头调整字段顺序"><slot name="header" :column="column">{{column.label}}</slot></span><span data-column-key="__actions" class="fixed-arrange">安排</span></div>
    <div v-for="(project,index) in projects" :key="project.id" class="arrangement-project" :style="{minWidth:gridStyle.minWidth}" @dragover.prevent @drop.prevent="drop($event,project)">
      <div class="project-summary" :style="gridStyle">
        <span>{{offset+index+1}}</span><span v-for="column in orderedColumns" :key="column.key" class="arrangement-field-cell" :data-field="column.key"><slot name="field" :row="project" :column="column">{{cell(project,column)}}</slot></span>
        <span class="fixed-arrange"><el-button :disabled="!canWrite" type="primary" link @click="arrange(project)">安排</el-button></span>
      </div>
      <div v-if="opened===project.id" class="project-assignees">
        <p>将左侧人员拖到此项目，或勾选人员后点击“安排”。同一项目可安排多项任务。</p>
        <ArrangementPlanPanel :ref="el=>setPlanPanel(project.id,el)" :project-id="project.id" :can-write="canWrite" :refresh-key="refreshKey" @changed="$emit('changed')" />
        <div v-for="(draft,index) in drafts[project.id]||[]" :key="draft.key" class="assignment-line">
          <strong>{{draft.name}}</strong><el-input v-model="draft.content" type="textarea" :autosize="{minRows:2,maxRows:5}" maxlength="10000" placeholder="填写具体任务（必填）" /><el-button link @click="drafts[project.id].splice(index,1)">移除</el-button>
        </div>
        <div v-if="drafts[project.id]?.length" class="assignment-actions"><span>任务日期</span><el-date-picker v-model="workDate" type="date" value-format="YYYY-MM-DD" :clearable="false" /><el-button type="primary" :loading="saving" @click="save(project)">保存安排</el-button></div>
      </div>
    </div>
    <el-empty v-if="!projects.length&&!loading" description="暂无符合条件的项目" />
  </div>
</template>
<script setup>
import { useTableColumnOrder } from '@/composables/useTableColumnOrder'
import { sortColumns, moveColumn } from '@/utils/tableColumnOrder'
import { bindColumnDrag } from '@/utils/columnDragGesture'
import { bindColumnResize } from '@/utils/tableColumnResize'
import {computed,reactive,ref,watch,onBeforeUnmount} from 'vue'
import {ElMessage} from 'element-plus'
import {assignProjectTasks} from '@/api/projectArrangements'
import ArrangementPlanPanel from './ArrangementPlanPanel.vue'
import {reportBusinessDate} from '@/utils/workReportForm'
import {formatBusinessDateTime} from '@/utils/dateTime'
const props=defineProps({projects:{type:Array,default:()=>[]},columns:{type:Array,default:()=>[{key:'orderNo',label:'订单号'},{key:'sourceFileName',label:'项目名称'},{key:'clientShortName',label:'客户简称'},{key:'projectStatus',label:'项目状态'},{key:'languagePair',label:'翻译方向'},{key:'translatorReturnTime',label:'译员回稿时间'},{key:'customerDeadlineTime',label:'客户回稿时间'}]},people:{type:Array,default:()=>[]},canWrite:Boolean,loading:Boolean,offset:{type:Number,default:0},formatReturns:{type:Function,default:()=>'-'},statusLabel:{type:Function,default:value=>value||'-'}})
const { order: columnOrder, setOrder: setColumnOrder } = useTableColumnOrder('translation-arrangements')
const headerRoot = ref(null)
const columnWidths = reactive({})
let unbindHeaderDrag, unbindHeaderResize
watch(headerRoot, root => {
  unbindHeaderDrag?.(); unbindHeaderResize?.()
  if (!root) return
  unbindHeaderResize = bindColumnResize(root, () => [...root.children].filter(element => element.dataset.columnKey).map(element => ({
    element, key: element.dataset.columnKey, label: element.textContent.trim(), width: element.offsetWidth, minimum: 40,
  })), (entry, width) => { columnWidths[entry.key] = width })
  unbindHeaderDrag = bindColumnDrag(root, element => {
    if (element?.closest('button,input,a,[role=button]')) return null
    const key = element?.closest('[data-column-key]')?.dataset.columnKey
    return columnOrder.value.includes(key) ? key : null
  }, (from, to) => setColumnOrder(moveColumn(columnOrder.value, from, to)))
}, { flush: 'post' })
onBeforeUnmount(() => { unbindHeaderDrag?.(); unbindHeaderResize?.() })
const orderedColumns = computed(() => sortColumns(props.columns, columnOrder.value))
const columnWidth=column=>columnWidths[column.key] || (column.key==='sourceFileName'?200:Math.min(230,Math.max(({customerDeadlineTime:200,translatorReturnTime:210,assignedTranslators:185})[column.key]||100,column.minWidth||140)))
const gridStyle=computed(()=>({gridTemplateColumns:`${columnWidths.__index || 40}px ${orderedColumns.value.map(column=>column.key==='sourceFileName'&&!columnWidths[column.key]?'minmax(200px,1fr)':`${columnWidth(column)}px`).join(' ')} ${columnWidths.__actions || 55}px`,minWidth:`${30+(columnWidths.__index||40)+(columnWidths.__actions||55)+orderedColumns.value.reduce((sum,column)=>sum+columnWidth(column)+10,0)}px`}))
function cell(project,column){
  const value=project[column.key]
  if(column.key==='projectStatus')return props.statusLabel(value)
  if(column.key==='translatorReturnTime')return props.formatReturns(project.assignedTranslators)
  if(column.formatter)return column.formatter(value,project)
  if(/(?:Time|At)$/.test(column.key))return formatBusinessDateTime(value)
  if(column.key==='sourceFileName')return value||project.projectName||'-'
  return value==null||value===''?'-':String(value)
}
const emit=defineEmits(['changed'])
const planPanels=new Map()
function setPlanPanel(id,panel){if(panel)planPanels.set(id,panel);else planPanels.delete(id)}
const opened=ref(''),drafts=reactive({}),refreshKey=ref(0),saving=ref(false),workDate=ref(reportBusinessDate())
function addPeople(project,people){drafts[project.id]||=[];for(const person of people)if(!drafts[project.id].some(d=>d.assignee_id===person.id))drafts[project.id].push({key:crypto.randomUUID(),assignee_id:person.id,name:person.name,content:''})}
function open(project){opened.value=project.id}
function arrange(project){if(opened.value===project.id)refreshKey.value++;else open(project);addPeople(project,props.people)}
function drop(event,project){if(!props.canWrite)return;try{const values=JSON.parse(event.dataTransfer.getData('application/x-project-personnel'));if(!Array.isArray(values))return;open(project);addPeople(project,values)}catch{ElMessage.warning('请从左侧拖动人员')}}
async function save(project){const values=drafts[project.id]||[];const bad=values.find(d=>!d.content.trim());if(bad){ElMessage.warning(`请填写${bad.name}的具体任务`);return}if(!workDate.value)return ElMessage.warning('请选择任务日期');const instruction=planPanels.get(project.id)?.getInstruction();if(!instruction)return ElMessage.warning('请等待项目说明加载完成，若有错误请先刷新安排');saving.value=true;try{await assignProjectTasks(project.id,values.map(d=>({assignee_id:d.assignee_id,content:d.content.trim(),work_date:workDate.value})),instruction);drafts[project.id]=[];refreshKey.value++;emit('changed');ElMessage.success('项目安排已保存，已生成个人任务')}catch(error){ElMessage.error(error.detail||'保存安排失败')}finally{saving.value=false}}
</script>
<style scoped>
.project-summary--header > span { position: relative; min-height: 26px; }
.project-summary--header :deep(.app-column-resize-handle) { right: -5px; }
.arrangement-column-drag { cursor: grab; }
.arrangement-column-drag:active { cursor: grabbing; }
.arrangement-projects{min-width:0;overflow-x:auto}.arrangement-project{border:1px solid #dbe3ec;border-radius:6px;margin-bottom:10px;min-width:100%;width:100%}.project-summary{display:grid;gap:10px;align-items:center;padding:12px;background:#f8fafc;font-size:13px;box-sizing:border-box;min-width:100%}.project-summary>span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.project-summary>.fixed-arrange{position:sticky;right:0;background:#f8fafc;z-index:1;overflow:visible;align-self:stretch;display:flex;align-items:center}.project-summary>.fixed-arrange{right:0}.order-cell{font-weight:600}.project-assignees{padding:12px;max-width:calc(100vw - 100px)}.project-assignees p{color:#64748b;font-size:12px}.assignment-line{display:flex;gap:12px;align-items:center;margin:12px 0}.assignment-line strong{width:85px;flex-shrink:0}.assignment-actions{display:flex;align-items:center;gap:12px}.assignment-line .el-input{flex:1}
</style>
