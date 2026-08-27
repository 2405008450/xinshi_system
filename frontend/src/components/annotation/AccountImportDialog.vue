<template>
  <el-dialog
    :model-value="modelValue"
    title="导入项目账号表"
    width="min(1120px, calc(100vw - 32px))"
    top="5vh"
    class="account-import-dialog"
    append-to-body
    @update:model-value="emit('update:modelValue', $event)"
    @closed="reset"
  >
    <el-alert type="info" :closable="false" show-icon title="请先从腾讯文档导出 XLSX。系统会识别说明行、双表头和重复列名，确认预览后才写入数据。" />

    <el-form label-position="top" class="defaults-grid">
      <el-form-item label="XLSX 文件*">
        <el-upload :auto-upload="false" :limit="1" accept=".xlsx" :on-change="selectFile" :on-remove="removeFile">
          <el-button>选择文件</el-button>
        </el-upload>
      </el-form-item>
      <el-form-item label="平台*">
        <el-select v-model="defaults.platformId" filterable><el-option v-for="item in platforms" :key="item.id" :label="item.platformName || item.platformUrl" :value="item.id" /></el-select>
      </el-form-item>
      <el-form-item label="语言方向*">
        <el-select v-model="defaults.languageItemIds" multiple collapse-tags filterable><el-option v-for="item in languageItems" :key="item.id" :label="item.display" :value="item.id" /></el-select>
      </el-form-item>
      <el-form-item label="负责人">
        <el-select v-model="defaults.ownerId" clearable filterable><el-option v-for="item in users" :key="item.id" :label="item.fullName || item.username" :value="item.id" /></el-select>
      </el-form-item>
      <el-form-item label="账号来源">
        <el-select v-model="defaults.accountSource"><el-option label="客户提供" value="client_provided" /><el-option label="自行注册" value="self_registered" /><el-option label="标注员自有" value="annotator_owned" /></el-select>
      </el-form-item>
    </el-form>

    <div class="toolbar">
      <el-button type="primary" :loading="previewing" :disabled="!canPreview" @click="preview(false)">生成预览</el-button>
      <template v-if="previewData">
        <el-select v-model="sheetName" style="width:220px" @change="preview(false)"><el-option v-for="name in previewData.sheets" :key="name" :label="name" :value="name" /></el-select>
        <span>表头行</span><el-input-number v-model="headerRow" :min="1" :max="20" controls-position="right" @change="preview(false)" />
        <el-button :loading="previewing" @click="preview(true)">应用映射并重新校验</el-button>
      </template>
    </div>

    <template v-if="previewData">
      <el-divider content-position="left">字段映射</el-divider>
      <el-table :data="mappingRows" border size="small" max-height="300">
        <el-table-column prop="uniqueLabel" label="源表列" min-width="180" />
        <el-table-column label="导入目标" min-width="230">
          <template #default="{ row }">
            <el-select v-model="row.uiTarget" style="width:100%" @change="targetChanged(row)">
              <el-option label="忽略" value="ignore" />
              <el-option label="登录账号" value="login_account" /><el-option label="密码" value="password" />
              <el-option label="账号昵称" value="nickname" /><el-option label="分配人员姓名" value="person_name" /><el-option label="人才性别" value="gender" />
              <el-option-group label="已有项目字段"><el-option v-for="field in previewData.projectFields" :key="field.id" :label="field.fieldLabel" :value="`custom:${field.id}`" /></el-option-group>
              <el-option label="新建项目字段" value="new_custom" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="新字段设置" min-width="440">
          <template #default="{ row }">
            <div v-if="row.target === 'new_custom'" class="new-field">
              <el-input v-model="row.fieldLabel" placeholder="显示名称" />
              <el-input v-model="row.fieldKey" placeholder="英文键，如 quality_status" />
              <el-select v-model="row.dataType"><el-option v-for="item in fieldTypes" :key="item.value" :label="item.label" :value="item.value" /></el-select>
              <el-input v-if="String(row.dataType).includes('select')" v-model="row.optionText" placeholder="选项用英文逗号分隔" />
            </div>
            <span v-else>-</span>
          </template>
        </el-table-column>
      </el-table>

      <el-divider content-position="left">导入预览</el-divider>
      <div class="summary">
        <el-tag>共 {{ previewData.summary.total }} 行</el-tag><el-tag type="success">新增 {{ previewData.summary.create }}</el-tag>
        <el-tag type="warning">更新 {{ previewData.summary.update }}</el-tag><el-tag type="danger">错误 {{ previewData.summary.error }}</el-tag>
        <span v-if="previewData.rows.length > 100">仅展示前 100 行，提交时会处理全部数据。</span>
      </div>
      <el-table :data="previewData.rows.slice(0, 100)" border size="small" max-height="360">
        <el-table-column prop="rowNumber" label="行号" width="70" />
        <el-table-column label="动作" width="90"><template #default="{row}"><el-tag :type="actionType(row.action)" size="small">{{ actionLabel(row.action) }}</el-tag></template></el-table-column>
        <el-table-column label="登录账号" min-width="190"><template #default="{row}">{{ previewValue(row, ['user email','登录账号','登录邮箱']) || '-' }}</template></el-table-column>
        <el-table-column label="人员" min-width="120"><template #default="{row}">{{ previewValue(row, ['所分配人员姓名','标注员','姓名']) || '-' }}</template></el-table-column>
        <el-table-column label="警告/错误" min-width="320"><template #default="{row}"><div class="messages"><span v-for="item in row.warnings" :key="`w${item}`" class="warning">{{ item }}</span><span v-for="item in row.errors" :key="`e${item}`" class="error">{{ item }}</span></div></template></el-table-column>
      </el-table>
    </template>

    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="importing" :disabled="!canImport" @click="submitImport">确认导入</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { importAccounts, previewAccountImport } from '@/api/annotationOps'

