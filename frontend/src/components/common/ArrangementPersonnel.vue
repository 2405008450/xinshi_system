<template>
  <aside class="arrangement-personnel">
    <div class="personnel-heading"><strong>部门人员</strong><el-button link :loading="loading" @click="loadPersonnel">刷新</el-button></div>
    <el-input v-model="keyword" clearable placeholder="搜索全体人员或部门" aria-label="搜索安排人员" />
    <template v-if="assignmentCounts"><el-select v-model="countFilter" multiple clearable collapse-tags collapse-tags-tooltip aria-label="筛选值班次数" placeholder="筛选值班次数"><el-option v-for="option in countDistribution" :key="option.count" :value="option.count" :label="`${option.count}次（${option.people}人）`" /></el-select><small>匹配 {{matchedPeopleCount}} 人 · 共 {{people.length}} 人；{{countDistribution.map(option=>`${option.count}次 ${option.people}人`).join('，')}}</small></template>
    <div class="personnel-controls">
      <el-radio-group v-model="viewMode" size="small" aria-label="人员显示方式"><el-radio-button value="departments">部门人员</el-radio-button><el-radio-button value="all">全体人员</el-radio-button></el-radio-group>
      <el-button link @click="toggleExpanded">{{ allExpanded ? '全部收起' : '全部展开' }}</el-button>
    </div>
    <small>{{assignmentCounts?'将人员拖到右侧周末日期；可多次安排，右上角数字为本月值班次数。拖回左侧撤销对应日期的安排。':monthly?`将人员拖到右侧班次；已排班人员会变灰，拖回此处即可撤销${schedulePeriod}安排。`:'勾选一人或多人后点击项目的“安排”，也可拖到项目上。'}}</small>
    <div class="personnel-order-tip"><small>拖动 ⠿ 调整部门或人员顺序；{{monthly?'拖动人员姓名可安排班次。':'拖动人员姓名可安排项目。'}}</small><el-button v-if="hasCustomOrder" link size="small" @click="resetOrder">恢复默认顺序</el-button></div>
    <el-alert v-if="ready === false" title="任务保存尚未开通，需先初始化数据库；人员仍可查看与选择。" type="info" :closable="false" />
    <el-alert v-else-if="serviceUnavailable" title="任务保存服务暂不可用，人员仍可查看与选择。" type="info" :closable="false" />
    <el-alert v-if="directoryError" :title="directoryError" type="error" :closable="false" />
    <el-collapse v-model="expanded">
      <el-collapse-item v-for="group in visibleGroups" :key="group.id" :name="group.id" @dragover="allowOrderDrop($event,'department')" @drop="dropDepartment($event,group.id)">
        <template #title><span v-if="viewMode==='departments'" class="roster-order-handle" role="button" tabindex="0" draggable="true" :aria-label="`调整${group.name}部门顺序`" title="上下拖动调整部门顺序，也可用方向键" @mousedown.stop @click.stop @keydown.stop="orderByKeyboard($event,'department',group.id)" @dragstart.stop="startOrderDrag($event,'department',group.id)" @dragend="orderDrag=null">⠿</span><span>{{group.name}}（{{group.people.length}}）</span></template>
        <div v-for="person in group.people" :key="person.id" class="person" :class="{'is-assigned':assignedIds.includes(person.id)}" :draggable="!disabled&&!assignedIds.includes(person.id)" @dragstart="drag($event,person)" @dragover="allowOrderDrop($event,'person',group.id)" @drop="dropPerson($event,group.id,person.id)">
          <span class="roster-order-handle" role="button" tabindex="0" draggable="true" :aria-label="`调整${person.name}人员顺序`" title="上下拖动调整本列表人员顺序，也可用方向键" @mousedown.stop @click.stop @keydown.stop="orderByKeyboard($event,'person',person.id,group.id)" @dragstart.stop="startOrderDrag($event,'person',person.id,group.id)" @dragend="orderDrag=null">⠿</span>
          <el-checkbox :model-value="modelValue.some(p=>p.id===person.id)" :disabled="disabled||assignedIds.includes(person.id)" @change="toggle(person,$event)">{{person.name}}</el-checkbox><small v-if="assignedIds.includes(person.id)">已排班</small>
          <span v-if="assignmentCounts" class="person-duty-count" :class="{'is-zero':!assignmentCounts[person.id]}" :aria-label="`${person.name}本月值班${assignmentCounts[person.id]||0}次`">{{assignmentCounts[person.id]||0}}</span>
        </div>
        <el-empty v-if="!group.people.length" description="暂无人员" :image-size="40" />
      </el-collapse-item>
    </el-collapse>
    <el-empty v-if="!loading && !directoryError && !visibleGroups.length" description="未找到匹配的人员或部门" :image-size="50" />
    <div class="personnel-heading"><span>已选 {{modelValue.length}} 人</span><el-button link @click="$emit('update:modelValue',[])">清空选择</el-button></div>
  </aside>
