<template>
  <div class="direction-editor">
    <div v-for="(item, index) in localValue" :key="index" class="direction-row">
      <el-select v-model="item.directionType" style="width:126px" @change="handleTypeChange(item)">
        <el-option label="单语/方言" value="single" />
        <el-option label="翻译方向" value="translation" />
      </el-select>
      <el-select v-model="item.sourceLanguageId" filterable placeholder="选择语种/方言" style="flex:1" @change="emitValue">
        <el-option v-for="language in languages" :key="language.id" :label="language.label" :value="language.id">
          <span>{{ language.label }}</span><el-tag v-if="language.isCustom" size="small" type="warning" class="new-tag">新</el-tag>
        </el-option>
      </el-select>
      <template v-if="item.directionType==='translation'">
        <span>→</span>
        <el-select v-model="item.targetLanguageId" filterable placeholder="选择目标语种" style="flex:1" @change="emitValue">
          <el-option v-for="language in languages" :key="language.id" :label="language.label" :value="language.id" :disabled="language.id===item.sourceLanguageId">
            <span>{{ language.label }}</span><el-tag v-if="language.isCustom" size="small" type="warning" class="new-tag">新</el-tag>
          </el-option>
        </el-select>
      </template>
      <el-button type="danger" link @click="remove(index)">删除</el-button>
    </div>
    <div class="direction-actions">
      <el-button class="soft-action-button" :icon="Plus" @click="add">新增方向</el-button>
      <el-popover v-model:visible="createVisible" trigger="click" placement="bottom-end" :width="320">
        <template #reference><el-button class="soft-action-button" :icon="Plus">新增共享语种</el-button></template>
        <el-form @submit.prevent>
          <el-form-item label="语种/方言名称"><el-input v-model="newLabel" maxlength="100" placeholder="例如：温州话" @keyup.enter="createLanguage" /></el-form-item>
          <div class="create-actions"><el-button @click="createVisible=false">取消</el-button><el-button type="primary" :loading="creating" @click="createLanguage">添加</el-button></div>
        </el-form>
      </el-popover>
    </div>
    <div class="hint">单语听音、正字转写等任务选择“单语/方言”；翻译类标注选择完整方向。自定义方言会进入项目共享语种目录。</div>
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { createProjectLanguage, getProjectLanguages } from '@/api/projectLanguages'

const props=defineProps({modelValue:{type:Array,default:()=>[]}})
const emit=defineEmits(['update:modelValue'])
const languages=ref([]),localValue=ref([]),createVisible=ref(false),creating=ref(false),newLabel=ref('')
let syncing=false
const normalize=items=>(items||[]).map(item=>({
  directionType:item.directionType||(item.targetLanguageId?'translation':'single'),
  sourceLanguageId:item.sourceLanguageId||'',
  targetLanguageId:item.targetLanguageId||'',
}))
watch(()=>props.modelValue,value=>{if(!syncing)localValue.value=normalize(value)},{immediate:true,deep:true})
const emitValue=()=>{syncing=true;emit('update:modelValue',normalize(localValue.value));queueMicrotask(()=>{syncing=false})}
const add=()=>{localValue.value.push({directionType:'single',sourceLanguageId:'',targetLanguageId:''});emitValue()}
const remove=index=>{localValue.value.splice(index,1);emitValue()}
const handleTypeChange=item=>{if(item.directionType==='single')item.targetLanguageId='';emitValue()}
const load=async()=>{try{languages.value=await getProjectLanguages()}catch{ElMessage.error('共享语种加载失败')}}
const createLanguage=async()=>{
  const label=newLabel.value.trim()
  if(!label)return ElMessage.warning('请输入语种或方言名称')
  creating.value=true
  try{
    const created=await createProjectLanguage(label)
    languages.value.push(created)
    languages.value.sort((a,b)=>Number(a.isCustom)-Number(b.isCustom)||a.label.localeCompare(b.label,'zh-CN'))
    newLabel.value='';createVisible.value=false;ElMessage.success('已添加到共享语种目录')
  }catch(error){ElMessage.error(error?.detail||'新增共享语种失败')}
  finally{creating.value=false}
}
onMounted(load)
</script>

<style scoped>
.direction-editor{width:100%}.direction-row{display:flex;align-items:center;gap:8px;margin-bottom:8px}.direction-actions,.create-actions{display:flex;gap:8px;justify-content:flex-end}.soft-action-button{--el-button-bg-color:var(--el-color-primary-light-9);--el-button-border-color:var(--el-color-primary-light-7);--el-button-text-color:var(--el-color-primary-dark-2);font-weight:500}.hint{margin-top:5px;color:var(--el-text-color-secondary);font-size:12px}.new-tag{float:right;margin-left:8px}@media(max-width:720px){.direction-row{align-items:stretch;flex-direction:column}.direction-row .el-select{width:100%!important}}
</style>