const props = defineProps({
  modelValue:{type:Boolean,default:false}, clientId:{type:String,default:''}, projectId:{type:String,default:''},
  platforms:{type:Array,default:()=>[]}, languageItems:{type:Array,default:()=>[]}, users:{type:Array,default:()=>[]},
  defaultLanguageIds:{type:Array,default:()=>[]},
})
const emit=defineEmits(['update:modelValue','imported'])
const file=ref(null),previewData=ref(null),mappingRows=ref([]),sheetName=ref(''),headerRow=ref(1),previewing=ref(false),importing=ref(false)
const defaults=reactive({platformId:'',languageItemIds:[],ownerId:localStorage.getItem('user_id')||'',accountSource:'client_provided'})
const fieldTypes=[['text','文本'],['number','数字'],['date','日期'],['datetime','日期时间'],['boolean','是/否'],['single_select','单选'],['multi_select','多选'],['url','链接']].map(([value,label])=>({value,label}))
const fullDefaults=computed(()=>({clientId:props.clientId,projectId:props.projectId,...defaults}))
const canPreview=computed(()=>Boolean(file.value&&props.clientId&&props.projectId&&defaults.platformId&&defaults.languageItemIds.length))
const canImport=computed(()=>Boolean(previewData.value&&!previewData.value.summary.error&&mappingRows.value.some(item=>item.target==='login_account')&&mappingRows.value.some(item=>item.target==='password')))

