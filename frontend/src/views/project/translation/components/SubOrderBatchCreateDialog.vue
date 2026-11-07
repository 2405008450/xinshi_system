<template>
  <DraggableFormDialog
    :model-value="modelValue"
    class="suborder-batch-create-dialog project-suborder-dialog"
    title="批量新增子订单"
    width="min(960px, calc(100vw - 32px))"
    top="5vh"
    append-to-body
    @update:model-value="emit('update:modelValue', $event)"
    @closed="reset"
  >
    <el-form-item :label="folderOnly?'母订单号':'本窗口预留的首个子订单号'"><ReadonlyField :model-value="folderOnly?project.orderNo:numberForm.orderNo" source="auto" placeholder="正在占用编号" /></el-form-item>
    <el-alert v-if="numbering.error.value" :title="numbering.error.value" type="error" :closable="false" />
    <el-tabs v-model="mode">
      <el-tab-pane label="UNC共享路径" name="unc">
        <el-form-item label="共享文件夹路径">
          <el-input v-model="uncPath" placeholder="请输入企业 UNC 共享文件夹路径" clearable @keyup.enter="readUncFolder" />
        </el-form-item>
        <el-alert type="info" :closable="false" show-icon title="保留所选根目录作为母订单，下面三层目录及其文件生成一至四级子订单，保存完整路径。" />
        <el-alert v-if="uncError" :title="uncError" type="error" :closable="false" show-icon />
        <div class="local-file-actions">
          <el-button :loading="uncLoading" :disabled="!uncPath.trim()" @click="readUncFolder">读取共享文件夹</el-button>
          <el-button v-if="!importTree" :disabled="!uncRows.length" @click="selectedUncIds=uncRows.filter(row=>row.status==='create').map(row=>row.id)">全选可用文件</el-button>
          <el-button v-if="!importTree" :disabled="!selectedUncIds.length" @click="selectedUncIds=[]">清空选择</el-button>
        </div>
        <div v-if="importTree && uncFolders.length" class="import-summary"><el-tag>{{ uncFolders.length }} 个文件夹</el-tag><el-tag>{{ uncFolders.reduce((n,row)=>n+row.files.length,0) }} 个文件</el-tag><el-tag>生成 {{ treeOrderCount }} 个子订单</el-tag></div>
        <div v-else class="import-summary"><el-tag>共 {{ uncRows.length }} 个文件</el-tag><el-tag type="success">已选 {{ selectedUncIds.length }} 个</el-tag></div>
        <el-checkbox v-if="!folderOnly" v-model="importTree">按文件夹层级导入（根目录作为母订单）</el-checkbox>
        <el-table v-if="!importTree" :data="uncRows" border size="small" max-height="320" empty-text="请先读取 UNC 共享文件夹">
          <el-table-column label="选择" width="64"><template #default="{row}"><el-checkbox :model-value="selectedUncIds.includes(row.id)" :disabled="row.status!=='create'" :aria-label="`选择${row.name}`" @change="checked=>toggleUncFile(row.id,checked)" /></template></el-table-column>
          <el-table-column prop="name" label="文件名称" min-width="260" show-overflow-tooltip />
          <el-table-column label="状态" width="92"><template #default="{row}"><el-tag :type="previewTagType(row.status)" size="small">{{ previewStatusLabel(row.status) }}</el-tag></template></el-table-column>
          <el-table-column prop="reason" label="说明" min-width="200"><template #default="{row}">{{ row.reason || '-' }}</template></el-table-column>
        </el-table>
      </el-tab-pane>
      <el-tab-pane :label="folderOnly?'读取本地文件夹':'读取本地文件'" name="localfiles">
        <el-alert type="info" :closable="false" show-icon title="多选文件可逐文件创建订单；选择文件夹则按目录层级导入，根目录为母订单。最多三层子文件夹及其文件，不上传正文。" />
        <div class="local-file-actions">
          <el-button v-if="!folderOnly" @click="localFileInput.click()">选择本地文件（可多选）</el-button>
          <el-button @click="chooseLocalFolder">选择本地文件夹</el-button>
          <input ref="localFileInput" type="file" multiple hidden aria-label="选择本地文件" @change="readLocalFiles" />
          <input ref="localFolderInput" type="file" multiple webkitdirectory hidden aria-label="选择本地文件夹" @change="readLocalFiles" />
          <el-button v-if="!localFolders.length" :disabled="!localRows.length" @click="selectedLocalIds=localRows.filter(row=>row.status==='create').map(row=>row.id)">全选可用文件</el-button>
          <el-button v-if="!localFolders.length" :disabled="!selectedLocalIds.length" @click="selectedLocalIds=[]">清空选择</el-button>
        </div>
        <p class="local-file-help">选择文件夹时，系统窗口只显示文件夹，不显示其中的文件。选定文件夹后，点击“上传”或“选择文件夹”，文件名会显示在下方列表中。“全选可用文件”会勾选下方所有可创建子订单的文件。</p>
        <div v-if="localFolders.length" class="import-summary"><el-tag>{{ localFolders.length }} 个文件夹</el-tag><el-tag>{{ localFolders.reduce((n,row)=>n+row.files.length,0) }} 个文件</el-tag><el-tag>生成 {{ treeOrderCount }} 个子订单</el-tag></div>
        <div v-else class="import-summary"><el-tag>共 {{ localRows.length }} 个文件</el-tag><el-tag type="success">已选 {{ selectedLocalIds.length }} 个</el-tag></div>
        <el-form-item v-if="localFolders.length" label="本地根文件夹完整路径"><el-input v-model="localRootPath" placeholder="请粘贴所选根文件夹的完整路径，如 D:\项目\客户资料" /></el-form-item>
        <el-alert v-if="localFolders.length" type="warning" :closable="false" title="浏览器只提供相对路径，请填写完整根路径。导入后，母订单项目名称调整为所选根文件夹名称。" />
        <el-table v-if="!localFolders.length" :data="localRows" border size="small" max-height="320" empty-text="请先选择本地文件或文件夹">
          <el-table-column label="选择" width="64"><template #default="{row}"><el-checkbox :model-value="selectedLocalIds.includes(row.id)" :disabled="row.status!=='create'" :aria-label="`选择${row.name}`" @change="checked=>toggleLocalFile(row.id,checked)" /></template></el-table-column>
          <el-table-column prop="name" label="文件名称" min-width="260" show-overflow-tooltip />
          <el-table-column label="状态" width="92"><template #default="{row}"><el-tag :type="previewTagType(row.status)" size="small">{{ previewStatusLabel(row.status) }}</el-tag></template></el-table-column>
          <el-table-column prop="reason" label="说明" min-width="200"><template #default="{row}">{{ row.reason || '-' }}</template></el-table-column>
        </el-table>
      </el-tab-pane>
      <el-tab-pane v-if="!folderOnly" label="按数量生成" name="quantity">
        <AppForm label-position="top">
          <el-row :gutter="16">
            <el-col :xs="24" :md="12"><el-form-item label="生成数量"><el-input-number v-model="form.count" :min="1" :max="500" style="width:100%" /></el-form-item></el-col>
            <el-col :xs="24" :md="12"><el-form-item label="起始序号"><el-input-number v-model="form.startIndex" :min="1" style="width:100%" /></el-form-item></el-col>
          </el-row>
          <el-form-item label="扩展名"><el-input v-model="form.fileExtension" placeholder="如 .docx、.pdf，每条订单对应一个文件" /></el-form-item>
          <el-form-item label="文件名称前缀"><el-input v-model="form.subProjectNamePrefix" maxlength="220" placeholder="留空则以母项目文件名为前缀，序号放在扩展名前" /></el-form-item>
          <el-alert type="info" :closable="false" show-icon :title="`将生成 ${quantityNames.length} 个子订单，文件名称示例：${quantityNames.slice(0, 3).join('、')}`" />
        </AppForm>
      </el-tab-pane>

      <el-tab-pane v-if="!folderOnly" label="按文件名导入" name="filenames">
        <el-alert type="info" :closable="false" show-icon title="选择 TXT 后内容会填入文本框；也可以直接粘贴文件名，每行一个。确认预览后才会创建子订单。" />
        <el-upload
          v-model:file-list="fileList"
          class="filename-upload"
          :auto-upload="false"
          :limit="1"
          accept=".txt,text/plain"
          :on-change="handleFileChange"
          :on-remove="handleFileRemove"
        >
          <el-button>选择 TXT 文件</el-button>
          <template #tip><div class="el-upload__tip">支持 UTF-8、UTF-16LE、GBK，文件不超过 1MB。</div></template>
        </el-upload>
        <el-input
          v-model="filenameText"
          type="textarea"
          :rows="9"
          resize="vertical"
          placeholder="示例：&#10;合同正文.docx&#10;附件一.xlsx&#10;客户说明.pdf"
        />
        <div class="import-summary">
          <el-tag>共 {{ previewRows.length }} 条</el-tag>
          <el-tag type="success">将新增 {{ previewSummary.create }}</el-tag>
          <el-tag type="warning">重复 {{ previewSummary.duplicate }}</el-tag>
          <el-tag type="danger">错误 {{ previewSummary.error }}</el-tag>
          <span v-if="previewRows.length > 100">仅展示前 100 条，提交时处理全部有效内容。</span>
        </div>
        <el-table v-if="previewRows.length" :data="previewRows.slice(0, 100)" border size="small" max-height="320">
          <el-table-column prop="lineNumber" label="行号" width="72" />
          <el-table-column label="状态" width="92">
            <template #default="{ row }"><el-tag :type="previewTagType(row.status)" size="small">{{ previewStatusLabel(row.status) }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="name" label="文件名称" min-width="300" show-overflow-tooltip />
          <el-table-column prop="reason" label="说明" min-width="220"><template #default="{ row }">{{ row.reason || '-' }}</template></el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <el-alert v-if="emptyFolders.length" type="warning" :closable="false" :title="`发现${emptyFolders.length}个空文件夹：不生成订单，确认导入后记录路径、操作人和时间。`" />
    <el-alert v-if="localFolders.length && !folderDetectionComplete && mode==='localfiles'" type="warning" :closable="false" title="兼容选择模式只能读取文件，无法检测空文件夹；本次导入记录会标明这一情况。" />
    <el-table v-if="treeEntries.length" :data="treeRows" border size="small" max-height="380">
      <el-table-column label="层级" width="110"><template #default="{row}">{{ row.level===0?'母订单':row.level+'级子订单' }}</template></el-table-column>
      <el-table-column label="项目名称" min-width="250"><template #default="{row}"><span :style="{paddingLeft:row.level*16+'px'}">{{ row.name }}</span></template></el-table-column>
      <el-table-column prop="kind" label="类型" width="90" />
      <el-table-column prop="path" label="完整路径" min-width="380" />
    </el-table>
    <template v-if="!treeEntries.length && !folderOnly">
    <el-divider content-position="left">批量公共字段</el-divider>
    <AppForm label-position="top">
      <el-row :gutter="16">
        <el-col :xs="24" :md="12"><el-form-item label="状态"><el-select v-model="form.status" clearable style="width:100%"><el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col>
        <el-col :xs="24" :md="12"><el-form-item label="优先级"><el-select v-model="form.priority" clearable style="width:100%"><el-option v-for="item in priorityOptions" :key="item" :label="item" :value="item" /></el-select></el-form-item></el-col>
      </el-row>
      <el-row :gutter="16">
        <el-col :xs="24" :md="12"><el-form-item label="文本类型"><el-input v-model="form.fileTypeSecondary" /></el-form-item></el-col>
        <el-col :xs="24" :md="12"><el-form-item label="翻译方向"><LanguagePairSelect v-model="form.languagePair" :show-hint="false" /></el-form-item></el-col>
      </el-row>
      <el-row :gutter="16">
        <el-col :xs="24" :md="12"><el-form-item label="客户交稿时间"><el-date-picker v-model="form.customerDeadlineTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width:100%" format="YYYY-MM-DD HH:mm" time-format="HH:mm" :show-now="true" :show-confirm="true" :show-footer="true" /></el-form-item></el-col>
      </el-row>
      <el-row :gutter="16">
        <el-col :xs="24" :md="12"><el-form-item label="发客户时间"><el-date-picker v-model="form.sentToClientTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width:100%" format="YYYY-MM-DD HH:mm" time-format="HH:mm" :show-now="true" :show-confirm="true" :show-footer="true" /></el-form-item></el-col>
        <el-col :xs="24" :md="12"><el-form-item label="译员 ID"><el-input v-model="form.translatorId" /></el-form-item></el-col>
      </el-row>
    </AppForm>

    </template>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="submitting" :disabled="!canSubmit" @click="submit">
        {{ treeEntries.length ? `按目录导入 ${treeOrderCount} 单` : mode !== 'quantity' ? `确认导入 ${previewSummary.create} 条` : `批量创建 ${quantityNames.length} 条` }}
      </el-button>
    </template>
  </DraggableFormDialog>
