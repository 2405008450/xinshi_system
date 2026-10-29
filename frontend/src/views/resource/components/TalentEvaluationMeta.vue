<template>
  <div class="talent-evaluation-meta">
    <label>评价人<ReadonlyField :model-value="account" source="auto" tooltip="由实际保存评价的登录账号自动记录" /></label>
    <label>评价时间<ReadonlyField :model-value="time" source="auto" tooltip="由后端保存时按 UTC+8 自动记录" /></label>
    <el-popover v-if="evaluation.id" trigger="click" placement="left" :width="760" title="评价修改记录" popper-class="talent-evaluation-history" @show="openHistory">
      <template #reference><el-button link type="primary">修改记录</el-button></template>
      <div v-loading="loading" class="evaluation-history-body">
        <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button link @click="loadHistory">重试</el-button></el-alert>
        <el-table v-else :data="items" border size="small" empty-text="暂无修改记录">
          <el-table-column prop="actorAccount" label="评价人" width="130" />
          <el-table-column label="评价时间" width="180"><template #default="{row}">{{ formatBusinessDateTime(row.createdAt) }}</template></el-table-column>
          <el-table-column label="修改内容" min-width="240"><template #default="{row}"><div v-for="change in changes(row)" :key="change.key" class="evaluation-change">{{ change.label }}：{{ change.before }} → {{ change.after }}</div></template></el-table-column>
        </el-table>
        <el-pagination v-model:current-page="page" :page-size="10" :total="total" layout="prev, pager, next, total" @current-change="loadHistory" />
      </div>
    </el-popover>
  </div>
</template>
<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
import { formatBusinessDateTime } from '@/utils/dateTime'
import { evaluationSnapshot, evaluationGroupMeta, evaluationFieldLabels } from '@/utils/talentEvaluationAudit'
import { reviewDisplay } from '@/utils/talentDuplicateReview'
import { getTalentEvaluationHistory } from '@/api/talents'
const props = defineProps({ evaluation: {type:Object,required:true}, groupKey:{type:String,required:true}, editing:Boolean })
const meta = computed(() => evaluationGroupMeta(props.evaluation, props.groupKey))
const dirty = computed(() => props.editing && JSON.stringify(evaluationSnapshot(props.evaluation)[props.groupKey]) !== JSON.stringify(props.evaluation.evaluationOriginal?.[props.groupKey] || evaluationSnapshot({})[props.groupKey]))
const account = computed(() => dirty.value ? localStorage.getItem('user_name') || '当前账号' : meta.value?.actorAccount || (props.evaluation.id ? '未记录' : localStorage.getItem('user_name') || '当前账号'))
const time = computed(() => dirty.value || !props.evaluation.id ? '保存后自动记录' : meta.value?.createdAt ? formatBusinessDateTime(meta.value.createdAt) : '未记录')
const items=ref([]),total=ref(0),page=ref(1),loading=ref(false),error=ref('')
let controller, sequence=0
async function loadHistory(){controller?.abort();controller=new AbortController();const request=++sequence;loading.value=true;error.value='';try{const result=await getTalentEvaluationHistory(props.evaluation.id,{group_key:props.groupKey,skip:(page.value-1)*10,limit:10},{signal:controller.signal});if(request!==sequence)return;items.value=result.items;total.value=result.total}catch(failure){if(failure.code!=='ERR_CANCELED'&&request===sequence)error.value=failure.detail||'修改记录加载失败'}finally{if(request===sequence)loading.value=false}}
function openHistory(){page.value=1;items.value=[];loadHistory()}
const changes=row=>Object.keys(row.afterValues||{}).filter(key=>JSON.stringify(row.beforeValues?.[key])!==JSON.stringify(row.afterValues[key])).map(key=>({key,label:evaluationFieldLabels[key]||key,before:reviewDisplay(row.beforeValues?.[key]),after:reviewDisplay(row.afterValues[key])}))
onBeforeUnmount(()=>controller?.abort())
</script>
<style scoped>
.talent-evaluation-meta{display:flex;align-items:flex-end;flex-wrap:wrap;gap:10px;margin:8px 0 14px;font-size:12px;color:var(--el-text-color-secondary)}
.talent-evaluation-meta label{display:flex;flex-direction:column;gap:4px;max-width:100%}
.talent-evaluation-meta label:first-child{width:150px}.talent-evaluation-meta label:nth-child(2){width:220px}
.evaluation-history-body{max-height:min(460px,calc(100vh - 140px));overflow:auto}.evaluation-change{white-space:pre-wrap;overflow-wrap:anywhere}
</style>
<style>.talent-evaluation-history{max-width:calc(100vw - 32px)}</style>