watch(()=>props.modelValue,value=>{if(value){defaults.platformId=props.platforms[0]?.id||'';defaults.languageItemIds=[...props.defaultLanguageIds]}})
watch(()=>props.platforms,items=>{if(props.modelValue&&!defaults.platformId)defaults.platformId=items[0]?.id||''})
const selectFile=upload=>{file.value=upload.raw;previewData.value=null}
const removeFile=()=>{file.value=null;previewData.value=null}
const mappingPayload=()=>mappingRows.value.map(({index,target,fieldId,fieldKey,fieldLabel,dataType,options,optionText})=>({index,target,fieldId,fieldKey,fieldLabel,dataType,options:String(optionText||'').trim()?String(optionText).split(',').map(item=>item.trim()).filter(Boolean):(options||[])}))
const initializeMapping=data=>{
  mappingRows.value=data.headers.map(header=>{
    const rule=data.mapping.find(item=>item.index===header.index)||{target:'ignore'}
    const uiTarget=rule.target==='custom'?`custom:${rule.fieldId}`:rule.target
    return {...header,...rule,optionText:(rule.options||[]).map(item=>item.value||item).join(','),uiTarget}
  })
}
const preview=async(useMapping=false)=>{
  if(!canPreview.value)return ElMessage.warning('请选择文件、平台和语言方向')
  previewing.value=true
  try{
    const data=await previewAccountImport(file.value,{defaults:fullDefaults.value,sheetName:sheetName.value||undefined,headerRow:previewData.value?headerRow.value:undefined,mapping:useMapping?mappingPayload():undefined})
    previewData.value=data;sheetName.value=data.sheetName;headerRow.value=data.headerRow;initializeMapping(data)
  }catch(error){ElMessage.error(error.detail||'生成导入预览失败')}finally{previewing.value=false}
}
const targetChanged=row=>{
  if(String(row.uiTarget).startsWith('custom:')){row.target='custom';row.fieldId=row.uiTarget.split(':')[1]}
  else{row.target=row.uiTarget;row.fieldId=null}
}
const submitImport=async()=>{
  importing.value=true
  try{
    const result=await importAccounts(file.value,{defaults:fullDefaults.value,sheetName:sheetName.value,headerRow:headerRow.value,mapping:mappingPayload()})
    const {success,failed,created,updated}=result.summary
    if(failed)downloadErrors(result.results.filter(item=>!item.success))
    ElMessage.success(`导入完成：新增 ${created}，更新 ${updated}，失败 ${failed}`)
    emit('imported',result);emit('update:modelValue',false)
  }catch(error){ElMessage.error(error.detail||'导入失败')}finally{importing.value=false}
}
const downloadErrors=rows=>{
  const csv=['行号,错误',...rows.map(item=>`${item.rowNumber},"${String(item.error||'').replaceAll('"','""')}"`)].join('\r\n')
  const link=document.createElement('a');link.href=URL.createObjectURL(new Blob(['\ufeff',csv],{type:'text/csv'}));link.download='账号导入错误明细.csv';link.click();URL.revokeObjectURL(link.href)
}
const previewValue=(row,labels)=>{for(const [key,value] of Object.entries(row.values||{})){if(labels.some(label=>key.toLowerCase().includes(label.toLowerCase())))return value}return ''}
const actionType=value=>({create:'success',update:'warning',error:'danger'}[value]||'info')
const actionLabel=value=>({create:'新增',update:'更新',error:'错误'}[value]||value)
const reset=()=>{file.value=null;previewData.value=null;mappingRows.value=[];sheetName.value='';headerRow.value=1}
</script>

<style scoped>
.defaults-grid{display:grid;grid-template-columns:repeat(5,minmax(150px,1fr));gap:12px;margin-top:16px}.defaults-grid :deep(.el-form-item){margin-bottom:0}.defaults-grid :deep(.el-select){width:100%}.toolbar,.summary,.new-field{display:flex;align-items:center;gap:8px}.toolbar{margin-top:16px;flex-wrap:wrap}.new-field>*{flex:1}.summary{margin-bottom:10px;flex-wrap:wrap}.summary span{color:var(--el-text-color-secondary);font-size:12px}.messages{display:flex;flex-direction:column}.warning{color:var(--el-color-warning)}.error{color:var(--el-color-danger)}
@media(max-width:900px){.defaults-grid{grid-template-columns:1fr 1fr}.new-field{align-items:stretch;flex-direction:column}}@media(max-width:600px){.defaults-grid{grid-template-columns:1fr}}
</style>

<style>
.account-import-dialog{display:flex;max-height:90vh;overflow:hidden;flex-direction:column}.account-import-dialog .el-dialog__header,.account-import-dialog .el-dialog__footer{flex-shrink:0}.account-import-dialog .el-dialog__body{flex:1;min-height:0;overflow-y:auto}.account-import-dialog .el-dialog__footer{border-top:1px solid var(--el-border-color-lighter);background:var(--el-fill-color-lighter)}
</style>
