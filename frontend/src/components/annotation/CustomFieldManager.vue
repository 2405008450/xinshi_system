<template>
  <el-popover v-model:visible="visible" trigger="click" placement="bottom-end" :width="520">
    <template #reference><el-button :disabled="disabled">{{ buttonLabel }}</el-button></template>
    <div class="manager" v-loading="loading">
      <div class="manager__header"><strong>动态字段管理</strong><el-button type="primary" link @click="startAdd">新增字段</el-button></div>
      <el-alert v-if="scopeHint" class="manager__hint" :title="scopeHint" type="info" :closable="false" show-icon />
      <el-table :data="fields" size="small" max-height="320">
        <el-table-column prop="fieldLabel" label="字段名" min-width="120" />
        <el-table-column prop="dataType" label="类型" width="105" />
        <el-table-column label="状态" width="70"><template #default="{row}"><el-tag :type="row.isActive?'success':'info'" size="small">{{ row.isActive?'启用':'停用' }}</el-tag></template></el-table-column>
        <el-table-column label="操作" width="130"><template #default="{row}"><el-button link type="primary" @click="startEdit(row)">编辑</el-button><el-button v-if="row.isActive" link type="danger" @click="disable(row)">停用</el-button><el-button v-else link type="success" @click="restore(row)">恢复</el-button></template></el-table-column>
      </el-table>
    </div>
  </el-popover>
  <el-dialog v-model="dialogVisible" :title="editingId?'编辑动态字段':'新增动态字段'" width="min(620px, calc(100vw - 32px))" append-to-body>
    <el-form label-width="90px"><el-form-item v-if="!autoFieldKey" label="字段键"><el-input v-model="form.fieldKey" :disabled="!!editingId" placeholder="例如 delivery_batch" /></el-form-item><el-form-item label="显示名称"><el-input v-model="form.fieldLabel" placeholder="例如：验收批次" /></el-form-item><el-form-item label="数据类型"><el-select v-model="form.dataType" style="width:100%"><el-option v-for="item in types" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item><el-form-item v-if="form.dataType.includes('select')" label="选项"><el-select v-model="form.options" multiple filterable allow-create default-first-option style="width:100%" /></el-form-item><el-form-item label="设置"><el-checkbox v-model="form.isRequired">必填</el-checkbox><el-checkbox v-model="form.isActive">启用</el-checkbox></el-form-item></el-form>
    <template #footer><el-button @click="dialogVisible=false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template>
  </el-dialog>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createCustomField, deleteCustomField, getCustomFields, updateCustomField } from '@/api/annotationOps'

const props = defineProps({ tableCode:{type:String,required:true}, projectId:{type:String,default:''}, buttonLabel:{type:String,default:'动态字段'}, disabled:{type:Boolean,default:false}, scopeHint:{type:String,default:''}, autoFieldKey:{type:Boolean,default:false} })
const emit = defineEmits(['changed'])
const visible=ref(false),dialogVisible=ref(false),loading=ref(false),saving=ref(false),editingId=ref(''),fields=ref([])
const types=computed(()=>[
  ['text','文本'],['number','数字'],['date','日期'],['datetime','日期时间'],['boolean','是/否'],
  ['single_select','单选'],['multi_select','多选'],['url','链接'],
  ...(props.tableCode==='account_assignment'?[['image','图片']]:[]),
].map(([value,label])=>({value,label})))
const empty=()=>({projectId:props.projectId||null,tableCode:props.tableCode,fieldKey:'',fieldLabel:'',dataType:'text',options:[],isRequired:false,isActive:true})
const form=reactive(empty())
const load=async()=>{loading.value=true;try{fields.value=await getCustomFields(props.tableCode,props.projectId||null,true)}finally{loading.value=false}}
const generateFieldKey=()=>`custom_${Date.now().toString(36)}_${Math.random().toString(36).slice(2,7)}`
const startAdd=()=>{editingId.value='';Object.assign(form,empty(),{fieldKey:props.autoFieldKey?generateFieldKey():''});dialogVisible.value=true}
const startEdit=(row)=>{editingId.value=row.id;Object.assign(form,empty(),row);dialogVisible.value=true}
const payload=source=>({projectId:source.projectId||null,tableCode:source.tableCode,fieldKey:source.fieldKey,fieldLabel:source.fieldLabel.trim(),dataType:source.dataType,options:source.options||[],sequenceNo:source.sequenceNo||null,isRequired:Boolean(source.isRequired),isActive:Boolean(source.isActive)})
const save=async()=>{if(!form.fieldKey.trim()||!form.fieldLabel.trim())return ElMessage.warning('请填写字段名称');saving.value=true;try{const data=payload(form);const action=editingId.value?updateCustomField(editingId.value,data):createCustomField(data);await action;ElMessage.success('动态字段已保存');dialogVisible.value=false;await load();emit('changed')}catch(error){ElMessage.error(error.detail||'保存失败')}finally{saving.value=false}}
const disable=async(row)=>{
  visible.value=false
  try{
    await ElMessageBox.confirm(`停用“${row.fieldLabel}”？该列会从当前项目表隐藏，但历史值会保留。`,'受限删除',{type:'warning',confirmButtonText:'确认停用',cancelButtonText:'取消'})
    await deleteCustomField(row.id)
    await load()
    emit('changed')
    ElMessage.success('字段已停用，历史值已保留')
  }catch(error){
    if(error==='cancel'||error==='close') return
    ElMessage.error(error.detail||error.message||'停用失败')
  }
}
const restore=async(row)=>{saving.value=true;try{await updateCustomField(row.id,payload({...row,isActive:true}));await load();emit('changed');ElMessage.success('字段已恢复')}catch(error){ElMessage.error(error.detail||'恢复失败')}finally{saving.value=false}}
onMounted(load)
watch(()=>[props.tableCode,props.projectId],()=>load())
</script>

<style scoped>.manager__header{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}.manager__hint{margin-bottom:10px}</style>
