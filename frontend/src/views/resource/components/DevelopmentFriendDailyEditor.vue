<template>
  <DraggableFormDialog v-model="visible" width="min(1380px, calc(100vw - 32px))" top="5vh" append-to-body non-modal :modal="false" modal-penetrable :lock-scroll="false" :close-on-click-modal="false" :close-on-press-escape="false" :before-close="beforeClose" class="friend-daily-dialog">
    <template #header><DialogFieldSearchHeader ref="fieldSearchRef" v-model="fieldSearchKeyword" title="群聊好友统计" placeholder="查找账号、语种或人数" :fetch-suggestions="fetchFieldSuggestions" @select="locateDialogField" @clear="clearFieldSearch" /></template>
    <div ref="bodyRef" v-loading="loading" @keydown.ctrl.enter.prevent="save" @keydown.meta.enter.prevent="save">
      <div class="friend-daily-intro"><el-date-picker :model-value="day" value-format="YYYY-MM-DD" format="YYYY年MM月DD日" :clearable="false" :disabled="saving || loading" aria-label="群聊统计日期" @update:model-value="switchDay" /><span>仅填写微信群聊途径的当天新增人数</span><el-button link :disabled="saving || loading" @click="open(day)">重新加载</el-button></div>
      <p class="friend-daily-hint">保存后同步人才概览；修改按差额更新。空白表示未填写，0 表示无新增。同一人同一账号请勿因会多种语言重复计数。</p>
      <el-alert v-if="!options.can_write" title="当前账号可查看统计；修改需要资源开拓代录权限。" type="info" :closable="false" />
      <AppForm ref="formRef" :model="form" :disabled="saving || loading || !options.can_write" class="friend-grid-form">
        <div class="friend-grid-scroll">
          <table class="friend-grid" :style="{ minWidth: `${gridAccounts.length * 60 + 420}px` }"><thead>
            <tr><th rowspan="2" class="friend-language-col">语种 / 方言</th><template v-for="channel in channels" :key="channel.key"><th :colspan="channelAccounts(channel.key).length + 1">{{ channel.label }}加好友人数</th></template><th rowspan="2">合计</th><th v-if="options.can_write" rowspan="2" class="friend-row-action">操作</th></tr>
            <tr><template v-for="channel in channels" :key="channel.key"><th v-for="a in channelAccounts(channel.key)" :key="a.key" :title="a.label">{{ shortName(a.label) }}</th><th class="friend-grid-total">小计</th></template></tr>
          </thead><tbody>
            <tr v-for="(row, index) in form.rows" :key="row.uiId" data-dialog-field-search-group>
              <td class="friend-language-col"><span hidden data-dialog-field-search-group-title>第{{ index + 1 }}行</span><el-form-item label="语种 / 方言" :prop="`rows.${index}.language_value`" :rules="required('请选择语种')"><el-select v-model="row.language_value" filterable allow-create default-first-option placeholder="选择或输入语种" @change="languageChanged(row)"><el-option v-for="l in options.languages" :key="l.id" :label="`${l.label}${l.language_type === 'dialect' ? '（方言）' : ''}`" :value="l.id" /></el-select></el-form-item>
                <template v-if="row.language_value && !knownLanguage(row)?.overview_key"><el-form-item v-if="!knownLanguage(row)" label="类型"><el-select v-model="row.language_type"><el-option label="语种" value="language" /><el-option label="方言" value="dialect" /></el-select></el-form-item><el-form-item label="概览对应语种" :prop="`rows.${index}.overview_key`" :rules="required('请选择概览语种')"><el-select v-model="row.overview_key" filterable placeholder="匹配概览语种"><el-option label="新增概览语种" value="__new__" /><el-option v-for="r in options.overview_rows" :key="r.key" :label="r.label" :value="r.key" /></el-select></el-form-item></template>
              </td>
              <template v-for="channel in channels" :key="channel.key"><td v-for="a in channelAccounts(channel.key)" :key="a.key" class="friend-number-cell"><el-form-item :label="`${channel.label} ${shortName(a.label)} 人数`" :prop="['rows', String(index), 'cells', a.key]" :rules="[{ validator: validateCount, trigger: 'change' }]"><el-input :model-value="row.cells[a.key] == null ? '' : String(row.cells[a.key])" inputmode="numeric" :data-grid-row="index" :data-grid-account="a.key" @update:model-value="row.cells[a.key] = parseFriendCount($event)" @keydown="moveCell($event, index, a.key)" @paste="pasteCells($event, index, a.key)" /></el-form-item></td><td class="friend-grid-total">{{ rowTotal(row, channel.key) }}</td></template>
              <td class="friend-grid-total">{{ rowTotal(row) }}</td><td v-if="options.can_write" class="friend-row-action"><el-button link type="danger" :disabled="saving || loading" :aria-label="`移除第${index + 1}行`" @click="form.rows.splice(index, 1)">移除</el-button></td>
            </tr>
            <tr v-if="!form.rows.length"><td :colspan="gridAccounts.length + 4 + (options.can_write ? 1 : 0)" class="friend-grid-empty">暂无统计，点击“增加语种行”开始填写</td></tr>
          </tbody><tfoot><tr><th class="friend-language-col">当天合计</th><template v-for="channel in channels" :key="channel.key"><td v-for="a in channelAccounts(channel.key)" :key="a.key">{{ columnTotal(a.key) }}</td><td>{{ subtotal(channel.key) }}</td></template><td>{{ subtotal() }}</td><td v-if="options.can_write"></td></tr></tfoot></table>
        </div>
        <div class="friend-grid-toolbar"><el-button v-if="options.can_write" :disabled="saving || loading" @click="addLine">＋ 增加语种行</el-button><span>Tab 横向填写，Enter 向下填写；可粘贴连续账号人数（不含小计）。</span></div>
      </AppForm>
      <el-popover v-if="options.can_write" v-model:visible="accountVisible" trigger="click" placement="top-start" :width="340" popper-class="friend-account-popover"><template #reference><el-button link type="primary">新增微信 / 企微账号</el-button></template>
        <AppForm ref="accountFormRef" :model="newAccount" :rules="{ name: required('请填写账号名') }" label-position="top"><el-form-item label="账号类型"><el-radio-group v-model="newAccount.channel"><el-radio value="wechat">微信</el-radio><el-radio value="enterprise">企微</el-radio></el-radio-group></el-form-item><el-form-item label="账号名" prop="name"><el-input v-model="newAccount.name" maxlength="60" placeholder="例如 HR7" @keyup.enter="createAccount" /></el-form-item></AppForm><p class="friend-daily-hint">同步增加人才概览对应账号列，已有账号不会重复创建。</p><el-button type="primary" :loading="accountSaving" @click="createAccount">新增账号</el-button>
      </el-popover>
      <p class="friend-daily-hint" v-if="updated">最近更新：{{ updated.name }} · {{ formatTime(updated.at) }}</p>
      <el-collapse v-if="audit.length"><el-collapse-item title="查看修改记录"><div v-for="(a, i) in audit" :key="i" class="friend-audit">{{ formatTime(a.at) }} · {{ a.actor }} · 微信 {{ a.totals.wechat }} 人 / 企微 {{ a.totals.enterprise }} 人</div></el-collapse-item></el-collapse>
    </div>
    <template #footer><span class="friend-footer-total">微信 {{ subtotal('wechat') }} 人 · 企微 {{ subtotal('enterprise') }} 人 · 合计 <strong>{{ subtotal('wechat') + subtotal('enterprise') }}</strong> 人</span><el-button :disabled="saving" @click="beforeClose(() => visible = false)">关闭</el-button><el-button v-if="options.can_write" type="primary" :disabled="loading" :loading="saving" @click="save">保存</el-button></template>
  </DraggableFormDialog>
