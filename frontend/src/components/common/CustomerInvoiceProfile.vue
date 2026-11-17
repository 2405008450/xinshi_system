<template>
  <section class="customer-invoice-profile" v-loading="loading">
    <div class="invoice-profile-heading">
      <button v-if="collapsible" type="button" class="invoice-profile-toggle"
        :aria-expanded="expanded" :aria-controls="detailsId" @click="expanded=!expanded">
        <el-icon aria-hidden="true"><CaretBottom v-if="expanded" /><CaretRight v-else /></el-icon>
        {{ profileTitle }}
      </button>
      <strong v-else>{{ profileTitle }}</strong>
      <el-button v-if="clientId&&canWrite" link type="primary" :disabled="loading||!!error" @click="edit">{{ subClientId ? '编辑子客户开票信息' : '编辑客户开票信息' }}</el-button>
      <el-button v-if="clientId" link @click="load">刷新</el-button>
    </div>
    <p v-if="!clientId">保存客户后可维护开票资料。</p>
    <template v-else>
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <div v-show="!collapsible||expanded" :id="detailsId">
        <template v-if="data&&!error">
          <p>默认发票类型：{{invoiceTypeLabels[data.invoice_type]||'电子普票'}}；开票主体：{{data.subject?.name||'待选择'}}</p>
          <InvoicePartyDetails :party="data.party" />
          <template v-if="data.subject">
            <strong>开票主体资料 · {{data.subject.name}}</strong>
            <InvoicePartyDetails :party="data.subject.party" />
            <small>主体信息在「财务管理 → 设置 → 发票设置」维护，此处同步显示。</small>
          </template>
        </template>
      </div>
    </template>
    <DraggableFormDialog v-model="visible" class="invoice-party-editor" width="min(900px, calc(100vw - 32px))" top="5vh" append-to-body destroy-on-close :close-on-click-modal="false" :before-close="beforeClose">
      <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword"  :title="profileTitle" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
      <div ref="body"><AppForm ref="formRef" :model="form" label-position="top" :disabled="saving"><el-form-item label="发票类型"><el-select v-model="form.invoice_type" ><el-option v-for="(label,key) in invoiceTypeLabels" :key="key" :value="key" :label="label" /></el-select></el-form-item><el-form-item label="开票主体"><el-select v-model="form.subject_key" clearable placeholder="请选择开票主体" style="width:100%"><el-option v-for="item in subjects" :key="item.key" :label="item.name" :value="item.key" /></el-select></el-form-item><InvoicePartyFields v-model="form.party" /></AppForm><el-alert v-if="saveError" :title="saveError" type="error" :closable="false" /></div>
      <template #footer><el-button :disabled="saving" @click="close">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存开票信息</el-button></template>
    </DraggableFormDialog>
  </section>
