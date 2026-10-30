<template>
  <section class="office-management" v-loading="loading">
    <el-collapse v-model="expanded"><el-collapse-item name="capacity" title="办公室人数设置">
      <div class="office-heading"><p>工位数按办公室设置；实际人数统计人员管理中在用且未删除、城市属于该办公室的人员。请假不改变人数，停用人员不计入实际人数。</p><div><el-button @click="load">刷新人数</el-button><el-button v-if="canWrite" type="primary" @click="edit()">增加其他城市办公室</el-button></div></div>
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <p v-if="data.unassigned_people" class="office-note">有 {{data.unassigned_people}} 名在用人员尚未设置城市，请在人员管理中补充。</p>
      <div class="office-grid"><el-card v-for="office in data.items||[]" :key="office.id" shadow="never"><div class="office-card-heading"><strong>{{office.name}}</strong><el-button v-if="canWrite" link type="primary" :aria-label="`设置${office.name}`" @click="edit(office)">设置工位 / 编辑</el-button></div><div class="office-capacity"><strong>{{office.seats==null?'待设置':office.seats}}</strong><span>工位</span><span class="office-count">实际人数：<el-button v-if="canRead" link type="primary" :aria-label="`查看${office.name}人员`" @click="$emit('people',office)">{{office.actual_people}} 人</el-button><strong v-else>{{office.actual_people}} 人</strong></span></div><p class="office-note">城市：{{office.city}}；登记人员 {{office.registered_people}} 人（含停用）。</p><el-tag v-if="office.seats!=null&&office.actual_people>office.seats" type="warning">超出工位 {{office.actual_people-office.seats}} 人</el-tag></el-card></div>
    </el-collapse-item></el-collapse>
    <DraggableFormDialog v-model="visible" :title="target?'编辑办公室设置':'增加城市办公室'" width="min(640px, calc(100vw - 32px))" top="5vh" class="office-settings-dialog" :close-on-click-modal="false" :before-close="close">
      <AppForm ref="formRef" :model="form" :rules="rules" label-position="top"><el-form-item label="城市" prop="city"><el-input v-model="form.city" maxlength="100" :disabled="saving" placeholder="例如：杭州" /></el-form-item><el-form-item label="办公室名称" prop="name"><el-input v-model="form.name" maxlength="200" :disabled="saving" placeholder="例如：杭州办公室" /></el-form-item><el-form-item label="工位数" prop="seats"><el-input-number v-model="form.seats" :min="0" :max="100000" :precision="0" :disabled="saving" placeholder="待设置" /><span class="office-note">可填0；留空表示尚未设置。</span></el-form-item></AppForm><p class="office-note">保存后，城市会同步到人员管理的城市下拉框。城市更名会同步显示，人员关联保持不变。</p><el-alert v-if="saveError" :title="saveError" type="error" :closable="false" />
      <template #footer><el-button :disabled="saving" @click="visible=false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存办公室设置</el-button></template>
    </DraggableFormDialog>
  </section>
</template>
<script setup>
import {ref,reactive,computed,onMounted,onBeforeUnmount} from 'vue'
import {ElMessage} from 'element-plus'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import {hasPermission} from '@/utils/permission'
import {getOffices,createOffice,updateOffice} from '@/api/offices'
const emit=defineEmits(['people']),canRead=computed(()=>hasPermission('system:users:read')),canWrite=computed(()=>hasPermission('system:users:write'))
const expanded=ref(['capacity']),data=ref({}),loading=ref(false),error=ref(''),visible=ref(false),target=ref(null),saving=ref(false),saveError=ref(''),formRef=ref()
const form=reactive({id:'office-settings-new',city:'',name:'',seats:null}),rules={city:[{required:true,whitespace:true,message:'请填写城市',trigger:'blur'}],name:[{required:true,whitespace:true,message:'请填写办公室名称',trigger:'blur'}]}
let controller,sequence=0,alive=true
async function load(){controller?.abort();controller=new AbortController();const id=++sequence;loading.value=true;error.value='';try{const value=await getOffices({signal:controller.signal});if(alive&&id===sequence)data.value=value}catch(e){if(alive&&id===sequence&&e.code!=='ERR_CANCELED')error.value=typeof e.detail==='string'?e.detail:'读取办公室设置失败'}finally{if(alive&&id===sequence)loading.value=false}}
function edit(office){target.value=office||null;Object.assign(form,{id:office?`office-settings:${office.id}`:'office-settings-new',city:office?.city||'',name:office?.name||'',seats:office?.seats??null});saveError.value='';visible.value=true}
function close(done){if(!saving.value)done()}
async function save(){if(saving.value||!await formRef.value.validate().catch(()=>false))return;saving.value=true;saveError.value='';try{const payload={city:form.city,name:form.name,seats:form.seats??null};const result=target.value?await updateOffice(target.value.id,{...payload,revision:target.value.revision}):await createOffice(payload);ElMessage.success(result.message);visible.value=false;window.dispatchEvent(new Event('office-cities-changed'));load()}catch(e){saveError.value=typeof e.detail==='string'?e.detail:'办公室设置未确认保存，请重试'}finally{saving.value=false}}
onMounted(()=>{load();window.addEventListener('focus',load);window.addEventListener('office-people-changed',load)})
onBeforeUnmount(()=>{alive=false;sequence++;controller?.abort();window.removeEventListener('focus',load);window.removeEventListener('office-people-changed',load)})
</script>
<style scoped>.office-heading,.office-heading>div,.office-card-heading,.office-capacity{display:flex;align-items:center;gap:12px;flex-wrap:wrap}.office-heading,.office-card-heading{justify-content:space-between}.office-heading p,.office-note{font-size:13px;line-height:1.7;color:#64748b}.office-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(320px,100%),1fr));gap:16px;margin:16px 0}.office-capacity{margin-top:20px}.office-capacity>strong{font-size:26px}.office-count{margin-left:12px}.office-note{margin-top:12px}</style>
<style>.office-settings-dialog.el-dialog{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}.office-settings-dialog>.el-dialog__header,.office-settings-dialog>.el-dialog__footer{flex-shrink:0}.office-settings-dialog>.el-dialog__body{flex:1;min-height:0;overflow-y:auto}.office-settings-dialog>.el-dialog__footer{border-top:1px solid #e2e8f0;background:#f8fafc}</style>