</template>
<script setup>
import { computed, nextTick, onBeforeUnmount, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import DialogFieldSearchHeader from '@/components/common/DialogFieldSearchHeader.vue'
import { useDialogFieldSearch } from '@/composables/useDialogFieldSearch'
import { friendDailyApi as api } from '@/api/resourceFriendDaily'
import { friendRowsToGrid, friendGridToRows, friendCount, parseFriendCount, parseFriendPaste } from '@/utils/resourceFriendGrid'
const props = defineProps({ options: { type: Object, required: true } })
const emit = defineEmits(['saved', 'options-changed'])
const visible = ref(false), loading = ref(false), saving = ref(false), day = ref(''), revision = ref(0), updated = ref(null), audit = ref([])
const form = reactive({ rows: [] }), formRef = ref(), bodyRef = ref(), accountFormRef = ref()
const accountVisible = ref(false), accountSaving = ref(false), newAccount = reactive({ channel: 'enterprise', name: '' })
const channels = [{ key: 'enterprise', label: '企微' }, { key: 'wechat', label: '微信' }]
const { fieldSearchRef, fieldSearchKeyword, fetchFieldSuggestions, locateDialogField, locateDialogFieldByLabel, clearFieldSearch } = useDialogFieldSearch(bodyRef)
let baseline = '', seq = 0, controller, nextId = 0
const required = message => [{ required: true, message, trigger: 'change' }]
const validateCount = (_, value, cb) => cb(value == null || Number.isInteger(value) && value >= 0 && value <= 1000000 ? undefined : new Error('人数须为 0～1000000 的整数'))
const gridAccounts = computed(() => channels.flatMap(ch => props.options.accounts.filter(a => a.channel === ch.key)))
const channelAccounts = channel => gridAccounts.value.filter(a => a.channel === channel)
const shortName = label => label.match(/^HR\d+/i)?.[0] || label.replace(/^(微信|企微)·/, '')
const payloadRows = () => friendGridToRows(form.rows, gridAccounts.value)
const signature = () => JSON.stringify(form.rows.map(({ uiId, ...row }) => row))
const rowTotal = (row, channel) => gridAccounts.value.filter(a => !channel || a.channel === channel).reduce((sum, a) => sum + friendCount(row.cells[a.key]), 0)
const subtotal = channel => form.rows.reduce((sum, row) => sum + rowTotal(row, channel), 0)
const columnTotal = key => form.rows.reduce((sum, row) => sum + friendCount(row.cells[key]), 0)
const knownLanguage = row => props.options.languages.find(l => l.id === row.language_value)
const languageChanged = row => { row.overview_key = knownLanguage(row)?.overview_key || props.options.overview_rows.find(r => r.label === row.language_value)?.key || ''; row.language_type = knownLanguage(row)?.language_type || 'language' }
const formatTime = value => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-'
function addLine() { form.rows.push({ uiId: ++nextId, language_value: '', language_type: 'language', overview_key: '', cells: {}, channels: {} }) }
async function moveCell(event, row, key) {
  if (event.ctrlKey || event.metaKey || !['Enter', 'ArrowUp', 'ArrowDown'].includes(event.key)) return
  const next = row + (event.key === 'ArrowUp' ? -1 : 1)
  if (next < 0 || next >= form.rows.length) return
  event.preventDefault()
  await nextTick()
  const target = bodyRef.value?.querySelector(`input[data-grid-row="${next}"][data-grid-account="${key}"]`)
  target?.focus(); target?.select()
}
function pasteCells(event, index, key) {
  if (!props.options.can_write || saving.value || loading.value) return
  event.preventDefault()
  try {
    const values = parseFriendPaste(event.clipboardData.getData('text/plain'))
    const col = gridAccounts.value.findIndex(a => a.key === key)
    if (values.some(row => row.length + col > gridAccounts.value.length) || values.length + index > 300) throw new Error('粘贴范围超出账号列或行数上限，请只复制人数区域。')
    while (form.rows.length < index + values.length) addLine()
    values.forEach((row, y) => row.forEach((count, x) => { form.rows[index + y].cells[gridAccounts.value[col + x].key] = count }))
  } catch (e) { ElMessage.error(e.message) }
}
async function allowDiscard() { if (!visible.value || signature() === baseline) return true; try { await ElMessageBox.confirm('有尚未保存的统计，是否放弃本次修改？', '未保存的修改', { confirmButtonText: '放弃修改', cancelButtonText: '继续填写', type: 'warning' }); return true } catch { return false } }
async function beforeClose(done) { if (saving.value || accountSaving.value) return; if (await allowDiscard()) { controller?.abort(); seq++; accountVisible.value = false; done() } }
function applyData(value, data) {
  day.value = value; revision.value = data.revision
  form.rows = friendRowsToGrid(data.rows).map(row => ({ ...row, uiId: ++nextId }))
  if (!form.rows.length && props.options.can_write) addLine()
  audit.value = data.audit || []; updated.value = data.updated_at ? { name: data.updated_by_name, at: data.updated_at } : null
  baseline = signature(); clearFieldSearch()
}
async function loadDate(value) {
  controller?.abort(); controller = new AbortController(); const current = ++seq; loading.value = true
  try { const data = await api.read(value, controller.signal); if (current !== seq) return; applyData(value, data); visible.value = true }
  catch (e) { if (!['ERR_CANCELED','CanceledError','AbortError'].includes(e.code || e.name)) ElMessage.error(e.message) }
  finally { if (seq === current) loading.value = false }
}
async function switchDay(value) { if (!value || value === day.value || saving.value || !await allowDiscard()) return; await loadDate(value) }
async function open(value) { if (saving.value || !await allowDiscard()) return; await loadDate(value) }
async function save() {
  if (saving.value || loading.value || !props.options.can_write || !await formRef.value.validate().catch(() => false)) return
  saving.value = true
  try { const data = await api.save(day.value, { revision: revision.value, rows: payloadRows() }); applyData(day.value, data); emit('saved'); emit('options-changed'); accountVisible.value = false; visible.value = false; ElMessage.success('统计已保存，人才概览已按差额更新') }
  catch (e) {
    ElMessage.error(e.message)
    const index = Number(e.message?.match(/第(\d+)行/)?.[1]) - 1
    const record = payloadRows()[index]
    const rowIndex = form.rows.findIndex(r => r.language_value === record?.language_value)
    if (rowIndex >= 0) await locateDialogFieldByLabel('语种 / 方言', rowIndex + 1)
  } finally { saving.value = false }
}
async function createAccount() {
  if (accountSaving.value || !await accountFormRef.value.validate().catch(() => false)) return
  accountSaving.value = true
  try { await api.addAccount(newAccount); newAccount.name = ''; accountVisible.value = false; emit('options-changed'); ElMessage.success('账号已就绪') } catch (e) { ElMessage.error(e.message) } finally { accountSaving.value = false }
}
onBeforeUnmount(() => { seq++; controller?.abort() })
defineExpose({ open })
</script>
<style>
.friend-daily-dialog{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}.friend-daily-dialog>.el-dialog__header,.friend-daily-dialog>.el-dialog__footer{flex-shrink:0}.friend-daily-dialog>.el-dialog__body{flex:1;min-height:0;overflow-y:auto}.friend-daily-dialog>.el-dialog__footer{border-top:1px solid #dbe5d5;background:#f6f9f3;display:flex;align-items:center;gap:10px;flex-wrap:wrap}.friend-footer-total{margin-right:auto;color:#475569;font-size:13px}.friend-daily-intro{display:flex;align-items:center;gap:16px;flex-wrap:wrap}.friend-daily-hint{font-size:12px;color:#64748b;line-height:1.7}.friend-audit{padding:6px 0;font-size:12px}.friend-account-popover{max-width:calc(100vw - 32px)}
.friend-grid-scroll{overflow-x:auto;border:1px solid #b9c8b1;margin:16px 0 12px}.friend-grid{border-collapse:separate;border-spacing:0;width:100%;font-size:13px;table-layout:fixed;min-width:0}.friend-grid th,.friend-grid td{border-right:1px solid #c5cfbf;border-bottom:1px solid #c5cfbf;min-width:64px;height:35px;text-align:center;padding:0 3px}.friend-grid th{background:#e2efd9;font-weight:600;color:#33412c}.friend-grid td{background:#fff;vertical-align:top}.friend-grid tr:last-child td{border-bottom:0}.friend-grid .friend-language-col{width:176px;position:sticky;left:0;z-index:2;background:#fff}.friend-grid thead .friend-language-col,.friend-grid tfoot .friend-language-col{background:#e2efd9}.friend-grid .friend-row-action{width:48px}.friend-grid .friend-grid-total,.friend-grid tfoot td{background:#f0f5eb;font-weight:600;vertical-align:middle}.friend-grid .el-form-item{margin:0}.friend-grid .el-form-item__label{position:absolute;width:1px;height:1px;padding:0;overflow:hidden;clip-path:inset(50%);white-space:nowrap}.friend-grid .el-input__wrapper,.friend-grid .el-select__wrapper{box-shadow:none!important;border-radius:0;background:#fff;padding:2px 5px;min-height:35px}.friend-grid .el-input__wrapper.is-focus,.friend-grid .el-select__wrapper.is-focused{outline:2px solid #71965a;outline-offset:-2px}.friend-grid .el-input__inner{text-align:right}.friend-grid .el-form-item__error{position:static;line-height:1.3;padding:3px;white-space:normal}.friend-grid .is-error .el-input__wrapper{outline:1px solid var(--el-color-danger);outline-offset:-1px}.friend-grid .friend-grid-empty{height:70px;color:#64748b}.friend-grid-toolbar{display:flex;align-items:center;gap:12px;margin-bottom:14px;flex-wrap:wrap}.friend-grid-toolbar>span{color:#64748b;font-size:12px}
@media(max-width:650px){.friend-footer-total{width:100%}.friend-grid .friend-language-col{width:150px}}
</style>