</template>

<script setup>
import { localSubOrderFiles,localFolderEntries,folderOrderPreview,enumerateFolderHandle } from '@/utils/localSubOrderFiles'
import { translationFileNameError, translationFileExtension } from '@/utils/translationFileName'
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { createSubOrdersBulk, inspectSharedSubOrderFolder,inspectSharedSubOrderTree,importSubOrderFolders } from '@/api/subOrders'
import LanguagePairSelect from '@/components/LanguagePairSelect.vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import { createEmptyWordCountMatrix } from '@/utils/wordCountMatrix'
import { getLocalizedErrorMessage } from '@/utils/errorMessages'
import ReadonlyField from '@/components/common/ReadonlyField.vue'
import {useBusinessNumber} from '@/composables/useBusinessNumber'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  project: { type: Object, default: () => ({}) },
  existingNames: { type: Array, default: () => [] },
  folderOnly:Boolean,
  initialMode: { type: String, default: 'quantity' },
})
const emit = defineEmits(['update:modelValue', 'created'])
const numberForm=reactive({orderNo:''})
const numbering=useBusinessNumber({model:()=>numberForm,kind:()=>'translation_suborder',field:()=>'orderNo',active:()=>props.modelValue&&!!props.project.id,parent:()=>props.project.id,date:()=>null})
const statusOptions = [
  ['初步咨询', 'initial_consultation'],
  ['简单需求', 'simple_requirement'], ['原文件+简单需求', 'source_file_simple_requirement'],
  ['待确认', 'pending_confirmation'], ['已确认', 'confirmed'], ['已整理', 'organized'],
  ['已排译员', 'translator_assigned'], ['已发译员', 'sent_to_translator'], ['译员发回', 'translator_returned'],
  ['已专检', 'special_checked'], ['已排版', 'typeset'], ['专检排版完成', 'special_checked_typeset'], ['已审核', 'reviewed'],
  ['已发客户', 'sent_to_client'], ['客户反馈', 'client_feedback'], ['反馈后发客户', 'feedback_sent_to_client'],
  ['已取消', 'cancelled'], ['部分取消', 'partially_cancelled'], ['已暂停', 'paused'],
].map(([label, value]) => ({ label, value }))
const priorityOptions = ['低', '中', '高', '紧急']
const mode = ref('quantity')
const filenameText = ref('')
const fileList = ref([])
const submitting = ref(false)
const uncPath = ref('')
const inspectedUncPath = ref('')
const uncRows = ref([])
const selectedUncIds = ref([])
const uncError = ref('')
const uncLoading = ref(false)
let uncRequest = 0
let uncController = null
const clearUncListing = () => {
  uncRequest += 1
  uncController?.abort()
  uncLoading.value = false
  uncRows.value = []
  uncFolders.value = []
  selectedUncIds.value = []
  inspectedUncPath.value = ''
  uncError.value = ''
}
const toggleUncFile = (id, checked) => {
  selectedUncIds.value = checked ? [...new Set([...selectedUncIds.value, id])] : selectedUncIds.value.filter(value => value !== id)
}
const readUncFolder = async () => {
  clearUncListing()
  if (!uncPath.value.trim()) return
  const request = uncRequest
  uncController = new AbortController()
  uncLoading.value = true
  try {
    const tree=await inspectSharedSubOrderTree(uncPath.value.trim(),{signal:uncController.signal})
    if(request!==uncRequest)return
    uncFolders.value=tree.folderEntries||[]
    inspectedUncPath.value=tree.storagePath
    const root=uncFolders.value.find(row=>!row.relativePath.includes('/'))
    uncRows.value=localSubOrderFiles((root?.files||[]).map(name=>({name})),props.existingNames)
    selectedUncIds.value=uncRows.value.filter(row=>row.status==='create').map(row=>row.id)
  } catch (error) {
    if (request === uncRequest) uncError.value = getLocalizedErrorMessage(error, '读取共享文件夹失败')
  } finally {
    if (request === uncRequest) uncLoading.value = false
  }
}
watch(uncPath, clearUncListing, { flush: 'sync' })
onBeforeUnmount(clearUncListing)
const localFileInput = ref(null)
const localFolderInput = ref(null)
const folderDetectionComplete=ref(true)
const chooseLocalFolder=async()=>{
 if(!window.showDirectoryPicker){folderDetectionComplete.value=false;ElMessage.warning('当前浏览器使用兼容文件夹选择，无法识别空文件夹；完整记录空目录请使用本机Chrome/Edge的localhost或HTTPS入口，或使用UNC共享路径');localFolderInput.value.click();return}
 try{
  const handle=await window.showDirectoryPicker({mode:'read'})
  const entries=await enumerateFolderHandle(handle)
  folderDetectionComplete.value=true;localFolders.value=entries;localRootPath.value='';localRows.value=[];selectedLocalIds.value=[]
 }catch(error){if(error.name!=='AbortError')ElMessage.error(error.message||'读取文件夹失败')}
}
const localFolders=ref([])
const localRootPath=ref('')
const uncFolders=ref([])
const importTree=ref(true)
const treeEntries=computed(()=>mode.value==='localfiles'?localFolders.value:mode.value==='unc'&&importTree.value?uncFolders.value:[])
const treeRows=computed(()=>folderOrderPreview(treeEntries.value,mode.value==='localfiles'?localRootPath.value:inspectedUncPath.value))
const treeOrderCount=computed(()=>treeRows.value.filter(row=>row.level>0&&!row.empty).length)
const emptyFolders=computed(()=>treeRows.value.filter(row=>row.empty))
const localRows = ref([])
const selectedLocalIds = ref([])
const toggleLocalFile = (id, checked) => {
  selectedLocalIds.value = checked ? [...new Set([...selectedLocalIds.value, id])] : selectedLocalIds.value.filter(value => value !== id)
}
const readLocalFiles = (event) => {
  try {
    const directory=Array.from(event.target.files||[]).some(file=>file.webkitRelativePath)
    folderDetectionComplete.value=!directory
    localFolders.value=directory?localFolderEntries(event.target.files):[]
    localRootPath.value=''
    const rows = directory?[]:localSubOrderFiles(event.target.files, props.existingNames)
    localRows.value = rows
    selectedLocalIds.value = rows.filter(row => row.status === 'create').map(row => row.id)
    if (!rows.length && !localFolders.value.length) ElMessage.info('所选文件夹第一层没有可读取的文件')
  } catch (error) {
    localFolders.value=[];localRows.value=[];selectedLocalIds.value=[]
    ElMessage.error(error.message || '读取本地文件失败')
  } finally {
    event.target.value = ''
  }
}

