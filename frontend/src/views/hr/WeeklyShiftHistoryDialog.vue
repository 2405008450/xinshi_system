<template>
  <DraggableFormDialog :model-value="modelValue" :title="kind==='duty'?'值班修改记录':'班次修改记录'" append-to-body width="min(960px, calc(100vw - 32px))" top="5vh" @update:model-value="$emit('update:modelValue',$event)">
    <p>{{week}} {{kind==='duty'?'月份':'所在周'}} · {{public?'仅显示已同步的修改记录':'包含尚未同步的草稿修改'}}</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <div v-loading="loading"><el-empty v-if="!items.length&&!loading" description="暂无修改记录" :image-size="60" />
      <article v-for="item in items" :key="item.id" class="shift-history-entry"><header><strong>{{labels[item.action]||item.action}}</strong><el-tag v-if="item.publication_revision==null" size="small" type="warning">未同步</el-tag><span>{{item.actor_name}} · {{formatBusinessDateTime(item.created_at)}}</span></header>
        <el-table v-if="item.changes.length" :data="item.changes" border size="small"><el-table-column prop="name" label="人员" min-width="110" /><el-table-column label="修改前" min-width="200"><template #default="{row}">{{describe(row.before)}}</template></el-table-column><el-table-column label="修改后" min-width="200"><template #default="{row}">{{describe(row.after)}}</template></el-table-column></el-table>
      </article>
    </div>
    <template #footer><span>共 {{total}} 条</span><el-button :disabled="loading||items.length>=total" @click="load(true)">加载更多</el-button><el-button @click="$emit('update:modelValue',false)">关闭</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {ref,watch,onBeforeUnmount,onMounted} from 'vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import {getWeeklyShiftHistory,getWeekendDutyHistory} from '@/api/monthlyShifts'
import {formatBusinessDateTime} from '@/utils/dateTime'
import {subscribe} from '@/utils/realtimeSocket'
const props=defineProps({modelValue:Boolean,kind:{type:String,default:'shift'},week:{type:String,required:true},public:{type:Boolean,default:true},shifts:{type:Array,default:()=>[]},departments:{type:Array,default:()=>[]}})
defineEmits(['update:modelValue'])
const items=ref([]),total=ref(0),loading=ref(false),error=ref('')
const labels={draft_save:'自动保存草稿',publish:'同步到工作台',enable_edit:'开启修改',copy:'复制周安排',move:'转移周安排',swap:'互换周安排'}
const describe=value=>value?`${props.departments.find(row=>row.code===value.department)?.label||value.department} · ${value.date||props.shifts.find(row=>row.code===value.shift)?.label||value.shift}${value.fixed?'（固定）':''}${value.home_rotation?'（居家轮班）':value.home_office_day?'（居家）':''}`:'未安排'
let controller,sequence=0,unsubscribe
async function load(more=false){controller?.abort();const id=++sequence;if(!props.modelValue)return;controller=new AbortController();loading.value=true;error.value='';if(!more)items.value=[];try{const result=await (props.kind==='duty'?getWeekendDutyHistory:getWeeklyShiftHistory)(props.week,{public:props.public,offset:more?items.value.length:0,signal:controller.signal});if(id===sequence){items.value=more?[...items.value,...result.items]:result.items;total.value=result.total}}catch(e){if(id===sequence&&e.code!=='ERR_CANCELED')error.value=e.detail||'读取修改记录失败'}finally{if(id===sequence)loading.value=false}}
watch([()=>props.modelValue,()=>props.week],()=>{if(props.modelValue)load();else{controller?.abort();sequence++}},{immediate:true})
onMounted(()=>{unsubscribe=subscribe(props.kind==='duty'?'weekend_duty_published':'weekly_shift_published',event=>{if(props.modelValue&&(event.month||event.week_start)===props.week)load()})})
onBeforeUnmount(()=>{controller?.abort();sequence++;unsubscribe?.()})
</script>
<style scoped>.shift-history-entry{padding:12px 0;border-bottom:1px solid #e2e8f0}.shift-history-entry header{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:8px}.shift-history-entry header span{font-size:12px;color:#64748b}</style>
