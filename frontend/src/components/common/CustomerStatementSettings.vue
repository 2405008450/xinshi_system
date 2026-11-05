<template>
  <el-button v-if="canWrite" @click="open">对账单设置</el-button>
  <DraggableFormDialog v-model="visible" class="statement-settings-dialog" append-to-body width="min(760px, calc(100vw - 32px))" top="5vh" :before-close="close" :close-on-click-modal="false">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" title="对账单设置" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="body" v-loading="loading||saving">
      <p>公司主体、账户信息和印章由所有客户对账单共用，保存后用于新生成的对账单，已有对账单保持原抬头。</p>
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <AppForm v-if="!loading" ref="form" :model="draft" :disabled="saving" label-position="top">
        <el-form-item label="公司主体" prop="company"><el-select v-model="draft.company" aria-label="公司主体" style="width:100%"><el-option v-for="company in companies" :key="company" :label="company" :value="company" /></el-select></el-form-item>
        <el-form-item label="开户行" prop="bank_name"><el-input v-model="draft.bank_name" maxlength="255" placeholder="填写开户行" /></el-form-item>
        <el-form-item label="账户名" prop="account_name"><el-input v-model="draft.account_name" maxlength="255" placeholder="填写收款账户名" /></el-form-item>
        <el-form-item label="账号" prop="account_number"><el-input v-model="draft.account_number" maxlength="100" placeholder="填写收款账号" /></el-form-item>
        <el-form-item label="印章图片" prop="stamp_image">
          <div><img :src="draft.stamp_image||defaultStamp" class="stamp-preview" alt="对账单印章预览" /><div class="stamp-actions"><el-button @click="fileInput.click()">更换印章图片</el-button><el-button @click="draft.stamp_image=null">恢复示例章</el-button></div><small>支持PNG、JPG、WebP，最大2MB。透明底PNG可保留真实盖章的叠印效果。</small><input ref="fileInput" type="file" accept="image/png,image/jpeg,image/webp" hidden @change="chooseStamp" /></div>
        </el-form-item>
      </AppForm>
    </div>
    <template #footer><el-button :disabled="saving" @click="close()">取消</el-button><el-button type="primary" :loading="saving" :disabled="loading||!ready" @click="save">保存设置</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import {reactive,ref,onBeforeUnmount} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import DraggableFormDialog from './DraggableFormDialog.vue'
import AppForm from './AppForm.vue'
import DialogFieldSearchHeader from './DialogFieldSearchHeader.vue'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import {getStatementSettings,saveStatementSettings} from '@/api/customerStatements'
import {hasPermission} from '@/utils/permission'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
const emit=defineEmits(['saved'])
const canWrite=hasPermission('clients:write'),visible=ref(false),ready=ref(false),loading=ref(false),saving=ref(false),error=ref(''),defaultStamp=ref(''),body=ref(),form=ref(),fileInput=ref()
const companies=['广州信实翻译服务有限公司','广州信实翻译服务有限公司深圳分公司','广州信实翻译服务有限公司上海分公司']
const draft=reactive({revision:0,company:companies[0],bank_name:'',account_name:'',account_number:'',stamp_image:null})
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(body)
let original='',sequence=0
const signature=()=>JSON.stringify(draft)
function apply(data){for(const key of Object.keys(draft))draft[key]=key==='company'?(data[key]||companies[0]):data[key];defaultStamp.value=data.default_stamp;original=signature();ready.value=true}
async function open(){const seq=++sequence;visible.value=true;ready.value=false;loading.value=true;error.value='';clearFieldSearch();try{const data=await getStatementSettings();if(seq===sequence)apply(data)}catch(e){if(seq===sequence)error.value=getLocalizedErrorMessage(e,'对账单设置加载失败')}finally{if(seq===sequence)loading.value=false}}
async function chooseStamp(event){const file=event.target.files?.[0];event.target.value='';if(!file)return;if(!['image/png','image/jpeg','image/webp'].includes(file.type)||file.size>2_000_000)return ElMessage.error('请选择2MB以内的PNG、JPG或WebP图片');const seq=sequence;try{const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(file)});if(seq===sequence)draft.stamp_image=data}catch{ElMessage.error('图片读取失败')}}
async function save(){if(saving.value||loading.value||!ready.value||!await form.value?.validate().catch(()=>false))return;saving.value=true;error.value='';try{apply(await saveStatementSettings({...draft}));emit('saved');visible.value=false;ElMessage.success('对账单设置已保存')}catch(e){error.value=getLocalizedErrorMessage(e,'设置保存失败，请重新打开后编辑')}finally{saving.value=false}}
async function close(done){if(saving.value)return;if(ready.value&&signature()!==original){try{await ElMessageBox.confirm('对账单设置有未保存的修改，确定放弃？','关闭设置',{confirmButtonText:'放弃修改',cancelButtonText:'继续编辑'})}catch{return}}sequence++;if(typeof done==='function')done();else visible.value=false}
onBeforeUnmount(()=>sequence++)
</script>
<style scoped>
.stamp-preview{width:150px;height:150px;object-fit:contain;border:1px dashed var(--el-border-color);background:#fff}.stamp-actions{margin:12px 0}small,p{color:var(--el-text-color-secondary)}
:global(.statement-settings-dialog){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}:global(.statement-settings-dialog .el-dialog__header),:global(.statement-settings-dialog .el-dialog__footer){flex:none}:global(.statement-settings-dialog .el-dialog__body){flex:1;min-height:0;overflow:auto}:global(.statement-settings-dialog .el-dialog__footer){border-top:1px solid var(--el-border-color);background:var(--el-fill-color-light)}
</style>