const createForm = () => ({
  fileExtension: translationFileExtension(props.project.sourceFileName || props.project.projectName),
  count: 1,
  startIndex: 1,
  subProjectNamePrefix: props.project.projectName ? `${props.project.projectName}-子订单` : '',
  fileTypeSecondary: props.project.fileTypeSecondary || '',
  languagePair: props.project.languagePair || '',
  priority: props.project.priority || '',
  wordCountMatrix: createEmptyWordCountMatrix(),
  customerDeadlineTime: props.project.customerDeadlineTime || '',
  sentToClientTime: props.project.sentToClientTime || '',
  clientFeedback: props.project.clientFeedback || '',
  translatorId: props.project.translatorId || '',
  translatorAssignmentTime: props.project.translatorAssignmentTime || '',
  status: props.project.projectStatus || props.project.status || 'pending_confirmation',
  translatorDeliveryProgress: props.project.translatorDeliveryProgress || '',
  preReviewQcProgress: props.project.preReviewQcProgress || '',
  reviewProgress: props.project.reviewProgress || '',
  review1Progress: props.project.review1Progress || '',
  review2Progress: props.project.review2Progress || '',
  postReviewQcProgress: props.project.postReviewQcProgress || '',
  layoutProgress: props.project.layoutProgress || '',
  consolidationProgress: props.project.consolidationProgress || '',
  networkFilePath: props.project.networkFilePath || '',
  remarks: '',
})
const form = reactive(createForm())
const normalizeName = (value) => String(value || '').trim().toLocaleLowerCase()

