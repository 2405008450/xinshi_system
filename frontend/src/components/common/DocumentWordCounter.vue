<template>
  <section class="document-counter" data-dialog-field-search-label="文件字数统计">
    <div class="counter-heading"><strong>从文件统计字数</strong><span>统计结果先预览，回填后仍需保存项目统计。</span></div>
    <el-radio-group v-model="source" :disabled="busy" size="small"><el-radio-button value="upload">选择本机文件</el-radio-button><el-radio-button value="unc">UNC 共享路径</el-radio-button></el-radio-group>
    <div v-if="source === 'upload'" class="counter-input">
      <input ref="fileInput" type="file" multiple accept=".docx,.xlsx,.pptx,.doc,.xls,.ppt,.pdf,.txt" :disabled="busy" aria-label="选择待统计文件" @change="pickFiles" />
      <small>每批最多 50 份，单文件 50 MB，合计 200 MB。</small>
    </div>
    <div v-else class="counter-input">
      <el-input v-model="path" :disabled="busy" placeholder="例如 \\Win-server\共享目录\项目文件" aria-label="统计共享路径" @input="clearDiscovery" />
      <div><el-checkbox v-model="recursive" :disabled="busy" @change="clearDiscovery">包含子文件夹</el-checkbox><el-button :loading="discovering" :disabled="busy || !path.trim()" @click="discover">读取文件列表</el-button></div>
      <el-table v-if="available.length" :data="available" max-height="210" size="small" row-key="relative_path" @selection-change="value => selected = value">
        <el-table-column type="selection" width="40" /><el-table-column prop="relative_path" label="选择需要统计的共享文件" min-width="220" show-overflow-tooltip /><el-table-column label="大小" width="90"><template #default="{row}">{{ Math.ceil(row.size/1024) }} KB</template></el-table-column>
      </el-table>
      <small v-if="available.length">共 {{ available.length }} 份，已选 {{ selected.length }} 份。共享路径由当前应用服务器读取。</small>
    </div>
    <div class="counter-options"><el-checkbox v-model="includeHidden" :disabled="busy">计入 Excel 隐藏内容</el-checkbox><el-checkbox v-model="includeExtra" :disabled="busy">计入备注、页眉页脚等额外内容</el-checkbox><el-button type="primary" :disabled="busy || !canStart" :loading="busy" @click="start">开始统计</el-button></div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-progress v-if="busy && result" :percentage="Math.round(result.completed/Math.max(1,result.total)*100)" />
    <template v-if="result">
      <div class="counter-summary">{{ result.completed }} / {{ result.total }} 份已处理 · 成功 {{ result.counted_files }} 份 · 待处理／失败 {{ result.failed_files }} 份 · 合计 <strong>{{ result.words.toLocaleString('zh-CN') }}</strong> 字</div>
      <el-table :data="result.files" max-height="220" size="small"><el-table-column prop="name" label="文件" min-width="200" show-overflow-tooltip /><el-table-column label="字数" width="95"><template #default="{row}">{{ row.words == null ? '—' : row.words.toLocaleString('zh-CN') }}</template></el-table-column><el-table-column label="状态／说明" min-width="160"><template #default="{row}">{{ row.status === 'counted' ? '完成' : row.message }}</template></el-table-column></el-table>
      <div v-if="result.status === 'completed'" class="counter-apply">
        <el-select v-model="dimension" aria-label="统计结果回填维度" style="width:140px"><el-option label="预统计" value="preliminary" /><el-option label="我司统计" value="company" /></el-select>
        <el-select v-model="metric" aria-label="统计结果回填口径" style="width:160px"><el-option label="字数" value="words" /><el-option label="不计空格字符数" value="characters_no_spaces" /></el-select>
        <el-button :disabled="!result.counted_files || result.failed_files > 0" @click="apply">回填统计结果</el-button><small v-if="result.failed_files">存在未成功统计的文件，请处理后重新统计，避免回填不完整总量。</small>
      </div>
      <div v-if="replacing" class="counter-apply"><el-alert title="该维度已有统计数量，确认后将替换为本次结果。回填后仍需保存。" type="warning" :closable="false" /><el-button @click="replacing=false">取消替换</el-button><el-button type="primary" @click="confirmApply">确认替换统计</el-button></div>
    </template>
  </section>
