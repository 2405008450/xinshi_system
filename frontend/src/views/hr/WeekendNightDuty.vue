<template>
  <section class="night-duty" v-loading="loading">
    <header><h3>周末夜间值班 · {{month}}</h3><div v-if="!readonly"><el-button :type="mode==='standalone'?'primary':'default'" :disabled="busy" @click="mode='standalone'">单独值班</el-button><el-button :type="mode==='continuation'?'primary':'default'" :disabled="busy" @click="mode='continuation'">接续值班</el-button></div><el-button :disabled="busy" @click="load">刷新夜间安排</el-button></header>
    <p>每月周六、周日19:00–23:00，全部居家，独立于普通居家额度。单独、接续夜间值班均不折算半天；有效工作时长计入多值班，优先抵扣待补班的请假；接续值班白天18:00下班，19:00重新上班打卡，23:00下班打卡，共两组。夜间签退须确认真实工作时间，可扣除无效时间并留记录。</p>
    <p v-if="!readonly">{{mode==='standalone'?'单独值班：左侧客户/销售人员拖到右侧日期。':'接续值班：先同步同一天的白天值班，再将该人员拖入夜间日期。'}}停止操作400毫秒后保存，点击同步才更新工作台；同步后点击修改再编辑。</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button v-if="dirty" @click="flush">重试保存</el-button></el-alert>
    <ProjectArrangementLayout :enabled="!readonly" :can-write="editable">
      <template #personnel><div @dragover.prevent @drop.prevent="returnPerson"><ArrangementPersonnel v-model="selected" monthly :assignment-counts="counts" :disabled="!editable" :directory-loader="customerDirectory" :availability-loader="availability" /></div></template>
      <div class="night-scroll"><table><thead><tr><th>安排方式</th><th v-for="day in dates" :key="day">{{dutyDateLabel(day)}}</th></tr></thead><tbody><tr v-for="kind in ['standalone','continuation']" :key="kind"><th>{{kind==='standalone'?'单独值班':'接续值班'}}<small>19:00–23:00 · 居家</small></th><td v-for="day in dates" :key="day" @dragover.prevent @drop.stop.prevent="drop($event,day,kind)"><div v-for="person in people(day,kind)" :key="person.user_id" class="night-person" :draggable="editable" @dragstart="drag($event,person)">{{person.name}}<el-button v-if="editable" link type="danger" :aria-label="`撤销${person.name}${day}夜间值班`" @click="remove(person)">×</el-button></div><span v-if="!people(day,kind).length">{{readonly?'暂无安排':`拖入${kind==='standalone'?'单独':'接续'}值班人员`}}</span><el-button v-if="!readonly&&kind===mode&&selected.length" link :disabled="!editable" @click="assign(selected,day,kind)">安排已选人员</el-button></td></tr></tbody></table></div>
    </ProjectArrangementLayout>
    <footer><span v-if="!readonly">{{saving?'保存中…':dirty?'待自动保存':plan.revision?'已保存':'尚无安排'}}</span><el-popover trigger="click" placement="top-end" :width="760"><template #reference><el-button link>夜间修改记录</el-button></template><div class="night-history"><article v-for="(item,index) in plan.history" :key="index"><strong>{{labels[item.action]}} · {{item.actor}} · {{formatBusinessDateTime(item.at)}}</strong><p>修改前：{{describe(item.before)}}</p><p>修改后：{{describe(item.after)}}</p><el-tag v-if="item.publication_revision==null" type="warning">未同步</el-tag></article><el-empty v-if="!plan.history?.length" description="暂无记录" /></div></el-popover><template v-if="!readonly"><el-button :disabled="busy||plan.can_edit!==false" @click="action('edit')">修改</el-button><el-button :type="plan.needs_sync||dirty?'warning':'primary'" :disabled="busy||(!plan.needs_sync&&!dirty&&plan.can_edit===false)" @click="action('sync')">{{!plan.published_revision?'同步（尚未同步）':plan.needs_sync||dirty?'同步（有未同步修改）':'同步'}}</el-button></template></footer>
  </section>