const quantityNames = computed(() => {
  const source=props.project.sourceFileName || props.project.projectName || ''
  const suffix=translationFileExtension(source)
  const stem=suffix ? source.slice(0,-suffix.length) : source
  const prefix = form.subProjectNamePrefix.trim() || (stem ? `${stem}-子订单` : '子订单')
  const extension=form.fileExtension.trim().replace(/^\.?/,'.')
  return Array.from({ length: Number(form.count) || 0 }, (_, offset) => `${prefix}${String(Number(form.startIndex) + offset).padStart(2, '0')}${extension}`)
})

const previewRows = computed(() => {
  if (mode.value === 'unc') return uncRows.value.filter(row => selectedUncIds.value.includes(row.id))
  if (mode.value === 'localfiles') return localRows.value.filter(row => selectedLocalIds.value.includes(row.id))
  const existing = new Set(props.existingNames.map(normalizeName).filter(Boolean))
  const seen = new Set()
  let contentIndex = 0
  return filenameText.value.split(/\r\n|\n|\r/).reduce((rows, rawName, index) => {
    const name = String(rawName || '').replace(/^\ufeff/, '').trim()
    if (!name) return rows
    contentIndex += 1
    const key = normalizeName(name)
    let status = 'create'
    let reason = ''
    if (contentIndex > 500) {
      status = 'error'; reason = '单次最多导入 500 条'
    } else if (translationFileNameError(name)) {
      status = 'error'; reason = translationFileNameError(name)
    } else if (existing.has(key)) {
      status = 'duplicate'; reason = '当前母订单已存在同名子订单'
    } else if (seen.has(key)) {
      status = 'duplicate'; reason = '本次导入内容中文件名称重复'
    }
    if (status === 'create') seen.add(key)
    rows.push({ lineNumber: index + 1, name, status, reason })
    return rows
  }, [])
})
const previewSummary = computed(() => previewRows.value.reduce((summary, row) => {
  summary[row.status] += 1
  return summary
}, { create: 0, duplicate: 0, error: 0 }))
const canSubmit = computed(() => {
  if (submitting.value || (!props.project.id && (!props.folderOnly || !props.project.orderNo))) return false
  if(props.folderOnly && !treeEntries.value.length)return false
  if(treeEntries.value.length)return treeRows.value.length>0&&(mode.value!=='localfiles'||!!localRootPath.value.trim())
  if (mode.value === 'unc' && (!inspectedUncPath.value || uncLoading.value)) return false
  if (mode.value === 'quantity') return quantityNames.value.length > 0 && quantityNames.value.every((name) => !translationFileNameError(name))
  return previewSummary.value.create > 0 && previewSummary.value.error === 0
})