</template>
<script setup>
import {ref,reactive,watch,onMounted,onBeforeUnmount,useId,computed} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import {CaretBottom,CaretRight} from '@element-plus/icons-vue'
import {getLocalizedErrorMessage} from '@/utils/errorMessages'
import {useDialogFieldSearch} from '@/composables/useDialogFieldSearch'
import {getClientInvoiceProfile,saveClientInvoiceProfile,getInvoiceSubjects,invoiceTypeLabels,emptyInvoiceParty,connectInvoiceParties,notifyInvoiceParties,invoicePartiesEvent} from '@/api/invoiceParties'
import DraggableFormDialog from './DraggableFormDialog.vue'
import AppForm from './AppForm.vue'
import DialogFieldSearchHeader from './DialogFieldSearchHeader.vue'
import InvoicePartyFields from './InvoicePartyFields.vue'
import InvoicePartyDetails from './InvoicePartyDetails.vue'
const props=defineProps({clientId:{type:[String,Number],default:''},subClientId:String,canWrite:Boolean,collapsible:Boolean,defaultCollapsed:Boolean})
const profileTitle = computed(() => props.subClientId ? '子客户开票资料' : '客户开（专）票信息')
const expanded=ref(!props.defaultCollapsed),detailsId=useId()
const data=ref(null),subjects=ref([]),loading=ref(false),error=ref(''),visible=ref(false),saving=ref(false),saveError=ref(''),formRef=ref(),body=ref()
const form=reactive({party:emptyInvoiceParty(),subject_key:null,invoice_type:'electronic_normal'})
const {fieldSearchRef,fieldSearchKeyword,fetchFieldSuggestions,locateDialogField,clearFieldSearch}=useDialogFieldSearch(body)
const source=`client-invoice-${Math.random().toString(36).slice(2)}`
let seq=0,alive=true,revision=0,original=''
const signature=()=>JSON.stringify(form)
async function load(){const current=++seq;if(!props.clientId){data.value=null;return}loading.value=true;error.value='';try{const value=await getClientInvoiceProfile(props.clientId,props.subClientId);if(alive&&current===seq)data.value=value}catch(e){if(alive&&current===seq)error.value=getLocalizedErrorMessage(e,'客户开票信息加载失败')}finally{if(current===seq)loading.value=false}}
async function edit(){saveError.value='';try{subjects.value=(await getInvoiceSubjects()).items||[];const fresh=await getClientInvoiceProfile(props.clientId,props.subClientId);data.value=fresh;revision=fresh.revision;Object.assign(form,{party:{...emptyInvoiceParty(),...fresh.party},subject_key:fresh.subject_key,invoice_type:fresh.invoice_type||'electronic_normal'});original=signature();clearFieldSearch();visible.value=true}catch(e){ElMessage.error(getLocalizedErrorMessage(e,'开票信息加载失败'))}}
async function save(){if(saving.value||!await formRef.value?.validate().catch(()=>false))return;saving.value=true;try{data.value=await saveClientInvoiceProfile(props.clientId,{revision,party:form.party,subject_key:form.subject_key||null,invoice_type:form.invoice_type},props.subClientId);visible.value=false;original=signature();notifyInvoiceParties({kind:'client',clientId:String(props.clientId),source});ElMessage.success('客户开票信息已保存，与发票窗口同步')}catch(e){saveError.value=getLocalizedErrorMessage(e,'开票信息保存失败')}finally{saving.value=false}}
async function beforeClose(done){if(saving.value)return;if(signature()!==original){try{await ElMessageBox.confirm('开票资料有未保存修改，是否放弃？','关闭客户开票信息',{type:'warning'})}catch{return}}done()}
function close(){void beforeClose(()=>visible.value=false)}
function changed(event){if(event.detail?.source===source)return;if(event.detail?.kind==='subject'||String(event.detail?.clientId)===String(props.clientId))void load()}
watch(()=>[props.clientId,props.subClientId],()=>{visible.value=false;void load()},{immediate:true})
onMounted(()=>{connectInvoiceParties();window.addEventListener(invoicePartiesEvent,changed)})
onBeforeUnmount(()=>{alive=false;seq++;window.removeEventListener(invoicePartiesEvent,changed)})
</script>
<style scoped>
.invoice-profile-toggle{display:inline-flex;align-items:center;gap:4px;padding:0;border:0;background:none;color:inherit;font:inherit;font-weight:700;cursor:pointer}
.invoice-profile-toggle:hover{color:var(--el-color-primary)}
.invoice-profile-heading{display:flex;align-items:center;gap:12px;flex-wrap:wrap}.customer-invoice-profile p,.customer-invoice-profile small{font-size:12px;color:var(--el-text-color-secondary)}.customer-invoice-profile{margin:12px 0}.customer-invoice-profile p{overflow-wrap:anywhere}:global(.invoice-party-editor){display:flex;flex-direction:column;max-height:90vh;overflow:hidden}:global(.invoice-party-editor>.el-dialog__header),:global(.invoice-party-editor>.el-dialog__footer){flex:none}:global(.invoice-party-editor>.el-dialog__body){flex:1;min-height:0;overflow-y:auto}
</style>