</template>
<script setup>
import {computed, onBeforeUnmount, ref, watch} from 'vue'
import api from '@/api'
const emit = defineEmits(['apply'])
const props = defineProps({currentMatrix: {type:Object, default:()=>({})}})
const source=ref('upload'), path=ref(''), recursive=ref(true), files=ref([]), available=ref([]), selected=ref([])
const includeHidden=ref(false), includeExtra=ref(false), busy=ref(false), discovering=ref(false), error=ref(''), result=ref(null)
const dimension=ref('preliminary'), metric=ref('words'), replacing=ref(false)
let timer, active=true
const canStart=computed(()=>!discovering.value && (source.value==='upload' ? files.value.length>0 : selected.value.length>0))
function clearDiscovery(){available.value=[];selected.value=[]}
function pickFiles(event){files.value=Array.from(event.target.files || [])}
function detail(exc){return exc?.detail || exc?.response?.data?.detail || exc?.message || '统计失败，请重试'}
async function discover(){
  discovering.value=true;error.value='';clearDiscovery();const requestedPath=path.value, requestedRecursive=recursive.value
  try{const data=await api.post('/document-word-count/discover',{path:path.value,recursive:recursive.value},{timeout:60000});if(path.value!==requestedPath || recursive.value!==requestedRecursive)return;available.value=data.files;if(!data.files.length)error.value='未找到支持的文件，请检查目录或访问权限'}catch(exc){error.value=detail(exc)}finally{discovering.value=false}
}
async function start(){
  if((source.value==='upload'?files.value.length:selected.value.length)>50){error.value='每批最多选择 50 份文件';return}
  busy.value=true;error.value='';result.value=null
  try{
    let response
    if(source.value==='upload'){
      const form=new FormData();files.value.forEach(file=>form.append('files',file));form.append('include_hidden',String(includeHidden.value));form.append('include_extra',String(includeExtra.value))
      response=await api.post('/document-word-count/upload',form,{headers:{'Content-Type':'multipart/form-data'},timeout:120000})
    }else response=await api.post('/document-word-count/paths',{path:path.value,relative_paths:selected.value.map(file=>file.relative_path),include_hidden:includeHidden.value,include_extra:includeExtra.value},{timeout:60000})
    await poll(response.job_id)
  }catch(exc){error.value=detail(exc);busy.value=false}
}
async function poll(id){
  if(!active)return
  try{
    const data=await api.get(`/document-word-count/jobs/${id}`)
    if(!active)return
    result.value=data
    if(['completed','failed'].includes(data.status)){busy.value=false;if(data.status==='failed')error.value='任务中断，请重新统计';return}
    timer=setTimeout(()=>poll(id),800)
  }catch(exc){if(active){error.value=detail(exc);busy.value=false}}
}
function apply(){
  const current=props.currentMatrix?.[dimension.value] || {}
  if(Object.values(current).some(value=>value!=null && value!=='')){replacing.value=true;return}
  confirmApply()
}
function confirmApply(){
  replacing.value=false
  emit('apply',{dimension:dimension.value,metric:metric.value,value:result.value[metric.value]})
}
watch([dimension,metric],()=>{replacing.value=false})
watch([source,path,recursive,includeHidden,includeExtra,files,selected],()=>{if(!busy.value){result.value=null;error.value='';replacing.value=false}})
onBeforeUnmount(()=>{active=false;clearTimeout(timer)})
</script>
<style scoped>
.document-counter{border:1px solid var(--el-border-color);border-radius:6px;padding:12px;margin:12px 0;background:var(--el-bg-color)}.counter-heading,.counter-options,.counter-apply{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:8px 0}.counter-heading span,.document-counter small{font-size:12px;color:var(--el-text-color-secondary)}.counter-input{display:grid;gap:8px;margin:10px 0}.counter-summary{padding:10px 0;font-size:13px}.counter-apply{padding-top:8px}
</style>