const decodeTextFile = async (file) => {
  if (!file.name.toLocaleLowerCase().endsWith('.txt')) throw new Error('请选择 TXT 文件')
  if (file.size > 1024 * 1024) throw new Error('TXT 文件不能超过 1MB')
  const buffer = await file.arrayBuffer()
  const bytes = new Uint8Array(buffer)
  if (bytes[0] === 0xff && bytes[1] === 0xfe) return new TextDecoder('utf-16le').decode(bytes.subarray(2))
  if (bytes[0] === 0xef && bytes[1] === 0xbb && bytes[2] === 0xbf) return new TextDecoder('utf-8').decode(bytes.subarray(3))
  try {
    return new TextDecoder('utf-8', { fatal: true }).decode(bytes)
  } catch {
    return new TextDecoder('gbk').decode(bytes)
  }
}
const handleFileChange = async (uploadFile) => {
  try {
    filenameText.value = await decodeTextFile(uploadFile.raw)
  } catch (error) {
    fileList.value = []
    ElMessage.error('读取 TXT 文件失败，请确认文件内容和编码格式')
  }
}
const handleFileRemove = () => { fileList.value = [] }
const previewTagType = (status) => ({ create: 'success', duplicate: 'warning', error: 'danger' }[status] || 'info')
const previewStatusLabel = (status) => ({ create: '新增', duplicate: '跳过', error: '错误' }[status] || status)
const progressValue = (value) => value === '' || value === null || value === undefined ? null : String(value)