</template>
<script setup>
import {computed,onMounted,ref,watch} from 'vue'
import {getArrangementDirectory, getArrangementPersonnel} from '@/api/projectArrangements'
import {matchesSearchFields} from '@/utils/searchMatching'
function dutyCountDistribution(people,counts){const result={};for(const id of new Set(people.map(person=>person.id))){const count=counts[id]||0;result[count]=(result[count]||0)+1}return Object.entries(result).map(([count,people])=>({count:Number(count),people})).sort((a,b)=>a.count-b.count)}
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
const props=defineProps({modelValue:{type:Array,default:()=>[]},disabled:Boolean,monthly:Boolean,schedulePeriod:{type:String,default:'本月'},assignedIds:{type:Array,default:()=>[]},assignmentCounts:{type:Object,default:null},defaultCollapsed:Boolean,directoryLoader:Function,availabilityLoader:Function})
const emit=defineEmits(['update:modelValue'])
const people=ref([]),departments=ref([]),keyword=ref(''),expanded=ref([]),ready=ref(null)
const countFilter=ref([])
const countDistribution=computed(()=>dutyCountDistribution(people.value.filter(matchesPersonText),props.assignmentCounts||{}))
const matchedPeopleCount=computed(()=>people.value.filter(matchesPerson).length)
const loading=ref(false),directoryError=ref(''),serviceUnavailable=ref(false),viewMode=ref('departments')
const order=ref({departments:[],people:{}}),orderDrag=ref(null)
const orderStorageKey=()=>{try{return `${props.monthly?'monthly-shift':'translation-arrangement'}:roster-order:${localStorage.getItem('user_id')||'anonymous'}`}catch{return ''}}
try{const raw=localStorage.getItem(orderStorageKey());if(raw){const parsed=JSON.parse(raw);if(!Array.isArray(parsed.departments)||!parsed.people||typeof parsed.people!=='object'||Array.isArray(parsed.people))throw new Error('invalid order');order.value={departments:parsed.departments.filter(id=>typeof id==='string'),people:Object.fromEntries(Object.entries(parsed.people).filter(([,ids])=>Array.isArray(ids)).map(([key,ids])=>[key,ids.filter(id=>typeof id==='string')]))}}}catch{try{localStorage.removeItem(orderStorageKey())}catch{/* 使用默认顺序。 */}}
const hasCustomOrder=computed(()=>order.value.departments.length>0||Object.values(order.value.people).some(ids=>ids.length))
function persistOrder(){try{localStorage.setItem(orderStorageKey(),JSON.stringify(order.value))}catch{/* 无本地存储时仍可拖动。 */}}
function sortBySaved(rows,ids){const rank=new Map(ids.map((id,index)=>[id,index]));return [...rows].sort((a,b)=>(rank.get(String(a.id))??ids.length)-(rank.get(String(b.id))??ids.length))}
function basePeople(groupId){return groupId==='all'?people.value:people.value.filter(person=>groupId==='ungrouped'?!person.departments.length:person.departments.some(d=>String(d.id)===String(groupId)))}
function sortedPeople(groupId){return sortBySaved(basePeople(groupId),order.value.people[groupId]||[])}
const matchesPersonText=person=>matchesSearchFields([person.name,person.username,...person.departments.map(d=>d.name)],keyword.value)
const matchesPerson=person=>matchesPersonText(person)&&(!props.assignmentCounts||!countFilter.value.length||countFilter.value.includes(props.assignmentCounts[person.id]||0))
const defaultGroups=computed(()=>{
  const priority=name=>{const value=String(name||'').replace(/\s/g,'');return /^项目部/.test(value)?0:/^(HR部?|人力资源部|人事部)$/i.test(value)?1:/^(排版|排版部)$/.test(value)?2:3}
  if(props.monthly)return [...departments.value]
  return [...departments.value,{id:'ungrouped',name:'未分部门'}].sort((a,b)=>priority(a.name)-priority(b.name)||a.name.localeCompare(b.name,'zh-CN'))
})
const groups=computed(()=>sortBySaved(defaultGroups.value,order.value.departments).map(group=>({...group,people:sortedPeople(group.id).filter(matchesPerson)})).filter(group=>group.people.length||(!props.monthly&&group.id!=='ungrouped'&&(!keyword.value.trim()||matchesSearchFields([group.name],keyword.value)))))
const visibleGroups=computed(()=>viewMode.value==='all'?[{id:'all',name:'全体人员',people:sortedPeople('all').filter(matchesPerson)}]:groups.value)
const allExpanded=computed(()=>visibleGroups.value.length>0&&visibleGroups.value.every(group=>expanded.value.includes(group.id)))
watch([keyword,viewMode],()=>{expanded.value=visibleGroups.value.map(group=>group.id)})
watch(countFilter,()=>{expanded.value=visibleGroups.value.map(group=>group.id);emit('update:modelValue',[])})
function toggleExpanded(){expanded.value=allExpanded.value?[]:visibleGroups.value.map(group=>group.id)}
function toggle(person,checked){emit('update:modelValue',checked?[...props.modelValue.filter(p=>p.id!==person.id),person]:props.modelValue.filter(p=>p.id!==person.id))}
function drag(event,person){if(props.disabled||props.assignedIds.includes(person.id)){event.preventDefault();return}const values=(props.modelValue.some(p=>p.id===person.id)?props.modelValue:[person]).filter(value=>!props.assignedIds.includes(value.id));event.dataTransfer.setData('application/x-project-personnel',JSON.stringify(values));event.dataTransfer.effectAllowed='copyMove'}
function resetOrder(){order.value={departments:[],people:{}};try{localStorage.removeItem(orderStorageKey())}catch{/* 当前页面仍恢复默认。 */}}
function startOrderDrag(event,kind,id,groupId){orderDrag.value={kind,id:String(id),groupId};event.dataTransfer.setData('application/x-arrangement-roster-order',JSON.stringify(orderDrag.value));event.dataTransfer.effectAllowed='move'}
function allowOrderDrop(event,kind,groupId){if(orderDrag.value?.kind===kind&&(kind!=='person'||orderDrag.value.groupId===groupId))event.preventDefault()}
function moveOrder(kind,from,to,groupId){
  const ids=(kind==='department'?sortBySaved(defaultGroups.value,order.value.departments):sortedPeople(groupId)).map(row=>String(row.id))
  const source=ids.indexOf(String(from)),target=ids.indexOf(String(to));if(source<0||target<0||source===target)return
  ids.splice(target,0,...ids.splice(source,1))
  if(kind==='department')order.value.departments=ids;else order.value.people={...order.value.people,[groupId]:ids}
  persistOrder()
}
function dropDepartment(event,id){if(orderDrag.value?.kind!=='department')return;event.preventDefault();event.stopPropagation();moveOrder('department',orderDrag.value.id,id);orderDrag.value=null}
function dropPerson(event,groupId,id){if(orderDrag.value?.kind!=='person'||orderDrag.value.groupId!==groupId)return;event.preventDefault();event.stopPropagation();moveOrder('person',orderDrag.value.id,id,groupId);orderDrag.value=null}
function orderByKeyboard(event,kind,id,groupId){if(!['ArrowUp','ArrowDown'].includes(event.key))return;event.preventDefault();const rows=kind==='department'?groups.value:visibleGroups.value.find(group=>group.id===groupId)?.people||[];const index=rows.findIndex(row=>String(row.id)===String(id)),target=rows[index+(event.key==='ArrowUp'?-1:1)];if(target)moveOrder(kind,id,target.id,groupId)}
let loadId=0
async function loadPersonnel(){
  const id=++loadId
  loading.value=true;directoryError.value='';serviceUnavailable.value=false
  // 使用已有组织名册接口，避免任务存储或新版接口未就绪时阻断人员展示。
  const directoryRequest=(props.directoryLoader||getArrangementPersonnel)().then(data=>{
    if(id!==loadId)return
    departments.value=Array.isArray(data.items)?data.items:[]
    people.value=(Array.isArray(data.people)?data.people:[]).filter(person=>person.active).map(person=>({...person,departments:Array.isArray(person.departments)?person.departments:[]}))
    const groupIds=new Set([...departments.value.map(group=>String(group.id)),'ungrouped','all'])
    order.value={departments:[...new Set(order.value.departments)].filter(id=>groupIds.has(id)&&id!=='all'),people:Object.fromEntries(Object.entries(order.value.people).filter(([key])=>groupIds.has(key)).map(([key,ids])=>{const members=new Set(basePeople(key).map(person=>String(person.id)));return [key,[...new Set(ids)].filter(id=>members.has(id))]}))}
    if(hasCustomOrder.value)persistOrder()
    expanded.value=props.defaultCollapsed?[]:visibleGroups.value.map(group=>group.id)
  }).catch(error=>{if(id===loadId)directoryError.value=getLocalizedErrorMessage(error,'人员名单加载失败，请点击刷新重试。')}).finally(()=>{if(id===loadId)loading.value=false})
  const statusRequest=(props.availabilityLoader||getArrangementDirectory)().then(data=>{if(id===loadId)ready.value=typeof data.ready==='boolean'?data.ready:null}).catch(()=>{if(id===loadId){ready.value=null;serviceUnavailable.value=true}})
  await Promise.allSettled([directoryRequest,statusRequest])
}
onMounted(loadPersonnel)
</script>
<style scoped>
.person.is-assigned{background:#f1f5f9;color:#94a3b8;cursor:default}.person.is-assigned>small{white-space:nowrap}.person.is-assigned :deep(.el-checkbox__label){color:#94a3b8}

.arrangement-personnel{display:flex;flex-direction:column;gap:12px;min-width:0;border:1px solid #e2e8f0;border-radius:8px;padding:14px;max-height:75vh;overflow-y:auto}.person{display:flex;align-items:center;justify-content:space-between;padding:4px;cursor:grab}small{color:#64748b}.person:hover{background:#eff6ff}
.personnel-heading,.personnel-controls{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap}.person{gap:8px}.person .el-checkbox{min-width:0;height:auto;min-height:32px}.person :deep(.el-checkbox__label){white-space:normal;overflow-wrap:anywhere}
.roster-order-handle{display:inline-flex;align-items:center;justify-content:center;flex-shrink:0;width:24px;min-height:28px;border-radius:4px;color:#94a3b8;cursor:grab;font-size:20px;user-select:none;margin-right:6px}.roster-order-handle:hover,.roster-order-handle:focus-visible{background:#dbeafe;color:#2563eb}.roster-order-handle:active{cursor:grabbing}.person .el-checkbox{flex:1}.personnel-order-tip{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
</style>
<style scoped>.person:has(.person-duty-count){position:relative;padding-right:30px;border:1px solid #e2e8f0;border-radius:6px;margin:4px 0;background:#fff}.person-duty-count{position:absolute;right:3px;top:2px;min-width:18px;height:18px;padding:0 3px;box-sizing:border-box;border-radius:9px;background:#409eff;color:#fff;font-size:11px;text-align:center;line-height:18px;font-weight:600}.person-duty-count.is-zero{background:#e2e8f0;color:#64748b}</style>