</template>
<script setup>
import {computed,ref,watch,onBeforeUnmount,onMounted} from 'vue'
import {ElMessage} from 'element-plus'
import api from '@/api'
import {getMonthlyShiftDirectory} from '@/api/monthlyShifts'
import ArrangementPersonnel from '@/components/common/ArrangementPersonnel.vue'
import ProjectArrangementLayout from '@/views/project/translation/components/ProjectArrangementLayout.vue'
import {dutyDateLabel} from '@/utils/weekendDuty'
import {formatBusinessDateTime} from '@/utils/dateTime'
import {subscribe} from '@/utils/realtimeSocket'
const props=defineProps({month:{type:String,required:true},readonly:Boolean,scope:String,week:String}),emit=defineEmits(['busy'])
const plan=ref({assignments:[],dates:[],history:[]}),mode=ref('standalone'),selected=ref([]),loading=ref(false),saving=ref(false),dirty=ref(false),error=ref('')
const busy=computed(()=>saving.value||dirty.value),editable=computed(()=>!props.readonly&&plan.value.ready&&plan.value.can_edit&&!loading.value&&!saving.value)
const counts=computed(()=>plan.value.assignments.reduce((result,row)=>{result[row.user_id]=(result[row.user_id]||0)+1;return result},{}))
const dates=computed(()=>plan.value.dates.filter(day=>!props.week||day>=props.week&&day<=weekEnd(props.week)))
function weekEnd(day){const date=new Date(`${day}T12:00:00+08:00`);return new Date(date.getTime()+6*86400000).toISOString().slice(0,10)}
const people=(day,kind)=>plan.value.assignments.filter(row=>row.date===day&&row.mode===kind&&(props.scope!=='mine'||row.user_id===localStorage.getItem('user_id')))
const availability=async()=>({ready:true})
async function customerDirectory(){const data=await getMonthlyShiftDirectory();return {...data,items:data.items.filter(row=>row.id==='customer'),people:data.people.filter(row=>row.departments.some(dep=>dep.id==='customer')).map(row=>({...row,departments:row.departments.filter(dep=>dep.id==='customer')}))}}
let timer,sequence=0,controller,unsubscribe,active=true,names=new Map()
async function load(){if(busy.value)return;controller?.abort();controller=new AbortController();const id=++sequence;loading.value=true;error.value='';try{const value=await api.get('/weekend-night-duty',{params:{month:props.month,public:props.readonly},signal:controller.signal});if(active&&id===sequence){plan.value=value;for(const [id,name] of Object.entries(value.names||{}))names.set(id,name)}}catch(e){if(id===sequence&&e.code!=='ERR_CANCELED')error.value=e.detail||'读取夜间值班失败'}finally{if(id===sequence)loading.value=false}}
function queue(rows){if(!editable.value)return;plan.value={...plan.value,assignments:rows};dirty.value=true;clearTimeout(timer);timer=setTimeout(flush,400)}
async function flush(){clearTimeout(timer);if(!dirty.value)return true;if(saving.value)return false;saving.value=true;try{const value=await api.put('/weekend-night-duty',{revision:plan.value.revision,assignments:plan.value.assignments.map(({user_id,date,mode})=>({user_id,date,mode}))},{params:{month:props.month}});plan.value=value;dirty.value=false;error.value='';return true}catch(e){error.value=e.detail||'自动保存失败，请重试后离开';return false}finally{saving.value=false}}
function assign(rows,date,kind,source){for(const row of rows)names.set(row.id||row.user_id,row.name);const ids=rows.map(row=>row.id||row.user_id);const remaining=plan.value.assignments.filter(row=>!(ids.includes(row.user_id)&&(row.date===date||source&&row.date===source)));queue([...remaining,...rows.map(row=>({user_id:row.id||row.user_id,name:row.name,date,mode:kind}))])}
function drag(event,row){if(!editable.value){event.preventDefault();return}event.dataTransfer.setData('application/x-night-duty',JSON.stringify(row))}
function drop(event,date,kind){if(!editable.value)return;try{const own=event.dataTransfer.getData('application/x-night-duty');if(own){const row=JSON.parse(own);assign([row],date,kind,row.date)}else{const rows=JSON.parse(event.dataTransfer.getData('application/x-project-personnel'));if(Array.isArray(rows))assign(rows,date,kind)}}catch{/* 忽略非人员拖动 */}}
function remove(row){queue(plan.value.assignments.filter(item=>item.user_id!==row.user_id||item.date!==row.date))}
function returnPerson(event){if(!editable.value)return;try{const row=JSON.parse(event.dataTransfer.getData('application/x-night-duty'));remove(row)}catch{/* 忽略名册排序 */}}
async function action(kind){if(!await flush())return;saving.value=true;try{plan.value=await api.post(`/weekend-night-duty/${kind}`,{revision:plan.value.revision},{params:{month:props.month}});ElMessage.success(kind==='sync'?'夜间值班及记录已同步到工作台':'可继续修改夜间值班')}catch(e){error.value=e.detail||'操作失败'}finally{saving.value=false}}
const labels={save:'自动保存',sync:'同步到工作台',edit:'开启修改'}
const describe=rows=>rows?.map(row=>`${names.get(row.user_id)||row.user_id} · ${row.date} · ${row.mode==='standalone'?'单独':'接续'}`).join('；')||'无安排'
watch(busy,value=>emit('busy',value));watch(()=>props.month,load,{immediate:true})
function beforeLeave(event){if(dirty.value||saving.value){event.preventDefault();event.returnValue=''}}
onMounted(()=>{unsubscribe=subscribe('weekend_duty_published',event=>{if(event.month===props.month)load()});window.addEventListener('beforeunload',beforeLeave)})
onBeforeUnmount(()=>{clearTimeout(timer);if(dirty.value&&!saving.value)void flush();active=false;sequence++;controller?.abort();unsubscribe?.();window.removeEventListener('beforeunload',beforeLeave);emit('busy',false)})
</script>
<style scoped>
.night-duty{margin-top:20px;min-width:0}.night-duty header,.night-duty footer{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.night-duty header h3{margin-right:auto}.night-duty>p,.night-duty footer{font-size:12px;color:#64748b;line-height:1.8}.night-scroll{overflow:auto;max-height:65vh;scrollbar-gutter:stable}.night-duty :deep(.arrangement-personnel){max-height:65vh;overflow-y:scroll;font-size:14px}.night-scroll table{border-collapse:collapse;min-width:100%;font-size:14px}.night-scroll th,.night-scroll td{border:1px solid #dbe3ec;padding:12px;min-width:150px;vertical-align:top}.night-scroll th{background:#f8fafc;position:sticky;top:0}.night-scroll small{display:block;font-size:12px;font-weight:normal}.night-scroll td>span{font-size:12px;color:#94a3b8}.night-person{display:flex;justify-content:space-between;border:1px solid #bfdbfe;background:#eff6ff;padding:8px;border-radius:6px;margin-bottom:8px}.night-person[draggable=true]{cursor:grab}.night-duty footer{justify-content:flex-end;padding-top:12px}.night-history{max-height:500px;overflow-y:auto;overflow-wrap:anywhere}.night-history article{border-bottom:1px solid #e2e8f0;padding:10px 0}.night-history p{font-size:12px}
</style>