const buildDefaults = () => ({
  fileTypeSecondary: form.fileTypeSecondary || null,
  languagePair: form.languagePair || null,
  priority: form.priority || null,
  wordCountMatrix: form.wordCountMatrix,
  customerDeadlineTime: form.customerDeadlineTime || null,
  sentToClientTime: form.sentToClientTime || null,
  clientFeedback: form.clientFeedback || null,
  translatorId: form.translatorId || null,
  translatorAssignmentTime: form.translatorAssignmentTime || null,
  status: form.status || 'pending_confirmation',
  translatorDeliveryProgress: progressValue(form.translatorDeliveryProgress),
  preReviewQcProgress: progressValue(form.preReviewQcProgress),
  reviewProgress: progressValue(form.reviewProgress),
  review1Progress: progressValue(form.review1Progress),
  review2Progress: progressValue(form.review2Progress),
  postReviewQcProgress: progressValue(form.postReviewQcProgress),
  layoutProgress: progressValue(form.layoutProgress),
  consolidationProgress: progressValue(form.consolidationProgress),
  networkFilePath: ['localfiles', 'unc'].includes(mode.value) ? null : form.networkFilePath || null,
  remarks: form.remarks || null,
})
const submit = async () => {
  if(!await numbering.ensure()){ElMessage.error(numbering.error.value||'请等待订单号占用完成');return}
  if (!canSubmit.value) return
  if (submitting.value) return
  submitting.value = true
  try {
    if(treeEntries.value.length){
      const result=await importSubOrderFolders({parentProjectId:props.project.id||null,orderNo:props.folderOnly?props.project.orderNo:null,sourceKind:mode.value==='unc'?'unc':'local',rootPath:mode.value==='unc'?inspectedUncPath.value:localRootPath.value.trim(),entries:treeEntries.value,emptyDetectionComplete:mode.value==='unc'||folderDetectionComplete.value},{headers:numbering.headers()})
      ElMessage.success(`按目录导入完成：新增${result.createdCount}单，跳过${result.skippedCount}项；空文件夹已记录`)
      emit('created',result);emit('update:modelValue',false);return
    }
    const names = mode.value === 'quantity'
      ? quantityNames.value
      : previewRows.value.filter((row) => row.status !== 'error').map((row) => row.name)
    const result = await createSubOrdersBulk({ parentProjectId: props.project.id, sourceFolderPath: mode.value === 'unc' ? inspectedUncPath.value : null, subProjectNames: names, defaults: buildDefaults() },{headers:numbering.headers()})
    ElMessage.success(`批量创建完成：新增 ${result.createdCount} 条，跳过 ${result.skippedCount} 条`)
    if (result.skippedCount) {
      const reasons = result.skipped.slice(0, 3).map((item) => `${item.name}：${item.reason}`).join('；')
      ElMessage.warning(`已跳过重复文件名称：${reasons}${result.skippedCount > 3 ? '；更多结果未展开' : ''}`)
    }
    emit('created', result)
    emit('update:modelValue', false)
  } catch (error) {
    ElMessage.error(getLocalizedErrorMessage(error, '批量创建子订单失败'))
  } finally {
    submitting.value = false
  }
}
const reset = () => {
  mode.value = props.folderOnly ? (props.initialMode==='unc'?'unc':'localfiles') : ['filenames', 'localfiles', 'unc'].includes(props.initialMode) ? props.initialMode : 'quantity'
  filenameText.value = ''
  fileList.value = []
  localRows.value = []
  localFolders.value=[]
  importTree.value=true
  localRootPath.value=''
  selectedLocalIds.value = []
  clearUncListing()
  uncPath.value = ''
  Object.assign(form, createForm())
}
watch(() => props.modelValue, (visible) => { if (visible) reset() })
</script>

<style scoped>
.local-file-help { color: var(--el-text-color-regular); font-size: 13px; line-height: 1.6; margin: 10px 0; }
.local-file-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
.filename-upload { margin: 14px 0; }
.import-summary { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin: 14px 0 10px; }
.import-summary span { color: var(--el-text-color-secondary); font-size: 12px; }
.word-count-summary { display: flex; align-items: center; justify-content: space-between; width: 100%; min-height: 32px; gap: 8px; padding: 0 10px; border: 1px solid var(--el-border-color); border-radius: 4px; background: var(--el-fill-color-lighter); }
</style>
